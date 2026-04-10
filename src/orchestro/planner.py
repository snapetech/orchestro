from __future__ import annotations

import re
from pathlib import Path

from orchestro.models import RunRequest
from orchestro.orchestrator import Orchestro


def build_plan_steps(
    app: Orchestro,
    *,
    goal: str,
    backend_name: str,
    strategy_name: str,
    working_directory: Path,
    domain: str | None,
) -> list[tuple[str, str | None]]:
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
                    return [(step, None) for step in parsed]
        except Exception:
            pass
    return fallback_plan_steps(goal=goal, domain=domain)


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


def fallback_plan_steps(*, goal: str, domain: str | None) -> list[tuple[str, str | None]]:
    domain_hint = f"Domain focus: {domain}." if domain else None
    return [
        ("Clarify the task boundary", f"Restate the goal and identify the expected output. {domain_hint or ''}".strip()),
        ("Inspect current context", "Read the relevant files, state, and recent runs before making changes."),
        ("Make the focused change", f"Execute the smallest useful step toward: {goal}"),
        ("Verify the result", "Run checks, inspect output, or confirm behavior against the goal."),
        ("Summarize findings", "Record what changed, what worked, and any remaining risks."),
    ]
