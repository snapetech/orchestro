from __future__ import annotations

import pytest

from orchestro.backends.base import Backend
from orchestro.backends.mock import MockBackend
from orchestro.models import BackendResponse, RatingRequest, RunRequest
from orchestro.orchestrator import Orchestro


def _make_orchestro(tmp_db):
    return Orchestro(db=tmp_db, backends={"mock": MockBackend()})


def _make_request(**overrides) -> RunRequest:
    defaults = dict(goal="Say hello", backend_name="mock", strategy_name="direct")
    defaults.update(overrides)
    return RunRequest(**defaults)


class UsageLimitBackend(Backend):
    name = "usage-limit"

    def run(self, request: RunRequest) -> BackendResponse:
        raise RuntimeError("You've hit your usage limit")


class CountingModelsBackend(Backend):
    name = "counting"

    def __init__(self) -> None:
        self.calls = 0

    def run(self, request: RunRequest) -> BackendResponse:
        return BackendResponse(output_text="ok")

    def list_models(self) -> list[str]:
        self.calls += 1
        return ["counting-model"]


class BrokenModelsBackend(Backend):
    name = "broken-models"

    def run(self, request: RunRequest) -> BackendResponse:
        return BackendResponse(output_text="ok")

    def list_models(self) -> list[str]:
        raise RuntimeError("model discovery failed")


class TestOrchestrInit:
    def test_init_with_mock_backend(self, tmp_db):
        orch = _make_orchestro(tmp_db)
        assert "mock" in orch.backends
        assert orch.db is tmp_db

    def test_available_backends_includes_mock(self, tmp_db):
        orch = _make_orchestro(tmp_db)
        caps = orch.available_backends()
        assert "mock" in caps

    def test_backend_statuses_cache_model_inventory(self, tmp_db, monkeypatch):
        backend = CountingModelsBackend()
        orch = Orchestro(db=tmp_db, backends={"counting": backend})
        monkeypatch.setenv("ORCHESTRO_BACKEND_MODEL_CACHE_TTL_SEC", "300")

        first = orch.backend_statuses()
        second = orch.backend_statuses()

        assert first[0]["available_models"] == ["counting-model"]
        assert second[0]["available_models"] == ["counting-model"]
        assert backend.calls == 1

    def test_backend_statuses_survive_model_discovery_errors(self, tmp_db, monkeypatch):
        orch = Orchestro(db=tmp_db, backends={"broken-models": BrokenModelsBackend()})
        monkeypatch.setenv("ORCHESTRO_BACKEND_MODEL_CACHE_TTL_SEC", "300")

        statuses = orch.backend_statuses()

        assert statuses[0]["name"] == "broken-models"
        assert statuses[0]["available_models"] == []
        assert statuses[0]["available_models_error"] == "model discovery failed"


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

    def test_auto_backend_reroutes_on_usage_limit(self, tmp_db):
        orch = Orchestro(db=tmp_db, backends={"claude-code": UsageLimitBackend(), "mock": MockBackend()})
        run_id = orch.run(_make_request(goal="use claude to say hello", backend_name="auto"))
        run = tmp_db.get_run(run_id)
        assert run is not None
        assert run.status == "done"
        assert "Mock backend response" in (run.final_output or "")
        events = tmp_db.list_events(run_id)
        event_types = [e["event_type"] for e in events]
        assert "backend_temporarily_unavailable" in event_types
        assert "backend_auto_rerouted" in event_types


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
