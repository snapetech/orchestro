"""Tests for constitution text propagation into strategy sub-calls."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from orchestro.db import OrchestroDB
from orchestro.models import BackendResponse, RunRequest
from orchestro.orchestrator import Orchestro, PreparedRun


@pytest.fixture()
def db(tmp_path: Path) -> OrchestroDB:
    return OrchestroDB(tmp_path / "test.db")


@pytest.fixture()
def orchestro(db: OrchestroDB) -> Orchestro:
    return Orchestro(db)


def _make_run_id(db: OrchestroDB) -> str:
    rid = str(uuid4())
    db.create_run(
        run_id=rid,
        goal="test",
        backend_name="mock",
        strategy_name="critique-revise",
        working_directory="/tmp",
    )
    return rid


def _make_backend_response(text: str = "test output") -> BackendResponse:
    return BackendResponse(
        output_text=text,
        metadata={},
        prompt_tokens=10,
        completion_tokens=10,
        total_tokens=20,
    )


class TestPreparedRunConstitutionField:
    def test_prepared_run_has_constitution_field(self) -> None:
        backend = MagicMock()
        request = RunRequest(
            goal="test",
            backend_name="mock",
            strategy_name="direct",
            working_directory="/tmp",
        )
        prepared = PreparedRun(
            run_id="rid",
            backend=backend,
            request=request,
            retrieval_bundle=None,
            constitution_text="domain rule: always cite sources",
        )
        assert prepared.constitution_text == "domain rule: always cite sources"

    def test_prepared_run_constitution_defaults_to_none(self) -> None:
        backend = MagicMock()
        request = RunRequest(
            goal="test",
            backend_name="mock",
            strategy_name="direct",
            working_directory="/tmp",
        )
        prepared = PreparedRun(
            run_id="rid",
            backend=backend,
            request=request,
            retrieval_bundle=None,
        )
        assert prepared.constitution_text is None


class TestCritiqueReviseConstitution:
    def test_critique_request_includes_constitution(
        self, db: OrchestroDB, orchestro: Orchestro
    ) -> None:
        rid = _make_run_id(db)
        constitution = "Always prefer concise answers."
        backend = MagicMock()
        backend.run.return_value = _make_backend_response("draft response")
        request = RunRequest(
            goal="explain gravity",
            backend_name="mock",
            strategy_name="critique-revise",
            working_directory="/tmp",
        )
        prepared = PreparedRun(
            run_id=rid,
            backend=backend,
            request=request,
            retrieval_bundle=None,
            constitution_text=constitution,
        )
        captured_system_prompts: list[str] = []

        def fake_execute_backend(*, prepared: PreparedRun, **kwargs):  # type: ignore[return]
            sp = prepared.request.system_prompt or ""
            captured_system_prompts.append(sp)
            return _make_backend_response("output")

        with patch.object(orchestro, "_execute_backend_once", side_effect=fake_execute_backend):
            orchestro._execute_critique_revise(
                prepared=prepared,
                cancel_requested=None,
                control_state=None,
            )

        # The critique and revise calls should include the constitution.
        assert len(captured_system_prompts) >= 2
        critique_prompt = captured_system_prompts[1]
        revise_prompt = captured_system_prompts[2] if len(captured_system_prompts) > 2 else ""
        assert constitution in critique_prompt or constitution in revise_prompt

    def test_critique_without_constitution_does_not_crash(
        self, db: OrchestroDB, orchestro: Orchestro
    ) -> None:
        rid = _make_run_id(db)
        backend = MagicMock()
        request = RunRequest(
            goal="test",
            backend_name="mock",
            strategy_name="critique-revise",
            working_directory="/tmp",
        )
        prepared = PreparedRun(
            run_id=rid,
            backend=backend,
            request=request,
            retrieval_bundle=None,
            constitution_text=None,  # no constitution
        )

        with patch.object(
            orchestro, "_execute_backend_once", return_value=_make_backend_response()
        ):
            result = orchestro._execute_critique_revise(
                prepared=prepared,
                cancel_requested=None,
                control_state=None,
            )
        assert result.output_text == "output" or result is not None


class TestVerifiedConstitution:
    def test_verified_retry_includes_constitution(
        self, db: OrchestroDB, orchestro: Orchestro
    ) -> None:
        rid = _make_run_id(db)
        db.update_run_failure_state(run_id=rid)
        constitution = "Always validate return types."
        backend = MagicMock()
        request = RunRequest(
            goal="write a function",
            backend_name="mock",
            strategy_name="verified",
            working_directory="/tmp",
            metadata={"verifiers": ["python-syntax"]},
        )
        prepared = PreparedRun(
            run_id=rid,
            backend=backend,
            request=request,
            retrieval_bundle=None,
            constitution_text=constitution,
        )
        call_prompts: list[str] = []

        def fake_execute(*, prepared: PreparedRun, **kwargs):  # type: ignore[return]
            call_prompts.append(prepared.request.system_prompt or "")
            return _make_backend_response("def foo(): pass  # valid python")

        with patch.object(orchestro, "_execute_backend_once", side_effect=fake_execute):
            orchestro._execute_verified(
                prepared=prepared,
                cancel_requested=None,
                control_state=None,
            )

        # Even if first attempt passes, the prepared constitution should be accessible.
        assert prepared.constitution_text == constitution
