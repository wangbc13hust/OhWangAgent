from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

_RUNNER = Callable[[str], str]


@dataclass
class CronJob:
    id: str
    expression: str
    prompt: str
    last_run: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "expression": self.expression,
            "prompt": self.prompt,
            "last_run": self.last_run,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CronJob":
        return cls(
            id=data.get("id", ""),
            expression=data.get("expression", ""),
            prompt=data.get("prompt", ""),
            last_run=data.get("last_run", 0.0),
        )


def _field(spec: str, lo: int, hi: int) -> set[int]:
    """Parse a cron field (e.g. '*', '*/5', '1,3', '2-6', '2-6/2') into ints."""
    if spec == "*":
        return set(range(lo, hi + 1))
    values: set[int] = set()
    for part in spec.split(","):
        if "/" in part:
            base, step_s = part.split("/", 1)
            step = int(step_s)
            if base == "*":
                values.update(range(lo, hi + 1, step))
            else:
                a, _, b = base.partition("-")
                a = lo if a == "" else int(a)
                b = hi if b == "" else int(b)
                values.update(range(a, b + 1, step))
        elif "-" in part:
            a, b = part.split("-", 1)
            values.update(range(int(a), int(b) + 1))
        else:
            values.add(int(part))
    return {v for v in values if lo <= v <= hi}


def cron_matches(expression: str, minute: int, hour: int, dom: int, month: int, dow: int) -> bool:
    """Match a 5-field cron expression against the given date/time parts."""
    parts = expression.split()
    if len(parts) != 5:
        return False
    m, h, d, mo, dw = (_field(p, lo, hi) for p, (lo, hi) in
                       zip(parts, [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]))
    return minute in m and hour in h and dom in d and month in mo and dow in dw


def py_dow_to_cron(tm_wday: int) -> int:
    """Convert Python time.localtime().tm_wday (0=Mon..6=Sun) to cron dow (0=Sun..6=Sat)."""
    return (tm_wday + 1) % 7


class Scheduler:
    """Background thread that fires cron jobs, running each prompt via `runner`.

    The runner is a callable taking the job prompt and returning a summary
    string. Call `start()` to begin polling (1s resolution); the worker stops
    on `stop()`.
    """

    def __init__(
        self,
        runner: Optional[_RUNNER] = None,
        state_file: str | Path | None = None,
    ) -> None:
        self._runner = runner
        self._state_file = Path(state_file) if state_file else None
        self._jobs: dict[str, CronJob] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        if self._state_file is not None:
            self._load()

    def _load(self) -> None:
        if self._state_file is None or not self._state_file.is_file():
            return
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8-sig"))
        except Exception:
            return
        jobs = data.get("jobs", []) if isinstance(data, dict) else data
        for entry in jobs:
            if not isinstance(entry, dict):
                continue
            job = CronJob.from_dict(entry)
            if job.id and self._valid_expression(job.expression):
                self._jobs[job.id] = job

    def _save(self) -> None:
        if self._state_file is None:
            return
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {"jobs": [j.to_dict() for j in self._jobs.values()]}
            self._state_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            pass

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=5)
        self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            now = time.time()
            lt = time.localtime(now)
            due: list[CronJob] = []
            with self._lock:
                for job in self._jobs.values():
                    if job.last_run > now - 30:
                        continue
                    if cron_matches(job.expression, lt.tm_min, lt.tm_hour,
                                    lt.tm_mday, lt.tm_mon, py_dow_to_cron(lt.tm_wday)):
                        due.append(job)
            for job in due:
                with self._lock:
                    job.last_run = now
                if self._runner is not None:
                    try:
                        self._runner(job.prompt)
                    except Exception:
                        pass
            self._stop.wait(1)

    def add(self, job_id: str, expression: str, prompt: str) -> bool:
        if not self._valid_expression(expression):
            return False
        with self._lock:
            if job_id in self._jobs:
                return False
            self._jobs[job_id] = CronJob(id=job_id, expression=expression, prompt=prompt)
        self._save()
        return True

    def remove(self, job_id: str) -> bool:
        with self._lock:
            removed = self._jobs.pop(job_id, None) is not None
        if removed:
            self._save()
        return removed

    def list(self) -> list[CronJob]:
        with self._lock:
            return list(self._jobs.values())

    def count(self) -> int:
        with self._lock:
            return len(self._jobs)

    @staticmethod
    def _valid_expression(expression: str) -> bool:
        try:
            parts = expression.split()
            if len(parts) != 5:
                return False
            for p, (lo, hi) in zip(parts, [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]):
                _field(p, lo, hi)
            return True
        except Exception:
            return False
