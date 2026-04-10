from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from typing import Callable
import time
from uuid import uuid4

from orchestro.backends import Backend, MockBackend, OpenAICompatBackend, SubprocessCommandBackend
from orchestro.db import OrchestroDB
from orchestro.instructions import load_instruction_bundle
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
            "subprocess-command": SubprocessCommandBackend(),
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
        instruction_bundle = load_instruction_bundle(cwd)
        if instruction_bundle.text:
            system_parts = [
                part
                for part in [
                    request.system_prompt,
                    "Use the following stable Orchestro instruction context when it is relevant.",
                    instruction_bundle.text,
                ]
                if part
            ]
            effective_request = replace(request, system_prompt="\n\n".join(system_parts))
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
        if instruction_bundle.sources:
            self.db.append_event(
                run_id=run_id,
                event_id=str(uuid4()),
                event_type="instruction_context_loaded",
                payload=instruction_bundle.metadata(),
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

    def execute_prepared_run(
        self,
        prepared: PreparedRun,
        *,
        cancel_requested: Callable[[], bool] | None = None,
        control_state: Callable[[], str | None] | None = None,
    ) -> str:
        try:
            process = prepared.backend.start(prepared.request)
            if process is not None:
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="backend_process_started",
                    payload={"backend": prepared.backend.name},
                )
                is_paused = False
                while process.poll() is None:
                    if cancel_requested and cancel_requested():
                        process.terminate()
                        self.db.append_event(
                            run_id=prepared.run_id,
                            event_id=str(uuid4()),
                            event_type="backend_process_terminated",
                            payload={"reason": "cancel requested"},
                        )
                        self.db.append_event(
                            run_id=prepared.run_id,
                            event_id=str(uuid4()),
                            event_type="run_canceled",
                            payload={"reason": "cancel requested during backend execution"},
                        )
                        self.db.cancel_run(
                            run_id=prepared.run_id,
                            error_message="run canceled during backend execution",
                        )
                        return prepared.run_id
                    desired_state = control_state() if control_state else None
                    if desired_state == "paused" and not is_paused:
                        process.pause()
                        is_paused = True
                        self.db.append_event(
                            run_id=prepared.run_id,
                            event_id=str(uuid4()),
                            event_type="backend_process_paused",
                            payload={"reason": "pause requested"},
                        )
                    elif desired_state == "running" and is_paused:
                        process.resume()
                        is_paused = False
                        self.db.append_event(
                            run_id=prepared.run_id,
                            event_id=str(uuid4()),
                            event_type="backend_process_resumed",
                            payload={"reason": "resume requested"},
                        )
                    time.sleep(0.1)
                result = process.wait()
                response = prepared.backend.response_from_process(prepared.request, result)
            else:
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
