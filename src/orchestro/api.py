from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from orchestro.cli import _index_embedding_jobs, create_app
from orchestro.embeddings import build_embedding_provider
from orchestro.models import RunRequest


class AskPayload(BaseModel):
    goal: str = Field(min_length=1)
    backend: str = "mock"
    strategy: str = "direct"
    cwd: str | None = None
    domain: str | None = None


class FactPayload(BaseModel):
    fact_key: str = Field(min_length=1)
    fact_value: str = Field(min_length=1)
    source: str | None = None


class CorrectionPayload(BaseModel):
    context: str = Field(min_length=1)
    wrong_answer: str = Field(min_length=1)
    right_answer: str = Field(min_length=1)
    domain: str | None = None
    severity: str = "normal"
    source_run_id: str | None = None


class EmbeddingIndexPayload(BaseModel):
    provider: str = "hash"
    limit: int = 20
    source_type: str | None = None
    model_name: str | None = None


class QueueEmbeddingsPayload(BaseModel):
    model_name: str = Field(min_length=1)
    source_type: str | None = None


class SemanticSearchPayload(BaseModel):
    query: str = Field(min_length=1)
    kind: str = "all"
    limit: int = 10
    provider: str = "hash"


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


@app.get("/shell-jobs")
def list_shell_jobs(limit: int = 20) -> list[dict[str, object]]:
    jobs = orchestro.db.list_shell_jobs(limit=limit)
    return [
        {
            "id": job.id,
            "run_id": job.run_id,
            "goal": job.goal,
            "backend_name": job.backend_name,
            "strategy_name": job.strategy_name,
            "domain": job.domain,
            "status": job.status,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "error_message": job.error_message,
            "cancel_requested_at": job.cancel_requested_at,
            "cancel_reason": job.cancel_reason,
            "control_state": job.control_state,
            "control_reason": job.control_reason,
        }
        for job in jobs
    ]


@app.get("/shell-jobs/{job_id}")
def get_shell_job(job_id: str) -> dict[str, object]:
    job = orchestro.db.get_shell_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="shell job not found")
    return {
        "job": {
            "id": job.id,
            "run_id": job.run_id,
            "goal": job.goal,
            "backend_name": job.backend_name,
            "strategy_name": job.strategy_name,
            "domain": job.domain,
            "status": job.status,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "error_message": job.error_message,
            "cancel_requested_at": job.cancel_requested_at,
            "cancel_reason": job.cancel_reason,
            "control_state": job.control_state,
            "control_reason": job.control_reason,
        },
        "events": [
            {
                "id": event.id,
                "job_id": event.job_id,
                "event_type": event.event_type,
                "sequence_no": event.sequence_no,
                "created_at": event.created_at,
                "payload": event.payload,
            }
            for event in orchestro.db.list_shell_job_events(job_id)
        ],
    }


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


@app.get("/interactions")
def list_interactions(limit: int = 20, query: str | None = None) -> list[dict[str, object]]:
    interactions = orchestro.db.list_interactions(limit=limit, query=query)
    return [
        {
            "id": interaction.id,
            "run_id": interaction.run_id,
            "query_text": interaction.query_text,
            "response_text": interaction.response_text,
            "backend_name": interaction.backend_name,
            "strategy_name": interaction.strategy_name,
            "domain": interaction.domain,
            "created_at": interaction.created_at,
            "rating": interaction.rating,
        }
        for interaction in interactions
    ]


@app.get("/search")
def search(query: str, kind: str = "all", limit: int = 10) -> list[dict[str, object]]:
    hits = orchestro.db.search(query=query, kind=kind, limit=limit)
    return [
        {
            "source_type": hit.source_type,
            "source_id": hit.source_id,
            "title": hit.title,
            "snippet": hit.snippet,
            "domain": hit.domain,
            "score": hit.score,
        }
        for hit in hits
    ]


@app.get("/vector-status")
def vector_status() -> dict[str, object]:
    return orchestro.db.vector_status()


