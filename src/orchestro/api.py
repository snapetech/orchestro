from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from orchestro.cli import _index_embedding_jobs, create_app
from orchestro.bench import compare_benchmark_summaries, default_benchmark_suite_path, run_benchmark_suite
from orchestro.constitutions import load_constitution_bundle
from orchestro.embeddings import build_embedding_provider
from orchestro.instructions import load_instruction_bundle
from orchestro.models import RunRequest
from orchestro.planner import build_plan_draft
from orchestro.tools import ToolRegistry, tool_result_payload


class AskPayload(BaseModel):
    goal: str = Field(min_length=1)
    backend: str = "mock"
    strategy: str = "direct"
    cwd: str | None = None
    domain: str | None = None
    providers: list[str] | None = None


class PlanPayload(BaseModel):
    goal: str = Field(min_length=1)
    backend: str = "mock"
    strategy: str = "direct"
    cwd: str | None = None
    domain: str | None = None


class ReplanPayload(BaseModel):
    note: str | None = None


class PlanStepPayload(BaseModel):
    sequence_no: int | None = None
    after_sequence_no: int | None = None
    title: str = Field(min_length=1)
    details: str | None = None


class BenchPayload(BaseModel):
    suite: str = str(default_benchmark_suite_path())
    backend: str = "mock"
    strategy: str = "direct"
    cwd: str | None = None
    providers: list[str] | None = None


class ToolRunPayload(BaseModel):
    tool_name: str = Field(min_length=1)
    argument: str = ""
    cwd: str | None = None
    approve: bool = False


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
tool_registry = ToolRegistry()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/backends")
def backends() -> dict[str, dict[str, object]]:
    return orchestro.available_backends()


@app.get("/instructions")
def get_instructions(cwd: str | None = None) -> dict[str, object]:
    working_directory = Path(cwd).resolve() if cwd else Path.cwd()
    bundle = load_instruction_bundle(working_directory)
    return {
        "cwd": str(working_directory),
        "text": bundle.text,
        "sources": bundle.metadata()["sources"],
    }


@app.get("/constitutions")
def get_constitution(domain: str, cwd: str | None = None) -> dict[str, object]:
    working_directory = Path(cwd).resolve() if cwd else Path.cwd()
    bundle = load_constitution_bundle(domain, working_directory)
    return {
        "cwd": str(working_directory),
        "domain": domain,
        "text": bundle.text,
        "sources": bundle.metadata()["sources"],
    }


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


@app.get("/plans")
def list_plans(limit: int = 20) -> list[dict[str, object]]:
    plans = orchestro.db.list_plans(limit=limit)
    return [
        {
            "id": plan.id,
            "goal": plan.goal,
            "backend_name": plan.backend_name,
            "strategy_name": plan.strategy_name,
            "working_directory": plan.working_directory,
            "domain": plan.domain,
            "status": plan.status,
            "current_step_no": plan.current_step_no,
            "created_at": plan.created_at,
            "updated_at": plan.updated_at,
        }
        for plan in plans
    ]


@app.get("/plans/{plan_id}")
def get_plan(plan_id: str) -> dict[str, object]:
    plan = orchestro.db.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="plan not found")
    return {
        "plan": {
            "id": plan.id,
            "goal": plan.goal,
            "backend_name": plan.backend_name,
            "strategy_name": plan.strategy_name,
            "working_directory": plan.working_directory,
            "domain": plan.domain,
            "status": plan.status,
            "current_step_no": plan.current_step_no,
            "created_at": plan.created_at,
            "updated_at": plan.updated_at,
        },
        "steps": [
            {
                "id": step.id,
                "sequence_no": step.sequence_no,
                "title": step.title,
                "details": step.details,
                "status": step.status,
            }
            for step in orchestro.db.list_plan_steps(plan_id)
        ],
        "events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "sequence_no": event.sequence_no,
                "created_at": event.created_at,
                "payload": event.payload,
            }
            for event in orchestro.db.list_plan_events(plan_id)
        ],
    }


