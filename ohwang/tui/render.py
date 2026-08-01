from __future__ import annotations

import json
import os
import sys

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
            if stream is not None:
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


class Renderer:
    def __init__(self) -> None:
        setup_utf8()
        self.console = Console()
        self._buffer: list[str] = []

    def _flush(self) -> None:
        if self._buffer:
            self.console.print("".join(self._buffer), end="", highlight=False)
            self._buffer.clear()

    def stream_text(self, text: str) -> None:
        self._buffer.append(text)

    def tool_call(self, tool_use: dict) -> None:
        self._flush()
        args = escape(json.dumps(tool_use.get("input", {}), ensure_ascii=False))
        self.console.print(
            f"\n[bold yellow]>> {escape(tool_use['name'])}[/bold yellow] [dim]{args}[/dim]",
            highlight=False,
        )

    def tool_result(self, name: str, is_error: bool) -> None:
        self._flush()
        mark = "FAIL" if is_error else "OK"
        color = "red" if is_error else "green"
        self.console.print(f"  [{color}]{mark} {name}[/{color}]", highlight=False)

    def end_turn(self) -> None:
        self._flush()
        self.console.print()

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
