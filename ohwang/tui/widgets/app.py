from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, RichLog, Static

from ...agent import Agent
from ...config import Config
from ...permissions import PermissionManager
from ...services import SessionStore


class ChatPanel(RichLog):
    DEFAULT_CSS = """
    ChatPanel {
        height: 1fr;
        border: solid green;
        padding: 0 1;
    }
    """


class ToolPanel(Static):
    DEFAULT_CSS = """
    ToolPanel {
        height: auto;
        max-height: 8;
        border: solid yellow;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__("")
        self._calls: list[str] = []

    def add_call(self, name: str, args: str) -> None:
        self._calls.append(f"◆ {name} {args[:80]}")
        if len(self._calls) > 10:
            self._calls = self._calls[-10:]
        self.update("\n".join(self._calls))

    def add_result(self, name: str, is_error: bool) -> None:
        mark = "✗" if is_error else "✓"
        self._calls.append(f"  {mark} {name}")
        if len(self._calls) > 10:
            self._calls = self._calls[-10:]
        self.update("\n".join(self._calls))


class StatusPanel(Static):
    DEFAULT_CSS = """
    StatusPanel {
        height: 1;
        border: solid blue;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__("")
        self.provider = ""
        self.model = ""
        self.mode = ""

    def update_status(self, provider: str, model: str, mode: str) -> None:
        self.provider = provider
        self.model = model
        self.mode = mode
        self.update(f"[{provider}] {model} | mode: {mode}")


class OhWangApp(App):
    """Textual TUI for OhWangAgent."""

    TITLE = "OhWangAgent"
    CSS = """
    Screen {
        layout: vertical;
    }
    #main-area {
        height: 1fr;
    }
    #input-area {
        height: 3;
        border: solid cyan;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+l", "clear", "Clear"),
        Binding("ctrl+a", "toggle_auto", "Auto"),
        Binding("ctrl+p", "toggle_plan", "Plan"),
    ]

    def __init__(
        self,
        agent: Agent,
        config: Config,
        session_store: SessionStore,
    ) -> None:
        super().__init__()
        self.agent = agent
        self.config = config
        self.session_store = session_store
        self._text_buffer = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-area"):
            yield ChatPanel(id="chat")
            yield ToolPanel(id="tools")
            yield StatusPanel(id="status")
        with Horizontal(id="input-area"):
            yield Input(placeholder="ohwang> ", id="prompt")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#status", StatusPanel).update_status(
            self.config.provider,
            self.config.model,
            self.agent.permissions.mode.label,
        )
        self.query_one("#prompt", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value:
            return
        event.input.value = ""

        if value in ("/exit", "/quit"):
            self.exit()
            return
        if value == "/clear":
            self.action_clear()
            return
        if value == "/auto":
            self.action_toggle_auto()
            return
        if value == "/tools":
            self._show_tools()
            return
        if value.startswith("/model "):
            new_model = value[len("/model "):].strip()
            self.config.model = new_model
            self.agent.provider.model = new_model
            self.query_one("#chat", ChatLog).write(f"Model set to {new_model}")
            return

        self._run_prompt(value)

    def _run_prompt(self, prompt: str) -> None:
        chat = self.query_one("#chat", ChatLog)
        tools = self.query_one("#tools", ToolPanel)
        chat.write(f"\n[bold cyan]You:[/bold cyan] {prompt}")

        import json

        def on_text(text: str):
            self._text_buffer += text
            if len(self._text_buffer) > 200:
                chat.write(self._text_buffer)
                self._text_buffer = ""

        def on_tool_call(tu: dict):
            args = json.dumps(tu.get("input", {}), ensure_ascii=False)[:80]
            tools.add_call(tu["name"], args)

        def on_tool_result(name: str, is_error: bool):
            tools.add_result(name, is_error)

        try:
            result = self.agent.run(
                prompt,
                on_text=on_text,
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
            )
            if self._text_buffer:
                chat.write(self._text_buffer)
                self._text_buffer = ""
            if result.strip():
                chat.write(f"\n[bold green]Agent:[/bold green] {result}")
        except Exception as exc:
            chat.write(f"\n[bold red]Error:[/bold red] {exc}")

    def _show_tools(self) -> None:
        chat = self.query_one("#chat", ChatLog)
        for t in self.agent.tools:
            chat.write(f"  {t.name}  [{t.default_permission}]")

    def action_clear(self) -> None:
        self.agent.reset()
        self.query_one("#chat", ChatLog).clear()
        self.query_one("#chat", ChatLog).write("Conversation cleared.")

    def action_toggle_auto(self) -> None:
        self.agent.permissions.auto_approve = not self.agent.permissions.auto_approve
        state = "ON" if self.agent.permissions.auto_approve else "OFF"
        self.query_one("#chat", ChatLog).write(f"Auto-approve {state}.")
        self.query_one("#status", StatusPanel).update_status(
            self.config.provider,
            self.config.model,
            self.agent.permissions.mode.label,
        )

    def action_toggle_plan(self) -> None:
        from ...modes import Mode
        if self.agent.permissions.mode == Mode.PLAN:
            self.agent.permissions.mode = Mode.DEFAULT
            self.query_one("#chat", ChatLog).write("Exited plan mode.")
        else:
            self.agent.permissions.mode = Mode.PLAN
            self.query_one("#chat", ChatLog).write("Entered plan mode (read-only).")
        self.query_one("#status", StatusPanel).update_status(
            self.config.provider,
            self.config.model,
            self.agent.permissions.mode.label,
        )
