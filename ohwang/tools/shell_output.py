from __future__ import annotations

import codecs
import locale
import subprocess
import threading
from typing import Callable, Optional

from .base import ToolResult


def decode_output(data: bytes) -> str:
    """Decode subprocess bytes to str, tolerant of encoding mismatch.

    Tries UTF-8 first (Windows tools often emit UTF-8 while the console codepage
    is GBK); on failure falls back to the locale encoding with replacement.
    """
    if not data:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode(locale.getpreferredencoding(False), errors="replace")
        except LookupError:
            return data.decode("utf-8", errors="replace")


def stream_command(
    cmd,
    *,
    shell: bool,
    timeout: int,
    cwd: str,
    on_chunk: Optional[Callable[[str, str], None]] = None,
) -> tuple[str, str, int, bool]:
    """Run a command while streaming output live; return the SAME final buffers.

    Pipes stdout/stderr and drains each in its own reader thread so a long
    command (build, test, `| tail`) no longer leaves the terminal frozen.
    Raw bytes are accumulated per stream and decoded with `decode_output()` at
    the end, so the returned (stdout, stderr) are byte-identical to a plain
    `subprocess.run(capture_output=True)` — callers keep the exact existing
    ToolResult formatting. When `on_chunk` is given, each incrementally-decoded
    text block is forwarded as `on_chunk(stream_name, text)` for live display
    (UTF-8 incremental decode with replacement; display-only approximation).

    Returns (stdout, stderr, returncode, timed_out).
    """
    proc = subprocess.Popen(
        cmd,
        shell=shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
    )
    out_raw: list[bytearray] = [bytearray()]
    err_raw: list[bytearray] = [bytearray()]
    out_lock = threading.Lock()
    err_lock = threading.Lock()

    def _reader(stream, sink, sink_lock, name) -> None:
        dec = codecs.getincrementaldecoder("utf-8")(errors="replace")
        while True:
            chunk = stream.read(4096)
            if not chunk:
                break
            with sink_lock:
                sink[0].extend(chunk)
            if on_chunk is not None:
                on_chunk(name, dec.decode(chunk))
        if on_chunk is not None:
            tail = dec.decode(b"", final=True)
            if tail:
                on_chunk(name, tail)

    t_out = threading.Thread(
        target=_reader, args=(proc.stdout, out_raw, out_lock, "stdout"), daemon=True
    )
    t_err = threading.Thread(
        target=_reader, args=(proc.stderr, err_raw, err_lock, "stderr"), daemon=True
    )
    t_out.start()
    t_err.start()

    timed_out = False
    try:
        returncode = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        returncode = proc.wait()
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass
        try:
            proc.stderr.close()
        except Exception:
            pass
        t_out.join(timeout=2)
        t_err.join(timeout=2)
    if on_chunk is not None:
        # End-of-stream signals: let the consumer flush any buffered partial
        # line (e.g. a command that exits without a trailing newline).
        on_chunk("stdout", "")
        on_chunk("stderr", "")

    with out_lock:
        stdout = decode_output(bytes(out_raw[0]))
    with err_lock:
        stderr = decode_output(bytes(err_raw[0]))
    return stdout, stderr, returncode, timed_out


def truncate(text: str, limit: int = 20000) -> str:
    if len(text) <= limit:
        return text
    keep = limit // 2
    return (
        text[:keep]
        + f"\n... [truncated {len(text) - limit} chars] ...\n"
        + text[-keep:]
    )


def command_result(
    stdout: str,
    stderr: str,
    returncode: int,
    timed_out: bool = False,
    timeout: int = 120,
) -> ToolResult:
    """Build a ToolResult from subprocess output (shared by bash/powershell)."""
    if timed_out:
        return ToolResult(content=f"Command timed out after {timeout}s.", is_error=True)

    out = stdout or ""
    err = stderr or ""
    combined = out
    if err:
        combined += ("\n--- stderr ---\n" + err) if out else err

    combined = truncate(combined)
    header = f"[exit code {returncode}]\n"
    return ToolResult(content=header + combined, is_error=returncode != 0)
