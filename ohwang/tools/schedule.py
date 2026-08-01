from __future__ import annotations

import time

from ..services.scheduler import Scheduler
from .base import BaseTool, ToolResult


def _fmt_due(job) -> str:
    due = job.last_run + 30 - time.time()
    return "next <30s" if due > 0 else "due now"


class CronCreateTool(BaseTool):
    name = "cron_create"
    description = (
        "Schedule a recurring task. Expression is 5-field cron: "
        "minute hour day-of-month month day-of-week. "
        "e.g. '*/10 * * * *' runs every 10 minutes. "
        "When a job fires, its prompt is run as a new task."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Unique job id."},
            "expression": {"type": "string", "description": "5-field cron expression."},
            "prompt": {"type": "string", "description": "Prompt to run when the job fires."},
        },
        "required": ["id", "expression", "prompt"],
    }
    default_permission = "ask"

    def __init__(self, scheduler: Scheduler) -> None:
        self._scheduler = scheduler

    def execute(self, input: dict) -> ToolResult:
        job_id = input["id"]
        expression = input["expression"]
        prompt = input["prompt"]
        if not self._scheduler.add(job_id, expression, prompt):
            return ToolResult(
                content=f"Failed to create cron job '{job_id}' (bad expression or duplicate id).",
                is_error=True,
            )
        return ToolResult(
            content=f"Scheduled '{job_id}': {expression} -> {prompt[:80]}"
        )


class CronDeleteTool(BaseTool):
    name = "cron_delete"
    description = "Delete a scheduled cron job."
    input_schema = {
        "type": "object",
        "properties": {"id": {"type": "string", "description": "Job id to remove."}},
        "required": ["id"],
    }
    default_permission = "ask"

    def __init__(self, scheduler: Scheduler) -> None:
        self._scheduler = scheduler

    def execute(self, input: dict) -> ToolResult:
        job_id = input["id"]
        if not self._scheduler.remove(job_id):
            return ToolResult(
                content=f"No cron job with id '{job_id}'.", is_error=True
            )
        return ToolResult(content=f"Deleted cron job '{job_id}'.")


class CronListTool(BaseTool):
    name = "cron_list"
    description = "List all scheduled cron jobs."
    input_schema = {"type": "object", "properties": {}}
    default_permission = "allow"

    def __init__(self, scheduler: Scheduler) -> None:
        self._scheduler = scheduler

    def execute(self, input: dict) -> ToolResult:
        jobs = self._scheduler.list()
        if not jobs:
            return ToolResult(content="No cron jobs scheduled.")
        lines = ["Cron jobs:"]
        for job in jobs:
            lines.append(
                f"  {job.id}  {job.expression}  {_fmt_due(job)}  {job.prompt[:80]}"
            )
        return ToolResult(content="\n".join(lines))
