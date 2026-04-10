from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from dataclasses import dataclass
from uuid import uuid4

from orchestro.backends import Backend, MockBackend, OpenAICompatBackend
from orchestro.db import OrchestroDB
from orchestro.models import RatingRequest, RunRequest
from orchestro.retrieval import RetrievalBuilder


@dataclass(slots=True)
class PreparedRun:
    run_id: str
    backend: Backend
    request: RunRequest
    retrieval_bundle: object | None


class Orchestro:
    def __init__(self, db: OrchestroDB, backends: dict[str, Backend] | None = None) -> None:
        self.db = db
        self.backends = backends or {
            "mock": MockBackend(),
            "openai-compat": OpenAICompatBackend(),
        }
        self.retrieval = RetrievalBuilder(db)

    def available_backends(self) -> dict[str, dict[str, object]]:
        return {name: backend.capabilities() for name, backend in self.backends.items()}

    def run(self, request: RunRequest) -> str:
        if request.backend_name not in self.backends:
            known = ", ".join(sorted(self.backends))
            raise ValueError(f"unknown backend '{request.backend_name}'. known backends: {known}")

        prepared = self.start_run(request)
        self.execute_prepared_run(prepared)
        return prepared.run_id

    def start_run(self, request: RunRequest) -> PreparedRun:
        run_id = str(uuid4())
        cwd = Path(request.working_directory).resolve()
        backend = self.backends[request.backend_name]
        retrieval_enabled = request.metadata.get("retrieval_enabled", True)
        domain = request.metadata.get("domain")
        effective_request = request
        retrieval_bundle = None
        if retrieval_enabled:
            retrieval_bundle = self.retrieval.build(request.goal, domain=domain)
            if retrieval_bundle.context_text:
                effective_request = replace(request, prompt_context=retrieval_bundle.context_text)

        self.db.create_run(
            run_id=run_id,
            parent_run_id=request.parent_run_id,
            goal=request.goal,
            backend_name=request.backend_name,
            strategy_name=request.strategy_name,
            working_directory=str(cwd),
            metadata=request.metadata,
        )
        self.db.append_event(
            run_id=run_id,
            event_id=str(uuid4()),
            event_type="run_started",
            payload={
                "goal": request.goal,
                "backend": request.backend_name,
                "strategy": request.strategy_name,
                "working_directory": str(cwd),
            },
        )
        if retrieval_bundle is not None:
            self.db.append_event(
                run_id=run_id,
                event_id=str(uuid4()),
                event_type="retrieval_built",
                payload=retrieval_bundle.metadata(),
            )
        return PreparedRun(
            run_id=run_id,
            backend=backend,
            request=effective_request,
            retrieval_bundle=retrieval_bundle,
        )

    def execute_prepared_run(self, prepared: PreparedRun) -> str:
        try:
            response = prepared.backend.run(prepared.request)
            self.db.append_event(
                run_id=prepared.run_id,
                event_id=str(uuid4()),
                event_type="backend_completed",
                payload=response.metadata,
            )
            self.db.complete_run(run_id=prepared.run_id, final_output=response.output_text)
            self.db.append_event(
                run_id=prepared.run_id,
                event_id=str(uuid4()),
                event_type="run_completed",
                payload={"output_length": len(response.output_text)},
            )
        except Exception as exc:
            self.db.append_event(
                run_id=prepared.run_id,
                event_id=str(uuid4()),
                event_type="run_failed",
                payload={"error": str(exc)},
            )
            self.db.fail_run(run_id=prepared.run_id, error_message=str(exc))
            raise
        return prepared.run_id

    def rate(self, request: RatingRequest) -> str:
        rating_id = str(uuid4())
        self.db.add_rating(
            rating_id=rating_id,
            target_type=request.target_type,
            target_id=request.target_id,
            rating=request.rating,
            note=request.note,
        )
        return rating_id
