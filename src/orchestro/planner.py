from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from orchestro.models import RunRequest
from orchestro.orchestrator import Orchestro


@dataclass(slots=True)
class PlanDraft:
    steps: list[tuple[str, str | None]]
    source: str
    notes: str


def build_plan_draft(
    app: Orchestro,
    *,
    goal: str,
    backend_name: str,
    strategy_name: str,
    working_directory: Path,
    domain: str | None,
) -> PlanDraft:
    fallback_reason = "no backend-specific plan could be parsed"
    if backend_name != "mock":
        try:
            plan_run_id = app.run(
                RunRequest(
                    goal=(
                        "Create a concise execution plan for the following goal.\n"
                        "Return 3 to 6 numbered steps. Each step must be a single line.\n"
                        f"Goal: {goal}"
                    ),
                    backend_name=backend_name,
                    strategy_name="plan",
                    working_directory=working_directory,
                    metadata={
                        "domain": domain,
                        "retrieval_enabled": False,
                        "plan_generation": True,
                    },
                    system_prompt=(
                        "You are generating an execution plan, not doing the work. "
                        "Return only a numbered list of actionable steps."
                    ),
                )
            )
            run = app.db.get_run(plan_run_id)
            if run and run.final_output:
                parsed = parse_numbered_steps(run.final_output)
                if parsed:
                    return PlanDraft(
                        steps=[(step, None) for step in parsed],
                        source="model",
                        notes="Plan steps were parsed from a backend-generated numbered plan.",
                    )
        except Exception as exc:
            fallback_reason = f"backend plan generation failed: {exc}"
    return fallback_plan_draft(goal=goal, domain=domain, reason=fallback_reason)


def parse_numbered_steps(text: str) -> list[str]:
    steps: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^(?:\d+[\).\:-]|\-)\s*(.+)$", line)
        if match:
            steps.append(match.group(1).strip())
    return [step for step in steps if step]


def fallback_plan_draft(*, goal: str, domain: str | None, reason: str | None = None) -> PlanDraft:
    domain_hint = f"Domain focus: {domain}." if domain else None
    return PlanDraft(
        steps=[
            ("Clarify the task boundary", f"Restate the goal and identify the expected output. {domain_hint or ''}".strip()),
            ("Inspect current context", "Read the relevant files, state, and recent runs before making changes."),
            ("Make the focused change", f"Execute the smallest useful step toward: {goal}"),
            ("Verify the result", "Run checks, inspect output, or confirm behavior against the goal."),
            ("Summarize findings", "Record what changed, what worked, and any remaining risks."),
        ],
        source="fallback",
        notes=(
            "A deterministic fallback plan was used"
            + (f" because {reason}." if reason else ".")
        ),
    )


def replan_plan_from_step(
    app: Orchestro,
    *,
    plan_id: str,
    note: str | None = None,
    sequence_no: int | None = None,
) -> PlanDraft:
    plan = app.db.get_plan(plan_id)
    if plan is None:
        raise ValueError(f"plan not found: {plan_id}")
    current_step = app.db.get_current_plan_step(plan_id)
    target_step = sequence_no if sequence_no is not None else (
        current_step.sequence_no if current_step is not None else plan.current_step_no
    )
    step_record = next((step for step in app.db.list_plan_steps(plan_id) if step.sequence_no == target_step), None)
    if step_record is None:
        raise ValueError(f"plan step not found: {target_step}")
    replan_goal_parts = [
        plan.goal,
        f"Replan from step {step_record.sequence_no}: {step_record.title}",
    ]
    if step_record.details:
        replan_goal_parts.append(f"Current step details: {step_record.details}")
    if note:
        replan_goal_parts.append(f"Replan note: {note}")
    draft = build_plan_draft(
        app,
        goal="\n\n".join(replan_goal_parts),
        backend_name=plan.backend_name,
        strategy_name=plan.strategy_name,
        working_directory=Path(plan.working_directory),
        domain=plan.domain,
    )
    app.db.replace_plan_steps_from(
        plan_id=plan_id,
        start_sequence_no=step_record.sequence_no,
        steps=draft.steps,
    )
    app.db.append_plan_event(
        plan_id=plan_id,
        event_id=str(uuid4()),
        event_type="plan_replanned",
        payload={
            "start_sequence_no": step_record.sequence_no,
            "note": note,
            "source_step_title": step_record.title,
        },
    )
    app.db.append_plan_event(
        plan_id=plan_id,
        event_id=str(uuid4()),
        event_type="think",
        payload={"source": draft.source, "notes": draft.notes},
    )
    return draft
