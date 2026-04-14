from __future__ import annotations

import pytest

from orchestro import cli
from orchestro.backends.mock import MockBackend
from orchestro.models import RunRequest
from orchestro.orchestrator import Orchestro


def _make_app(tmp_db):
    return Orchestro(db=tmp_db, backends={"mock": MockBackend()})


@pytest.mark.acceptance
def test_cli_acceptance_run_annotations_and_listing(tmp_db, tmp_path, monkeypatch, capsys):
    app = _make_app(tmp_db)
    monkeypatch.setattr(cli, "create_app", lambda: app)

    assert cli.main(["ask", "Acceptance CLI run", "--backend", "mock", "--cwd", str(tmp_path)]) == 0
    run = app.db.list_runs(limit=1)[0]

    assert cli.main(["run-summary", run.id, "CLI acceptance summary"]) == 0
    assert cli.main(["run-note", run.id, "Checked from CLI acceptance"]) == 0
    assert cli.main(["runs", "--backend", "mock", "--status", "done"]) == 0

    refreshed = app.db.get_run(run.id)
    assert refreshed is not None
    assert refreshed.summary == "CLI acceptance summary"
    assert refreshed.operator_note == "Checked from CLI acceptance"

    captured = capsys.readouterr()
    assert run.id in captured.out
    assert "CLI acceptance summary" in captured.out
    assert "Checked from CLI acceptance" in captured.out


@pytest.mark.acceptance
def test_cli_acceptance_session_and_plan_workflow(tmp_db, tmp_path, monkeypatch, capsys):
    app = _make_app(tmp_db)
    monkeypatch.setattr(cli, "create_app", lambda: app)

    assert cli.main(["session-new", "Acceptance Session"]) == 0
    session = app.db.list_sessions(limit=1)[0]

    app.run(
        RunRequest(
            goal="Seed CLI session history",
            backend_name="mock",
            working_directory=tmp_path,
            metadata={"session_id": session.id},
        )
    )

    assert cli.main(["session-compact", session.id, "--limit", "10"]) == 0
    assert cli.main(["plan-create", "Acceptance CLI plan", "--backend", "mock", "--cwd", str(tmp_path)]) == 0
    plan = app.db.list_plans(limit=1)[0]

    assert cli.main(
        [
            "plan-step-add",
            plan.id,
            str(plan.current_step_no),
            "Inserted acceptance step",
            "Run the CLI acceptance workflow.",
        ]
    ) == 0
    assert cli.main(["plan-run", plan.id]) == 0
    assert cli.main(["plan-show", plan.id]) == 0

    updated_plan = app.db.get_plan(plan.id)
    assert updated_plan is not None
    assert updated_plan.status in {"in_progress", "done"}

    captured = capsys.readouterr()
    assert "Compacted 1 run(s)" in captured.out
    assert "Inserted acceptance step" in captured.out
    assert "Mock backend response" in captured.out

