from __future__ import annotations

import json
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from typing import Callable
import time
from uuid import uuid4

from orchestro.backend_profiles import build_default_backends, decide_auto_backend, reachable_backend_names
from orchestro.paths import data_dir
from orchestro.plugins import HOOK_ON_FAILURE, HOOK_POST_RUN, HOOK_POST_TOOL, HOOK_PRE_RUN, HOOK_PRE_TOOL, PluginManager
from orchestro.backends import Backend
from orchestro.budget import BudgetExhausted, load_budget_defaults
from orchestro.compaction import CompactionResult, compact_tool_state, should_compact
from orchestro.constitutions import load_constitution_bundle
from orchestro.db import OrchestroDB
from orchestro.git_changes import collect_git_changes, summarize_git_delta
from orchestro.instructions import load_instruction_bundle
from orchestro.models import BackendResponse, RatingRequest, RunRequest
from orchestro.policies import PolicyEngine, load_policies
from orchestro.correction_aware import should_elevate_approval
from orchestro.quality import quality_from_strategy, promote_quality
from orchestro.escalation import Escalator, load_escalation_config
from orchestro.recovery import recovery_recipe_for
from orchestro.retrieval import RetrievalBuilder
from orchestro.tasks import TaskPacket, TaskRecord, run_acceptance_tests, validate_task_packet
from orchestro.tools import ToolRegistry, tool_result_payload
from orchestro.trust import TRUST_AUTO, TRUST_CONFIRM, TRUST_DENY, TrustPolicy, load_trust_policy, resolve_trust_tier
from orchestro.verifiers import VerificationResult, VerifierRegistry


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
        self.tools = ToolRegistry(db=db)
        self.trust_policy = load_trust_policy()
        self.policy_engine = PolicyEngine(load_policies())
        self.escalator = Escalator(load_escalation_config())
        plugins_dir = data_dir() / "plugins"
        self.plugins = PluginManager(plugins_dir)
        self.plugins.load_all()
        self.verifiers = VerifierRegistry()

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
        session_id = request.metadata.get("session_id")
        session = self.db.get_session(session_id) if session_id else None
        effective_request = request
        retrieval_bundle = None
        instruction_bundle = load_instruction_bundle(cwd)
        constitution_bundle = load_constitution_bundle(domain, cwd)

        stable_parts: list[str] = []
        if instruction_bundle.text and "instructions" in provider_set:
            stable_parts.extend([
                "Use the following stable Orchestro instruction context when it is relevant.",
                instruction_bundle.text,
            ])
        if constitution_bundle.text:
            stable_parts.extend([
                f"Apply the following domain constitution for '{domain}' when answering.",
                constitution_bundle.text,
            ])
        if stable_parts:
            effective_request = replace(
                effective_request,
                stable_prefix="\n\n".join(stable_parts),
            )
        if retrieval_enabled:
            retrieval_bundle = self.retrieval.build(request.goal, domain=domain, providers=context_providers)
            if retrieval_bundle.context_text:
                effective_request = replace(effective_request, prompt_context=retrieval_bundle.context_text)

        self.db.create_run(
            run_id=run_id,
            parent_run_id=request.parent_run_id,
            session_id=session_id,
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
        if session is not None:
            self.db.append_event(
                run_id=run_id,
                event_id=str(uuid4()),
                event_type="session_attached",
                payload={
                    "session_id": session.id,
                    "title": session.title,
                    "has_context_snapshot": bool(session.context_snapshot),
                },
            )
            if session.context_snapshot:
                self.db.append_event(
                    run_id=run_id,
                    event_id=str(uuid4()),
                    event_type="session_context_loaded",
                    payload={"session_id": session.id, "summary": session.summary},
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

    def _record_response_token_usage(self, run_id: str, response: BackendResponse) -> None:
        self.db.update_run_token_usage(
            run_id=run_id,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            total_tokens=response.total_tokens,
            cache_read_tokens=response.cache_read_tokens,
            cache_write_tokens=response.cache_write_tokens,
        )
        if response.cache_read_tokens or response.cache_write_tokens:
            self.db.append_event(
                run_id=run_id,
                event_id=str(uuid4()),
                event_type="cache_stats",
                payload={
                    "cache_read_tokens": response.cache_read_tokens,
                    "cache_write_tokens": response.cache_write_tokens,
                },
            )

    def execute_prepared_run(
        self,
        prepared: PreparedRun,
        *,
        cancel_requested: Callable[[], bool] | None = None,
        control_state: Callable[[], str | None] | None = None,
        approve_tool: Callable[[str, str], bool] | None = None,
        operator_input: Callable[[], list[str]] | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> str:
        pre_run_result = self.plugins.hooks.run(HOOK_PRE_RUN, {
            "run_id": prepared.run_id,
            "goal": prepared.request.goal,
            "backend": prepared.request.backend_name,
            "strategy": prepared.request.strategy_name,
        })
        if pre_run_result.action == "abort":
            self.db.fail_run(
                run_id=prepared.run_id,
                error_message=f"aborted by plugin: {pre_run_result.reason}",
            )
            return prepared.run_id
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
                quality = quality_from_strategy(prepared.request.strategy_name)
                if quality != "unverified":
                    self.db.update_run_quality_level(prepared.run_id, quality)
                return prepared.run_id

            if prepared.request.strategy_name == "verified":
                response = self._execute_verified(
                    prepared=prepared,
                    cancel_requested=cancel_requested,
                    control_state=control_state,
                )
                self.db.complete_run(run_id=prepared.run_id, final_output=response.output_text)
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="run_completed",
                    payload={"output_length": len(response.output_text), "strategy": "verified"},
                )
                quality = quality_from_strategy(prepared.request.strategy_name)
                if response.metadata.get("verification_quality"):
                    quality = promote_quality(quality, response.metadata["verification_quality"])
                if quality != "unverified":
                    self.db.update_run_quality_level(prepared.run_id, quality)
                return prepared.run_id

            if prepared.request.strategy_name == "self-consistency":
                response = self._execute_self_consistency(
                    prepared=prepared,
                    cancel_requested=cancel_requested,
                    control_state=control_state,
                )
                self.db.complete_run(run_id=prepared.run_id, final_output=response.output_text)
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="run_completed",
                    payload={"output_length": len(response.output_text), "strategy": "self-consistency"},
                )
                quality = quality_from_strategy(prepared.request.strategy_name)
                if quality != "unverified":
                    self.db.update_run_quality_level(prepared.run_id, quality)
                return prepared.run_id

            if prepared.request.strategy_name == "critique-revise":
                response = self._execute_critique_revise(
                    prepared=prepared,
                    cancel_requested=cancel_requested,
                    control_state=control_state,
                )
                self.db.complete_run(run_id=prepared.run_id, final_output=response.output_text)
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="run_completed",
                    payload={"output_length": len(response.output_text), "strategy": "critique-revise"},
                )
                quality = quality_from_strategy(prepared.request.strategy_name)
                if quality != "unverified":
                    self.db.update_run_quality_level(prepared.run_id, quality)
                return prepared.run_id

            if prepared.request.strategy_name == "debate":
                response = self._execute_debate(
                    prepared=prepared,
                    cancel_requested=cancel_requested,
                    control_state=control_state,
                )
                self.db.complete_run(run_id=prepared.run_id, final_output=response.output_text)
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="run_completed",
                    payload={"output_length": len(response.output_text), "strategy": "debate"},
                )
                quality = quality_from_strategy(prepared.request.strategy_name)
                if quality != "unverified":
                    self.db.update_run_quality_level(prepared.run_id, quality)
                return prepared.run_id

            if prepared.request.strategy_name == "plan-execute":
                response = self._execute_plan_execute(
                    prepared=prepared,
                    cancel_requested=cancel_requested,
                    control_state=control_state,
                )
                self.db.complete_run(run_id=prepared.run_id, final_output=response.output_text)
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="run_completed",
                    payload={"output_length": len(response.output_text), "strategy": "plan-execute"},
                )
                quality = quality_from_strategy(prepared.request.strategy_name)
                if quality != "unverified":
                    self.db.update_run_quality_level(prepared.run_id, quality)
                return prepared.run_id

            allow_reflect_retry = prepared.request.strategy_name in {"reflect-retry", "reflect-retry-once"}
            current_request = prepared.request
            current_backend = prepared.backend
            attempt_no = 1
            while True:
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
                            backend=current_backend,
                            request=current_request,
                            retrieval_bundle=prepared.retrieval_bundle,
                        ),
                        cancel_requested=cancel_requested,
                        control_state=control_state,
                        on_chunk=on_chunk,
                    )
                    if response is None:
                        return prepared.run_id
                    self._record_response_token_usage(prepared.run_id, response)
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="backend_completed",
                        payload={
                            **response.metadata,
                            "attempt": attempt_no,
                            "prompt_tokens": response.prompt_tokens,
                            "completion_tokens": response.completion_tokens,
                            "total_tokens": response.total_tokens,
                        },
                    )
                    self.db.complete_run(run_id=prepared.run_id, final_output=response.output_text)
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="run_completed",
                        payload={"output_length": len(response.output_text), "attempt": attempt_no},
                    )
                    quality = quality_from_strategy(prepared.request.strategy_name)
                    if quality != "unverified":
                        self.db.update_run_quality_level(prepared.run_id, quality)
                    return prepared.run_id
                except Exception as exc:
                    error_text = str(exc)
                    failure_category = self._classify_failure(error_text)
                    recipe = recovery_recipe_for(failure_category) if allow_reflect_retry else recovery_recipe_for("general_failure")
                    recovery_step = recipe.step_for_failure(attempt_no - 1) if allow_reflect_retry else "abandon"
                    reflection = self._build_reflection(current_request=current_request, error_text=error_text)
                    recovery_payload: dict[str, object] = {
                        "attempt": attempt_no,
                        "failure_category": failure_category,
                        "step": recovery_step,
                    }
                    retry_guidance = [
                        "Retry guidance from the last failed attempt:",
                        self._reflection_prompt_block(reflection),
                    ]
                    self.db.update_run_failure_state(
                        run_id=prepared.run_id,
                        failure_category=failure_category,
                        recovery_attempts=max(0, attempt_no - 1),
                    )
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="reflection",
                        payload={"attempt": attempt_no, **reflection},
                    )
                    if recovery_step == "retry_different_backend":
                        next_backend = self._select_recovery_backend(
                            goal=current_request.goal,
                            current_backend_name=current_request.backend_name,
                            strategy_name=current_request.strategy_name,
                            domain=current_request.metadata.get("domain"),
                        )
                        if next_backend is None:
                            recovery_step = "escalate"
                            recovery_payload["step"] = recovery_step
                        else:
                            recovery_payload["next_backend"] = next_backend
                            current_backend = self.backends[next_backend]
                            current_request = replace(current_request, backend_name=next_backend)
                            retry_guidance.append(f"Retry on backend: {next_backend}")
                    if recovery_step == "compact_context":
                        compacted_context = self._compact_prompt_context(current_request.prompt_context)
                        current_request = replace(current_request, prompt_context=compacted_context)
                        recovery_payload["compacted"] = True
                        retry_guidance.append("Context was compacted before retrying.")
                    elif recovery_step == "simplify_strategy":
                        current_request = replace(current_request, strategy_name="direct")
                        recovery_payload["new_strategy"] = "direct"
                        retry_guidance.append("Retry using the simplest direct strategy.")
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="recovery_attempted",
                        payload=recovery_payload,
                    )
                    if recovery_step in {"retry_same", "retry_different_backend", "compact_context", "simplify_strategy"}:
                        self.db.update_run_failure_state(
                            run_id=prepared.run_id,
                            failure_category=failure_category,
                            recovery_attempts=attempt_no,
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
                                for part in [current_request.system_prompt, *retry_guidance]
                                if part
                            ),
                        )
                        attempt_no += 1
                        continue
                    if recovery_step == "escalate":
                        self.db.append_event(
                            run_id=prepared.run_id,
                            event_id=str(uuid4()),
                            event_type="recovery_escalated",
                            payload={
                                "attempt": attempt_no,
                                "failure_category": failure_category,
                                "reason": error_text,
                            },
                        )
                        self.escalator.escalate(
                            run_id=prepared.run_id,
                            reason=error_text,
                            category="recovery_exhausted",
                        )
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="run_failed",
                        payload={
                            "error": error_text,
                            "attempt": attempt_no,
                            "failure_category": failure_category,
                            "recovery_step": recovery_step,
                        },
                    )
                    self.db.fail_run(
                        run_id=prepared.run_id,
                        error_message=error_text,
                        failure_category=failure_category,
                        recovery_attempts=max(0, attempt_no - 1),
                    )
                    self._record_failure_postmortem(run_id=prepared.run_id, error_text=error_text)
                    raise

        finally:
            run = self.db.get_run(prepared.run_id)
            if run is not None and run.status in {"done", "failed", "canceled"}:
                self._record_git_snapshot(
                    run_id=prepared.run_id,
                    cwd=Path(prepared.request.working_directory),
                    phase="end",
                )
            self.plugins.hooks.run(HOOK_POST_RUN, {
                "run_id": prepared.run_id,
                "status": run.status if run else "unknown",
                "goal": prepared.request.goal,
            })

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
        budget = load_budget_defaults(prepared.request.metadata)
        budget.start()
        self.db.append_event(
            run_id=prepared.run_id,
            event_id=str(uuid4()),
            event_type="budget_initialized",
            payload={
                "max_tool_calls": budget.max_tool_calls,
                "max_tokens": budget.max_tokens,
                "max_wall_seconds": budget.max_wall_seconds,
                "max_file_edits": budget.max_file_edits,
                "max_bash_calls": budget.max_bash_calls,
            },
        )
        self.db.append_event(
            run_id=prepared.run_id,
            event_id=str(uuid4()),
            event_type="tool_loop_started",
            payload={"max_steps": max_steps, "tool_count": len(self.tools.list_tools())},
        )
        for step_no in range(1, max_steps + 1):
            try:
                budget.check()
            except BudgetExhausted as exc:
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="budget_exhausted",
                    payload={
                        "resource": exc.resource,
                        "limit": exc.limit,
                        "used": exc.used,
                        **budget.to_dict(),
                    },
                )
                self.escalator.escalate(
                    run_id=prepared.run_id,
                    reason=f"budget exhausted for {exc.resource} ({exc.used}/{exc.limit})",
                    category="budget_exhausted",
                )
                return BackendResponse(
                    output_text=f"Run stopped: budget exhausted for {exc.resource} ({exc.used}/{exc.limit}).",
                    metadata={"strategy": "tool-loop", "steps": step_no - 1, "budget_exhausted": exc.resource},
                )
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
            self._record_response_token_usage(prepared.run_id, response)
            if response.total_tokens:
                budget.record_tokens(response.total_tokens)
            self.db.append_event(
                run_id=prepared.run_id,
                event_id=str(uuid4()),
                event_type="backend_completed",
                payload={
                    **response.metadata,
                    "step": step_no,
                    "prompt_tokens": response.prompt_tokens,
                    "completion_tokens": response.completion_tokens,
                    "total_tokens": response.total_tokens,
                },
            )
            action = self._parse_tool_loop_action(response.output_text)
            confidence = action.get("confidence") if isinstance(action.get("confidence"), (int, float)) else None
            if confidence is not None:
                confidence = max(0.0, min(1.0, float(confidence)))
            think_payload: dict[str, object] = {"mode": "tool-loop", "step": step_no, "action": action}
            if confidence is not None:
                think_payload["confidence"] = confidence
            self.db.append_event(
                run_id=prepared.run_id,
                event_id=str(uuid4()),
                event_type="think",
                payload=think_payload,
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
                pre_tool_result = self.plugins.hooks.run(HOOK_PRE_TOOL, {
                    "run_id": prepared.run_id,
                    "step": step_no,
                    "tool": tool_name,
                    "argument": argument,
                })
                if pre_tool_result.action == "abort":
                    tool_state.append(f"Tool {tool_name} blocked by plugin: {pre_tool_result.reason}")
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="tool_rejected",
                        payload={"step": step_no, "tool": tool_name, "reason": f"plugin: {pre_tool_result.reason}"},
                    )
                    continue
                domain = prepared.request.metadata.get("domain")
                policy_context = {
                    "tool": tool_name,
                    "domain": domain or "",
                    "strategy": prepared.request.strategy_name,
                }
                policy_action = self.policy_engine.evaluate(policy_context)
                if policy_action and policy_action.action == "auto-approve":
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="policy_auto_approved",
                        payload={"step": step_no, "tool": tool_name},
                    )
                    tool_called_payload: dict[str, object] = {"step": step_no, "tool": tool_name, "argument": argument}
                    if confidence is not None:
                        tool_called_payload["confidence"] = confidence
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="tool_called",
                        payload=tool_called_payload,
                    )
                    result = self.tools.run(
                        tool_name,
                        argument,
                        Path(prepared.request.working_directory),
                        approved=True,
                        run_id=prepared.run_id,
                    )
                    if confidence is not None:
                        result.confidence = confidence
                    budget.record_tool_call(tool_name)
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
                    self.plugins.hooks.run(HOOK_POST_TOOL, {
                        "run_id": prepared.run_id,
                        "step": step_no,
                        "tool": tool_name,
                        "argument": argument,
                        "ok": result.ok,
                        "output": result.output,
                    })
                    tool_feedback_parts = [
                        f"Tool step {step_no}",
                        f"tool: {tool_name}",
                        f"argument: {argument}",
                        f"ok: {result.ok}",
                    ]
                    if confidence is not None:
                        tool_feedback_parts.append(f"confidence: {confidence}")
                    tool_feedback_parts.extend(["output:", result.output])
                    tool_state.append("\n".join(tool_feedback_parts))
                    continue
                if policy_action and policy_action.action == "deny":
                    tool_state.append(f"Tool request denied by policy: {tool_name}")
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="policy_denied",
                        payload={"step": step_no, "tool": tool_name},
                    )
                    continue
                tier = resolve_trust_tier(
                    tool_name,
                    policy=self.trust_policy,
                    domain=domain,
                    base_tier=tool_definition.approval,
                )
                elevate, elevate_reason = should_elevate_approval(
                    tool_name, argument, prepared.run_id, self.db,
                )
                if elevate and tier != TRUST_CONFIRM and tier != TRUST_DENY:
                    tier = TRUST_CONFIRM
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="correction_elevated_approval",
                        payload={"step": step_no, "tool": tool_name, "reason": elevate_reason},
                    )
                if tier == TRUST_DENY:
                    tool_state.append(f"Tool request denied by trust policy: {tool_name}")
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="tool_denied",
                        payload={"step": step_no, "tool": tool_name, "reason": "denied by trust policy"},
                    )
                    continue
                if tier == TRUST_CONFIRM:
                    if prepared.request.autonomous:
                        tool_state.append(
                            f"Tool {tool_name} skipped: requires approval but run is autonomous."
                        )
                        self.db.append_event(
                            run_id=prepared.run_id,
                            event_id=str(uuid4()),
                            event_type="autonomous_tool_escalated",
                            payload={"step": step_no, "tool": tool_name, "argument": argument},
                        )
                        continue
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
                    approved = tier == TRUST_AUTO and tool_definition.approval == "confirm"
                tool_called_payload2: dict[str, object] = {"step": step_no, "tool": tool_name, "argument": argument}
                if confidence is not None:
                    tool_called_payload2["confidence"] = confidence
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="tool_called",
                    payload=tool_called_payload2,
                )
                result = self.tools.run(
                    tool_name,
                    argument,
                    Path(prepared.request.working_directory),
                    approved=approved,
                    run_id=prepared.run_id,
                )
                if confidence is not None:
                    result.confidence = confidence
                budget.record_tool_call(tool_name)
                result_payload = tool_result_payload(result)
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="tool_result",
                    payload={"step": step_no, "tool": tool_name, **result_payload},
                )
                if result.metadata.get("bash_risk") == "warn":
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="bash_risk_warning",
                        payload={
                            "step": step_no,
                            "command": argument,
                            "reasons": result.metadata.get("bash_risk_reasons", []),
                        },
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
                self.plugins.hooks.run(HOOK_POST_TOOL, {
                    "run_id": prepared.run_id,
                    "step": step_no,
                    "tool": tool_name,
                    "argument": argument,
                    "ok": result.ok,
                    "output": result.output,
                })
                tool_feedback_parts2 = [
                    f"Tool step {step_no}",
                    f"tool: {tool_name}",
                    f"argument: {argument}",
                    f"ok: {result.ok}",
                ]
                if confidence is not None:
                    tool_feedback_parts2.append(f"confidence: {confidence}")
                tool_feedback_parts2.extend(["output:", result.output])
                tool_state.append("\n".join(tool_feedback_parts2))
                if should_compact(tool_state):
                    tool_state, compaction = compact_tool_state(tool_state)
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="context_compacted",
                        payload={
                            "step": step_no,
                            "original_length": compaction.original_length,
                            "compacted_length": compaction.compacted_length,
                            "steps_compacted": compaction.steps_compacted,
                            "steps_preserved": compaction.steps_preserved,
                        },
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
                acceptance_tests = action.get("acceptance_tests")
                if isinstance(acceptance_tests, list):
                    acceptance_tests = [str(t) for t in acceptance_tests if t]
                else:
                    acceptance_tests = None

                task_id: str | None = None
                if acceptance_tests:
                    task_id = str(uuid4())
                    packet = TaskPacket(
                        objective=child_goal,
                        acceptance_tests=acceptance_tests,
                        escalation_policy=str(action.get("escalation_policy", "escalate")),
                    )
                    self.db.create_task(
                        task_id=task_id,
                        parent_run_id=prepared.run_id,
                        objective=child_goal,
                        packet_json=json.dumps({
                            "objective": packet.objective,
                            "acceptance_tests": packet.acceptance_tests,
                            "escalation_policy": packet.escalation_policy,
                        }, sort_keys=True),
                    )
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="task_created",
                        payload={
                            "step": step_no,
                            "task_id": task_id,
                            "objective": child_goal,
                            "acceptance_tests": acceptance_tests,
                        },
                    )

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

                if task_id is not None:
                    self.db.assign_task(task_id, child_prepared.run_id)

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
                        "task_id": task_id,
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
                child_status = child_run.status if child_run else "unknown"
                child_output = child_run.final_output if child_run and child_run.final_output else ""

                acceptance_summary: str | None = None
                if task_id is not None and acceptance_tests and child_status == "done":
                    cwd = Path(prepared.request.working_directory)
                    all_passed, test_results = run_acceptance_tests(acceptance_tests, cwd)
                    acceptance_json = json.dumps(
                        {"all_passed": all_passed, "results": test_results}, sort_keys=True
                    )
                    if all_passed:
                        self.db.complete_task(task_id, child_output, acceptance_result=acceptance_json)
                    else:
                        self.db.fail_task(task_id, child_output)
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="task_acceptance_tested",
                        payload={
                            "step": step_no,
                            "task_id": task_id,
                            "all_passed": all_passed,
                            "results": test_results,
                        },
                    )
                    passed_count = sum(1 for r in test_results if r["passed"])
                    acceptance_summary = (
                        f"acceptance_tests: {passed_count}/{len(test_results)} passed"
                    )
                elif task_id is not None and child_status != "done":
                    self.db.fail_task(task_id, child_output or f"child run {child_status}")

                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="child_run_completed",
                    payload={
                        "step": step_no,
                        "child_run_id": child_prepared.run_id,
                        "status": child_status,
                        "task_id": task_id,
                    },
                )
                feedback_parts = [
                    f"Delegated step {step_no}",
                    f"child_run_id: {child_prepared.run_id}",
                    f"status: {child_status}",
                    "output:",
                    child_output,
                ]
                if acceptance_summary:
                    feedback_parts.append(acceptance_summary)
                tool_state.append("\n".join(feedback_parts))
                if should_compact(tool_state):
                    tool_state, compaction = compact_tool_state(tool_state)
                    self.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="context_compacted",
                        payload={
                            "step": step_no,
                            "original_length": compaction.original_length,
                            "compacted_length": compaction.compacted_length,
                            "steps_compacted": compaction.steps_compacted,
                            "steps_preserved": compaction.steps_preserved,
                        },
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

    def _execute_self_consistency(
        self,
        *,
        prepared: PreparedRun,
        cancel_requested: Callable[[], bool] | None,
        control_state: Callable[[], str | None] | None,
    ) -> BackendResponse:
        sample_count = int(prepared.request.metadata.get("consistency_samples", 3))
        self.db.append_event(
            run_id=prepared.run_id,
            event_id=str(uuid4()),
            event_type="self_consistency_started",
            payload={"sample_count": sample_count},
        )
        samples: list[tuple[int, BackendResponse]] = []
        for i in range(sample_count):
            if cancel_requested and cancel_requested():
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="run_canceled",
                    payload={"reason": "cancel requested during self-consistency sampling"},
                )
                self.db.cancel_run(
                    run_id=prepared.run_id,
                    error_message="run canceled during self-consistency sampling",
                )
                raise RuntimeError("run canceled during self-consistency sampling")
            response = self._execute_backend_once(
                prepared=prepared,
                cancel_requested=cancel_requested,
                control_state=control_state,
            )
            if response is None:
                raise RuntimeError("run canceled during self-consistency execution")
            self._record_response_token_usage(prepared.run_id, response)
            self.db.append_event(
                run_id=prepared.run_id,
                event_id=str(uuid4()),
                event_type="self_consistency_sample",
                payload={
                    "sample_index": i,
                    "output_preview": response.output_text[:200],
                    "prompt_tokens": response.prompt_tokens,
                    "completion_tokens": response.completion_tokens,
                    "total_tokens": response.total_tokens,
                },
            )
            samples.append((i, response))
        selected_index, selected_response, method = self._pick_majority_answer(samples)
        self.db.append_event(
            run_id=prepared.run_id,
            event_id=str(uuid4()),
            event_type="self_consistency_resolved",
            payload={
                "selected_index": selected_index,
                "method": method,
                "sample_count": sample_count,
            },
        )
        return BackendResponse(
            output_text=selected_response.output_text,
            metadata={
                **selected_response.metadata,
                "strategy": "self-consistency",
                "sample_count": sample_count,
                "selected_index": selected_index,
                "selection_method": method,
            },
            prompt_tokens=selected_response.prompt_tokens,
            completion_tokens=selected_response.completion_tokens,
            total_tokens=selected_response.total_tokens,
        )

    @staticmethod
    def _pick_majority_answer(
        samples: list[tuple[int, BackendResponse]],
    ) -> tuple[int, BackendResponse, str]:
        from collections import Counter

        texts = [(idx, resp, resp.output_text) for idx, resp in samples]

        exact_counts = Counter(text for _, _, text in texts)
        most_common_text, most_common_count = exact_counts.most_common(1)[0]
        if most_common_count > 1:
            for idx, resp, text in texts:
                if text == most_common_text:
                    return idx, resp, "majority"

        normalized = [(idx, resp, text.strip().lower()) for idx, resp, text in texts]
        norm_counts = Counter(norm for _, _, norm in normalized)
        most_common_norm, most_common_norm_count = norm_counts.most_common(1)[0]
        if most_common_norm_count > 1:
            for idx, resp, norm in normalized:
                if norm == most_common_norm:
                    return idx, resp, "majority"

        longest_idx, longest_resp = max(samples, key=lambda s: len(s[1].output_text))
        return longest_idx, longest_resp, "longest"

    def _execute_critique_revise(
        self,
        *,
        prepared: PreparedRun,
        cancel_requested: Callable[[], bool] | None,
        control_state: Callable[[], str | None] | None,
    ) -> BackendResponse:
        goal = prepared.request.goal

        draft_response = self._execute_backend_once(
            prepared=prepared,
            cancel_requested=cancel_requested,
            control_state=control_state,
        )
        if draft_response is None:
            raise RuntimeError("run canceled during critique-revise draft generation")
        self._record_response_token_usage(prepared.run_id, draft_response)
        draft_output = draft_response.output_text
        self.db.append_event(
            run_id=prepared.run_id,
            event_id=str(uuid4()),
            event_type="critique_revise_draft",
            payload={"output_preview": draft_output[:200]},
        )

        critique_request = replace(
            prepared.request,
            system_prompt=(
                "You are a critical reviewer. Analyze the following draft response "
                "for accuracy, completeness, and clarity. List specific issues and "
                "suggest improvements. Be concise and actionable.\n\n"
                f"Original goal: {goal}\n\n"
                f"Draft response:\n{draft_output}"
            ),
            goal=f"Critique the draft response for: {goal}",
            prompt_context=None,
        )
        critique_response = self._execute_backend_once(
            prepared=PreparedRun(
                run_id=prepared.run_id,
                backend=prepared.backend,
                request=critique_request,
                retrieval_bundle=None,
            ),
            cancel_requested=cancel_requested,
            control_state=control_state,
        )
        if critique_response is None:
            raise RuntimeError("run canceled during critique-revise critique pass")
        self._record_response_token_usage(prepared.run_id, critique_response)
        critique_output = critique_response.output_text
        self.db.append_event(
            run_id=prepared.run_id,
            event_id=str(uuid4()),
            event_type="critique_revise_critique",
            payload={"output_preview": critique_output[:200]},
        )

        revise_request = replace(
            prepared.request,
            system_prompt=(
                "Revise your response based on the following critique. "
                "Produce only the final improved response.\n\n"
                f"Original goal: {goal}\n\n"
                f"Your draft:\n{draft_output}\n\n"
                f"Critique:\n{critique_output}\n\n"
                "Revised response:"
            ),
            goal=goal,
            prompt_context=None,
        )
        revised_response = self._execute_backend_once(
            prepared=PreparedRun(
                run_id=prepared.run_id,
                backend=prepared.backend,
                request=revise_request,
                retrieval_bundle=None,
            ),
            cancel_requested=cancel_requested,
            control_state=control_state,
        )
        if revised_response is None:
            raise RuntimeError("run canceled during critique-revise revision pass")
        self._record_response_token_usage(prepared.run_id, revised_response)
        self.db.append_event(
            run_id=prepared.run_id,
            event_id=str(uuid4()),
            event_type="critique_revise_final",
            payload={"output_preview": revised_response.output_text[:200]},
        )

        return BackendResponse(
            output_text=revised_response.output_text,
            metadata={
                **revised_response.metadata,
                "strategy": "critique-revise",
                "steps": 3,
            },
            prompt_tokens=revised_response.prompt_tokens,
            completion_tokens=revised_response.completion_tokens,
            total_tokens=revised_response.total_tokens,
        )

    def _execute_debate(
        self,
        *,
        prepared: PreparedRun,
        cancel_requested: Callable[[], bool] | None,
        control_state: Callable[[], str | None] | None,
    ) -> BackendResponse:
        goal = prepared.request.goal
        total_prompt = 0
        total_completion = 0
        total_tokens_acc = 0

        perspective_a_request = replace(
            prepared.request,
            system_prompt=(
                "You are Perspective A. Provide a thorough, well-reasoned answer "
                "to the following goal. Focus on practical considerations and "
                "concrete recommendations."
            ),
        )
        a_response = self._execute_backend_once(
            prepared=PreparedRun(
                run_id=prepared.run_id,
                backend=prepared.backend,
                request=perspective_a_request,
                retrieval_bundle=prepared.retrieval_bundle,
            ),
            cancel_requested=cancel_requested,
            control_state=control_state,
        )
        if a_response is None:
            raise RuntimeError("run canceled during debate perspective A")
        total_prompt += a_response.prompt_tokens or 0
        total_completion += a_response.completion_tokens or 0
        total_tokens_acc += a_response.total_tokens or 0
        self._record_response_token_usage(prepared.run_id, a_response)
        self.db.append_event(
            run_id=prepared.run_id,
            event_id=str(uuid4()),
            event_type="debate_perspective_a",
            payload={
                "output_preview": a_response.output_text[:200],
                "prompt_tokens": a_response.prompt_tokens,
                "completion_tokens": a_response.completion_tokens,
                "total_tokens": a_response.total_tokens,
            },
        )

        if cancel_requested and cancel_requested():
            self.db.append_event(
                run_id=prepared.run_id,
                event_id=str(uuid4()),
                event_type="run_canceled",
                payload={"reason": "cancel requested between debate perspectives"},
            )
            self.db.cancel_run(
                run_id=prepared.run_id,
                error_message="run canceled between debate perspectives",
            )
            raise RuntimeError("run canceled between debate perspectives")

        perspective_b_request = replace(
            prepared.request,
            system_prompt=(
                "You are Perspective B. Provide a thorough, well-reasoned answer "
                "to the following goal. Focus on potential risks, alternative "
                "approaches, and edge cases that might be overlooked."
            ),
            prompt_context=None,
        )
        b_response = self._execute_backend_once(
            prepared=PreparedRun(
                run_id=prepared.run_id,
                backend=prepared.backend,
                request=perspective_b_request,
                retrieval_bundle=None,
            ),
            cancel_requested=cancel_requested,
            control_state=control_state,
        )
        if b_response is None:
            raise RuntimeError("run canceled during debate perspective B")
        total_prompt += b_response.prompt_tokens or 0
        total_completion += b_response.completion_tokens or 0
        total_tokens_acc += b_response.total_tokens or 0
        self._record_response_token_usage(prepared.run_id, b_response)
        self.db.append_event(
            run_id=prepared.run_id,
            event_id=str(uuid4()),
            event_type="debate_perspective_b",
            payload={
                "output_preview": b_response.output_text[:200],
                "prompt_tokens": b_response.prompt_tokens,
                "completion_tokens": b_response.completion_tokens,
                "total_tokens": b_response.total_tokens,
            },
        )

        if cancel_requested and cancel_requested():
            self.db.append_event(
                run_id=prepared.run_id,
                event_id=str(uuid4()),
                event_type="run_canceled",
                payload={"reason": "cancel requested before debate synthesis"},
            )
            self.db.cancel_run(
                run_id=prepared.run_id,
                error_message="run canceled before debate synthesis",
            )
            raise RuntimeError("run canceled before debate synthesis")

        synthesis_request = replace(
            prepared.request,
            system_prompt=(
                "You are a synthesis judge. Two independent perspectives have "
                "addressed the following goal. Synthesize them into a single "
                "authoritative answer that incorporates the strongest points "
                f"from each.\n\nPerspective A:\n{a_response.output_text}\n\n"
                f"Perspective B:\n{b_response.output_text}\n\n"
                "Provide only the final synthesized answer."
            ),
            prompt_context=None,
        )
        synthesis_response = self._execute_backend_once(
            prepared=PreparedRun(
                run_id=prepared.run_id,
                backend=prepared.backend,
                request=synthesis_request,
                retrieval_bundle=None,
            ),
            cancel_requested=cancel_requested,
            control_state=control_state,
        )
        if synthesis_response is None:
            raise RuntimeError("run canceled during debate synthesis")
        total_prompt += synthesis_response.prompt_tokens or 0
        total_completion += synthesis_response.completion_tokens or 0
        total_tokens_acc += synthesis_response.total_tokens or 0
        self._record_response_token_usage(prepared.run_id, synthesis_response)
        self.db.append_event(
            run_id=prepared.run_id,
            event_id=str(uuid4()),
            event_type="debate_synthesized",
            payload={
                "output_preview": synthesis_response.output_text[:200],
                "prompt_tokens": synthesis_response.prompt_tokens,
                "completion_tokens": synthesis_response.completion_tokens,
                "total_tokens": synthesis_response.total_tokens,
            },
        )

        return BackendResponse(
            output_text=synthesis_response.output_text,
            metadata={
                **synthesis_response.metadata,
                "strategy": "debate",
                "steps": 3,
            },
            prompt_tokens=total_prompt,
            completion_tokens=total_completion,
            total_tokens=total_tokens_acc,
        )

    def _execute_plan_execute(
        self,
        *,
        prepared: PreparedRun,
        cancel_requested: Callable[[], bool] | None,
        control_state: Callable[[], str | None] | None,
    ) -> BackendResponse:
        from orchestro.planner import parse_numbered_steps

        goal = prepared.request.goal
        max_steps = 8

        plan_request = replace(
            prepared.request,
            system_prompt=(
                "Generate a numbered step-by-step plan to accomplish the following goal. "
                "Return only the numbered steps, one per line.\n\n"
                f"Goal: {goal}"
            ),
            goal=f"Plan: {goal}",
            prompt_context=None,
        )
        plan_response = self._execute_backend_once(
            prepared=PreparedRun(
                run_id=prepared.run_id,
                backend=prepared.backend,
                request=plan_request,
                retrieval_bundle=None,
            ),
            cancel_requested=cancel_requested,
            control_state=control_state,
        )
        if plan_response is None:
            raise RuntimeError("run canceled during plan-execute plan generation")
        self._record_response_token_usage(prepared.run_id, plan_response)
        steps = parse_numbered_steps(plan_response.output_text)
        if not steps:
            steps = [goal]
        steps = steps[:max_steps]
        self.db.append_event(
            run_id=prepared.run_id,
            event_id=str(uuid4()),
            event_type="plan_execute_plan_generated",
            payload={"steps": steps, "count": len(steps)},
        )

        step_results: list[str] = []
        for step_idx, step in enumerate(steps):
            if cancel_requested and cancel_requested():
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="run_canceled",
                    payload={"reason": "cancel requested during plan-execute step"},
                )
                self.db.cancel_run(
                    run_id=prepared.run_id,
                    error_message="run canceled during plan-execute step",
                )
                raise RuntimeError("run canceled during plan-execute step")

            context_parts = [prepared.request.prompt_context] if prepared.request.prompt_context else []
            if step_results:
                context_parts.append(
                    "Results from previous steps:\n"
                    + "\n".join(
                        f"Step {i + 1}: {result}"
                        for i, result in enumerate(step_results)
                    )
                )
            step_request = replace(
                prepared.request,
                goal=step,
                prompt_context="\n\n".join(context_parts) if context_parts else None,
            )
            try:
                step_response = self._execute_backend_once(
                    prepared=PreparedRun(
                        run_id=prepared.run_id,
                        backend=prepared.backend,
                        request=step_request,
                        retrieval_bundle=prepared.retrieval_bundle,
                    ),
                    cancel_requested=cancel_requested,
                    control_state=control_state,
                )
                if step_response is None:
                    raise RuntimeError("run canceled during plan-execute step execution")
                self._record_response_token_usage(prepared.run_id, step_response)
                step_results.append(step_response.output_text)
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="plan_execute_step_completed",
                    payload={
                        "step_index": step_idx,
                        "step": step,
                        "output_preview": step_response.output_text[:200],
                    },
                )
            except RuntimeError:
                raise
            except Exception as exc:
                step_results.append(f"FAILED: {exc}")
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="plan_execute_step_completed",
                    payload={
                        "step_index": step_idx,
                        "step": step,
                        "failed": True,
                        "error": str(exc),
                    },
                )
                completed_summary = "\n".join(
                    f"Step {i + 1}: {result}"
                    for i, result in enumerate(step_results)
                )
                replan_request = replace(
                    prepared.request,
                    system_prompt=(
                        "The current plan encountered a failure. Generate a revised numbered plan "
                        "for the remaining work. Return only the numbered steps, one per line.\n\n"
                        f"Original goal: {goal}\n\n"
                        f"Completed steps:\n{completed_summary}\n\n"
                        f"Failure at step {step_idx + 1}: {exc}\n\n"
                        "Revised plan for remaining work:"
                    ),
                    goal=f"Replan: {goal}",
                    prompt_context=None,
                )
                replan_response = self._execute_backend_once(
                    prepared=PreparedRun(
                        run_id=prepared.run_id,
                        backend=prepared.backend,
                        request=replan_request,
                        retrieval_bundle=None,
                    ),
                    cancel_requested=cancel_requested,
                    control_state=control_state,
                )
                if replan_response is None:
                    raise RuntimeError("run canceled during plan-execute replanning")
                self._record_response_token_usage(prepared.run_id, replan_response)
                new_steps = parse_numbered_steps(replan_response.output_text)
                if new_steps:
                    remaining_budget = max_steps - (step_idx + 1)
                    steps[step_idx + 1:] = new_steps[:remaining_budget]
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="plan_execute_replanned",
                    payload={
                        "failed_step_index": step_idx,
                        "new_steps": new_steps[:max_steps - (step_idx + 1)] if new_steps else [],
                    },
                )

        completed_summary = "\n".join(
            f"Step {i + 1}: {result}" for i, result in enumerate(step_results)
        )
        synthesize_request = replace(
            prepared.request,
            system_prompt=(
                "Synthesize the results of the following plan steps into a final cohesive answer.\n\n"
                f"Original goal: {goal}\n\n"
                f"Completed steps:\n{completed_summary}"
            ),
            goal=goal,
            prompt_context=None,
        )
        synth_response = self._execute_backend_once(
            prepared=PreparedRun(
                run_id=prepared.run_id,
                backend=prepared.backend,
                request=synthesize_request,
                retrieval_bundle=None,
            ),
            cancel_requested=cancel_requested,
            control_state=control_state,
        )
        if synth_response is None:
            raise RuntimeError("run canceled during plan-execute synthesis")
        self._record_response_token_usage(prepared.run_id, synth_response)
        self.db.append_event(
            run_id=prepared.run_id,
            event_id=str(uuid4()),
            event_type="plan_execute_synthesized",
            payload={"output_preview": synth_response.output_text[:200]},
        )
        return BackendResponse(
            output_text=synth_response.output_text,
            metadata={
                **synth_response.metadata,
                "strategy": "plan-execute",
                "steps": len(step_results),
            },
            prompt_tokens=synth_response.prompt_tokens,
            completion_tokens=synth_response.completion_tokens,
            total_tokens=synth_response.total_tokens,
        )

    def _execute_verified(
        self,
        *,
        prepared: PreparedRun,
        cancel_requested: Callable[[], bool] | None,
        control_state: Callable[[], str | None] | None,
    ) -> BackendResponse:
        max_attempts = 3
        verifier_names = prepared.request.metadata.get("verifiers", ["python-syntax"])
        verification_context = prepared.request.metadata.get("verification_context")
        self.db.append_event(
            run_id=prepared.run_id,
            event_id=str(uuid4()),
            event_type="verification_started",
            payload={"verifiers": verifier_names, "max_attempts": max_attempts},
        )
        best_response: BackendResponse | None = None
        best_error_count: int | None = None
        current_request = prepared.request
        for attempt in range(1, max_attempts + 1):
            if cancel_requested and cancel_requested():
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="run_canceled",
                    payload={"reason": "cancel requested during verified strategy"},
                )
                self.db.cancel_run(
                    run_id=prepared.run_id,
                    error_message="run canceled during verified strategy",
                )
                raise RuntimeError("run canceled during verified strategy")
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
                raise RuntimeError("run canceled during verified execution")
            self._record_response_token_usage(prepared.run_id, response)
            self.db.append_event(
                run_id=prepared.run_id,
                event_id=str(uuid4()),
                event_type="verification_attempted",
                payload={"attempt": attempt, "output_preview": response.output_text[:200]},
            )
            results = self.verifiers.verify_output(
                response.output_text, verifier_names, context=verification_context,
            )
            all_passed = all(r.passed for r in results)
            error_count = sum(len(r.errors) for r in results)
            if best_response is None or (best_error_count is not None and error_count < best_error_count):
                best_response = response
                best_error_count = error_count
            if all_passed:
                self.db.append_event(
                    run_id=prepared.run_id,
                    event_id=str(uuid4()),
                    event_type="verification_passed",
                    payload={
                        "attempt": attempt,
                        "verifiers": [r.verifier for r in results],
                    },
                )
                return BackendResponse(
                    output_text=response.output_text,
                    metadata={
                        **response.metadata,
                        "strategy": "verified",
                        "attempts": attempt,
                        "verification_quality": "tool-verified",
                    },
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                    total_tokens=response.total_tokens,
                )
            all_errors = []
            for r in results:
                all_errors.extend(r.errors)
            self.db.append_event(
                run_id=prepared.run_id,
                event_id=str(uuid4()),
                event_type="verification_failed",
                payload={
                    "attempt": attempt,
                    "errors": all_errors,
                    "verifiers": [r.verifier for r in results],
                },
            )
            if attempt < max_attempts:
                error_summary = "\n".join(f"- {e}" for e in all_errors)
                retry_prompt = (
                    "Your previous response failed verification.\n"
                    f"Errors:\n{error_summary}\n\n"
                    "Please fix these issues and try again."
                )
                current_request = replace(
                    current_request,
                    system_prompt="\n\n".join(
                        part for part in [current_request.system_prompt, retry_prompt] if part
                    ),
                )
        assert best_response is not None
        return BackendResponse(
            output_text=best_response.output_text,
            metadata={
                **best_response.metadata,
                "strategy": "verified",
                "attempts": max_attempts,
                "verification_quality": "unverified",
            },
            prompt_tokens=best_response.prompt_tokens,
            completion_tokens=best_response.completion_tokens,
            total_tokens=best_response.total_tokens,
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
        on_chunk: Callable[[str], None] | None = None,
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
        if on_chunk and prepared.backend.capabilities().get("streaming"):
            return prepared.backend.run_streaming(prepared.request, on_chunk=on_chunk)
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
        category = run.failure_category or self._classify_failure(error_text)
        recent_events = self.db.list_events(run_id)[-8:]
        event_types = [event["event_type"] for event in recent_events]
        summary = "\n".join(
            [
                f"Goal: {run.goal}",
                f"Category: {category}",
                f"Failure: {error_text}",
                f"Recent events: {', '.join(event_types) if event_types else 'none'}",
                f"Recovery attempts: {run.recovery_attempts}",
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
        if "timed out" in lowered or "timeout" in lowered:
            return "backend_timeout"
        if "connection refused" in lowered or "not set" in lowered or "unknown backend" in lowered or "http" in lowered:
            return "backend_unreachable"
        if "context" in lowered and ("overflow" in lowered or "too long" in lowered or "maximum context" in lowered):
            return "context_overflow"
        if "approval" in lowered and "timeout" in lowered:
            return "approval_timeout"
        if "path" in lowered or "file" in lowered or "workspace" in lowered:
            return "workspace_conflict"
        if "tool" in lowered or "permission" in lowered:
            return "tool_crash"
        return "general_failure"

    def _select_recovery_backend(
        self,
        *,
        goal: str,
        current_backend_name: str,
        strategy_name: str,
        domain: str | None,
    ) -> str | None:
        available = reachable_backend_names(self.backends)
        if current_backend_name in available:
            available.remove(current_backend_name)
        if not available:
            return None
        decision = decide_auto_backend(
            goal,
            strategy_name=strategy_name,
            domain=domain,
            available=available,
        )
        if decision.selected_backend == current_backend_name:
            return None
        return decision.selected_backend

    def _compact_prompt_context(self, prompt_context: str | None) -> str | None:
        if not prompt_context:
            return prompt_context
        compact_limit = 2400
        if len(prompt_context) <= compact_limit:
            return prompt_context
        head = prompt_context[:1200].rstrip()
        tail = prompt_context[-800:].lstrip()
        return "\n\n".join([head, "[... context compacted by Orchestro ...]", tail])

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
                'You may include a "confidence" field (0.0-1.0) in your action JSON to indicate how confident you are in the action.',
                "You may inspect prior tool results in the prompt context.",
                "Before a complex sequence of tool calls, use the think tool to organize your reasoning and plan the steps.",
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
        parent_run_id: str | None = None
        event_type: str | None = None

        if request.target_type == "event":
            with self.db.connect() as conn:
                row = conn.execute(
                    "SELECT run_id, event_type FROM run_events WHERE id = ?",
                    (request.target_id,),
                ).fetchone()
            if row is None:
                raise ValueError(f"event not found: {request.target_id}")
            parent_run_id = row["run_id"]
            event_type = row["event_type"]

        rating_id = str(uuid4())
        self.db.add_rating(
            rating_id=rating_id,
            target_type=request.target_type,
            target_id=request.target_id,
            rating=request.rating,
            note=request.note,
        )

        if request.target_type == "event":
            if parent_run_id is not None and event_type == "tool_result":
                self.db.append_event(
                    run_id=parent_run_id,
                    event_id=str(uuid4()),
                    event_type="step_rated",
                    payload={
                        "rated_event_id": request.target_id,
                        "rating": request.rating,
                        "note": request.note,
                    },
                )
        elif request.target_type == "run":
            run = self.db.get_run(request.target_id)
            if run:
                from orchestro.quality import quality_from_rating
                new_quality = quality_from_rating(request.rating, run.quality_level)
                if new_quality != run.quality_level:
                    self.db.update_run_quality_level(request.target_id, new_quality)
        return rating_id
