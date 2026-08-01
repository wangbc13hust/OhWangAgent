from __future__ import annotations

from .base import BaseTool, ToolResult


class VerifyPlanExecutionTool(BaseTool):
    name = "verify_plan_execution"
    description = (
        "After carrying out a multi-step plan, verify that each planned step was "
        "actually completed. Pass the list of planned steps and a per-step "
        "verification status (done/partial/missed) with evidence. Use after "
        "exiting plan mode to confirm deliverables before declaring success."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "description": "List of steps to verify. Each: {step, status: done|partial|missed, evidence}",
                "items": {
                    "type": "object",
                    "properties": {
                        "step": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["done", "partial", "missed"],
                        },
                        "evidence": {"type": "string"},
                    },
                    "required": ["step", "status"],
                },
            }
        },
        "required": ["steps"],
    }
    default_permission = "allow"

    def execute(self, input: dict) -> ToolResult:
        steps = input.get("steps", [])
        if not steps:
            return ToolResult(
                content="Nothing to verify (steps list is empty).", is_error=True
            )

        done = sum(1 for s in steps if s.get("status") == "done")
        partial = sum(1 for s in steps if s.get("status") == "partial")
        missed = sum(1 for s in steps if s.get("status") == "missed")
        total = len(steps)

        lines = [f"Verification: {done}/{total} done, {partial} partial, {missed} missed"]
        for i, s in enumerate(steps, 1):
            status = s.get("status", "?")
            mark = {"done": "✅", "partial": "⚠️", "missed": "❌"}.get(status, "?")
            lines.append(f"{mark} [{status}] {s.get('step', '')}")
            if s.get("evidence"):
                lines.append(f"      evidence: {s['evidence'][:200]}")

        all_done = missed == 0 and partial == 0
        if all_done:
            lines.append("All planned steps completed.")
            is_error = False
        elif missed == 0:
            lines.append("Plan mostly complete; partial steps remain (re-check them).")
            is_error = False
        else:
            lines.append("Missed steps remain — do not claim success yet.")
            is_error = True
        return ToolResult(content="\n".join(lines), is_error=is_error)
