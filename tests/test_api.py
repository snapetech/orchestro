from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from orchestro import api
from orchestro import mcp_client
from orchestro import lsp_client
from orchestro.backends.mock import MockBackend
from orchestro.orchestrator import Orchestro
from orchestro.plugins import PluginMetadata


@pytest.fixture()
def client(tmp_db):
    orch = Orchestro(db=tmp_db, backends={"mock": MockBackend()})
    original_orchestro = api.orchestro
    original_worker = api._embedding_worker
    api.orchestro = orch
    api._embedding_worker = None
    try:
        with TestClient(api.app) as test_client:
            yield test_client, orch
    finally:
        api.orchestro = original_orchestro
        api._embedding_worker = original_worker


def test_health_endpoint(client):
    test_client, _ = client
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_backends_endpoint_returns_mock_status(client):
    test_client, _ = client
    response = test_client.get("/backends")
    assert response.status_code == 200
    backends = response.json()
    assert len(backends) == 1
    assert backends[0]["name"] == "mock"
    assert backends[0]["reachable"] is True
    assert backends[0]["temporarily_unavailable"] is False
    assert backends[0]["available_models"] == []


def test_plugins_endpoint_exposes_load_and_hook_errors(client):
    test_client, orch = client
    orch.plugins.loaded.append(PluginMetadata(name="demo-plugin", version="1.2.3"))
    orch.plugins.load_errors = [{"plugin": "broken", "error": "import boom"}]
    orch.plugins.hooks.last_errors = [{"hook": "pre_run", "plugin": "demo-plugin", "error": "hook boom"}]

    response = test_client.get("/plugins")

    assert response.status_code == 200
    payload = response.json()
    assert payload["loaded"][0]["name"] == "demo-plugin"
    assert payload["load_errors"] == [{"plugin": "broken", "error": "import boom"}]
    assert payload["hook_errors"] == [{"hook": "pre_run", "plugin": "demo-plugin", "error": "hook boom"}]


def test_mcp_status_endpoint_exposes_degraded_details(client, monkeypatch):
    test_client, _ = client

    class FakeManager:
        def __init__(self):
            self.connections = {}

        def load_config(self):
            return [object()]

        def start_all(self, configs):
            self.connections = {}

        def status(self):
            return {
                "connected": [],
                "degraded": ["bad-server"],
                "degraded_details": {"bad-server": "initialize request failed"},
                "tool_count": 0,
            }

        def stop_all(self):
            return None

    monkeypatch.setattr(mcp_client, "MCPClientManager", FakeManager)

    response = test_client.get("/mcp-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] == 1
    assert payload["degraded"] == ["bad-server"]
    assert payload["degraded_details"]["bad-server"] == "initialize request failed"
    assert payload["tools"] == []


def test_lsp_status_endpoint_exposes_degraded_details(client, monkeypatch):
    test_client, _ = client

    class FakeLSPManager:
        def load_config(self):
            return []

        def status(self):
            return {
                "configured": ["pyright"],
                "active": {},
                "degraded": ["pyright"],
                "degraded_details": {"pyright": "initialize request failed"},
                "supported_languages": ["python"],
            }

    monkeypatch.setattr(lsp_client, "LSPManager", FakeLSPManager)

    response = test_client.get("/lsp-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] == ["pyright"]
    assert payload["degraded"] == ["pyright"]
    assert payload["degraded_details"]["pyright"] == "initialize request failed"
    assert payload["supported_languages"] == ["python"]


def test_ask_endpoint_runs_and_persists_run(client):
    test_client, orch = client
    response = test_client.post("/ask", json={"goal": "Say hello from the API", "backend": "mock"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "done"
    assert "Mock backend response" in payload["output"]

    run = orch.db.get_run(payload["run_id"])
    assert run is not None
    assert run.goal == "Say hello from the API"
    assert run.status == "done"


def test_ask_endpoint_unknown_backend_returns_400(client):
    test_client, _ = client
    response = test_client.post("/ask", json={"goal": "fail", "backend": "missing-backend"})
    assert response.status_code == 400
    assert "unknown backend" in response.json()["detail"]


def test_ask_endpoint_model_alias_persists_backend_model(client, monkeypatch):
    test_client, orch = client
    monkeypatch.setattr(api, "resolve_alias", lambda alias, backends: ("mock", "special-model"))

    response = test_client.post("/ask", json={"goal": "Say hello", "model_alias": "smart"})

    assert response.status_code == 200
    run = orch.db.get_run(response.json()["run_id"])
    assert run is not None
    assert run.metadata["backend_model"] == "special-model"


def test_ask_stream_endpoint_emits_token_and_done_events(client):
    test_client, _ = client
    with test_client.stream("POST", "/ask/stream", json={"goal": "Stream this", "backend": "mock"}) as response:
        assert response.status_code == 200
        lines = [line for line in response.iter_lines() if line]

    events = [json.loads(line.removeprefix("data: ")) for line in lines]
    assert any("token" in event and "Mock backend response" in event["token"] for event in events)
    assert any(event.get("done") is True and event.get("status") == "done" for event in events)


def test_facts_and_corrections_endpoints_round_trip(client):
    test_client, _ = client

    fact_response = test_client.post(
        "/facts",
        json={"fact_key": "capital", "fact_value": "Paris", "source": "api-test"},
    )
    assert fact_response.status_code == 200
    assert fact_response.json()["id"]

    correction_response = test_client.post(
        "/corrections",
        json={
            "context": "Paris is in Germany",
            "wrong_answer": "Germany",
            "right_answer": "France",
            "domain": "geography",
        },
    )
    assert correction_response.status_code == 200
    assert correction_response.json()["id"]

    facts = test_client.get("/facts").json()
    corrections = test_client.get("/corrections", params={"domain": "geography"}).json()

    assert any(item["fact_key"] == "capital" and item["fact_value"] == "Paris" for item in facts)
    assert any(
        item["context"] == "Paris is in Germany" and item["right_answer"] == "France"
        for item in corrections
    )


def test_tools_run_endpoint_uses_live_orchestro_tool_registry(client, tmp_path):
    test_client, orch = client

    response = test_client.post(
        "/tools/run",
        json={
            "tool_name": "propose_fact",
            "argument": "capital Regina --source api-test",
            "cwd": str(tmp_path),
            "approve": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "Fact proposed" in payload["output"]
    facts = orch.db.list_facts(limit=10)
    assert any(fact.fact_key == "capital" and fact.fact_value == "Regina" for fact in facts)
