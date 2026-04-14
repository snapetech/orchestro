from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from orchestro import api
from orchestro.backends.mock import MockBackend
from orchestro.models import RunRequest
from orchestro.orchestrator import Orchestro


@pytest.fixture()
def acceptance_client(tmp_db):
    orch = Orchestro(db=tmp_db, backends={"mock": MockBackend()})
    original_orchestro = api.orchestro
    original_tool_registry = api.tool_registry
    original_worker = api._embedding_worker
    api.orchestro = orch
    api.tool_registry = orch.tools
    api._embedding_worker = None
    try:
        with TestClient(api.app) as test_client:
            yield test_client, orch
    finally:
        api.orchestro = original_orchestro
        api.tool_registry = original_tool_registry
        api._embedding_worker = original_worker


@pytest.mark.acceptance
def test_api_acceptance_run_and_tool_workflow(acceptance_client, tmp_path):
    test_client, _ = acceptance_client

    ask_response = test_client.post(
        "/ask",
        json={
            "goal": "Acceptance API run",
            "backend": "mock",
            "cwd": str(tmp_path),
        },
    )
    assert ask_response.status_code == 200
    run_id = ask_response.json()["run_id"]

    runs_response = test_client.get(
        "/runs",
        params={"backend_name": "mock", "status": "done"},
    )
    assert runs_response.status_code == 200
    runs = runs_response.json()
    assert any(item["id"] == run_id for item in runs)

    detail_response = test_client.get(f"/runs/{run_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["run"]["id"] == run_id
    assert detail["run"]["status"] == "done"
    assert "Mock backend response" in detail["run"]["final_output"]

    summary_response = test_client.put(
        f"/runs/{run_id}/summary",
        json={"text": "Acceptance summary"},
    )
    assert summary_response.status_code == 200
    note_response = test_client.put(
        f"/runs/{run_id}/note",
        json={"text": "Operator checked"},
    )
    assert note_response.status_code == 200

    updated_run = test_client.get(f"/runs/{run_id}").json()["run"]
    assert updated_run["summary"] == "Acceptance summary"
    assert updated_run["operator_note"] == "Operator checked"

    tool_response = test_client.post(
        "/tools/run",
        json={"tool_name": "pwd", "cwd": str(tmp_path)},
    )
    assert tool_response.status_code == 200
    payload = tool_response.json()
    assert payload["ok"] is True
    assert payload["output"] == str(tmp_path.resolve())


@pytest.mark.acceptance
def test_api_acceptance_session_and_plan_workflow(acceptance_client, tmp_path):
    test_client, orch = acceptance_client

    session_response = test_client.post("/sessions", json={"title": "Acceptance Session"})
    assert session_response.status_code == 200
    session_id = session_response.json()["session"]["id"]

    orch.run(
        RunRequest(
            goal="Seed session history",
            backend_name="mock",
            working_directory=tmp_path,
            metadata={"session_id": session_id},
        )
    )

    compact_response = test_client.post(f"/sessions/{session_id}/compact", params={"limit": 10})
    assert compact_response.status_code == 200
    compacted = compact_response.json()["session"]
    assert compacted["summary"] == "Compacted 1 run(s)"
    assert "Seed session history" in compacted["context_snapshot"]

    plan_response = test_client.post(
        "/plans",
        json={
            "goal": "Acceptance API plan",
            "backend": "mock",
            "cwd": str(tmp_path),
        },
    )
    assert plan_response.status_code == 200
    plan_id = plan_response.json()["id"]

    plan_detail = test_client.get(f"/plans/{plan_id}")
    assert plan_detail.status_code == 200
    initial_steps = plan_detail.json()["steps"]
    assert len(initial_steps) >= 1

    add_response = test_client.post(
        f"/plans/{plan_id}/steps",
        json={
            "after_sequence_no": initial_steps[-1]["sequence_no"],
            "title": "Acceptance inserted step",
            "details": "Verify API workflow edits are persisted.",
        },
    )
    assert add_response.status_code == 200
    inserted = next(
        step for step in add_response.json()["steps"] if step["title"] == "Acceptance inserted step"
    )

    edit_response = test_client.put(
        f"/plans/{plan_id}/steps/{inserted['sequence_no']}",
        json={
            "title": "Acceptance edited step",
            "details": "Edited via API acceptance workflow.",
        },
    )
    assert edit_response.status_code == 200
    assert any(
        step["sequence_no"] == inserted["sequence_no"] and step["title"] == "Acceptance edited step"
        for step in edit_response.json()["steps"]
    )

    delete_response = test_client.delete(f"/plans/{plan_id}/steps/{inserted['sequence_no']}")
    assert delete_response.status_code == 200
    assert all(step["sequence_no"] != inserted["sequence_no"] for step in delete_response.json()["steps"])

    replan_response = test_client.post(
        f"/plans/{plan_id}/replan",
        json={"note": "Acceptance workflow requested a refresh."},
    )
    assert replan_response.status_code == 200
    replan_events = [event["event_type"] for event in replan_response.json()["events"]]
    assert "plan_replanned" in replan_events

