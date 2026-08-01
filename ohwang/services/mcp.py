from __future__ import annotations

import json
import os
import subprocess
import threading
from typing import Optional

from ..tools.base import BaseTool, ToolResult


class MCPClient:
    """Minimal stdio JSON-RPC 2.0 client for an MCP server."""

    def __init__(
        self,
        name: str,
        command: str,
        args: Optional[list[str]] = None,
        env: Optional[dict] = None,
    ) -> None:
        self.name = name
        self.command = command
        self.args = list(args or [])
        self.env = env
        self._proc: Optional[subprocess.Popen] = None
        self._id = 0
        self._lock = threading.Lock()
        self._responses: dict[int, dict] = {}
        self._events: dict[int, threading.Event] = {}
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        full_env = dict(os.environ)
        if self.env:
            full_env.update(self.env)
        self._proc = subprocess.Popen(
            [self.command, *self.args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=full_env,
            text=True,
            bufsize=1,
        )
        threading.Thread(target=self._read_loop, daemon=True).start()
        self._started = True
        self._initialize()

    def _read_loop(self) -> None:
        assert self._proc and self._proc.stdout
        for line in self._proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            mid = msg.get("id")
            if mid is not None and mid in self._events:
                self._responses[mid] = msg
                self._events[mid].set()

    def _send(self, method: str, params=None, timeout: float = 30.0):
        with self._lock:
            self._id += 1
            rid = self._id
        req = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            req["params"] = params
        ev = threading.Event()
        self._events[rid] = ev
        assert self._proc and self._proc.stdin
        self._proc.stdin.write(json.dumps(req) + "\n")
        self._proc.stdin.flush()
        if not ev.wait(timeout=timeout):
            self._events.pop(rid, None)
            raise TimeoutError(f"MCP {method} timed out")
        resp = self._responses.pop(rid, None)
        self._events.pop(rid, None)
        if resp is None:
            raise RuntimeError(f"MCP {method}: no response")
        if "error" in resp:
            raise RuntimeError(f"MCP error: {resp['error']}")
        return resp.get("result")

    def _notify(self, method: str, params=None) -> None:
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        assert self._proc and self._proc.stdin
        self._proc.stdin.write(json.dumps(msg) + "\n")
        self._proc.stdin.flush()

    def _initialize(self) -> None:
        self._send(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ohwang", "version": "0.1.0"},
            },
        )
        self._notify("notifications/initialized", {})

    def list_tools(self) -> list[dict]:
        result = self._send("tools/list", {})
        return result.get("tools", []) if result else []

    def call_tool(self, name: str, args: dict):
        return self._send("tools/call", {"name": name, "arguments": args})

    def stop(self) -> None:
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None
        self._started = False


class MCPToolWrapper(BaseTool):
    def __init__(self, client: MCPClient, spec: dict) -> None:
        self._client = client
        self._tool_name = spec["name"]
        self.name = f"mcp__{client.name}__{self._tool_name}"
        self.description = spec.get("description", f"MCP tool {self._tool_name}")
        self.input_schema = spec.get("inputSchema", {"type": "object", "properties": {}})
        self.default_permission = "ask"

    def execute(self, input: dict) -> ToolResult:
        try:
            result = self._client.call_tool(self._tool_name, input)
        except Exception as exc:
            return ToolResult(content=f"MCP call failed: {exc}", is_error=True)
        return ToolResult(
            content=self._extract_text(result),
            is_error=self._is_error(result),
        )

    @staticmethod
    def _extract_text(result) -> str:
        if not isinstance(result, dict):
            return str(result)
        content = result.get("content", [])
        parts = [
            c.get("text", "")
            for c in content
            if isinstance(c, dict) and c.get("type") == "text"
        ]
        return "\n".join(parts) if parts else json.dumps(result, ensure_ascii=False)

    @staticmethod
    def _is_error(result) -> bool:
        return bool(result.get("isError")) if isinstance(result, dict) else False


def load_mcp_tools(workdir: str, registry) -> list[str]:
    """Load MCP servers from .ohwang/mcp.json and register their tools."""
    path = os.path.join(workdir, ".ohwang", "mcp.json")
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception:
        return []
    added: list[str] = []
    for name, cfg in (config.get("mcpServers", {}) or {}).items():
        try:
            client = MCPClient(
                name, cfg.get("command"), cfg.get("args"), cfg.get("env")
            )
            client.start()
            for spec in client.list_tools():
                wrapper = MCPToolWrapper(client, spec)
                registry.register(wrapper)
                added.append(wrapper.name)
        except Exception:
            continue
    return added
