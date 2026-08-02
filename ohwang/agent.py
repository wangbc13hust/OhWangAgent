from __future__ import annotations

import sys
from typing import Callable, Optional

from .config import Config
from .permissions import PermissionManager
from .providers.base import BaseProvider
from .services.compact import Compactor, is_prompt_too_long_error, microcompact
from .services.git_context import git_context
from .tools.base import ToolResult
from .tools.registry import ToolRegistry
from .tools.todo import TodoStore


class Agent:
    """The agentic loop: LLM -> tool_call -> execute -> feed back -> repeat."""

    def __init__(
        self,
        provider: BaseProvider,
        tools: ToolRegistry,
        permissions: PermissionManager,
        config: Config,
        system: str,
        todo_store: Optional[TodoStore] = None,
        compactor: Optional[Compactor] = None,
        hooks=None,
        policy=None,
        usage=None,
        memory_store=None,
        session_summary: Optional[str] = None,
    ) -> None:
        self.provider = provider
        self.tools = tools
        self.permissions = permissions
        self.config = config
        self.system = system
        self.todo_store = todo_store
        self.memory_store = memory_store
        self.compactor = compactor
        self.hooks = hooks
        self.policy = policy
        self.usage = usage
        self.messages: list[dict] = []
        self.iterations = 0
        self.session_summary = session_summary or ""
        self._system_cache: str | None = None

    def reset(self) -> None:
        self.messages.clear()
        self.iterations = 0
        self.session_summary = ""
        self._system_cache = None
        if self.todo_store is not None:
            self.todo_store.set([])

    def _effective_system(self) -> str:
        if self._system_cache is not None:
            return self._system_cache
        parts = [self.system]
        git_ctx = git_context(self.config.workdir)
        if git_ctx:
            parts.append(git_ctx)
        if self.todo_store is not None:
            parts.append(self.todo_store.render())
        if self.memory_store is not None:
            # Relevance-rank facts against the latest user message so the most
            # useful memories surface; render_context owns its own section
            # headers (no double "# Project Memory" wrapper here).
            memory_ctx = self.memory_store.render_context(
                query=self._latest_user_text()
            )
            if memory_ctx:
                parts.append(memory_ctx)
        if self.session_summary:
            parts.append("\n# Session Context\n" + self.session_summary)
        self._system_cache = "\n".join(p for p in parts if p)
        return self._system_cache

    def _latest_user_text(self) -> str:
        """Return the most recent user text block, or "" if none exists.

        Tool results are also user-role messages but have no text blocks, so
        the scan naturally stops at the latest real user utterance.
        """
        for msg in reversed(self.messages):
            if msg.get("role") != "user":
                continue
            content = msg.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                for block in content:
                    if block.get("type") == "text":
                        return block.get("text", "")
        return ""

    def _invalidate_system(self) -> None:
        self._system_cache = None

    def run(
        self,
        user_input: str,
        on_text: Optional[Callable[[str], None]] = None,
        on_tool_call: Optional[Callable[[dict], None]] = None,
        on_tool_result: Optional[Callable[[str, bool], None]] = None,
        on_compact: Optional[Callable[[int, int], None]] = None,
        max_iterations: int = 50,
    ) -> str:
        self.messages.append(
            {"role": "user", "content": [{"type": "text", "text": user_input}]}
        )
        self._invalidate_system()
        if self.hooks is not None:
            self.hooks.emit("user_prompt_submit", prompt=user_input)

        final_text = ""
        for _ in range(max_iterations):
            self.iterations += 1

            # Trim oversized tool results every turn so a giant file read or
            # command dump cannot silently bloat the context (microCompact).
            microcompact(self.messages)

            if self.compactor is not None and self.compactor.should_compact(
                self.messages, model=self.provider.model
            ):
                before = len(self.messages)
                self.messages = self.compactor.compact(
                    self.messages, self.provider, self._effective_system()
                )
                if on_compact:
                    on_compact(before, len(self.messages))

            text_parts: list[str] = []
            tool_uses: list[dict] = []

            # Reactive compact (mirror of Claude Code's withheld-413 path): if
            # the API rejects the request as too long, summarize old messages
            # and retry the SAME turn once instead of crashing the run.
            reactive_retried = False
            while True:
                try:
                    for event in self.provider.chat(
                        system=self._effective_system(),
                        messages=self.messages,
                        tools=self.tools.specs(),
                        max_tokens=self.config.max_tokens,
                    ):
                        etype = event.get("type")
                        if etype == "text":
                            text_parts.append(event["text"])
                            if on_text:
                                try:
                                    on_text(event["text"])
                                except Exception as exc:
                                    sys.stderr.write(
                                        f"[renderer] on_text error: {type(exc).__name__}: {exc}\n"
                                    )
                        elif etype == "tool_use":
                            tool_uses.append(event)
                    break
                except RuntimeError as exc:
                    if (
                        self.compactor is not None
                        and is_prompt_too_long_error(exc)
                        and not reactive_retried
                    ):
                        reactive_retried = True
                        before = len(self.messages)
                        self.messages = self.compactor.compact(
                            self.messages, self.provider, self._effective_system()
                        )
                        self._invalidate_system()
                        if on_compact:
                            on_compact(before, len(self.messages))
                        if len(self.messages) >= before:
                            # Compaction did not shrink the conversation; a
                            # retry would only repeat the same error.
                            raise
                        continue
                    raise

            full_text = "".join(text_parts)
            if full_text.strip():
                final_text += full_text

            assistant_blocks: list[dict] = []
            if full_text.strip():
                assistant_blocks.append({"type": "text", "text": full_text})
            assistant_blocks.extend(
                {
                    "type": "tool_use",
                    "id": tu.get("id", ""),
                    "name": tu.get("name", ""),
                    "input": tu.get("input", {}),
                }
                for tu in tool_uses
            )
            if assistant_blocks:
                self.messages.append({"role": "assistant", "content": assistant_blocks})

            if not tool_uses:
                break

            result_blocks: list[dict] = []
            for tu in tool_uses:
                if on_tool_call:
                    try:
                        on_tool_call(tu)
                    except Exception as exc:
                        sys.stderr.write(
                            f"[renderer] on_tool_call error: {type(exc).__name__}: {exc}\n"
                        )
                block = self._run_tool(tu)
                if on_tool_result:
                    try:
                        on_tool_result(tu.get("name", "?"), block.get("is_error", False))
                    except Exception as exc:
                        sys.stderr.write(
                            f"[renderer] on_tool_result error: {type(exc).__name__}: {exc}\n"
                        )
                result_blocks.append(block)
            self._invalidate_system()
            self.messages.append({"role": "user", "content": result_blocks})

        if self.hooks is not None:
            self.hooks.emit("stop", final_text=final_text)
        return final_text

    def _run_tool(self, tool_use: dict) -> dict:
        name = tool_use.get("name", "unknown")
        tool_id = tool_use.get("id", "unknown")
        input_ = tool_use.get("input", {}) or {}

        tool = self.tools.get(name)
        if tool is None:
            return {
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": f"Unknown tool: {name}",
                "is_error": True,
            }

        if self.hooks is not None:
            allowed, reason, input_ = self.hooks.run_pre_tool(name, input_)
            if not allowed:
                return {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": f"Blocked by hook: {reason}",
                    "is_error": True,
                }

        if not self.permissions.can_run(tool, input_):
            # A denied call still counts toward the policy budget so a model that
            # keeps retrying a blocked tool cannot loop unbounded.
            if self.policy is not None:
                self.policy.record(name)
            return {
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": "Permission denied (mode/permission rules blocked this tool).",
                "is_error": True,
            }

        if self.policy is not None and not self.policy.check_tool(name):
            return {
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": f"Policy limit reached for tool '{name}'.",
                "is_error": True,
            }

        try:
            result: ToolResult = tool.execute(input_)
            block = {
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": result.content,
                "is_error": result.is_error,
            }
        except Exception as exc:
            block = {
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": f"Tool raised: {type(exc).__name__}: {exc}",
                "is_error": True,
            }

        if self.policy is not None:
            self.policy.record(name)
        if self.usage is not None:
            self.usage.record(name, block["is_error"])
        if self.hooks is not None:
            self.hooks.run_post_tool(name, block)
        return block
