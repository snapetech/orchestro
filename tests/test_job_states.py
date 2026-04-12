from __future__ import annotations

import pytest

from orchestro.job_states import (
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    InvalidTransition,
    can_transition,
    validate_transition,
)


@pytest.mark.parametrize(
    "from_state,to_state",
    [
        ("pending", "running"),
        ("pending", "waiting_approval"),
        ("pending", "cancelled"),
        ("waiting_approval", "running"),
        ("running", "paused"),
        ("running", "completed"),
        ("running", "failed"),
        ("running", "recovering"),
        ("running", "cancelled"),
        ("paused", "running"),
        ("recovering", "running"),
        ("recovering", "failed"),
    ],
)
def test_valid_transitions_accepted(from_state: str, to_state: str):
    validate_transition(from_state, to_state)


@pytest.mark.parametrize(
    "from_state,to_state",
    [
        ("completed", "running"),
        ("failed", "running"),
        ("cancelled", "running"),
        ("pending", "completed"),
        ("paused", "completed"),
    ],
)
def test_invalid_transitions_raise(from_state: str, to_state: str):
    with pytest.raises(InvalidTransition):
        validate_transition(from_state, to_state)


def test_terminal_states_have_no_valid_transitions():
    for state in TERMINAL_STATES:
        assert VALID_TRANSITIONS[state] == set()


def test_can_transition_returns_true_for_valid():
    assert can_transition("pending", "running") is True
    assert can_transition("running", "paused") is True


def test_can_transition_returns_false_for_invalid():
    assert can_transition("completed", "running") is False
    assert can_transition("pending", "completed") is False


def test_can_transition_returns_false_for_unknown_state():
    assert can_transition("nonexistent", "running") is False


def test_invalid_transition_for_terminal_state_mentions_terminal():
    with pytest.raises(InvalidTransition, match="terminal state"):
        validate_transition("completed", "running")


def test_invalid_transition_for_unknown_source_state():
    with pytest.raises(InvalidTransition, match="unknown state"):
        validate_transition("nonexistent", "running")


def test_invalid_transition_str_representation():
    exc = InvalidTransition("pending", "completed", "transition not allowed")
    assert "pending" in str(exc)
    assert "completed" in str(exc)
    assert "transition not allowed" in str(exc)
