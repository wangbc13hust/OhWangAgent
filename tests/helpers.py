from __future__ import annotations

import os

from ohwang.agent import Agent
from ohwang.config import Config
from ohwang.modes import Mode
from ohwang.permissions import PermissionManager
from ohwang.prompts import build_system_prompt
from ohwang.providers.base import BaseProvider
from ohwang.services.compact import Compactor
from ohwang.tools import default_tools
from ohwang.tools.todo import TodoStore


class ScriptedProvider(BaseProvider):
    """Replays a scripted list of event-lists, one per chat() call."""

    name = "scripted"

    def __init__(self, responses: list[list[dict]]) -> None:
        super().__init__("fake-key", "scripted-model")
        self.responses = [list(r) for r in responses]
        self.i = 0
        self.calls: list[dict] = []

    def chat(self, system, messages, tools, max_tokens):
        self.calls.append(
            {"system": system, "messages": list(messages), "tools": list(tools)}
        )
        if self.i >= len(self.responses):
            yield {"type": "text", "text": ""}
            return
        for e in self.responses[self.i]:
            yield e
        self.i += 1


class MockSearchProvider:
    """Search provider that returns canned results without network."""

    name = "mock_search"

    def search(self, query: str, max_results: int = 5):
        return [
            {
                "title": f"Result for: {query}",
                "url": f"https://example.com/{query.replace(' ', '-')}",
                "snippet": f"This is a mock result for '{query}'.",
            }
        ][:max_results]


def build_agent(
    responses,
    mode: Mode = Mode.AUTO,
    with_todo: bool = True,
    with_compactor: bool = False,
    compact_threshold: int = 10**9,
):
    config = Config(workdir=os.getcwd()).resolve()
    provider = ScriptedProvider(responses)
    todo_store = TodoStore() if with_todo else None
    perms = PermissionManager(mode=mode)
    tools = default_tools(
        todo_store=todo_store,
        permissions=perms,
        search_provider=MockSearchProvider(),
    )
    compactor = (
        Compactor(threshold_tokens=compact_threshold) if with_compactor else None
    )
    agent = Agent(
        provider,
        tools,
        perms,
        config,
        build_system_prompt(config.workdir),
        todo_store=todo_store,
        compactor=compactor,
    )
    return agent, provider
