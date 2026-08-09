"""Localhost HTTP daemon that exposes the agent kernel to a web front.

The CLI binds the agent's five progress callbacks (on_text / on_tool_call /
on_tool_result / on_compact / on_turn) to a terminal renderer. This module binds
the same seam to HTTP: a JSON ``POST /run`` for the final answer and an SSE
``POST /stream`` for the wire events, so a web front can render the same
feedback the terminal shows.

The agent loop is synchronous, so each request thread simply calls
``agent.run()`` inline while holding the shared ``run_lock`` and writes events
into the open response — everything stays on the stdlib (``http.server`` +
``threading``), zero new dependencies. New/resumed conversations are persisted
through ``SessionStore``.
"""

from __future__ import annotations

import json
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from urllib.parse import urlparse

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8237  # avoids common dev ports (3000/5000/8000/8080)
DRAIN_TIMEOUT = 10.0  # seconds to wait for in-flight runs on shutdown


def _first_user_text(messages: list[dict]) -> str:
    """Return the first user text block (used as a session preview)."""
    for m in messages:
        if m.get("role") != "user":
            continue
        content = m.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            for block in content:
                if block.get("type") == "text":
                    return block.get("text", "")
    return ""


class AgentHTTPServer(ThreadingHTTPServer):
    """Threading HTTP server that also carries the assembled agent kernel.

    The kernel is attached here (rather than via globals or a handler factory)
    so a request handler can reach ``self.server.agent`` etc. ``daemon_threads``
    means the process can exit even if a client abandons a connection mid-stream.
    """

    daemon_threads = True

    def __init__(
        self,
        addr,
        handler,
        agent,
        run_lock: Lock,
        session_store,
        memory_extractor=None,
    ) -> None:
        super().__init__(addr, handler)
        self.agent = agent
        self.run_lock = run_lock
        self.session_store = session_store
        self.memory_extractor = memory_extractor
        # In-flight request count, so shutdown can wait for runs to drain.
        self.active = 0
        self.active_lock = Lock()


class _Handler(BaseHTTPRequestHandler):
    """Routes /health, /run, /stream for the agent daemon."""

    # HTTP/1.0 keeps the response framing trivial: /run and /health carry an
    # explicit Content-Length, and an SSE /stream response ends at connection
    # close (right after the `done` event), which urllib and browsers both read
    # correctly without needing chunked encoding.
    protocol_version = "HTTP/1.0"

    # ---- request routing -------------------------------------------------

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/health":
            self._send_json(
                200, {"status": "ready", "model": self.server.agent.provider.model}
            )
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/run":
            self._with_active(self._run_request)
        elif path == "/stream":
            self._with_active(self._stream_request)
        else:
            self._send_json(404, {"error": "not found"})

    # ---- shared helpers --------------------------------------------------

    def _with_active(self, fn) -> None:
        """Track this request in server.active so shutdown can drain runs."""
        with self.server.active_lock:
            self.server.active += 1
        try:
            fn()
        finally:
            with self.server.active_lock:
                self.server.active -= 1

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if length <= 0:
            return None
        try:
            raw = self.rfile.read(length)
        except OSError:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    def _message_and_session(self) -> tuple[str, str | None] | None:
        """Parse the shared request body shape, or None after a 400 is sent."""
        body = self._read_json_body()
        if body is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return None
        message = body.get("message")
        if not isinstance(message, str) or not message.strip():
            self._send_json(400, {"error": "message (string) required"})
            return None
        session_id = body.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            session_id = None
        return message, session_id

    # ---- /run ------------------------------------------------------------

    def _run_request(self) -> None:
        parsed = self._message_and_session()
        if parsed is None:
            return
        message, session_id = parsed
        try:
            sid, final_text = self._run_locked(message, session_id, lambda *_: None)
        except ValueError as exc:  # unknown session
            self._send_json(404, {"error": str(exc)})
            return
        except Exception as exc:  # agent run failure — never crash the daemon
            self._send_json(500, {"error": f"{type(exc).__name__}: {exc}"})
            return
        self._send_json(200, {"session_id": sid, "final_text": final_text})

    # ---- /stream ---------------------------------------------------------

    def _stream_request(self) -> None:
        parsed = self._message_and_session()
        if parsed is None:
            return
        message, session_id = parsed

        # The SSE response stays open until the run finishes and `done` is
        # written; the connection closing after that frames the end of stream.
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.flush()

        def emit(event: str, data: dict) -> None:
            payload = json.dumps(data, ensure_ascii=False)
            chunk = f"event: {event}\ndata: {payload}\n\n".encode("utf-8")
            try:
                self.wfile.write(chunk)
                self.wfile.flush()
            except (BrokenPipeError, OSError):
                pass  # client went away mid-run; the run itself keeps going

        try:
            sid, final_text = self._run_locked(message, session_id, emit)
        except ValueError as exc:
            emit("error", {"error": str(exc)})
            return
        except Exception as exc:
            emit("error", {"error": f"{type(exc).__name__}: {exc}"})
            return
        emit("done", {"session_id": sid, "final_text": final_text})

    # ---- run execution ---------------------------------------------------

    def _run_locked(
        self, message: str, session_id: str | None, emit
    ) -> tuple[str, str]:
        """Run one agent turn under the lock, mirroring cli._run_once.

        Returns (session_id, final_text). Everything that mutates
        ``agent.messages`` happens under ``run_lock`` — a second request must
        never reset or reload history mid-run. Post-run steps (memory
        extraction, session save) use a snapshot taken inside the lock so a
        subsequent run cannot corrupt what is being persisted.
        """
        server = self.server
        agent = server.agent
        store = server.session_store

        with server.run_lock:
            if session_id:
                history = store.load(session_id)
                if history is None:
                    raise ValueError(f"unknown session {session_id}")
                agent.messages = history
            else:
                # Fresh conversation: clear the exchange but keep the global
                # todo list (office state, not per-session state).
                agent.messages.clear()
            agent.iterations = 0
            agent.session_summary = ""
            agent._invalidate_system()

            final_text = agent.run(
                message,
                on_text=lambda text: emit("text", {"text": text}),
                on_tool_call=lambda tu: emit("tool_call", tu),
                on_tool_result=lambda name, is_error: emit(
                    "tool_result", {"tool": name, "is_error": bool(is_error)}
                ),
                on_compact=lambda b, a: emit("compact", {"before": b, "after": a}),
                on_turn=lambda it, n: emit("turn", {"iteration": it, "n_messages": n}),
            )
            snapshot = list(agent.messages)

        if server.memory_extractor is not None and snapshot:
            try:
                server.memory_extractor.maybe_extract(agent.provider, snapshot)
            except Exception:
                pass  # memory extraction must never fail the request

        preview = message[:80]
        if session_id:
            first = _first_user_text(snapshot)
            if first:
                preview = first[:80]
            # Resumed conversation keeps its id (overwrite in place).
            sid = (
                session_id
                if store.update(session_id, snapshot, preview=preview)
                else store.save(snapshot, preview=preview)
            )
        else:
            sid = store.save(snapshot, preview=preview)
        return sid, final_text