@app.post("/plans/{plan_id}/replan")
def replan(plan_id: str, payload: ReplanPayload) -> dict[str, object]:
    plan = orchestro.db.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="plan not found")
    current_step = orchestro.db.get_current_plan_step(plan_id)
    start_sequence_no = current_step.sequence_no if current_step is not None else plan.current_step_no
    draft = build_plan_draft(
        orchestro,
        goal=plan.goal if not payload.note else f"{plan.goal}\n\nReplan note: {payload.note}",
        backend_name=plan.backend_name,
        strategy_name=plan.strategy_name,
        working_directory=Path(plan.working_directory),
        domain=plan.domain,
    )
    orchestro.db.replace_plan_steps_from(
        plan_id=plan_id,
        start_sequence_no=start_sequence_no,
        steps=draft.steps,
    )
    orchestro.db.append_plan_event(
        plan_id=plan_id,
        event_id=str(uuid4()),
        event_type="plan_replanned",
        payload={"start_sequence_no": start_sequence_no, "note": payload.note},
    )
    orchestro.db.append_plan_event(
        plan_id=plan_id,
        event_id=str(uuid4()),
        event_type="think",
        payload={"source": draft.source, "notes": draft.notes},
    )
    return get_plan(plan_id)


@app.post("/plans")
def create_plan(payload: PlanPayload) -> dict[str, str]:
    plan_id = str(uuid4())
    working_directory = Path(payload.cwd).resolve() if payload.cwd else Path.cwd()
    draft = build_plan_draft(
        orchestro,
        goal=payload.goal,
        backend_name=payload.backend,
        strategy_name=payload.strategy,
        working_directory=working_directory,
        domain=payload.domain,
    )
    orchestro.db.create_plan(
        plan_id=plan_id,
        goal=payload.goal,
        backend_name=payload.backend,
        strategy_name=payload.strategy,
        working_directory=str(working_directory),
        domain=payload.domain,
        steps=draft.steps,
    )
    orchestro.db.append_plan_event(
        plan_id=plan_id,
        event_id=str(uuid4()),
        event_type="plan_created",
        payload={
            "goal": payload.goal,
            "backend": payload.backend,
            "strategy": payload.strategy,
            "domain": payload.domain,
        },
    )
    orchestro.db.append_plan_event(
        plan_id=plan_id,
        event_id=str(uuid4()),
        event_type="think",
        payload={"source": draft.source, "notes": draft.notes},
    )
    return {"id": plan_id}


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


@app.get("/benchmark-runs")
def list_benchmark_runs(limit: int = 20) -> list[dict[str, object]]:
    runs = orchestro.db.list_benchmark_runs(limit=limit)
    return [
        {
            "id": record.id,
            "suite_name": record.suite_name,
            "backend_name": record.backend_name,
            "strategy_name": record.strategy_name,
            "created_at": record.created_at,
            "summary": record.summary,
        }
        for record in runs
    ]


@app.get("/benchmark-runs/compare")
def compare_benchmark_runs(left_id: str, right_id: str) -> dict[str, object]:
    left = orchestro.db.get_benchmark_run(left_id)
    right = orchestro.db.get_benchmark_run(right_id)
    if left is None or right is None:
        raise HTTPException(status_code=404, detail="benchmark run not found")
    return compare_benchmark_summaries(left.summary, right.summary)


@app.get("/benchmark-runs/{benchmark_run_id}/baseline")
def compare_benchmark_run_to_baseline(benchmark_run_id: str) -> dict[str, object]:
    current = orchestro.db.get_benchmark_run(benchmark_run_id)
    if current is None:
        raise HTTPException(status_code=404, detail="benchmark run not found")
    baseline = orchestro.db.find_previous_benchmark_run(
        suite_name=current.suite_name,
        backend_name=current.backend_name,
        strategy_name=current.strategy_name,
        created_before=current.created_at,
    )
    if baseline is None:
        raise HTTPException(status_code=404, detail="no previous comparable benchmark run found")
    return compare_benchmark_summaries(baseline.summary, current.summary)


@app.get("/benchmark-runs/{benchmark_run_id}")
def get_benchmark_run(benchmark_run_id: str) -> dict[str, object]:
    record = orchestro.db.get_benchmark_run(benchmark_run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="benchmark run not found")
    return {
        "id": record.id,
        "suite_name": record.suite_name,
        "backend_name": record.backend_name,
        "strategy_name": record.strategy_name,
        "created_at": record.created_at,
        "summary": record.summary,
    }


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
        "children": [
            {
                "id": child.id,
                "goal": child.goal,
                "status": child.status,
                "backend_name": child.backend_name,
                "strategy_name": child.strategy_name,
                "created_at": child.created_at,
                "updated_at": child.updated_at,
                "completed_at": child.completed_at,
            }
            for child in orchestro.db.list_child_runs(run_id, limit=50)
        ],
    }


