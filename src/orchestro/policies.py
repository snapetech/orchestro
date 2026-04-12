from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path

from orchestro.paths import data_dir


@dataclass(frozen=True, slots=True)
class PolicyCondition:
    field: str
    operator: str
    value: str | list[str]


@dataclass(frozen=True, slots=True)
class PolicyAction:
    action: str
    params: dict[str, str] | None = None


@dataclass(frozen=True, slots=True)
class Policy:
    name: str
    conditions: tuple[PolicyCondition, ...]
    action: PolicyAction
    enabled: bool = True


class PolicyEngine:
    def __init__(self, policies: list[Policy] | None = None) -> None:
        self.policies = policies or []

    def evaluate(self, context: dict[str, str]) -> PolicyAction | None:
        for policy in self.policies:
            if not policy.enabled:
                continue
            if self._matches(policy.conditions, context):
                return policy.action
        return None

    def _matches(
        self, conditions: tuple[PolicyCondition, ...], context: dict[str, str]
    ) -> bool:
        for cond in conditions:
            ctx_value = context.get(cond.field, "")
            if cond.operator == "eq" and ctx_value != cond.value:
                return False
            elif cond.operator == "not_eq" and ctx_value == cond.value:
                return False
            elif cond.operator == "in" and ctx_value not in cond.value:
                return False
            elif cond.operator == "matches":
                if not fnmatch.fnmatch(ctx_value, str(cond.value)):
                    return False
        return True


def _policies_json_path(dir_path: Path | None = None) -> Path:
    base = dir_path if dir_path is not None else data_dir()
    return base / "policies.json"


def load_policies(dir_path: Path | None = None) -> list[Policy]:
    path = _policies_json_path(dir_path)
    if not path.exists():
        return list(DEFAULT_POLICIES)
    raw = json.loads(path.read_text(encoding="utf-8"))
    policies: list[Policy] = list(DEFAULT_POLICIES)
    for entry in raw:
        conditions: list[PolicyCondition] = []
        when = entry.get("when", {})
        for field_name, val in when.items():
            if isinstance(val, list):
                conditions.append(PolicyCondition(field=field_name, operator="in", value=val))
            else:
                conditions.append(PolicyCondition(field=field_name, operator="eq", value=val))
        action_raw = entry.get("action", {})
        action = PolicyAction(
            action=action_raw.get("action", "auto-approve"),
            params=action_raw.get("params"),
        )
        policies.append(Policy(
            name=entry.get("name", "custom"),
            conditions=tuple(conditions),
            action=action,
            enabled=entry.get("enabled", True),
        ))
    return policies


DEFAULT_POLICIES: tuple[Policy, ...] = (
    Policy(
        name="auto-approve-read-only",
        conditions=(
            PolicyCondition(field="tool", operator="in", value=["pwd", "ls", "read_file", "rg", "think"]),
        ),
        action=PolicyAction(action="auto-approve"),
    ),
    Policy(
        name="postmortem-on-tool-loop-failure",
        conditions=(
            PolicyCondition(field="strategy", operator="eq", value="tool-loop"),
            PolicyCondition(field="run_status", operator="eq", value="failed"),
        ),
        action=PolicyAction(action="record-postmortem"),
    ),
    Policy(
        name="queue-embedding-on-success",
        conditions=(
            PolicyCondition(field="run_status", operator="eq", value="done"),
        ),
        action=PolicyAction(action="queue-embedding"),
    ),
)
