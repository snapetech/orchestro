from __future__ import annotations

import json
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from typing import Callable
import time
from uuid import uuid4

from orchestro.backend_profiles import build_default_backends, decide_auto_backend, reachable_backend_names
from orchestro.backends import Backend
from orchestro.constitutions import load_constitution_bundle
from orchestro.db import OrchestroDB
from orchestro.git_changes import collect_git_changes, summarize_git_delta
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
        self.backends = backends or build_default_backends()
        self.retrieval = RetrievalBuilder(db)
        self.tools = ToolRegistry()

    def available_backends(self) -> dict[str, dict[str, object]]:
        return {name: backend.capabilities() for name, backend in self.backends.items()}

    def backend_statuses(self) -> list[dict[str, object]]:
        reachable = reachable_backend_names(self.backends)
        statuses: list[dict[str, object]] = []
        for name in sorted(self.backends):
            backend = self.backends[name]
            capabilities = backend.capabilities()
            statuses.append(
                {
                    "name": name,
                    "reachable": name in reachable,
                    **capabilities,
                }
            )
        return statuses

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
        auto_route = None
        if request.backend_name == "auto":
            auto_route = decide_auto_backend(
                request.goal,
                strategy_name=request.strategy_name,
                domain=request.metadata.get("domain"),
                available=reachable_backend_names(self.backends),
            )
            request = replace(request, backend_name=auto_route.selected_backend)
        backend = self.backends[request.backend_name]
        context_providers = request.metadata.get(
            "context_providers",
            ["instructions", "lexical", "semantic", "corrections", "interactions", "postmortems"],
        )
        provider_set = set(context_providers)
        retrieval_enabled = request.metadata.get("retrieval_enabled", True) and bool(
            {"lexical", "semantic", "corrections", "interactions", "postmortems"} & provider_set
        )
        domain = request.metadata.get("domain")
        effective_request = request
        retrieval_bundle = None
        instruction_bundle = load_instruction_bundle(cwd)
        constitution_bundle = load_constitution_bundle(domain, cwd)
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
        if constitution_bundle.text:
            system_parts = [
                part
                for part in [
                    effective_request.system_prompt,
                    f"Apply the following domain constitution for '{domain}' when answering.",
                    constitution_bundle.text,
                ]
                if part
            ]
            effective_request = replace(effective_request, system_prompt="\n\n".join(system_parts))
        if retrieval_enabled:
            retrieval_bundle = self.retrieval.build(request.goal, domain=domain, providers=context_providers)
            if retrieval_bundle.context_text:
                effective_request = replace(effective_request, prompt_context=retrieval_bundle.context_text)

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
        if auto_route is not None:
            self.db.append_event(
                run_id=run_id,
                event_id=str(uuid4()),
                event_type="backend_auto_routed",
                payload={
                    "requested_backend": "auto",
                    "selected_backend": auto_route.selected_backend,
                    "preferred_backend": auto_route.preferred_backend,
                    "reason": auto_route.reason,
                    "reachable": auto_route.reachable,
                },
            )
        if instruction_bundle.sources and "instructions" in provider_set:
            self.db.append_event(
                run_id=run_id,
                event_id=str(uuid4()),
                event_type="instruction_context_loaded",
                payload=instruction_bundle.metadata(),
            )
        if constitution_bundle.sources:
            self.db.append_event(
                run_id=run_id,
                event_id=str(uuid4()),
                event_type="constitution_loaded",
                payload=constitution_bundle.metadata(),
            )
        self.db.append_event(
            run_id=run_id,
            event_id=str(uuid4()),
            event_type="context_providers_selected",
            payload={"providers": context_providers},
        )
        self._record_git_snapshot(run_id=run_id, cwd=cwd, phase="start")
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
        approve_tool: Callable[[str, str], bool] | None = None,
        operator_input: Callable[[], list[str]] | None = None,
    ) -> str:
        try:
            if prepared.request.strategy_name == "tool-loop":
                response = self._execute_tool_loop(
                    prepared=prepared,
                    cancel_requested=cancel_requested,
                    control_state=control_state,
                    approve_tool=approve_tool,
                    operator_input=operator_input,
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
                    self._record_failure_postmortem(run_id=prepared.run_id, error_text=str(exc))
                    raise
        finally:
            run = self.db.get_run(prepared.run_id)
            if run is not None and run.status in {"done", "failed", "canceled"}:
                self._record_git_snapshot(
                    run_id=prepared.run_id,
                    cwd=Path(prepared.request.working_directory),
                    phase="end",
                )

    def _execute_tool_loop(
        self,
        *,
        prepared: PreparedRun,
        cancel_requested: Callable[[], bool] | None,
        control_state: Callable[[], str | None] | None,
        approve_tool: Callable[[str, str], bool] | None,
        operator_input: Callable[[], list[str]] | None,
    ) -> BackendResponse:
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
            while control_state and control_state() == "paused":
                time.sleep(0.1)
                if cancel_requested and cancel_requested():
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="run_canceled",
                        payload={"reason": "cancel requested while tool-loop paused"},
                    )
                    self.db.cancel_run(
                        run_id=prepared.run_id,
                        error_message="run canceled while tool-loop paused",
                    )
                    raise RuntimeError("run canceled while tool-loop paused")
            if operator_input is not None:
                injected_notes = [note.strip() for note in operator_input() if note.strip()]
                if injected_notes:
                    for note in injected_notes:
                        self.db.append_event(
                            run_id=prepared.run_id,
                            event_id=str(uuid4()),
                            event_type="operator_input_received",
                            payload={"step": step_no, "note": note},
                        )
                        tool_state.append(
                            "\n".join(
                                [
                                    f"Operator note before step {step_no}",
                                    note,
                                ]
                            )
                        )
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
                tool_definition = self.tools.get_tool(tool_name)
                if tool_definition is None:
                    tool_state.append(f"Tool request rejected because the tool does not exist: {tool_name}")
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="tool_rejected",
                        payload={"step": step_no, "tool": tool_name, "reason": "unknown tool"},
                    )
                    continue
                if tool_definition.approval == "confirm":
                    approved = approve_tool(tool_name, argument) if approve_tool is not None else False
                    if not approved:
                        tool_state.append(
                            f"Tool request rejected because {tool_name} requires operator approval."
                        )
                        self.db.append_event(
                            run_id=prepared.run_id,
                            event_id=str(uuid4()),
                            event_type="tool_rejected",
                            payload={"step": step_no, "tool": tool_name, "reason": "approval required"},
                        )
                        continue
                else:
                    approved = False
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="tool_called",
                    payload={"step": step_no, "tool": tool_name, "argument": argument},
                )
                result = self.tools.run(
                    tool_name,
                    argument,
                    Path(prepared.request.working_directory),
                    approved=approved,
                )
                result_payload = tool_result_payload(result)
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="tool_result",
                    payload={"step": step_no, "tool": tool_name, **result_payload},
                )
                if not result.ok:
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="reflection",
                        payload={
                            "mode": "tool-failure",
                            "step": step_no,
                            "tool": tool_name,
                            "notes": "The tool call failed. Change the next action instead of repeating the same failed call.",
                        },
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
                self.execute_prepared_run(
                    child_prepared,
                    cancel_requested=cancel_requested,
                    control_state=control_state,
                    approve_tool=approve_tool,
                    operator_input=operator_input,
                )
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

    def _record_git_snapshot(self, *, run_id: str, cwd: Path, phase: str) -> None:
        snapshot = collect_git_changes(cwd)
        run = self.db.get_run(run_id)
        if run is None:
            return
        summary = None
        if phase == "end":
            summary = summarize_git_delta(run.git_snapshot_start, snapshot)
        self.db.update_run_git_snapshot(run_id=run_id, phase=phase, snapshot=snapshot, summary=summary)
        payload = {
            "phase": phase,
            "ok": bool(snapshot.get("ok")),
            "changed_count": len(snapshot.get("changed_files", [])) if snapshot.get("ok") else 0,
            "branch": snapshot.get("branch"),
        }
        if not snapshot.get("ok"):
            payload["error"] = snapshot.get("error")
        if summary is not None:
            payload["delta"] = summary
        self.db.append_event(
            run_id=run_id,
            event_id=str(uuid4()),
            event_type="run_git_snapshot",
            payload=payload,
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

    def _record_failure_postmortem(self, *, run_id: str, error_text: str) -> None:
        run = self.db.get_run(run_id)
        if run is None:
            return
        category = self._classify_failure(error_text)
        recent_events = self.db.list_events(run_id)[-5:]
        event_types = [event["event_type"] for event in recent_events]
        summary = "\n".join(
            [
                f"Goal: {run.goal}",
                f"Category: {category}",
                f"Failure: {error_text}",
                f"Recent events: {', '.join(event_types) if event_types else 'none'}",
                "Lesson: inspect the last failing step and avoid retrying the exact same action without changing context or approach.",
            ]
        )
        self.db.add_postmortem(
            postmortem_id=str(uuid4()),
            run_id=run_id,
            summary=summary,
            error_message=error_text,
            category=category,
            domain=run.metadata.get("domain"),
        )
        self.db.append_event(
            run_id=run_id,
            event_id=str(uuid4()),
            event_type="postmortem_recorded",
            payload={"category": category},
        )

    def _classify_failure(self, error_text: str) -> str:
        lowered = error_text.lower()
        if "timeout" in lowered:
            return "timeout"
        if "tool" in lowered:
            return "tool"
        if "backend" in lowered or "http" in lowered:
            return "backend"
        if "path" in lowered or "file" in lowered:
            return "workspace"
        return "general"

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