@app.get("/index-jobs")
def list_index_jobs(
    limit: int = 50,
    source_type: str | None = None,
    status: str | None = None,
) -> list[dict[str, object]]:
    jobs = orchestro.db.list_embedding_jobs(limit=limit, source_type=source_type, status=status)
    return [
        {
            "id": job.id,
            "source_type": job.source_type,
            "source_id": job.source_id,
            "model_name": job.model_name,
            "content_hash": job.content_hash,
            "status": job.status,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "indexed_at": job.indexed_at,
            "error_message": job.error_message,
        }
        for job in jobs
    ]


@app.post("/index-jobs/run")
def run_index_jobs(payload: EmbeddingIndexPayload) -> dict[str, int]:
    try:
        indexed = _index_embedding_jobs(
            orchestro.db,
            provider=payload.provider,
            limit=payload.limit,
            source_type=payload.source_type,
            model_name=payload.model_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"indexed": indexed}


@app.post("/index-jobs/queue")
def queue_index_jobs(payload: QueueEmbeddingsPayload) -> dict[str, int]:
    queued = orchestro.db.queue_embedding_jobs_for_model(
        model_name=payload.model_name,
        source_type=payload.source_type,
    )
    return {"queued": queued}


@app.post("/semantic-search")
def semantic_search(payload: SemanticSearchPayload) -> list[dict[str, object]]:
    try:
        embedder = build_embedding_provider(payload.provider)
        query_result = embedder.embed(payload.query)
        hits = orchestro.db.semantic_search(
            query_embedding=query_result.embedding_blob,
            model_name=query_result.model_name,
            kind=payload.kind,
            limit=payload.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [
        {
            "source_type": hit.source_type,
            "source_id": hit.source_id,
            "title": hit.title,
            "snippet": hit.snippet,
            "domain": hit.domain,
            "score": hit.score,
        }
        for hit in hits
    ]


@app.get("/facts")
def list_facts(limit: int = 50, key: str | None = None) -> list[dict[str, object]]:
    facts = orchestro.db.list_facts(limit=limit, key=key)
    return [
        {
            "id": fact.id,
            "fact_key": fact.fact_key,
            "fact_value": fact.fact_value,
            "source": fact.source,
            "status": fact.status,
            "created_at": fact.created_at,
            "updated_at": fact.updated_at,
        }
        for fact in facts
    ]


@app.post("/facts")
def add_fact(payload: FactPayload) -> dict[str, str]:
    fact_id = str(uuid4())
    orchestro.db.add_fact(
        fact_id=fact_id,
        fact_key=payload.fact_key,
        fact_value=payload.fact_value,
        source=payload.source,
    )
    return {"id": fact_id}


@app.get("/corrections")
def list_corrections(
    limit: int = 50,
    domain: str | None = None,
    query: str | None = None,
) -> list[dict[str, object]]:
    corrections = orchestro.db.list_corrections(limit=limit, domain=domain, query=query)
    return [
        {
            "id": correction.id,
            "source_run_id": correction.source_run_id,
            "domain": correction.domain,
            "severity": correction.severity,
            "context": correction.context,
            "wrong_answer": correction.wrong_answer,
            "right_answer": correction.right_answer,
            "created_at": correction.created_at,
        }
        for correction in corrections
    ]


@app.post("/corrections")
def add_correction(payload: CorrectionPayload) -> dict[str, str]:
    correction_id = str(uuid4())
    orchestro.db.add_correction(
        correction_id=correction_id,
        context=payload.context,
        wrong_answer=payload.wrong_answer,
        right_answer=payload.right_answer,
        domain=payload.domain,
        severity=payload.severity,
        source_run_id=payload.source_run_id,
    )
    return {"id": correction_id}


@app.post("/ask")
def ask(payload: AskPayload) -> dict[str, object]:
    try:
        run_id = orchestro.run(
            RunRequest(
                goal=payload.goal,
                backend_name=payload.backend,
                strategy_name=payload.strategy,
                working_directory=Path(payload.cwd or Path.cwd()),
                metadata={"domain": payload.domain} if payload.domain else {},
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
