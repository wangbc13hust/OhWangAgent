from __future__ import annotations

from ..services.browser import BrowserSession
from .base import BaseTool, ToolResult


class WebBrowserTool(BaseTool):
    name = "browser_action"
    description = (
        "Drive a headless Chromium browser via Playwright. Actions: navigate "
        "(URL), dom (return current HTML), screenshot (save a PNG), click "
        "(CSS selector), fill (selector + text), scroll (up/down), evaluate "
        "(arbitrary JS returning a string). Great for inspecting and testing "
        "running web applications."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["navigate", "dom", "screenshot", "click", "fill", "scroll", "evaluate"],
            },
            "url": {"type": "string", "description": "For navigate: the URL to open."},
            "selector": {"type": "string", "description": "For click/fill: CSS selector."},
            "text": {"type": "string", "description": "For fill: text to enter."},
            "direction": {
                "type": "string",
                "enum": ["up", "down"],
                "description": "For scroll.",
            },
            "js": {"type": "string", "description": "For evaluate: JavaScript expression."},
        },
        "required": ["action"],
    }
    default_permission = "ask"

    def __init__(self, session: BrowserSession) -> None:
        self._session = session

    def execute(self, input: dict) -> ToolResult:
        action = input["action"]
        try:
            if action == "navigate":
                title = self._session.navigate(input["url"])
                return ToolResult(content=f"Navigated to {input['url']}. Title: {title}")
            if action == "dom":
                return ToolResult(content=self._session.get_dom())
            if action == "screenshot":
                path = self._session.screenshot()
                return ToolResult(content=f"Screenshot saved to {path}")
            if action == "click":
                return ToolResult(content=self._session.click(input["selector"]))
            if action == "fill":
                return ToolResult(
                    content=self._session.fill(input["selector"], input.get("text", ""))
                )
            if action == "scroll":
                return ToolResult(content=self._session.scroll(input.get("direction", "down")))
            if action == "evaluate":
                return ToolResult(content=self._session.evaluate(input.get("js", "")))
            return ToolResult(content=f"Unknown action: {action}", is_error=True)
        except RuntimeError as exc:
            return ToolResult(content=str(exc), is_error=True)
        except Exception as exc:
            return ToolResult(
                content=f"Browser action failed: {type(exc).__name__}: {exc}",
                is_error=True,
            )
