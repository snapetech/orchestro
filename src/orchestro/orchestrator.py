from __future__ import annotations

import json
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from typing import Callable
import time
from uuid import uuid4

from orchestro.backends import Backend, MockBackend, OpenAICompatBackend, SubprocessCommandBackend
from orchestro.db import OrchestroDB
from orchestro.instructions import load_instruction_bundle
from orchestro.models import BackendResponse, RatingRequest, RunRequest
from orchestro.retrieval import RetrievalBuilder
from orchestro.tools import ToolRegistry, tool_result_payload


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
        self.tools = ToolRegistry()

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
        context_providers = request.metadata.get(
            "context_providers",
            ["instructions", "lexical", "semantic", "corrections", "interactions"],
        )
        provider_set = set(context_providers)
        retrieval_enabled = request.metadata.get("retrieval_enabled", True) and bool(
            {"lexical", "semantic", "corrections", "interactions"} & provider_set
        )
        domain = request.metadata.get("domain")
        effective_request = request
        retrieval_bundle = None
        instruction_bundle = load_instruction_bundle(cwd)
        if instruction_bundle.text and "instructions" in provider_set:
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
            retrieval_bundle = self.retrieval.build(request.goal, domain=domain, providers=context_providers)
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
        if instruction_bundle.sources and "instructions" in provider_set:
            self.db.append_event(
                run_id=run_id,
                event_id=str(uuid4()),
                event_type="instruction_context_loaded",
                payload=instruction_bundle.metadata(),
            )
        self.db.append_event(
            run_id=run_id,
            event_id=str(uuid4()),
            event_type="context_providers_selected",
            payload={"providers": context_providers},
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
        if prepared.request.strategy_name == "tool-loop":
            response = self._execute_tool_loop(
                prepared=prepared,
                cancel_requested=cancel_requested,
                control_state=control_state,
            )
            self.db.complete_run(run_id=prepared.run_id, final_output=response.output_text)
            self.db.append_event(
                run_id=prepared.run_id,
                event_id=str(uuid4()),
                event_type="run_completed",
                payload={"output_length": len(response.output_text), "strategy": "tool-loop"},
            )
            return prepared.run_id

        allow_reflect_retry = prepared.request.strategy_name in {"reflect-retry", "reflect-retry-once"}
        current_request = prepared.request
        max_attempts = 2 if allow_reflect_retry else 1
        for attempt_no in range(1, max_attempts + 1):
            self.db.append_event(
                run_id=prepared.run_id,
                event_id=str(uuid4()),
                event_type="attempt_started",
                payload={"attempt": attempt_no, "strategy": current_request.strategy_name},
            )
            try:
                response = self._execute_backend_once(
                    prepared=PreparedRun(
                        run_id=prepared.run_id,
                        backend=prepared.backend,
                        request=current_request,
                        retrieval_bundle=prepared.retrieval_bundle,
                    ),
                    cancel_requested=cancel_requested,
                    control_state=control_state,
                )
                if response is None:
                    return prepared.run_id
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="backend_completed",
                    payload={**response.metadata, "attempt": attempt_no},
                )
                self.db.complete_run(run_id=prepared.run_id, final_output=response.output_text)
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="run_completed",
                    payload={"output_length": len(response.output_text), "attempt": attempt_no},
                )
                return prepared.run_id
            except Exception as exc:
                is_last_attempt = attempt_no >= max_attempts
                if not is_last_attempt:
                    reflection = self._build_reflection(current_request=current_request, error_text=str(exc))
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="reflection",
                        payload={"attempt": attempt_no, **reflection},
                    )
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="retry_scheduled",
                        payload={"from_attempt": attempt_no, "to_attempt": attempt_no + 1},
                    )
                    current_request = replace(
                        current_request,
                        system_prompt="\n\n".join(
                            part
                            for part in [
                                current_request.system_prompt,
                                "Retry guidance from the last failed attempt:",
                                self._reflection_prompt_block(reflection),
                            ]
                            if part
                        ),
                    )
                    continue
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="run_failed",
                    payload={"error": str(exc), "attempt": attempt_no},
                )
                self.db.fail_run(run_id=prepared.run_id, error_message=str(exc))
                raise
        return prepared.run_id

    def _execute_tool_loop(
        self,
        *,
        prepared: PreparedRun,
        cancel_requested: Callable[[], bool] | None,
        control_state: Callable[[], str | None] | None,
    ) -> BackendResponse:
        del control_state
        max_steps = 6
        depth = int(prepared.request.metadata.get("delegation_depth", 0))
        tool_state: list[str] = []
        self.db.append_event(
            run_id=prepared.run_id,
            event_id=str(uuid4()),
            event_type="tool_loop_started",
            payload={"max_steps": max_steps, "tool_count": len(self.tools.list_tools())},
        )
        for step_no in range(1, max_steps + 1):
            if cancel_requested and cancel_requested():
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="run_canceled",
                    payload={"reason": "cancel requested before tool-loop step"},
                )
                self.db.cancel_run(
                    run_id=prepared.run_id,
                    error_message="run canceled before tool-loop step",
                )
                raise RuntimeError("run canceled before tool-loop step")
            self.db.append_event(
                run_id=prepared.run_id,
                event_id=str(uuid4()),
                event_type="tool_loop_step_started",
                payload={"step": step_no},
            )
            loop_request = replace(
                prepared.request,
                system_prompt="\n\n".join(
                    part
                    for part in [
                        prepared.request.system_prompt,
                        self._tool_loop_system_prompt(depth=depth),
                    ]
                    if part
                ),
                prompt_context="\n\n".join(
                    part
                    for part in [
                        prepared.request.prompt_context,
                        "\n\n".join(tool_state) if tool_state else None,
                    ]
                    if part
                ),
            )
            response = self._execute_backend_once(
                prepared=PreparedRun(
                    run_id=prepared.run_id,
                    backend=prepared.backend,
                    request=loop_request,
                    retrieval_bundle=prepared.retrieval_bundle,
                ),
                cancel_requested=cancel_requested,
                control_state=None,
            )
            if response is None:
                raise RuntimeError("run canceled during tool-loop execution")
            self.db.append_event(
                run_id=prepared.run_id,
                event_id=str(uuid4()),
                event_type="backend_completed",
                payload={**response.metadata, "step": step_no},
            )
            action = self._parse_tool_loop_action(response.output_text)
            self.db.append_event(
                run_id=prepared.run_id,
                event_id=str(uuid4()),
                event_type="think",
                payload={"mode": "tool-loop", "step": step_no, "action": action},
            )
            if action["action"] == "final":
                return BackendResponse(
                    output_text=str(action.get("content") or response.output_text),
                    metadata={**response.metadata, "strategy": "tool-loop", "steps": step_no},
                )
            if action["action"] == "tool":
                tool_name = str(action.get("tool") or "")
                argument = str(action.get("argument") or "")
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="tool_called",
                    payload={"step": step_no, "tool": tool_name, "argument": argument},
                )
                result = self.tools.run(tool_name, argument, Path(prepared.request.working_directory))
                result_payload = tool_result_payload(result)
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="tool_result",
                    payload={"step": step_no, "tool": tool_name, **result_payload},
                )
                tool_state.append(
                    "\n".join(
                        [
                            f"Tool step {step_no}",
                            f"tool: {tool_name}",
                            f"argument: {argument}",
                            f"ok: {result.ok}",
                            "output:",
                            result.output,
                        ]
                    )
                )
                continue
            if action["action"] == "delegate":
                if depth >= 2:
                    tool_state.append(
                        "Delegation request rejected because the maximum delegation depth was reached."
                    )
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="child_run_rejected",
                        payload={"reason": "max delegation depth reached", "step": step_no},
                    )
                    continue
                child_goal = str(action.get("goal") or "").strip()
                if not child_goal:
                    tool_state.append("Delegation request rejected because no child goal was provided.")
                    continue
                child_request = RunRequest(
                    goal=child_goal,
                    backend_name=str(action.get("backend") or prepared.request.backend_name),
                    strategy_name=str(action.get("strategy") or "direct"),
                    working_directory=prepared.request.working_directory,
                    parent_run_id=prepared.run_id,
                    metadata={
                        **prepared.request.metadata,
                        "delegation_depth": depth + 1,
                    },
                )
                child_prepared = self.start_run(child_request)
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="child_run_spawned",
                    payload={
                        "step": step_no,
                        "child_run_id": child_prepared.run_id,
                        "goal": child_goal,
                        "backend": child_request.backend_name,
                        "strategy": child_request.strategy_name,
                    },
                )
                self.execute_prepared_run(child_prepared)
                child_run = self.db.get_run(child_prepared.run_id)
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="child_run_completed",
                    payload={
                        "step": step_no,
                        "child_run_id": child_prepared.run_id,
                        "status": child_run.status if child_run else "unknown",
                    },
                )
                tool_state.append(
                    "\n".join(
                        [
                            f"Delegated step {step_no}",
                            f"child_run_id: {child_prepared.run_id}",
                            f"status: {child_run.status if child_run else 'unknown'}",
                            "output:",
                            child_run.final_output if child_run and child_run.final_output else "",
                        ]
                    )
                )
                continue
            return BackendResponse(
                output_text=response.output_text,
                metadata={**response.metadata, "strategy": "tool-loop", "steps": step_no},
            )
        self.db.append_event(
            run_id=prepared.run_id,
            event_id=str(uuid4()),
            event_type="tool_loop_exhausted",
            payload={"max_steps": max_steps},
        )
        return BackendResponse(
            output_text="Tool loop stopped after reaching the maximum step count without a final answer.",
            metadata={"strategy": "tool-loop", "steps": max_steps},
        )

    def _execute_backend_once(
        self,
        *,
        prepared: PreparedRun,
        cancel_requested: Callable[[], bool] | None,
        control_state: Callable[[], str | None] | None,
    ):
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
                    return None
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
            return prepared.backend.response_from_process(prepared.request, result)
        return prepared.backend.run(prepared.request)

    def _build_reflection(self, *, current_request: RunRequest, error_text: str) -> dict[str, str]:
        lowered = error_text.lower()
        if "not set" in lowered or "unknown backend" in lowered:
            probable_cause = "configuration"
            next_action = "check backend configuration and retry with corrected settings"
        elif "timed out" in lowered or "timeout" in lowered:
            probable_cause = "timeout"
            next_action = "retry once with the same goal and preserve the current context"
        elif "failed" in lowered or "error" in lowered:
            probable_cause = "backend or tool failure"
            next_action = "retry once after explicitly acknowledging the prior failure"
        else:
            probable_cause = "unknown"
            next_action = "retry once with the failure context attached"
        return {
            "mode": "reflect-retry",
            "strategy": current_request.strategy_name,
            "error": error_text,
            "probable_cause": probable_cause,
            "next_action": next_action,
        }

    def _reflection_prompt_block(self, reflection: dict[str, str]) -> str:
        return "\n".join(
            [
                f"- prior_error: {reflection['error']}",
                f"- probable_cause: {reflection['probable_cause']}",
                f"- next_action: {reflection['next_action']}",
            ]
        )

    def _tool_loop_system_prompt(self, *, depth: int) -> str:
        tool_lines = [
            f"- {tool['name']}: {tool['description']}"
            for tool in self.tools.list_tools()
        ]
        return "\n".join(
            [
                "You are running in Orchestro tool-loop mode.",
                "Respond with exactly one JSON object and no surrounding prose.",
                'Use {"action":"final","content":"..."} when you are ready to answer.',
                'Use {"action":"tool","tool":"<name>","argument":"..."} to call a local tool.',
                'Use {"action":"delegate","goal":"...","backend":"optional","strategy":"optional"} only if a child run would help.',
                "You may inspect prior tool results in the prompt context.",
                f"Current delegation depth: {depth}",
                "Available tools:",
                *tool_lines,
            ]
        )

    def _parse_tool_loop_action(self, output_text: str) -> dict[str, object]:
        try:
            parsed = json.loads(output_text)
        except json.JSONDecodeError:
            return {"action": "final", "content": output_text}
        if not isinstance(parsed, dict):
            return {"action": "final", "content": output_text}
        action = parsed.get("action")
        if action not in {"final", "tool", "delegate"}:
            return {"action": "final", "content": output_text}
        return parsed

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
