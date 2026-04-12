from __future__ import annotations

from orchestro.correction_aware import should_elevate_approval
from orchestro.db import OrchestroDB


def test_returns_false_when_no_retrieval_event(tmp_db: OrchestroDB):
    tmp_db.create_run(
        run_id="run-ca-1",
        goal="test correction",
        backend_name="mock",
        strategy_name="direct",
        working_directory="/tmp",
    )
    elevate, reason = should_elevate_approval("bash", "ls -la", "run-ca-1", tmp_db)
    assert elevate is False
    assert reason == ""


def test_returns_false_when_corrections_dont_match_tool(tmp_db: OrchestroDB):
    tmp_db.create_run(
        run_id="run-ca-2",
        goal="test correction mismatch",
        backend_name="mock",
        strategy_name="direct",
        working_directory="/tmp",
    )
    tmp_db.append_event(
        run_id="run-ca-2",
        event_id="evt-ret-1",
        event_type="retrieval_built",
        payload={"correction_count": 1},
    )
    tmp_db.add_correction(
        correction_id="corr-nomatch",
        context="user asked about Python version",
        wrong_answer="Python 2 is latest",
        right_answer="Python 3 is latest",
        domain="coding",
        severity="normal",
        source_run_id=None,
    )
    elevate, reason = should_elevate_approval("bash", "ls -la", "run-ca-2", tmp_db)
    assert elevate is False
    assert reason == ""


def test_returns_true_when_correction_mentions_tool(tmp_db: OrchestroDB):
    tmp_db.create_run(
        run_id="run-ca-3",
        goal="test correction match",
        backend_name="mock",
        strategy_name="direct",
        working_directory="/tmp",
    )
    tmp_db.append_event(
        run_id="run-ca-3",
        event_id="evt-ret-2",
        event_type="retrieval_built",
        payload={"correction_count": 1},
    )
    tmp_db.add_correction(
        correction_id="corr-match",
        context="bash command was wrong, used rm -rf instead of rm",
        wrong_answer="ran bash rm -rf /",
        right_answer="use rm with caution",
        domain="ops",
        severity="critical",
        source_run_id=None,
    )
    elevate, reason = should_elevate_approval("bash", "rm file.txt", "run-ca-3", tmp_db)
    assert elevate is True
    assert "correction" in reason.lower() or "bash" in reason.lower()


def test_returns_true_when_correction_matches_tool_args(tmp_db: OrchestroDB):
    tmp_db.create_run(
        run_id="run-ca-4",
        goal="test arg match",
        backend_name="mock",
        strategy_name="direct",
        working_directory="/tmp",
    )
    tmp_db.append_event(
        run_id="run-ca-4",
        event_id="evt-ret-3",
        event_type="retrieval_built",
        payload={"correction_count": 1},
    )
    tmp_db.add_correction(
        correction_id="corr-arg-match",
        context="deploy script had wrong target directory",
        wrong_answer="deployed to production",
        right_answer="should deploy to staging first",
        domain="ops",
        severity="high",
        source_run_id=None,
    )
    elevate, reason = should_elevate_approval(
        "edit_file", "deploy script target", "run-ca-4", tmp_db
    )
    assert elevate is True
    assert reason != ""
