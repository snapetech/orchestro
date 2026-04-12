from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from orchestro.db import OrchestroDB
from orchestro.models import RunRequest

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ScheduledTask:
    task_id: str
    name: str
    schedule: str
    goal: str
    backend: str | None = None
    strategy: str = "direct"
    domain: str | None = None
    autonomous: bool = True
    max_wall_time: int = 1800
    enabled: bool = True
    run_count: int = 0
    last_run_at: str | None = None
    last_run_status: str | None = None
    created_at: str = ""


def parse_cron(expression: str) -> dict[str, set[int] | None]:
    fields = expression.strip().split()
    if len(fields) != 5:
        raise ValueError(f"cron expression must have 5 fields, got {len(fields)}: {expression!r}")

    limits = [
        ("minute", 0, 59),
        ("hour", 0, 23),
        ("day", 1, 31),
        ("month", 1, 12),
        ("weekday", 0, 6),
    ]
    result: dict[str, set[int] | None] = {}
    for field, (name, lo, hi) in zip(fields, limits):
        result[name] = _parse_cron_field(field, lo, hi)
    return result


def _parse_cron_field(field: str, lo: int, hi: int) -> set[int] | None:
    if field == "*":
        return None
    values: set[int] = set()
    for part in field.split(","):
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
            if start < lo or end > hi or start > end:
                raise ValueError(f"invalid range {part} for bounds [{lo}, {hi}]")
            values.update(range(start, end + 1))
        else:
            val = int(part)
            if val < lo or val > hi:
                raise ValueError(f"value {val} out of bounds [{lo}, {hi}]")
            values.add(val)
    return values


def cron_is_due(expression: str, now: datetime | None = None) -> bool:
    if now is None:
        now = datetime.now()
    parsed = parse_cron(expression)
    checks = [
        (parsed["minute"], now.minute),
        (parsed["hour"], now.hour),
        (parsed["day"], now.day),
        (parsed["month"], now.month),
        (parsed["weekday"], (now.weekday() + 1) % 7),
    ]
    for allowed, current in checks:
        if allowed is not None and current not in allowed:
            return False
    return True


class SchedulerLoop:
    def __init__(self, db: OrchestroDB, orchestro: object) -> None:
        self.db = db
        self.orchestro = orchestro
        self._stop = threading.Event()

    def start(self) -> threading.Thread:
        t = threading.Thread(target=self._run, daemon=True)
        t.start()
        return t

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(60):
            self._tick()

    def _tick(self) -> None:
        tasks = self.db.list_scheduled_tasks(enabled_only=True)
        now = datetime.now()
        for task in tasks:
            try:
                if cron_is_due(task.schedule, now):
                    self._execute_task(task)
            except Exception:
                logger.exception("scheduler: failed to execute task %s", task.task_id)

    def _execute_task(self, task: ScheduledTask) -> None:
        from orchestro.orchestrator import Orchestro

        orchestro: Orchestro = self.orchestro  # type: ignore[assignment]
        request = RunRequest(
            goal=task.goal,
            backend_name=task.backend or "auto",
            strategy_name=task.strategy,
            working_directory=Path.cwd(),
            metadata={
                **({"domain": task.domain} if task.domain else {}),
                "scheduled_task_id": task.task_id,
            },
            autonomous=task.autonomous,
        )
        status = "done"
        try:
            orchestro.run(request)
        except Exception:
            logger.exception("scheduler: task %s run failed", task.task_id)
            status = "failed"
        self.db.update_scheduled_task_run(task.task_id, status)
