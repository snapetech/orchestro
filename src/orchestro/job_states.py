from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from orchestro.db import OrchestroDB

VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"running", "waiting_approval", "cancelled"},
    "waiting_approval": {"running", "cancelled"},
    "running": {"paused", "waiting_input", "completed", "failed", "recovering", "cancelled"},
    "paused": {"running", "cancelled"},
    "waiting_input": {"running", "cancelled"},
    "recovering": {"running", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}

TERMINAL_STATES = {"completed", "failed", "cancelled"}


@dataclass(slots=True)
class InvalidTransition(Exception):
    from_state: str
    to_state: str
    reason: str

    def __str__(self) -> str:
        msg = f"invalid transition: {self.from_state} -> {self.to_state}"
        if self.reason:
            msg += f" ({self.reason})"
        return msg


def validate_transition(from_state: str, to_state: str) -> None:
    allowed = VALID_TRANSITIONS.get(from_state)
    if allowed is None:
        raise InvalidTransition(from_state, to_state, f"unknown state: {from_state}")
    if to_state not in allowed:
        if from_state in TERMINAL_STATES:
            raise InvalidTransition(from_state, to_state, f"{from_state} is a terminal state")
        raise InvalidTransition(from_state, to_state, "transition not allowed")


def can_transition(from_state: str, to_state: str) -> bool:
    allowed = VALID_TRANSITIONS.get(from_state)
    if allowed is None:
        return False
    return to_state in allowed


def transition_job(db: OrchestroDB, job_id: str, to_state: str, *, reason: str = "") -> str:
    job = db.get_shell_job(job_id)
    if job is None:
        raise ValueError(f"shell job not found: {job_id}")
    from_state = job.control_state
    validate_transition(from_state, to_state)
    db.update_shell_job_status(job_id=job_id, status=to_state)
    db.append_shell_job_event(
        job_id=job_id,
        event_id=f"{job_id}-state-{uuid4()}",
        event_type="state_changed",
        payload={
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason,
        },
    )
    return to_state
