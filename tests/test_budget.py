from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from orchestro.budget import BudgetExhausted, RunBudget, load_budget_defaults


def test_check_passes_when_under_limits():
    budget = RunBudget(max_tool_calls=5, max_tokens=1000)
    budget.tool_calls_used = 3
    budget.tokens_used = 500
    budget.check()


def test_check_raises_when_tool_calls_exceed_max():
    budget = RunBudget(max_tool_calls=2)
    budget.tool_calls_used = 3
    with pytest.raises(BudgetExhausted, match="tool_calls"):
        budget.check()


def test_check_raises_when_tokens_exceed_max():
    budget = RunBudget(max_tokens=100)
    budget.tokens_used = 200
    with pytest.raises(BudgetExhausted, match="tokens"):
        budget.check()


def test_check_raises_when_file_edits_exceed_max():
    budget = RunBudget(max_file_edits=1)
    budget.file_edits_used = 2
    with pytest.raises(BudgetExhausted, match="file_edits"):
        budget.check()


def test_check_raises_when_bash_calls_exceed_max():
    budget = RunBudget(max_bash_calls=1)
    budget.bash_calls_used = 2
    with pytest.raises(BudgetExhausted, match="bash_calls"):
        budget.check()


def test_record_tool_call_increments_counters():
    budget = RunBudget()
    budget.record_tool_call("read_file")
    budget.record_tool_call("bash")
    budget.record_tool_call("edit_file")
    budget.record_tool_call("bash")

    assert budget.tool_calls_used == 4
    assert budget.bash_calls_used == 2
    assert budget.file_edits_used == 1


def test_remaining_returns_correct_values():
    budget = RunBudget(max_tool_calls=10, max_tokens=5000, max_bash_calls=5, max_file_edits=3)
    budget.tool_calls_used = 4
    budget.tokens_used = 2000
    budget.bash_calls_used = 1
    budget.file_edits_used = 2

    rem = budget.remaining()
    assert rem["tool_calls"] == 6
    assert rem["tokens"] == 3000
    assert rem["bash_calls"] == 4
    assert rem["file_edits"] == 1


def test_load_budget_defaults_reads_metadata_overrides():
    meta = {
        "budget_max_tool_calls": 50,
        "budget_max_tokens": 100_000,
        "budget_max_wall_seconds": 600.0,
        "budget_max_bash_calls": 10,
    }
    budget = load_budget_defaults(meta)
    assert budget.max_tool_calls == 50
    assert budget.max_tokens == 100_000
    assert budget.max_wall_seconds == 600.0
    assert budget.max_bash_calls == 10
    assert budget.max_file_edits == 10  # default, not overridden


def test_load_budget_defaults_empty_metadata():
    budget = load_budget_defaults({})
    assert budget.max_tool_calls == 20
    assert budget.max_tokens == 50_000


def test_wall_clock_budget_expiry():
    budget = RunBudget(max_wall_seconds=1.0)
    fake_start = time.time() - 2.0
    budget.started_at = fake_start
    with pytest.raises(BudgetExhausted, match="wall_seconds"):
        budget.check()


def test_budget_exhausted_attributes():
    exc = BudgetExhausted("tokens", 1000, 1500)
    assert exc.resource == "tokens"
    assert exc.limit == 1000
    assert exc.used == 1500
    assert "tokens" in str(exc)
