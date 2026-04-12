"""Tests for enriched postmortem lesson derivation."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from orchestro.db import OrchestroDB
from orchestro.orchestrator import Orchestro


@pytest.fixture()
def db(tmp_path: Path) -> OrchestroDB:
    return OrchestroDB(tmp_path / "test.db")


@pytest.fixture()
def orchestro(db: OrchestroDB) -> Orchestro:
    return Orchestro(db)


class TestDeriveLessonMethod:
    def test_backend_timeout_lesson(self, orchestro: Orchestro) -> None:
        lesson = orchestro._derive_lesson("backend_timeout", [], [], "timed out")
        assert "timeout" in lesson.lower() or "timed" in lesson.lower() or "faster" in lesson.lower()

    def test_backend_unreachable_lesson(self, orchestro: Orchestro) -> None:
        lesson = orchestro._derive_lesson("backend_unreachable", [], [], "connection refused")
        assert "unreachable" in lesson.lower() or "server" in lesson.lower()

    def test_context_overflow_lesson(self, orchestro: Orchestro) -> None:
        lesson = orchestro._derive_lesson("context_overflow", [], [], "context too long")
        assert "compact" in lesson.lower() or "context" in lesson.lower()

    def test_approval_timeout_lesson(self, orchestro: Orchestro) -> None:
        lesson = orchestro._derive_lesson("approval_timeout", [], [], "approval timed out")
        assert "approval" in lesson.lower()

    def test_workspace_conflict_lesson(self, orchestro: Orchestro) -> None:
        lesson = orchestro._derive_lesson("workspace_conflict", [], [], "path not found")
        assert "conflict" in lesson.lower() or "file" in lesson.lower() or "working" in lesson.lower()

    def test_tool_crash_repeated_tool_lesson(self, orchestro: Orchestro) -> None:
        tool_calls = ["bash(rm -rf)", "bash(rm -rf)", "bash(rm -rf)"]
        tool_errors = ["permission denied", "permission denied"]
        lesson = orchestro._derive_lesson("tool_crash", tool_calls, tool_errors, "tool failed")
        assert "bash" in lesson.lower() or "repeat" in lesson.lower() or "same" in lesson.lower()

    def test_tool_crash_single_error_lesson(self, orchestro: Orchestro) -> None:
        lesson = orchestro._derive_lesson("tool_crash", ["edit_file(foo.py)"], [], "edit failed")
        assert "tool" in lesson.lower() or "precondition" in lesson.lower()

    def test_general_failure_fallback(self, orchestro: Orchestro) -> None:
        lesson = orchestro._derive_lesson("general_failure", [], [], "something went wrong")
        assert len(lesson) > 10  # non-empty meaningful text


class TestRecordFailurePostmortem:
    def _make_run(self, db: OrchestroDB) -> str:
        run_id = str(uuid4())
        db.create_run(
            run_id=run_id,
            goal="test goal for postmortem",
            backend_name="mock",
            strategy_name="direct",
            working_directory="/tmp",
        )
        return run_id

    def test_postmortem_recorded_with_lesson(self, db: OrchestroDB, orchestro: Orchestro) -> None:
        run_id = self._make_run(db)
        orchestro._record_failure_postmortem(run_id=run_id, error_text="connection refused: backend down")
        postmortems = db.list_postmortems(limit=10)
        assert len(postmortems) == 1
        pm = postmortems[0]
        assert "Lesson:" in pm.summary
        assert pm.category == "backend_unreachable"

    def test_postmortem_records_goal(self, db: OrchestroDB, orchestro: Orchestro) -> None:
        run_id = self._make_run(db)
        orchestro._record_failure_postmortem(run_id=run_id, error_text="timed out")
        pm = db.list_postmortems(limit=1)[0]
        assert "test goal for postmortem" in pm.summary

    def test_postmortem_records_strategy(self, db: OrchestroDB, orchestro: Orchestro) -> None:
        run_id = self._make_run(db)
        orchestro._record_failure_postmortem(run_id=run_id, error_text="tool crash")
        pm = db.list_postmortems(limit=1)[0]
        assert "direct" in pm.summary

    def test_postmortem_records_backend(self, db: OrchestroDB, orchestro: Orchestro) -> None:
        run_id = self._make_run(db)
        orchestro._record_failure_postmortem(run_id=run_id, error_text="context too long overflow")
        pm = db.list_postmortems(limit=1)[0]
        assert "mock" in pm.summary

    def test_postmortem_missing_run_does_not_crash(self, orchestro: Orchestro) -> None:
        orchestro._record_failure_postmortem(run_id="nonexistent", error_text="some error")

    def test_postmortem_category_from_error_text(self, db: OrchestroDB, orchestro: Orchestro) -> None:
        run_id = self._make_run(db)
        orchestro._record_failure_postmortem(run_id=run_id, error_text="timed out waiting for response")
        pm = db.list_postmortems(limit=1)[0]
        assert pm.category == "backend_timeout"

    def test_postmortem_event_recorded_with_lesson(self, db: OrchestroDB, orchestro: Orchestro) -> None:
        run_id = self._make_run(db)
        orchestro._record_failure_postmortem(run_id=run_id, error_text="connection refused")
        events = db.list_events(run_id)
        pm_events = [e for e in events if e["event_type"] == "postmortem_recorded"]
        assert len(pm_events) == 1
        assert "lesson" in pm_events[0]["payload"]
        assert len(pm_events[0]["payload"]["lesson"]) > 5
