from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from .base import BaseTool, ToolResult


class AgentTool(BaseTool):
    name = "agent"
    description = (
        "Spawn one or more sub-agents with isolated contexts to work on "
        "subtasks. Pass a single 'prompt' for one sub-agent, or 'tasks' (a "
        "list of {description, prompt}) to fan out several in PARALLEL. "
        "Returns each sub-agent's final answer, ordered by input."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "Short (3-5 word) label for the single-prompt mode.",
            },
            "prompt": {
                "type": "string",
                "description": "The task for a single sub-agent.",
            },
            "tasks": {
                "type": "array",
                "description": (
                    "Optional: list of parallel sub-tasks to run concurrently. "
                    "When present, each item is a {description, prompt}."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Short (3-5 word) label.",
                        },
                        "prompt": {
                            "type": "string",
                            "description": "The task for this sub-agent.",
                        },
                    },
                    "required": ["description", "prompt"],
                },
            },
        },
    }
    default_permission = "allow"

    # Cap concurrent sub-agents so one tool call cannot hammer the API.
    MAX_PARALLEL_WORKERS = 4

    def __init__(self, factory: Callable[[], "object"], hooks=None) -> None:
        self._factory = factory
        self._hooks = hooks

    def execute(self, input: dict) -> ToolResult:
        tasks = input.get("tasks")
        if isinstance(tasks, list) and tasks:
            return self._run_parallel(tasks)
        return self._run_single(input)

    def _run_single(self, input: dict) -> ToolResult:
        prompt = input["prompt"]
        description = input.get("description", "subtask")
        if self._hooks is not None:
            self._hooks.emit("subagent_start", description=description, prompt=prompt)
        sub = self._factory()
        try:
            result = sub.run(prompt)
        except Exception as exc:
            if self._hooks is not None:
                self._hooks.emit("subagent_stop", description=description, error=str(exc))
            return ToolResult(content=f"Sub-agent failed: {exc}", is_error=True)
        if self._hooks is not None:
            self._hooks.emit("subagent_stop", description=description)
        return ToolResult(content=result or "(sub-agent produced no output)")

    def _run_parallel(self, tasks: list[dict]) -> ToolResult:
        def run_one(item: dict) -> str:
            description = item.get("description", "subtask")
            prompt = item["prompt"]
            if self._hooks is not None:
                self._hooks.emit("subagent_start", description=description, prompt=prompt)
            sub = self._factory()
            try:
                result = sub.run(prompt)
            except Exception as exc:
                if self._hooks is not None:
                    self._hooks.emit("subagent_stop", description=description, error=str(exc))
                return f"Sub-agent failed: {exc}"
            if self._hooks is not None:
                self._hooks.emit("subagent_stop", description=description)
            return result or "(sub-agent produced no output)"

        # pool.map preserves input order while running the tasks concurrently;
        # run_one already swallows exceptions so no item aborts the rest.
        with ThreadPoolExecutor(
            max_workers=min(len(tasks), self.MAX_PARALLEL_WORKERS)
        ) as pool:
            results = list(pool.map(run_one, tasks))
        parts = [
            f"[{i}] {item.get('description', 'subtask')}: {result}"
            for i, (item, result) in enumerate(zip(tasks, results))
        ]
        return ToolResult(content="\n".join(parts))
