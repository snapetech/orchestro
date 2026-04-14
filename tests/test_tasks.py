from __future__ import annotations

from pathlib import Path

from orchestro.tasks import TaskPacket, TaskRecord, run_acceptance_tests, validate_task_packet


# ---------------------------------------------------------------------------
# TaskPacket / validate_task_packet
# ---------------------------------------------------------------------------

def test_validate_valid_packet_no_errors():
    packet = TaskPacket(objective="Implement feature X")
    errors = validate_task_packet(packet)
    assert errors == []


def test_validate_empty_objective_returns_error():
    packet = TaskPacket(objective="")
    errors = validate_task_packet(packet)
    assert any("objective" in e for e in errors)


def test_validate_whitespace_only_objective_error():
    packet = TaskPacket(objective="   ")
    errors = validate_task_packet(packet)
    assert any("objective" in e for e in errors)


def test_task_packet_defaults():
    packet = TaskPacket(objective="do stuff")
    assert packet.commit_policy == "none"
    assert packet.escalation_policy == "escalate"
    assert packet.max_wall_time == 900
    assert packet.reporting == "summary"
    assert packet.scope is None
    assert packet.acceptance_tests is None
    assert packet.context is None


def test_validate_invalid_commit_policy():
    packet = TaskPacket(objective="do task", commit_policy="invalid")
    errors = validate_task_packet(packet)
    assert any("commit_policy" in e for e in errors)


def test_validate_valid_commit_policies():
    for policy in ("squash", "per-step", "none"):
        packet = TaskPacket(objective="do task", commit_policy=policy)
        assert validate_task_packet(packet) == []


def test_validate_invalid_escalation_policy():
    packet = TaskPacket(objective="do task", escalation_policy="give-up")
    errors = validate_task_packet(packet)
    assert any("escalation_policy" in e for e in errors)


def test_validate_valid_escalation_policies():
    for policy in ("escalate", "abandon", "retry"):
        packet = TaskPacket(objective="do task", escalation_policy=policy)
        assert validate_task_packet(packet) == []


def test_validate_invalid_reporting_mode():
    packet = TaskPacket(objective="do task", reporting="verbose")
    errors = validate_task_packet(packet)
    assert any("reporting" in e for e in errors)


def test_validate_valid_reporting_modes():
    for mode in ("summary", "full-trace", "structured"):
        packet = TaskPacket(objective="do task", reporting=mode)
        assert validate_task_packet(packet) == []


def test_validate_zero_max_wall_time():
    packet = TaskPacket(objective="do task", max_wall_time=0)
    errors = validate_task_packet(packet)
    assert any("max_wall_time" in e for e in errors)


def test_validate_negative_max_wall_time():
    packet = TaskPacket(objective="do task", max_wall_time=-1)
    errors = validate_task_packet(packet)
    assert any("max_wall_time" in e for e in errors)


def test_validate_multiple_errors_at_once():
    packet = TaskPacket(objective="", commit_policy="bad", max_wall_time=0)
    errors = validate_task_packet(packet)
    assert len(errors) >= 3


# ---------------------------------------------------------------------------
# TaskRecord
# ---------------------------------------------------------------------------

def test_task_record_fields():
    rec = TaskRecord(
        task_id="t-1",
        parent_run_id="r-1",
        objective="Do the thing",
        packet_json="{}",
        status="pending",
    )
    assert rec.task_id == "t-1"
    assert rec.parent_run_id == "r-1"
    assert rec.status == "pending"
    assert rec.assigned_run_id is None
    assert rec.output is None


# ---------------------------------------------------------------------------
# run_acceptance_tests
# ---------------------------------------------------------------------------

def test_passing_command_returns_true(tmp_path: Path):
    passed, results = run_acceptance_tests(["true"], cwd=tmp_path)
    assert passed is True
    assert results[0]["passed"] is True


def test_failing_command_returns_false(tmp_path: Path):
    passed, results = run_acceptance_tests(["false"], cwd=tmp_path)
    assert passed is False
    assert results[0]["passed"] is False


def test_multiple_tests_all_pass(tmp_path: Path):
    passed, results = run_acceptance_tests(["true", "true"], cwd=tmp_path)
    assert passed is True
    assert len(results) == 2


def test_one_failing_marks_all_failed(tmp_path: Path):
    passed, results = run_acceptance_tests(["true", "false"], cwd=tmp_path)
    assert passed is False


def test_results_include_test_command(tmp_path: Path):
    _, results = run_acceptance_tests(["true"], cwd=tmp_path)
    assert results[0]["test"] == "true"


def test_output_captured(tmp_path: Path):
    _, results = run_acceptance_tests(["echo hello"], cwd=tmp_path)
    assert "hello" in results[0]["output"]


def test_nonexistent_command_returns_false(tmp_path: Path):
    passed, results = run_acceptance_tests(["this-command-xyz-does-not-exist"], cwd=tmp_path)
    assert passed is False
    assert results[0]["passed"] is False
