from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

VALID_COMMIT_POLICIES = {"squash", "per-step", "none"}
VALID_ESCALATION_POLICIES = {"escalate", "abandon", "retry"}
VALID_REPORTING_MODES = {"summary", "full-trace", "structured"}


@dataclass(slots=True)
class TaskPacket:
    objective: str
    scope: str | None = None
    acceptance_tests: list[str] | None = None
    commit_policy: str = "none"
    escalation_policy: str = "escalate"
    max_wall_time: int = 900
    context: dict | None = None
    reporting: str = "summary"


@dataclass(slots=True)
class TaskRecord:
    task_id: str
    parent_run_id: str
    objective: str
    packet_json: str
    status: str
    assigned_run_id: str | None = None
    output: str | None = None
    acceptance_result: str | None = None
    created_at: str = ""
    completed_at: str | None = None


def run_acceptance_tests(tests: list[str], cwd: Path) -> tuple[bool, list[dict]]:
    results: list[dict] = []
    all_passed = True
    for test_cmd in tests:
        try:
            proc = subprocess.run(
                test_cmd,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            passed = proc.returncode == 0
            output = (proc.stdout + proc.stderr).strip()
        except subprocess.TimeoutExpired:
            passed = False
            output = "timed out after 30s"
        except Exception as exc:
            passed = False
            output = str(exc)
        if not passed:
            all_passed = False
        results.append({"test": test_cmd, "passed": passed, "output": output[:2000]})
    return all_passed, results


def validate_task_packet(packet: TaskPacket) -> list[str]:
    errors: list[str] = []
    if not packet.objective or not packet.objective.strip():
        errors.append("objective must be non-empty")
    if packet.max_wall_time <= 0:
        errors.append("max_wall_time must be > 0")
    if packet.escalation_policy not in VALID_ESCALATION_POLICIES:
        errors.append(
            f"escalation_policy must be one of {sorted(VALID_ESCALATION_POLICIES)}, "
            f"got '{packet.escalation_policy}'"
        )
    if packet.commit_policy not in VALID_COMMIT_POLICIES:
        errors.append(
            f"commit_policy must be one of {sorted(VALID_COMMIT_POLICIES)}, "
            f"got '{packet.commit_policy}'"
        )
    if packet.reporting not in VALID_REPORTING_MODES:
        errors.append(
            f"reporting must be one of {sorted(VALID_REPORTING_MODES)}, "
            f"got '{packet.reporting}'"
        )
    return errors