@app.post("/plans/{plan_id}/steps")
def add_plan_step(plan_id: str, payload: PlanStepPayload) -> dict[str, object]:
    plan = orchestro.db.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="plan not found")
    after_sequence_no = payload.after_sequence_no
    if after_sequence_no is None:
        after_sequence_no = max((step.sequence_no for step in orchestro.db.list_plan_steps(plan_id)), default=0)
    sequence_no = orchestro.db.insert_plan_step(
        plan_id=plan_id,
        after_sequence_no=after_sequence_no,
        title=payload.title,
        details=payload.details,
    )
    orchestro.db.append_plan_event(
        plan_id=plan_id,
        event_id=str(uuid4()),
        event_type="step_added",
        payload={"sequence_no": sequence_no, "title": payload.title},
    )
    return get_plan(plan_id)


@app.put("/plans/{plan_id}/steps/{sequence_no}")
def update_plan_step(plan_id: str, sequence_no: int, payload: PlanStepPayload) -> dict[str, object]:
    plan = orchestro.db.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="plan not found")
    updated = orchestro.db.update_plan_step(
        plan_id=plan_id,
        sequence_no=sequence_no,
        title=payload.title,
        details=payload.details,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="plan step not found")
    orchestro.db.append_plan_event(
        plan_id=plan_id,
        event_id=str(uuid4()),
        event_type="step_edited",
        payload={"sequence_no": sequence_no, "title": payload.title},
    )
    return get_plan(plan_id)


@app.delete("/plans/{plan_id}/steps/{sequence_no}")
def delete_plan_step(plan_id: str, sequence_no: int) -> dict[str, object]:
    plan = orchestro.db.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="plan not found")
    deleted = orchestro.db.delete_plan_step(plan_id=plan_id, sequence_no=sequence_no)
    if not deleted:
        raise HTTPException(status_code=404, detail="plan step not found")
    orchestro.db.append_plan_event(
        plan_id=plan_id,
        event_id=str(uuid4()),
        event_type="step_deleted",
        payload={"sequence_no": sequence_no},
    )
    return get_plan(plan_id)


@app.post("/bench/run")
def run_bench(payload: BenchPayload) -> dict[str, object]:
    working_directory = Path(payload.cwd).resolve() if payload.cwd else Path.cwd()
    return run_benchmark_suite(
        orchestro,
        suite_path=Path(payload.suite),
        backend_name=payload.backend,
        strategy_name=payload.strategy,
        working_directory=working_directory,
        context_providers=payload.providers,
    )


@app.get("/tools")
def list_tools() -> list[dict[str, str]]:
    return tool_registry.list_tools()


@app.post("/tools/run")
def run_tool(payload: ToolRunPayload) -> dict[str, object]:
    cwd = Path(payload.cwd).resolve() if payload.cwd else Path.cwd()
    try:
        result = tool_registry.run(payload.tool_name, payload.argument, cwd, approved=payload.approve)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return tool_result_payload(result)


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


@app.get("/postmortems")
def list_postmortems(
    limit: int = 50,
    domain: str | None = None,
    query: str | None = None,
) -> list[dict[str, object]]:
    postmortems = orchestro.db.list_postmortems(limit=limit, domain=domain, query=query)
    return [
        {
            "id": postmortem.id,
            "run_id": postmortem.run_id,
            "domain": postmortem.domain,
            "category": postmortem.category,
            "summary": postmortem.summary,
            "error_message": postmortem.error_message,
            "created_at": postmortem.created_at,
        }
        for postmortem in postmortems
    ]


@app.post("/ask")
def ask(payload: AskPayload) -> dict[str, object]:
    try:
        prepared = orchestro.start_run(
            RunRequest(
                goal=payload.goal,
                backend_name=payload.backend,
                strategy_name=payload.strategy,
                working_directory=Path(payload.cwd or Path.cwd()),
                metadata={
                    **({"domain": payload.domain} if payload.domain else {}),
                    "context_providers": payload.providers
                    or ["instructions", "lexical", "semantic", "corrections", "interactions", "postmortems"],
                },
            )
        )
        orchestro.execute_prepared_run(prepared)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        run_id = prepared.run_id if "prepared" in locals() else None
        raise HTTPException(
            status_code=502,
            detail={"message": str(exc), "run_id": run_id},
        ) from exc
    run = orchestro.db.get_run(prepared.run_id)
    assert run is not None
    return {
        "run_id": prepared.run_id,
        "status": run.status,
        "output": run.final_output,
    }