def _wire_signals(event: threading.Event) -> None:
    """Turn SIGINT/SIGTERM into a graceful-shutdown request (main thread only)."""
    def _handle(*_args):
        event.set()

    try:
        signal.signal(signal.SIGINT, _handle)
        signal.signal(signal.SIGTERM, _handle)
    except (ValueError, OSError):
        # Not the main thread (tests drive shutdown via their own event).
        pass


def _drain_active(server: AgentHTTPServer) -> None:
    """Wait briefly for in-flight runs to finish after the listener is closed."""
    deadline = time.time() + DRAIN_TIMEOUT
    while time.time() < deadline:
        with server.active_lock:
            active = server.active
        if active == 0:
            return
        time.sleep(0.05)


def run_server(
    agent,
    run_lock: Lock,
    session_store,
    memory_extractor=None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    shutdown_event: threading.Event | None = None,
    on_ready=None,
) -> AgentHTTPServer:
    """Run the daemon in the calling thread until shutdown is requested.

    Blocks the calling thread (normally the CLI main thread). ``shutdown_event``
    defaults to a fresh event wired to SIGINT/SIGTERM; tests pass their own event
    and run this in a background thread. ``on_ready(actual_port)`` fires once the
    listener is bound — needed when ``port=0`` to learn the assigned port.
    Returns the server after a clean shutdown (listener closed, in-flight runs
    drained), so the bound address remains inspectable.
    """
    server = AgentHTTPServer(
        (host, port), _Handler, agent, run_lock, session_store, memory_extractor
    )
    event = shutdown_event if shutdown_event is not None else threading.Event()
    if shutdown_event is None:
        _wire_signals(event)

    thread = threading.Thread(
        target=server.serve_forever, name="ohwang-serve", daemon=True
    )
    thread.start()
    if on_ready is not None:
        on_ready(server.server_address[1])

    event.wait()
    server.shutdown()  # stop accepting new connections
    server.server_close()  # release the listening port
    _drain_active(server)  # let any in-flight run finish before returning
    return server
