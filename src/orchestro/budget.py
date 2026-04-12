from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


class BudgetExhausted(Exception):
    def __init__(self, resource: str, limit: int | float, used: int | float) -> None:
        self.resource = resource
        self.limit = limit
        self.used = used
        super().__init__(f"budget exhausted: {resource} ({used}/{limit})")


@dataclass(slots=True)
class RunBudget:
    max_tool_calls: int = 20
    max_tokens: int = 50_000
    max_wall_seconds: float = 300.0
    max_file_edits: int = 10
    max_bash_calls: int = 5

    tool_calls_used: int = 0
    tokens_used: int = 0
    file_edits_used: int = 0
    bash_calls_used: int = 0
    started_at: float = 0.0

    def start(self) -> None:
        self.started_at = time.time()

    def record_tool_call(self, tool_name: str) -> None:
        self.tool_calls_used += 1
        if tool_name == "bash":
            self.bash_calls_used += 1
        if tool_name == "edit_file":
            self.file_edits_used += 1

    def record_tokens(self, count: int) -> None:
        self.tokens_used += count

    def check(self) -> None:
        if self.tool_calls_used > self.max_tool_calls:
            raise BudgetExhausted("tool_calls", self.max_tool_calls, self.tool_calls_used)
        if self.tokens_used > self.max_tokens:
            raise BudgetExhausted("tokens", self.max_tokens, self.tokens_used)
        if self.file_edits_used > self.max_file_edits:
            raise BudgetExhausted("file_edits", self.max_file_edits, self.file_edits_used)
        if self.bash_calls_used > self.max_bash_calls:
            raise BudgetExhausted("bash_calls", self.max_bash_calls, self.bash_calls_used)
        if self.started_at > 0:
            elapsed = time.time() - self.started_at
            if elapsed > self.max_wall_seconds:
                raise BudgetExhausted("wall_seconds", self.max_wall_seconds, elapsed)

    def remaining(self) -> dict[str, int | float]:
        elapsed = time.time() - self.started_at if self.started_at > 0 else 0.0
        return {
            "tool_calls": self.max_tool_calls - self.tool_calls_used,
            "tokens": self.max_tokens - self.tokens_used,
            "file_edits": self.max_file_edits - self.file_edits_used,
            "bash_calls": self.max_bash_calls - self.bash_calls_used,
            "wall_seconds": max(0.0, self.max_wall_seconds - elapsed),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_tool_calls": self.max_tool_calls,
            "max_tokens": self.max_tokens,
            "max_wall_seconds": self.max_wall_seconds,
            "max_file_edits": self.max_file_edits,
            "max_bash_calls": self.max_bash_calls,
            "tool_calls_used": self.tool_calls_used,
            "tokens_used": self.tokens_used,
            "file_edits_used": self.file_edits_used,
            "bash_calls_used": self.bash_calls_used,
            "started_at": self.started_at,
        }


def load_budget_defaults(metadata: dict[str, Any]) -> RunBudget:
    overrides: dict[str, Any] = {}
    field_map = {
        "budget_max_tool_calls": "max_tool_calls",
        "budget_max_tokens": "max_tokens",
        "budget_max_wall_seconds": "max_wall_seconds",
        "budget_max_file_edits": "max_file_edits",
        "budget_max_bash_calls": "max_bash_calls",
    }
    for meta_key, field_name in field_map.items():
        value = metadata.get(meta_key)
        if value is not None:
            if field_name == "max_wall_seconds":
                overrides[field_name] = float(value)
            else:
                overrides[field_name] = int(value)
    return RunBudget(**overrides)
