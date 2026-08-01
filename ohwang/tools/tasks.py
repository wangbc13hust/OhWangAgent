from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

from .base import BaseTool, ToolResult

_STATUSES = ("pending", "in_progress", "completed", "cancelled")


class TaskStore:
    """Structured task objects persisted to .ohwang/tasks/*.json.

    Unlike the flat in-memory todo list, tasks carry an id, description,
    status, optional parent/subtask links, and a captured output. Useful for
    multi-step office workflows where the agent tracks several deliverables.
    """

    def __init__(self, workdir: str | Path | None = None) -> None:
        self.dir = Path(workdir or ".") / ".ohwang" / "tasks"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, task_id: str) -> Path:
        safe = re.sub(r"[^\w\-]", "_", task_id)
        return self.dir / f"{safe}.json"

    def create(
        self,
        title: str,
        description: str = "",
        parent: str | None = None,
    ) -> dict:
        task = {
            "id": f"task-{uuid.uuid4().hex[:8]}",
            "title": title,
            "description": description,
            "status": "pending",
            "parent": parent,
            "output": "",
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        self._path(task["id"]).write_text(
            json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return task

    def get(self, task_id: str) -> dict | None:
        path = self._path(task_id)
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return None

    def list(self) -> list[dict]:
        out: list[dict] = []
        for f in sorted(self.dir.glob("*.json"), key=lambda p: p.name):
            task = self.get(f.stem)
            if task is not None:
                out.append(task)
        return out

    def update(self, task_id: str, **fields) -> dict | None:
        task = self.get(task_id)
        if task is None:
            return None
        if "status" in fields and fields["status"] not in _STATUSES:
            fields.pop("status")
        allowed = {"title", "description", "status", "output", "parent"}
        for k in list(fields):
            if k not in allowed:
                fields.pop(k)
        task.update(fields)
        task["updated_at"] = time.time()
        self._path(task_id).write_text(
            json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return task

    def remove(self, task_id: str) -> bool:
        path = self._path(task_id)
        if not path.is_file():
            return False
        path.unlink()
        return True


def _fmt_task(t: dict) -> str:
    mark = {"pending": " ", "in_progress": "*", "completed": "x", "cancelled": "-"}.get(
        t.get("status", "pending"), " "
    )
    title = t.get("title", "")
    desc = t.get("description", "")
    line = f"[{mark}] {t['id']}: {title} ({t.get('status', 'pending')})"
    if desc:
        line += f"\n    {desc}"
    if t.get("parent"):
        line += f"\n    parent: {t['parent']}"
    return line


class TaskCreateTool(BaseTool):
    name = "task_create"
    description = (
        "Create a structured task object. Tasks persist to .ohwang/tasks/ and "
        "carry id/status/output, unlike the flat todo list. Use for multi-step "
        "office deliverables that need tracked status and results."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Task title."},
            "description": {"type": "string", "description": "Optional details."},
            "parent": {"type": "string", "description": "Optional parent task id."},
        },
        "required": ["title"],
    }
    default_permission = "allow"

    def __init__(self, store: TaskStore) -> None:
        self.store = store

    def execute(self, input: dict) -> ToolResult:
        task = self.store.create(
            input.get("title", ""), input.get("description", ""), input.get("parent")
        )
        return ToolResult(content=f"Created task {task['id']}: {task['title']}")


class TaskGetTool(BaseTool):
    name = "task_get"
    description = "Get one structured task by id, including its current output."
    input_schema = {
        "type": "object",
        "properties": {"task_id": {"type": "string"}},
        "required": ["task_id"],
    }
    default_permission = "allow"

    def __init__(self, store: TaskStore) -> None:
        self.store = store

    def execute(self, input: dict) -> ToolResult:
        task = self.store.get(input.get("task_id", ""))
        if task is None:
            return ToolResult(content=f"Task not found: {input.get('task_id', '')}", is_error=True)
        out = _fmt_task(task)
        if task.get("output"):
            out += f"\n    output: {task['output'][:500]}"
        return ToolResult(content=out)


class TaskUpdateTool(BaseTool):
    name = "task_update"
    description = (
        "Update a task's status (pending/in_progress/completed/cancelled), title, "
        "description, or output. Pass only the fields to change."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "status": {"type": "string", "enum": list(_STATUSES)},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "output": {"type": "string", "description": "Result/summary text captured on completion."},
        },
        "required": ["task_id"],
    }
    default_permission = "allow"

    def __init__(self, store: TaskStore) -> None:
        self.store = store

    def execute(self, input: dict) -> ToolResult:
        task_id = input.get("task_id", "")
        fields = {
            k: input[k]
            for k in ("status", "title", "description", "output")
            if k in input
        }
        task = self.store.update(task_id, **fields)
        if task is None:
            return ToolResult(content=f"Task not found: {task_id}", is_error=True)
        return ToolResult(content=f"Updated task {task_id} -> {_fmt_task(task)}")


class TaskListTool(BaseTool):
    name = "task_list"
    description = "List all structured tasks (optionally filter by status)."
    input_schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": list(_STATUSES), "description": "Optional filter."}
        },
    }
    default_permission = "allow"

    def __init__(self, store: TaskStore) -> None:
        self.store = store

    def execute(self, input: dict) -> ToolResult:
        tasks = self.store.list()
        status_filter = input.get("status")
        if status_filter:
            tasks = [t for t in tasks if t.get("status") == status_filter]
        if not tasks:
            return ToolResult(content="No tasks.")
        return ToolResult(content="\n".join(_fmt_task(t) for t in tasks))


class TaskStopTool(BaseTool):
    name = "task_stop"
    description = "Mark a task as cancelled."
    input_schema = {
        "type": "object",
        "properties": {"task_id": {"type": "string"}},
        "required": ["task_id"],
    }
    default_permission = "allow"

    def __init__(self, store: TaskStore) -> None:
        self.store = store

    def execute(self, input: dict) -> ToolResult:
        task = self.store.update(input.get("task_id", ""), status="cancelled")
        if task is None:
            return ToolResult(content=f"Task not found: {input.get('task_id', '')}", is_error=True)
        return ToolResult(content=f"Cancelled task {task['id']}")


class TaskOutputTool(BaseTool):
    name = "task_output"
    description = "Attach the final output/result text to a completed task."
    input_schema = {
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "output": {"type": "string"},
        },
        "required": ["task_id", "output"],
    }
    default_permission = "allow"

    def __init__(self, store: TaskStore) -> None:
        self.store = store

    def execute(self, input: dict) -> ToolResult:
        task = self.store.update(
            input.get("task_id", ""),
            output=input.get("output", ""),
            status="completed",
        )
        if task is None:
            return ToolResult(content=f"Task not found: {input.get('task_id', '')}", is_error=True)
        return ToolResult(content=f"Task {task['id']} completed with output recorded.")
