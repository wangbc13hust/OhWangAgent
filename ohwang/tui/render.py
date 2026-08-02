from __future__ import annotations

import json
import os
import sys
import threading
import time

from rich.console import Console
from rich.markup import escape
from rich.prompt import Prompt


def setup_utf8() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            if stream is not None and stream is not sys.stdin:
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def read_stdin_line(prompt: str = "") -> str:
    """Read one line of stdin, tolerant of pipe vs TTY and encoding mismatch.

    Interactive terminals use regular input(). When stdin is a pipe (scripted /
    CI usage), the bytes arrive in whatever encoding the upstream process chose
    (often the system codepage, e.g. GBK on Chinese Windows), so we decode
    bytes manually with a UTF-8-then-locale fallback instead of relying on the
    stream's configured encoding.
    """
    if prompt:
        sys.stdout.write(prompt)
        sys.stdout.flush()
    buf = getattr(sys.stdin, "buffer", None)
    if buf is None:
        line = sys.stdin.readline()
        if line == "":
            raise EOFError
        return line.rstrip("\n")
    try:
        import locale

        raw = buf.readline()
    except Exception:
        raw = b""
    if raw == b"":
        raise EOFError
    text = raw.decode("utf-8", errors="replace")
    if "\ufffd" in text:
        try:
            text = raw.decode(locale.getpreferredencoding(False))
        except (UnicodeDecodeError, LookupError):
            pass
    if text.startswith("\ufeff"):
        text = text[len("\ufeff"):]
    return text.rstrip("\r\n")


class Renderer:
    # Per-line truncation for live tool output so a chatty command cannot flood
    # the terminal with a single giant line.
    _OUT_LINE_LIMIT = 200

    def __init__(self) -> None:
        setup_utf8()
        self.console = Console()
        self._buffer: list[str] = []
        self._flush_at = 128
        self._flush_every = 0.05
        self._last_flush = time.time()
        # Guards tool_output/progress: called from parallel sub-agent worker
        # threads while the REPL thread may also be writing.
        self._out_lock = threading.Lock()
        self._out_partial: dict[str, str] = {}

    def _flush(self) -> None:
        if self._buffer:
            sys.stdout.write("".join(self._buffer))
            sys.stdout.flush()
            self._buffer.clear()
            self._last_flush = time.time()

    def _last_char(self) -> str:
        if self._buffer:
            return self._buffer[-1][-1:]
        return ""

    def stream_text(self, text: str) -> None:
        now = time.time()
        self._buffer.append(text)
        buffered = sum(len(p) for p in self._buffer)
        timed = now - self._last_flush >= self._flush_every
        sentence_end = text.endswith(("\n", " ", "。", "！", "？", ".", "!", "?"))
        if buffered >= self._flush_at or timed or sentence_end:
            self._flush()

    def tool_call(self, tool_use: dict) -> None:
        if self._buffer or self._last_char() not in ("", "\n"):
            self._flush()
        if self._last_char() != "\n":
            sys.stdout.write("\n")
            sys.stdout.flush()
        args = escape(json.dumps(tool_use.get("input", {}), ensure_ascii=False))
        self.console.print(
            f"[bold yellow]>> {escape(tool_use['name'])}[/bold yellow] [dim]{args}[/dim]",
            highlight=False,
        )

    def tool_result(self, name: str, is_error: bool) -> None:
        self._flush()
        mark = "FAIL" if is_error else "OK"
        color = "red" if is_error else "green"
        self.console.print(f"  [{color}]{mark} {name}[/{color}]", highlight=False)

    def tool_output(self, stream: str, text: str) -> None:
        """Live-stream a chunk of tool stdout/stderr, one '│ ' line at a time.

        Called from sub-agent worker threads as well as the REPL thread, so
        every write happens under _out_lock. Partial lines are buffered per
        stream until a newline (or an explicit drain at end of stream) flushes
        them, keeping the terminal readable during long commands.
        """
        with self._out_lock:
            if not text:
                # End-of-stream signal: flush any buffered partial line.
                pending = self._out_partial.pop(stream, None)
                if pending:
                    clipped = pending[: self._OUT_LINE_LIMIT]
                    self.console.print(f"  │ {escape(clipped)}", highlight=False)
                self._flush()
                return
            pending = self._out_partial.get(stream, "") + text
            lines = pending.split("\n")
            self._out_partial[stream] = lines.pop()
            for line in lines:
                if not line:
                    continue
                clipped = line[: self._OUT_LINE_LIMIT]
                self.console.print(f"  │ {escape(clipped)}", highlight=False)
            if not self._out_partial[stream]:
                self._out_partial.pop(stream, None)
        self._flush()

    def progress(self, message: str) -> None:
        """A dim one-line stage indicator (e.g. '— turn 3 · context 12 msgs —')."""
        with self._out_lock:
            self.console.print(f"[dim]{escape(message)}[/dim]", highlight=False)

    def end_turn(self) -> None:
        self._flush()
        sys.stdout.write("\n")
        sys.stdout.flush()

    def info(self, message: str) -> None:
        self.console.print(f"[dim]{escape(message)}[/dim]", highlight=False)

    def warn(self, message: str) -> None:
        self.console.print(f"[bold yellow]{escape(message)}[/bold yellow]", highlight=False)

    def ask(self, tool_name: str, input: dict) -> str:
        self._flush()
        args = escape(json.dumps(input, ensure_ascii=False))
        self.console.print(
            f"\n[bold cyan]? {escape(tool_name)}[/bold cyan] [dim]{args}[/dim]",
            highlight=False,
        )
        try:
            answer = Prompt.ask(
                "[y]es / [n]o / a[lways]",
                choices=["y", "n", "a"],
                default="n",
                console=self.console,
            )
        except EOFError:
            self.console.print(
                "[dim]Non-interactive input: defaulting to deny.[/dim]"
            )
            return "deny"
        return {"y": "allow", "a": "always"}.get(answer, "deny")

    def ask_question(self, question: str, options: list) -> str:
        self._flush()
        self.console.print(
            f"\n[bold cyan]? {escape(question)}[/bold cyan]", highlight=False
        )
        for i, opt in enumerate(options, 1):
            label = opt.get("label", "") if isinstance(opt, dict) else str(opt)
            desc = opt.get("description", "") if isinstance(opt, dict) else ""
            line = f"  [{i}] {escape(label)}"
            if desc:
                line += f" -- {escape(desc)}"
            self.console.print(line, highlight=False)
        try:
            choice = Prompt.ask(
                "Select option",
                console=self.console,
            )
        except EOFError:
            self.console.print(
                "[dim]Non-interactive input: defaulting to option 1.[/dim]"
            )
            return "1"
        return choice.strip()
