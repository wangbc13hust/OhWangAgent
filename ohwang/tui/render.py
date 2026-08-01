from __future__ import annotations

import json
import os
import sys

from rich.console import Console
from rich.prompt import Prompt


class Renderer:
    def __init__(self) -> None:
        force_utf8 = sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8"
        self.console = Console(force_terminal=True) if force_utf8 else Console()
        self._buffer: list[str] = []

    def _flush(self) -> None:
        if self._buffer:
            self.console.print("".join(self._buffer), end="", highlight=False)
            self._buffer.clear()

    def stream_text(self, text: str) -> None:
        self._buffer.append(text)

    def tool_call(self, tool_use: dict) -> None:
        self._flush()
        args = json.dumps(tool_use.get("input", {}), ensure_ascii=False)
        self.console.print(
            f"\n[bold yellow]>> {tool_use['name']}[/bold yellow] [dim]{args}[/dim]",
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
        self.console.print(f"[dim]{message}[/dim]", highlight=False)

    def warn(self, message: str) -> None:
        self.console.print(f"[bold yellow]{message}[/bold yellow]", highlight=False)

    def ask(self, tool_name: str, input: dict) -> str:
        self._flush()
        args = json.dumps(input, ensure_ascii=False)
        self.console.print(
            f"\n[bold cyan]? {tool_name}[/bold cyan] [dim]{args}[/dim]",
            highlight=False,
        )
        answer = Prompt.ask(
            "[y]es / [n]o / a[lways]",
            choices=["y", "n", "a"],
            default="n",
            console=self.console,
        )
        return {"y": "allow", "a": "always"}.get(answer, "deny")

    def ask_question(self, question: str, options: list) -> str:
        self._flush()
        self.console.print(f"\n[bold cyan]? {question}[/bold cyan]", highlight=False)
        for i, opt in enumerate(options, 1):
            label = opt.get("label", "") if isinstance(opt, dict) else str(opt)
            desc = opt.get("description", "") if isinstance(opt, dict) else ""
            line = f"  [{i}] {label}"
            if desc:
                line += f" -- {desc}"
            self.console.print(line, highlight=False)
        choice = Prompt.ask(
            "Select option",
            console=self.console,
        )
        return choice.strip()
