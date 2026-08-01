from __future__ import annotations

import json
import os
import subprocess
import threading
from typing import Optional


class LSPClient:
    """Minimal LSP client for diagnostics (textDocument/diagnostic).

    Supports any LSP-compliant server (pyright, pylsp, typescript-language-server, etc.)
    launched via stdio.
    """

    def __init__(
        self,
        command: str,
        args: Optional[list[str]] = None,
        workdir: Optional[str] = None,
    ) -> None:
        self.command = command
        self.args = list(args or [])
        self.workdir = workdir or os.getcwd()
        self._proc: Optional[subprocess.Popen] = None
        self._id = 0
        self._lock = threading.Lock()
        self._initialized = False

    def start(self) -> None:
        if self._proc is not None:
            return
        self._proc = subprocess.Popen(
            [self.command, *self.args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=self.workdir,
            text=True,
            bufsize=1,
        )
        self._initialize()

    def stop(self) -> None:
        if self._proc:
            try:
                self._send("shutdown", None)
                self._notify("exit", None)
            except Exception:
                pass
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None
        self._initialized = False

    def diagnose(self, file_path: str) -> list[dict]:
        """Get diagnostics for a file. Returns list of {severity, message, line}."""
        if not self._initialized:
            return []
        uri = _path_to_uri(file_path)
        content = _read_file(file_path)
        if content is None:
            return []

        self._notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": _guess_language(file_path),
                    "version": 1,
                    "text": content,
                }
            },
        )

        result = self._send(
            "textDocument/diagnostic",
            {"textDocument": {"uri": uri}},
            timeout=10,
        )

        if not result:
            return []

        items = result.get("items", []) if isinstance(result, dict) else []
        return [
            {
                "severity": _severity_name(d.get("severity", 1)),
                "message": d.get("message", ""),
                "line": d.get("range", {}).get("start", {}).get("line", 0) + 1,
            }
            for d in items
        ]

    def _initialize(self) -> None:
        result = self._send(
            "initialize",
            {
                "processId": None,
                "rootUri": _path_to_uri(self.workdir),
                "capabilities": {
                    "textDocument": {
                        "diagnostic": {"dynamicRegistration": True},
                    }
                },
            },
            timeout=10,
        )
        self._notify("initialized", {})
        self._initialized = True

    def _send(self, method: str, params, timeout: float = 30) -> Optional[dict]:
        with self._lock:
            self._id += 1
            rid = self._id
        request = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            request["params"] = params
        response = _rpc_call(self._proc, request, timeout=timeout)
        if response and "result" in response:
            return response["result"]
        return None

    def _notify(self, method: str, params) -> None:
        notification = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            notification["params"] = params
        _rpc_notify(self._proc, notification)


def _rpc_call(proc: subprocess.Popen, msg: dict, timeout: float = 30) -> Optional[dict]:
    body = json.dumps(msg)
    header = f"Content-Length: {len(body.encode())}\r\n\r\n"
    try:
        proc.stdin.write(header + body)
        proc.stdin.flush()
    except Exception:
        return None

    try:
        line = proc.stdout.readline()
        if not line:
            return None
        length = int(line.split(":")[1].strip())
        proc.stdout.readline()
        data = proc.stdout.read(length)
        return json.loads(data)
    except Exception:
        return None


def _rpc_notify(proc: subprocess.Popen, msg: dict) -> None:
    body = json.dumps(msg)
    header = f"Content-Length: {len(body.encode())}\r\n\r\n"
    try:
        proc.stdin.write(header + body)
        proc.stdin.flush()
    except Exception:
        pass


def _path_to_uri(path: str) -> str:
    abs_path = os.path.abspath(path).replace("\\", "/")
    if not abs_path.startswith("/"):
        abs_path = "/" + abs_path
    return f"file://{abs_path}"


def _read_file(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def _guess_language(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    mapping = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescriptreact",
        ".js": "javascript",
        ".jsx": "javascriptreact",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
    }
    return mapping.get(ext, "plaintext")


def _severity_name(code: int) -> str:
    return {1: "error", 2: "warning", 3: "info", 4: "hint"}.get(code, "error")


def load_lsp_tools(workdir: str, registry) -> list[str]:
    """Load an LSP server from .ohwang/lsp.json and register lsp_diagnose.

    Supported formats:
      {"command": "pyright-langserver", "args": ["--stdio"]}
      {"servers": {"pyright": {"command": "...", "args": [...]}}}  (first wins)
    """
    path = os.path.join(workdir, ".ohwang", "lsp.json")
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception:
        return []

    cfg = config
    servers = config.get("servers") or {}
    if servers:
        cfg = next(iter(servers.values()))
    command = cfg.get("command") if isinstance(cfg, dict) else None
    if not command:
        return []

    from ..tools.lsp_diagnose import LSPDiagnoseTool

    client = LSPClient(command, cfg.get("args") or [], workdir=workdir)
    try:
        client.start()
    except Exception:
        return []
    if not client._initialized:
        return []
    registry.register(LSPDiagnoseTool(client))
    return ["lsp_diagnose"]
