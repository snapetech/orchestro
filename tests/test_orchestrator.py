from __future__ import annotations

import pytest

from orchestro.backends.mock import MockBackend
from orchestro.models import BackendResponse, RatingRequest, RunRequest
from orchestro.orchestrator import Orchestro


def _make_orchestro(tmp_db):
    return Orchestro(db=tmp_db, backends={"mock": MockBackend()})


def _make_request(**overrides) -> RunRequest:
    defaults = dict(goal="Say hello", backend_name="mock", strategy_name="direct")
    defaults.update(overrides)
    return RunRequest(**defaults)


class TestOrchestrInit:
    def test_init_with_mock_backend(self, tmp_db):
        orch = _make_orchestro(tmp_db)
        assert "mock" in orch.backends
        assert orch.db is tmp_db

    def test_available_backends_includes_mock(self, tmp_db):
        orch = _make_orchestro(tmp_db)
        caps = orch.available_backends()
        assert "mock" in caps


class TestOrchestrRun:
    def test_run_returns_run_id(self, tmp_db):
        orch = _make_orchestro(tmp_db)
        run_id = orch.run(_make_request())
        assert isinstance(run_id, str)
        assert len(run_id) > 0

    def test_run_creates_events(self, tmp_db):
        orch = _make_orchestro(tmp_db)
        run_id = orch.run(_make_request())
        events = tmp_db.list_events(run_id)
        assert len(events) > 0
        event_types = [e["event_type"] for e in events]
        assert "run_started" in event_types
        assert "run_completed" in event_types

    def test_run_unknown_backend_raises(self, tmp_db):
        orch = _make_orchestro(tmp_db)
        with pytest.raises(ValueError, match="unknown backend"):
            orch.run(_make_request(backend_name="nonexistent"))

    def test_run_self_consistency_completes(self, tmp_db):
        orch = _make_orchestro(tmp_db)
        request = _make_request(
            strategy_name="self-consistency",
            metadata={"consistency_samples": 2},
        )
        run_id = orch.run(request)
        run = tmp_db.get_run(run_id)
        assert run is not None
        assert run.status == "done"


class TestOrchestrRate:
    def test_rate_stores_rating(self, tmp_db):
        orch = _make_orchestro(tmp_db)
        run_id = orch.run(_make_request())
        rating_id = orch.rate(RatingRequest(
            target_type="run",
            target_id=run_id,
            rating="good",
            note="nice",
        ))
        assert isinstance(rating_id, str)
        assert len(rating_id) > 0
