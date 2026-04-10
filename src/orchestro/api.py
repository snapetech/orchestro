from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from orchestro.cli import create_app
from orchestro.models import RunRequest


class AskPayload(BaseModel):
    goal: str = Field(min_length=1)
    backend: str = "mock"
    strategy: str = "direct"
    cwd: str | None = None


app = FastAPI(title="Orchestro", version="0.1.0")
orchestro = create_app()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/backends")
def backends() -> dict[str, dict[str, object]]:
    return orchestro.available_backends()


@app.get("/runs")
def list_runs(limit: int = 20) -> list[dict[str, object]]:
    runs = orchestro.db.list_runs(limit=limit)
    return [
        {
            "id": run.id,
            "goal": run.goal,
            "status": run.status,
            "backend_name": run.backend_name,
            "strategy_name": run.strategy_name,
            "working_directory": run.working_directory,
            "created_at": run.created_at,
            "updated_at": run.updated_at,
            "completed_at": run.completed_at,
            "error_message": run.error_message,
        }
        for run in runs
    ]


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, object]:
    run = orchestro.db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {
        "run": {
            "id": run.id,
            "goal": run.goal,
            "status": run.status,
            "backend_name": run.backend_name,
            "strategy_name": run.strategy_name,
            "working_directory": run.working_directory,
            "created_at": run.created_at,
            "updated_at": run.updated_at,
            "completed_at": run.completed_at,
            "error_message": run.error_message,
            "final_output": run.final_output,
            "metadata": run.metadata,
        },
        "events": orchestro.db.list_events(run_id),
    }


@app.post("/ask")
def ask(payload: AskPayload) -> dict[str, object]:
    try:
        run_id = orchestro.run(
            RunRequest(
                goal=payload.goal,
                backend_name=payload.backend,
                strategy_name=payload.strategy,
                working_directory=Path(payload.cwd or Path.cwd()),
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    run = orchestro.db.get_run(run_id)
    assert run is not None
    return {
        "run_id": run_id,
        "status": run.status,
        "output": run.final_output,
    }
