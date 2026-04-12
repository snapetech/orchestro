from __future__ import annotations

from orchestro.policies import (
    DEFAULT_POLICIES,
    Policy,
    PolicyAction,
    PolicyCondition,
    PolicyEngine,
    load_policies,
)


def test_engine_with_no_policies_returns_none():
    engine = PolicyEngine(policies=[])
    assert engine.evaluate({"tool": "bash"}) is None


def test_engine_matches_eq_condition():
    policy = Policy(
        name="match-bash",
        conditions=(PolicyCondition(field="tool", operator="eq", value="bash"),),
        action=PolicyAction(action="confirm"),
    )
    engine = PolicyEngine(policies=[policy])
    result = engine.evaluate({"tool": "bash"})
    assert result is not None
    assert result.action == "confirm"


def test_engine_matches_in_condition():
    policy = Policy(
        name="read-only",
        conditions=(PolicyCondition(field="tool", operator="in", value=["ls", "pwd"]),),
        action=PolicyAction(action="auto-approve"),
    )
    engine = PolicyEngine(policies=[policy])
    assert engine.evaluate({"tool": "ls"}) is not None
    assert engine.evaluate({"tool": "bash"}) is None


def test_engine_stops_at_first_match():
    p1 = Policy(
        name="first",
        conditions=(PolicyCondition(field="tool", operator="eq", value="bash"),),
        action=PolicyAction(action="confirm"),
    )
    p2 = Policy(
        name="second",
        conditions=(PolicyCondition(field="tool", operator="eq", value="bash"),),
        action=PolicyAction(action="deny"),
    )
    engine = PolicyEngine(policies=[p1, p2])
    result = engine.evaluate({"tool": "bash"})
    assert result is not None
    assert result.action == "confirm"


def test_load_policies_returns_defaults_when_no_file(tmp_path):
    policies = load_policies(tmp_path)
    assert len(policies) == len(DEFAULT_POLICIES)


def test_default_policies_auto_approve_read_only():
    engine = PolicyEngine(policies=list(DEFAULT_POLICIES))
    for tool in ("pwd", "ls", "read_file", "rg", "think"):
        result = engine.evaluate({"tool": tool})
        assert result is not None, f"expected match for {tool}"
        assert result.action == "auto-approve"
