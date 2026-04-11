from __future__ import annotations

import argparse
import cmd
import os
import readline
import shlex
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from orchestro.approvals import ToolApprovalStore, approval_key
from orchestro.db import OrchestroDB
from orchestro.bench import compare_benchmark_summaries, default_benchmark_suite_path, run_benchmark_suite
from orchestro.constitutions import load_constitution_bundle
from orchestro.embeddings import build_embedding_provider
from orchestro.facts_file import sync_facts_file
from orchestro.instructions import load_instruction_bundle
from orchestro.models import RatingRequest, RunRequest
from orchestro.orchestrator import Orchestro
from orchestro.paths import db_path, facts_path, global_instructions_path, tool_approvals_path
from orchestro.planner import build_plan_draft, replan_plan_from_step
from orchestro.tools import ToolRegistry, tool_result_json


VALID_RATINGS = {"good", "bad", "edit", "skip"}
DEFAULT_CONTEXT_PROVIDERS = ["instructions", "lexical", "semantic", "corrections", "interactions", "postmortems"]


@dataclass(slots=True)
class BackgroundJob:
    job_id: str
    thread: threading.Thread
    error: str | None = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orchestro")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask_parser = subparsers.add_parser("ask", help="Run one query through Orchestro.")
    ask_parser.add_argument("goal", help="Prompt or goal to execute.")
    ask_parser.add_argument("--backend", default="auto", help="Backend name.")
    ask_parser.add_argument("--strategy", default="direct", help="Strategy name.")
    ask_parser.add_argument("--cwd", default=str(Path.cwd()), help="Working directory.")
    ask_parser.add_argument("--domain", default=None, help="Optional domain label.")
    ask_parser.add_argument("--providers", default=",".join(DEFAULT_CONTEXT_PROVIDERS), help="Comma-separated context providers.")

    shell_parser = subparsers.add_parser("shell", help="Launch the Orchestro shell.")
    shell_parser.add_argument("--backend", default="auto", help="Default backend.")
    shell_parser.add_argument("--strategy", default="direct", help="Default strategy.")
    shell_parser.add_argument("--domain", default=None, help="Default domain label.")
    shell_parser.add_argument("--providers", default=",".join(DEFAULT_CONTEXT_PROVIDERS), help="Comma-separated default context providers.")

    serve_parser = subparsers.add_parser("serve", help="Run the Orchestro API server.")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8765)

    rate_parser = subparsers.add_parser("rate", help="Rate a run or event.")
    rate_parser.add_argument("target_type", choices=["run", "event"])
    rate_parser.add_argument("target_id")
    rate_parser.add_argument("rating", choices=sorted(VALID_RATINGS))
    rate_parser.add_argument("--note", default=None)

    runs_parser = subparsers.add_parser("runs", help="List recent runs.")
    runs_parser.add_argument("--limit", type=int, default=10)

    plans_parser = subparsers.add_parser("plans", help="List persisted plans.")
    plans_parser.add_argument("--limit", type=int, default=20)

    plan_show_parser = subparsers.add_parser("plan-show", help="Show one persisted plan.")
    plan_show_parser.add_argument("plan_id")

    plan_add_parser = subparsers.add_parser("plan-step-add", help="Insert a plan step after a sequence number.")
    plan_add_parser.add_argument("plan_id")
    plan_add_parser.add_argument("after_sequence_no", type=int)
    plan_add_parser.add_argument("title", nargs="?", default=None)
    plan_add_parser.add_argument("details", nargs="?", default=None)
    plan_add_parser.add_argument("--editor", action="store_true")

    plan_edit_parser = subparsers.add_parser("plan-step-edit", help="Edit an existing plan step.")
    plan_edit_parser.add_argument("plan_id")
    plan_edit_parser.add_argument("sequence_no", type=int)
    plan_edit_parser.add_argument("title", nargs="?", default=None)
    plan_edit_parser.add_argument("details", nargs="?", default=None)
    plan_edit_parser.add_argument("--editor", action="store_true")

    plan_drop_parser = subparsers.add_parser("plan-step-drop", help="Delete one plan step.")
    plan_drop_parser.add_argument("plan_id")
    plan_drop_parser.add_argument("sequence_no", type=int)

    plan_create_parser = subparsers.add_parser("plan-create", help="Create a plan for a goal.")
    plan_create_parser.add_argument("goal")
    plan_create_parser.add_argument("--backend", default="auto")
    plan_create_parser.add_argument("--strategy", default="direct")
    plan_create_parser.add_argument("--cwd", default=str(Path.cwd()))
    plan_create_parser.add_argument("--domain", default=None)

    plan_run_parser = subparsers.add_parser("plan-run", help="Run the current step of a persisted plan.")
    plan_run_parser.add_argument("plan_id")

    bench_parser = subparsers.add_parser("bench", help="Run a benchmark suite.")
    bench_parser.add_argument("--suite", default=str(default_benchmark_suite_path()))
    bench_parser.add_argument("--backend", default="mock")
    bench_parser.add_argument("--strategy", default="direct")
    bench_parser.add_argument("--cwd", default=str(Path.cwd()))
    bench_parser.add_argument("--providers", default=",".join(DEFAULT_CONTEXT_PROVIDERS))

    benchmark_runs_parser = subparsers.add_parser("benchmark-runs", help="List stored benchmark runs.")
    benchmark_runs_parser.add_argument("--limit", type=int, default=20)

    benchmark_compare_parser = subparsers.add_parser("benchmark-compare", help="Compare two stored benchmark runs.")
    benchmark_compare_parser.add_argument("left_id", nargs="?", default=None)
    benchmark_compare_parser.add_argument("right_id", nargs="?", default=None)

    approvals_queue_parser = subparsers.add_parser("approval-requests", help="List pending or resolved approval requests.")
    approvals_queue_parser.add_argument("--status", default="pending")
    approvals_queue_parser.add_argument("--limit", type=int, default=20)

    approve_parser = subparsers.add_parser("approval-resolve", help="Approve or deny one approval request.")
    approve_parser.add_argument("request_id")
    approve_parser.add_argument("decision", choices=["approved", "denied"])
    approve_parser.add_argument("--note", default=None)
    approve_parser.add_argument("--pattern", default=None)

    children_parser = subparsers.add_parser("children", help="List child runs for one parent run.")
    children_parser.add_argument("run_id")
    children_parser.add_argument("--limit", type=int, default=50)

    delegate_parser = subparsers.add_parser("delegate", help="Run a delegated child task under a parent run.")
    delegate_parser.add_argument("parent_run_id")
    delegate_parser.add_argument("goal")
    delegate_parser.add_argument("--backend", default="auto")
    delegate_parser.add_argument("--strategy", default="direct")
    delegate_parser.add_argument("--cwd", default=str(Path.cwd()))
    delegate_parser.add_argument("--domain", default=None)
    delegate_parser.add_argument("--providers", default=",".join(DEFAULT_CONTEXT_PROVIDERS))

    tools_parser = subparsers.add_parser("tools", help="List available local tools.")
    del tools_parser

    tool_approvals_parser = subparsers.add_parser("tool-approvals", help="List stored tool approval patterns.")
    del tool_approvals_parser

    tool_run_parser = subparsers.add_parser("tool-run", help="Run one local tool.")
    tool_run_parser.add_argument("tool_name")
    tool_run_parser.add_argument("argument", nargs="?", default="")
    tool_run_parser.add_argument("--cwd", default=str(Path.cwd()))
    tool_run_parser.add_argument("--approve", action="store_true")

    constitutions_parser = subparsers.add_parser("constitutions-show", help="Show loaded constitution files for a domain.")
    constitutions_parser.add_argument("domain")
    constitutions_parser.add_argument("--cwd", default=str(Path.cwd()))

    instructions_parser = subparsers.add_parser("instructions-show", help="Show loaded Orchestro instruction files.")
    instructions_parser.add_argument("--cwd", default=str(Path.cwd()), help="Working directory to resolve project instructions from.")

    shell_jobs_parser = subparsers.add_parser("shell-jobs", help="List persisted shell jobs.")
    shell_jobs_parser.add_argument("--limit", type=int, default=20)

    shell_job_show_parser = subparsers.add_parser("shell-job-show", help="Show one shell job and its events.")
    shell_job_show_parser.add_argument("job_id")

    shell_job_inject_parser = subparsers.add_parser("shell-job-inject", help="Queue operator input for a shell job.")
    shell_job_inject_parser.add_argument("job_id")
    shell_job_inject_parser.add_argument("note")
    shell_job_inject_parser.add_argument("--resume", action="store_true")
    shell_job_inject_parser.add_argument("--replan", action="store_true")

    plan_step_replan_parser = subparsers.add_parser("plan-step-replan", help="Replan a plan from one step forward.")
    plan_step_replan_parser.add_argument("plan_id")
    plan_step_replan_parser.add_argument("note")
    plan_step_replan_parser.add_argument("--sequence-no", type=int, default=None)

    interactions_parser = subparsers.add_parser("interactions", help="List stored interactions.")
    interactions_parser.add_argument("--limit", type=int, default=10)
    interactions_parser.add_argument("--query", default=None)

    search_parser = subparsers.add_parser("search", help="Search interactions and corrections.")
    search_parser.add_argument("query")
    search_parser.add_argument("--kind", choices=["all", "interactions", "corrections"], default="all")
    search_parser.add_argument("--limit", type=int, default=10)

    semantic_search_parser = subparsers.add_parser("semantic-search", help="Semantic search using stored vectors.")
    semantic_search_parser.add_argument("query")
    semantic_search_parser.add_argument("--kind", choices=["all", "interactions", "corrections"], default="all")
    semantic_search_parser.add_argument("--limit", type=int, default=10)
    semantic_search_parser.add_argument("--provider", choices=["hash", "openai-compat"], default="hash")

    show_parser = subparsers.add_parser("show", help="Show one run and its events.")
    show_parser.add_argument("run_id")

    review_parser = subparsers.add_parser("review", help="Show unrated runs.")
    review_parser.add_argument("--limit", type=int, default=10)

    facts_parser = subparsers.add_parser("facts", help="List stored facts.")
    facts_parser.add_argument("--limit", type=int, default=20)
    facts_parser.add_argument("--key", default=None)

    facts_sync_parser = subparsers.add_parser("facts-sync", help="Write accepted facts to facts.md.")
    del facts_sync_parser

    fact_add_parser = subparsers.add_parser("fact-add", help="Add one accepted fact.")
    fact_add_parser.add_argument("fact_key")
    fact_add_parser.add_argument("fact_value")
    fact_add_parser.add_argument("--source", default=None)

    corrections_parser = subparsers.add_parser("corrections", help="List stored corrections.")
    corrections_parser.add_argument("--limit", type=int, default=20)
    corrections_parser.add_argument("--domain", default=None)
    corrections_parser.add_argument("--query", default=None)

    postmortems_parser = subparsers.add_parser("postmortems", help="List stored failure postmortems.")
    postmortems_parser.add_argument("--limit", type=int, default=20)
    postmortems_parser.add_argument("--domain", default=None)
    postmortems_parser.add_argument("--query", default=None)

    vector_status_parser = subparsers.add_parser("vector-status", help="Show sqlite-vec status.")
    del vector_status_parser

    index_status_parser = subparsers.add_parser("index-status", help="List embedding jobs.")
    index_status_parser.add_argument("--limit", type=int, default=20)
    index_status_parser.add_argument("--source-type", choices=["interaction", "correction"], default=None)
    index_status_parser.add_argument("--status", default=None)

    index_embeddings_parser = subparsers.add_parser("index-embeddings", help="Process pending embedding jobs.")
    index_embeddings_parser.add_argument("--limit", type=int, default=20)
    index_embeddings_parser.add_argument("--provider", choices=["hash", "openai-compat"], default="hash")
    index_embeddings_parser.add_argument("--source-type", choices=["interaction", "correction"], default=None)
    index_embeddings_parser.add_argument("--model-name", default=None, help="Optional job model filter.")

    queue_embeddings_parser = subparsers.add_parser("queue-embeddings", help="Queue embedding jobs for a model.")
    queue_embeddings_parser.add_argument("--model-name", required=True)
    queue_embeddings_parser.add_argument("--source-type", choices=["interaction", "correction"], default=None)

    correction_add_parser = subparsers.add_parser("correction-add", help="Add one correction.")
    correction_add_parser.add_argument("--context", required=True)
    correction_add_parser.add_argument("--wrong", required=True)
    correction_add_parser.add_argument("--right", required=True)
    correction_add_parser.add_argument("--domain", default=None)
    correction_add_parser.add_argument("--severity", default="normal")
    correction_add_parser.add_argument("--source-run-id", default=None)

    return parser


class OrchestroShell(cmd.Cmd):
    intro = "Orchestro shell. Type /help for commands, or enter a prompt to run it."
    prompt = "orchestro> "

    def __init__(self, app: Orchestro, *, backend: str, strategy: str, domain: str | None) -> None:
        super().__init__()
        self.app = app
        self.tool_registry = ToolRegistry()
        self.tool_approvals = ToolApprovalStore(tool_approvals_path())
        self.backend = backend
        self.strategy = strategy
        self.domain = domain
        self.context_providers = list(DEFAULT_CONTEXT_PROVIDERS)
        self.mode = "act"
        self.jobs: dict[str, BackgroundJob] = {}
        self.last_run_id: str | None = None
        self.current_plan_id: str | None = None
        self.prompt = "orchestro[act]> "

    def default(self, line: str) -> bool | None:
        stripped = line.strip()
        if not stripped:
            return None
        if stripped.startswith("/"):
            return self.onecmd(stripped[1:])
        if self.mode == "plan":
            plan_id = self._create_plan(stripped)
            self.current_plan_id = plan_id
            print(f"plan: {plan_id}")
            _print_plan(self.app, plan_id)
            return None
        run_id = self._run_goal(stripped)
        self.last_run_id = run_id
        print(f"run: {run_id}")
        _print_run(self.app, run_id)
        return None

    def do_bg(self, arg: str) -> None:
        goal = arg.strip()
        if not goal:
            print("usage: /bg <goal>")
            return
        job_id = str(uuid4())[:8]

        def worker() -> None:
            try:
                request = self._make_request(goal)
                prepared = self.app.start_run(request)
                self.app.db.attach_shell_job_run(job_id=job_id, run_id=prepared.run_id)
                grace_seconds = _background_dispatch_grace_seconds()
                if grace_seconds > 0:
                    deadline = time.time() + grace_seconds
                    while time.time() < deadline:
                        if self.app.db.is_shell_job_cancel_requested(job_id):
                            break
                        time.sleep(0.01)
                if self.app.db.is_shell_job_cancel_requested(job_id):
                    self.app.db.append_shell_job_event(
                        job_id=job_id,
                        event_id=str(uuid4()),
                        event_type="job_canceled",
                        payload={"reason": "shell job canceled before backend execution"},
                    )
                    self.app.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="run_canceled",
                        payload={"reason": "shell job canceled before backend execution"},
                    )
                    self.app.db.cancel_run(
                        run_id=prepared.run_id,
                        error_message="shell job canceled before backend execution",
                    )
                    self.app.db.update_shell_job(job_id=job_id, status="canceled")
                    return
                self.app.execute_prepared_run(
                    prepared,
                    cancel_requested=lambda: self.app.db.is_shell_job_cancel_requested(job_id),
                    control_state=lambda: self.app.db.get_shell_job_control_state(job_id),
                    approve_tool=lambda tool_name, argument: self._approve_tool_for_job(
                        job_id,
                        prepared.run_id,
                        tool_name,
                        argument,
                    ),
                    operator_input=lambda: self._consume_job_inputs(job_id),
                )
                run = self.app.db.get_run(prepared.run_id)
                if run is not None and run.status == "canceled":
                    self.app.db.append_shell_job_event(
                        job_id=job_id,
                        event_id=str(uuid4()),
                        event_type="job_canceled",
                        payload={"reason": run.error_message or "run canceled"},
                    )
                    self.app.db.update_shell_job(job_id=job_id, status="canceled")
                    return
                if self.app.db.is_shell_job_cancel_requested(job_id):
                    self.app.db.append_shell_job_event(
                        job_id=job_id,
                        event_id=str(uuid4()),
                        event_type="cancel_not_honored",
                        payload={"reason": "cancel was requested during backend execution"},
                    )
                    self.app.db.append_event(
                        run_id=prepared.run_id,
                        event_id=str(uuid4()),
                        event_type="cancel_not_honored",
                        payload={"reason": "cancel was requested during backend execution"},
                    )
                self.app.db.update_shell_job(job_id=job_id, status="done")
                self.app.db.append_shell_job_event(
                    job_id=job_id,
                    event_id=str(uuid4()),
                    event_type="job_completed",
                    payload={"run_id": prepared.run_id},
                )
            except Exception as exc:
                self.jobs[job_id].error = str(exc)
                self.app.db.update_shell_job(job_id=job_id, status="failed", error_message=str(exc))
                self.app.db.append_shell_job_event(
                    job_id=job_id,
                    event_id=str(uuid4()),
                    event_type="job_failed",
                    payload={"error": str(exc)},
                )

        thread = threading.Thread(target=worker, daemon=True, name=f"orchestro-job-{job_id}")
        self.app.db.create_shell_job(
            job_id=job_id,
            goal=goal,
            backend_name=self.backend,
            strategy_name=self.strategy,
            domain=self.domain,
        )
        self.jobs[job_id] = BackgroundJob(job_id=job_id, thread=thread)
        thread.start()
        print(f"job: {job_id}")
        while True:
            job = self.app.db.get_shell_job(job_id)
            if job and job.run_id:
                print(f"run: {job.run_id}")
                break
            if not thread.is_alive():
                break
            time.sleep(0.01)

    def do_jobs(self, arg: str) -> None:
        limit_raw = arg.strip()
        limit = int(limit_raw or "20")
        jobs = self.app.db.list_shell_jobs(limit=limit)
        if not jobs:
            print("no shell jobs")
            return
        for job in jobs:
            print(
                f"{job.id}\t{job.status}\t{job.backend_name}\t{job.strategy_name}\t"
                f"{job.domain or ''}\t{job.control_state}\t{job.run_id or ''}\t{job.goal}"
            )

    def do_children(self, arg: str) -> None:
        target = arg.strip() or (self.last_run_id or "")
        if not target:
            print("usage: /children <run-id>")
            return
        run_id = self._resolve_run_id(target) or target
        children = self.app.db.list_child_runs(run_id, limit=50)
        if not children:
            print("no child runs")
            return
        for child in children:
            print(f"{child.id}\t[{child.status}]\t{child.backend_name}/{child.strategy_name}\t{child.goal}")

    def do_job_show(self, arg: str) -> None:
        token = arg.strip()
        if not token:
            print("usage: /job_show <job-id|run-id>")
            return
        job = self._resolve_job(token)
        if job is None:
            print(f"unknown job or run: {token}")
            return
        _print_shell_job(self.app, job.id)

    def do_wait(self, arg: str) -> None:
        job_id = arg.strip()
        if not job_id:
            print("usage: /wait <job-id>")
            return
        job = self.app.db.get_shell_job(job_id)
        if job is None:
            print(f"unknown job: {job_id}")
            return
        while job.status in {"running", "cancel_requested", "paused"}:
            time.sleep(0.1)
            job = self.app.db.get_shell_job(job_id)
            if job is None:
                print(f"job not found: {job_id}")
                return
        if job.status == "canceled":
            print("job canceled")
        if job.error_message:
            print(f"job failed: {job.error_message}")
        if not job.run_id:
            print("job finished without a run id")
            return
        _print_run(self.app, job.run_id)

    def do_watch(self, arg: str) -> None:
        token = arg.strip()
        if not token:
            print("usage: /watch <job-id|run-id>")
            return
        job = self._resolve_job(token)
        run_id = self._resolve_run_id(token)
        if job is None and run_id is None:
            print(f"unknown job or run: {token}")
            return
        seen_job_events: set[int] = set()
        seen_run_events: set[int] = set()
        while True:
            if job is not None:
                current_job = self.app.db.get_shell_job(job.id)
                if current_job is not None:
                    for event in self.app.db.list_shell_job_events(current_job.id):
                        if event.sequence_no in seen_job_events:
                            continue
                        print(f"job {current_job.id} {event.sequence_no}. {event.event_type} {event.payload}")
                        seen_job_events.add(event.sequence_no)
                    if current_job.run_id and run_id is None:
                        run_id = current_job.run_id
                else:
                    current_job = None
            else:
                current_job = None
            if run_id is not None:
                run = self.app.db.get_run(run_id)
                if run is None:
                    print(f"run not found: {run_id}")
                    return
                for event in self.app.db.list_events(run_id):
                    if event["sequence_no"] in seen_run_events:
                        continue
                    print(f"run {run.id} {event['sequence_no']}. {event['event_type']} {event['payload']}")
                    seen_run_events.add(event["sequence_no"])
                if run.status in {"done", "failed", "canceled"} and (
                    current_job is None or current_job.status in {"done", "failed", "canceled"}
                ):
                    self.last_run_id = run_id
                    return
            elif current_job is not None and current_job.status in {"done", "failed", "canceled"}:
                return
            time.sleep(0.25)

    def do_fg(self, arg: str) -> None:
        run_or_job = arg.strip()
        if not run_or_job:
            print("usage: /fg <job-id|run-id>")
            return
        job = self.app.db.get_shell_job(run_or_job)
        if job is not None:
            if job.status in {"running", "cancel_requested", "paused"}:
                print(f"job {run_or_job} is still active [{job.status}]")
                return
            if job.error_message:
                print(f"job failed: {job.error_message}")
                return
            if not job.run_id:
                print("job finished without a run id")
                return
            _print_run(self.app, job.run_id)
            self.last_run_id = job.run_id
            return
        _print_run(self.app, run_or_job)
        self.last_run_id = run_or_job

    def do_last(self, arg: str) -> None:
        del arg
        if not self.last_run_id:
            print("no last run")
            return
        _print_run(self.app, self.last_run_id)

    def do_retry(self, arg: str) -> None:
        try:
            parts = shlex.split(arg)
        except ValueError as exc:
            print(f"parse error: {exc}")
            return
        target = parts[0] if parts else (self.last_run_id or "")
        if not target:
            print("usage: /retry <job-id|run-id>")
            return
        run_id = self._resolve_run_id(target)
        if run_id is None:
            print(f"unknown job or run: {target}")
            return
        request = self._request_from_run(run_id)
        if request is None:
            print(f"run not found: {run_id}")
            return
        new_run_id = self.app.run(request)
        self.last_run_id = new_run_id
        print(f"run: {new_run_id}")
        _print_run(self.app, new_run_id)

    def do_escalate(self, arg: str) -> None:
        try:
            parts = shlex.split(arg)
        except ValueError as exc:
            print(f"parse error: {exc}")
            return
        target = parts[0] if parts else (self.last_run_id or "")
        backend_override = parts[1] if len(parts) > 1 else None
        if not target:
            print("usage: /escalate <job-id|run-id> [backend]")
            return
        run_id = self._resolve_run_id(target)
        if run_id is None:
            print(f"unknown job or run: {target}")
            return
        request = self._request_from_run(run_id)
        if request is None:
            print(f"run not found: {run_id}")
            return
        request.backend_name = backend_override or self._next_backend(request.backend_name)
        try:
            new_run_id = self.app.run(request)
        except Exception as exc:
            print(f"escalation failed: {exc}")
            return
        self.last_run_id = new_run_id
        print(f"run: {new_run_id}")
        _print_run(self.app, new_run_id)

    def do_cancel(self, arg: str) -> None:
        try:
            parts = shlex.split(arg)
        except ValueError as exc:
            print(f"parse error: {exc}")
            return
        target = parts[0] if parts else ""
        reason = " ".join(parts[1:]) if len(parts) > 1 else None
        if not target:
            print("usage: /cancel <job-id|run-id> [reason]")
            return
        job = self._resolve_job(target)
        if job is None:
            print(f"unknown job or run: {target}")
            return
        if not self.app.db.request_shell_job_cancel(job_id=job.id, reason=reason):
            print(f"job {job.id} is not cancelable")
            return
        if job.run_id:
            self.app.db.append_event(
                run_id=job.run_id,
                event_id=str(uuid4()),
                event_type="cancel_requested",
                payload={"job_id": job.id, "reason": reason},
            )
        print(
            f"cancel requested for job {job.id}"
            " (the current backend call may still finish before the request can be honored)"
        )

    def do_pause(self, arg: str) -> None:
        try:
            parts = shlex.split(arg)
        except ValueError as exc:
            print(f"parse error: {exc}")
            return
        target = parts[0] if parts else ""
        reason = " ".join(parts[1:]) if len(parts) > 1 else None
        if not target:
            print("usage: /pause <job-id|run-id> [reason]")
            return
        job = self._resolve_job(target)
        if job is None:
            print(f"unknown job or run: {target}")
            return
        if not self.app.db.request_shell_job_pause(job_id=job.id, reason=reason):
            print(f"job {job.id} is not pausable")
            return
        self.app.db.update_shell_job(job_id=job.id, status="paused")
        if job.run_id:
            self.app.db.append_event(
                run_id=job.run_id,
                event_id=str(uuid4()),
                event_type="pause_requested",
                payload={"job_id": job.id, "reason": reason},
            )
        print(f"pause requested for job {job.id}")

    def do_resume(self, arg: str) -> None:
        try:
            parts = shlex.split(arg)
        except ValueError as exc:
            print(f"parse error: {exc}")
            return
        target = parts[0] if parts else ""
        reason = " ".join(parts[1:]) if len(parts) > 1 else None
        if not target:
            print("usage: /resume <job-id|run-id> [reason]")
            return
        job = self._resolve_job(target)
        if job is None:
            print(f"unknown job or run: {target}")
            return
        if not self.app.db.request_shell_job_resume(job_id=job.id, reason=reason):
            print(f"job {job.id} is not resumable")
            return
        self.app.db.update_shell_job(job_id=job.id, status="running")
        if job.run_id:
            self.app.db.append_event(
                run_id=job.run_id,
                event_id=str(uuid4()),
                event_type="resume_requested",
                payload={"job_id": job.id, "reason": reason},
            )
        print(f"resume requested for job {job.id}")

    def do_inject(self, arg: str) -> None:
        try:
            parts = shlex.split(arg)
        except ValueError as exc:
            print(f"parse error: {exc}")
            return
        if len(parts) < 2:
            print("usage: /inject <job-id|run-id> [--resume] [--replan] <note>")
            return
        resume = False
        replan = False
        if "--resume" in parts:
            parts.remove("--resume")
            resume = True
        if "--replan" in parts:
            parts.remove("--replan")
            replan = True
        if len(parts) < 2:
            print("usage: /inject <job-id|run-id> [--resume] [--replan] <note>")
            return
        token = parts[0]
        note = " ".join(parts[1:]).strip()
        if not note:
            print("injected note cannot be empty")
            return
        job = self._resolve_job(token)
        if job is None:
            print(f"unknown job or run: {token}")
            return
        self._inject_job_input(job_id=job.id, run_id=job.run_id, note=note, resume=resume, replan=replan)
        print(f"queued operator input for job {job.id}")

    def do_backend(self, arg: str) -> None:
        value = arg.strip()
        if not value:
            print(f"current backend: {self.backend}")
            return
        self.backend = value
        print(f"backend set to {self.backend}")

    def do_context(self, arg: str) -> None:
        value = arg.strip()
        if not value:
            print(f"context providers: {', '.join(self.context_providers)}")
            return
        if value == "reset":
            self.context_providers = list(DEFAULT_CONTEXT_PROVIDERS)
            print(f"context providers reset: {', '.join(self.context_providers)}")
            return
        try:
            providers = _parse_context_providers(value)
        except ValueError as exc:
            print(str(exc))
            return
        self.context_providers = providers
        print(f"context providers set: {', '.join(self.context_providers)}")

    def do_strategy(self, arg: str) -> None:
        value = arg.strip()
        if not value:
            print(f"current strategy: {self.strategy}")
            return
        self.strategy = value
        print(f"strategy set to {self.strategy}")

    def do_domain(self, arg: str) -> None:
        value = arg.strip()
        if not value:
            print(f"current domain: {self.domain or '-'}")
            return
        self.domain = value
        print(f"domain set to {self.domain}")

    def do_backends(self, arg: str) -> None:
        del arg
        for name, caps in self.app.available_backends().items():
            print(f"{name}: {caps}")

    def do_runs(self, arg: str) -> None:
        limit = int(arg.strip() or "10")
        for run in self.app.db.list_runs(limit=limit):
            print(f"{run.id} [{run.status}] {run.backend_name}/{run.strategy_name} {run.goal}")

    def do_mode(self, arg: str) -> None:
        value = arg.strip()
        if not value:
            print(f"current mode: {self.mode}")
            return
        if value not in {"plan", "act"}:
            print("usage: /mode <plan|act>")
            return
        self.mode = value
        self.prompt = f"orchestro[{self.mode}]> "
        print(f"mode set to {self.mode}")

    def do_plan(self, arg: str) -> None:
        goal = arg.strip()
        if not goal:
            if self.current_plan_id:
                _print_plan(self.app, self.current_plan_id)
                return
            print("usage: /plan <goal>")
            return
        plan_id = self._create_plan(goal)
        self.current_plan_id = plan_id
        print(f"plan: {plan_id}")
        _print_plan(self.app, plan_id)

    def do_plans(self, arg: str) -> None:
        limit = int(arg.strip() or "20")
        for plan in self.app.db.list_plans(limit=limit):
            print(
                f"{plan.id}\t{plan.status}\tstep={plan.current_step_no}\t"
                f"{plan.backend_name}\t{plan.domain or ''}\t{plan.goal}"
            )

    def do_plan_show(self, arg: str) -> None:
        plan_id = arg.strip() or self.current_plan_id
        if not plan_id:
            print("usage: /plan_show <plan-id>")
            return
        _print_plan(self.app, plan_id)

    def do_plan_add(self, arg: str) -> None:
        try:
            parts = shlex.split(arg)
        except ValueError as exc:
            print(f"parse error: {exc}")
            return
        if len(parts) < 2:
            print("usage: /plan_add <plan-id> <after-step-no> [title] [details]")
            return
        plan_id = parts[0]
        try:
            after_step_no = int(parts[1])
        except ValueError:
            print("after-step-no must be an integer")
            return
        if len(parts) > 2:
            title = parts[2]
            details = " ".join(parts[3:]) if len(parts) > 3 else None
        else:
            try:
                edited = _edit_plan_step_text(title=None, details=None)
            except ValueError as exc:
                print(str(exc))
                return
            if edited is None:
                print("editor canceled")
                return
            title, details = edited
        new_no = self.app.db.insert_plan_step(
            plan_id=plan_id,
            after_sequence_no=after_step_no,
            title=title,
            details=details,
        )
        self.app.db.append_plan_event(
            plan_id=plan_id,
            event_id=str(uuid4()),
            event_type="step_added",
            payload={"sequence_no": new_no, "title": title},
        )
        _print_plan(self.app, plan_id)

    def do_plan_edit(self, arg: str) -> None:
        try:
            parts = shlex.split(arg)
        except ValueError as exc:
            print(f"parse error: {exc}")
            return
        if len(parts) < 2:
            print("usage: /plan_edit <plan-id> <step-no> [title] [details]")
            return
        plan_id = parts[0]
        try:
            step_no = int(parts[1])
        except ValueError:
            print("step-no must be an integer")
            return
        if len(parts) > 2:
            title = parts[2]
            details = " ".join(parts[3:]) if len(parts) > 3 else None
        else:
            step = next((item for item in self.app.db.list_plan_steps(plan_id) if item.sequence_no == step_no), None)
            if step is None:
                print("plan step not found")
                return
            try:
                edited = _edit_plan_step_text(title=step.title, details=step.details)
            except ValueError as exc:
                print(str(exc))
                return
            if edited is None:
                print("editor canceled")
                return
            title, details = edited
        updated = self.app.db.update_plan_step(
            plan_id=plan_id,
            sequence_no=step_no,
            title=title,
            details=details,
        )
        if not updated:
            print("plan step not found")
            return
        self.app.db.append_plan_event(
            plan_id=plan_id,
            event_id=str(uuid4()),
            event_type="step_edited",
            payload={"sequence_no": step_no, "title": title},
        )
        _print_plan(self.app, plan_id)

    def do_plan_drop(self, arg: str) -> None:
        try:
            parts = shlex.split(arg)
        except ValueError as exc:
            print(f"parse error: {exc}")
            return
        if len(parts) != 2:
            print("usage: /plan_drop <plan-id> <step-no>")
            return
        plan_id = parts[0]
        try:
            step_no = int(parts[1])
        except ValueError:
            print("step-no must be an integer")
            return
        deleted = self.app.db.delete_plan_step(plan_id=plan_id, sequence_no=step_no)
        if not deleted:
            print("plan step not found")
            return
        self.app.db.append_plan_event(
            plan_id=plan_id,
            event_id=str(uuid4()),
            event_type="step_deleted",
            payload={"sequence_no": step_no},
        )
        _print_plan(self.app, plan_id)

    def do_replan(self, arg: str) -> None:
        parts = shlex.split(arg) if arg.strip() else []
        plan_id = parts[0] if parts else (self.current_plan_id or "")
        note = " ".join(parts[1:]) if len(parts) > 1 else None
        if not plan_id:
            print("usage: /replan <plan-id> [note]")
            return
        try:
            replan_plan_from_step(self.app, plan_id=plan_id, note=note)
        except ValueError as exc:
            print(str(exc))
            return
        self.current_plan_id = plan_id
        _print_plan(self.app, plan_id)

    def do_plan_step_replan(self, arg: str) -> None:
        try:
            parts = shlex.split(arg)
        except ValueError as exc:
            print(f"parse error: {exc}")
            return
        if len(parts) < 2:
            print("usage: /plan_step_replan <plan-id> <note> [--sequence-no N]")
            return
        sequence_no: int | None = None
        if "--sequence-no" in parts:
            index = parts.index("--sequence-no")
            if index + 1 >= len(parts):
                print("missing value for --sequence-no")
                return
            try:
                sequence_no = int(parts[index + 1])
            except ValueError:
                print("sequence number must be an integer")
                return
            del parts[index:index + 2]
        if len(parts) < 2:
            print("usage: /plan_step_replan <plan-id> <note> [--sequence-no N]")
            return
        plan_id = parts[0]
        note = " ".join(parts[1:]).strip()
        try:
            replan_plan_from_step(self.app, plan_id=plan_id, note=note, sequence_no=sequence_no)
        except ValueError as exc:
            print(str(exc))
            return
        self.current_plan_id = plan_id
        _print_plan(self.app, plan_id)

    def do_plan_run(self, arg: str) -> None:
        plan_id = arg.strip() or self.current_plan_id
        if not plan_id:
            print("usage: /plan_run <plan-id>")
            return
        result = self._prepare_plan_step_run(plan_id)
        if result is None:
            return
        prepared, step = result
        run_error: Exception | None = None
        try:
            self.app.execute_prepared_run(prepared, approve_tool=self._approve_tool_interactive)
        except Exception as exc:
            run_error = exc
        self._finalize_plan_step_run(plan_id=plan_id, step=step, run_id=prepared.run_id, run_error=run_error)
        print(f"run: {prepared.run_id}")
        _print_run(self.app, prepared.run_id)
        if run_error is not None:
            print(f"plan step failed: {run_error}")

    def do_plan_bg(self, arg: str) -> None:
        plan_id = arg.strip() or self.current_plan_id
        if not plan_id:
            print("usage: /plan_bg <plan-id>")
            return
        result = self._prepare_plan_step_run(plan_id)
        if result is None:
            return
        prepared, step = result
        job_id = str(uuid4())[:8]

        def worker() -> None:
            try:
                self.app.db.attach_shell_job_run(job_id=job_id, run_id=prepared.run_id)
                self.app.execute_prepared_run(
                    prepared,
                    cancel_requested=lambda: self.app.db.is_shell_job_cancel_requested(job_id),
                    control_state=lambda: self.app.db.get_shell_job_control_state(job_id),
                    approve_tool=lambda tool_name, argument: self._approve_tool_for_job(
                        job_id,
                        prepared.run_id,
                        tool_name,
                        argument,
                    ),
                    operator_input=lambda: self._consume_job_inputs(job_id),
                )
                run = self.app.db.get_run(prepared.run_id)
                run_error = None if run is None or run.status == "done" else RuntimeError(run.error_message or run.status)
                self._finalize_plan_step_run(plan_id=plan_id, step=step, run_id=prepared.run_id, run_error=run_error)
                updated_run = self.app.db.get_run(prepared.run_id)
                if updated_run is not None and updated_run.status == "canceled":
                    self.app.db.append_shell_job_event(
                        job_id=job_id,
                        event_id=str(uuid4()),
                        event_type="job_canceled",
                        payload={"reason": updated_run.error_message or "run canceled"},
                    )
                    self.app.db.update_shell_job(job_id=job_id, status="canceled")
                    return
                self.app.db.update_shell_job(job_id=job_id, status="done")
                self.app.db.append_shell_job_event(
                    job_id=job_id,
                    event_id=str(uuid4()),
                    event_type="job_completed",
                    payload={"run_id": prepared.run_id, "plan_id": plan_id, "step_no": step.sequence_no},
                )
            except Exception as exc:
                self.jobs[job_id].error = str(exc)
                self.app.db.update_shell_job(job_id=job_id, status="failed", error_message=str(exc))
                self.app.db.append_shell_job_event(
                    job_id=job_id,
                    event_id=str(uuid4()),
                    event_type="job_failed",
                    payload={"error": str(exc)},
                )

        self.app.db.create_shell_job(
            job_id=job_id,
            goal=f"{prepared.request.goal}",
            backend_name=prepared.request.backend_name,
            strategy_name=prepared.request.strategy_name,
            domain=prepared.request.metadata.get("domain"),
        )
        thread = threading.Thread(target=worker, daemon=True, name=f"orchestro-plan-job-{job_id}")
        self.jobs[job_id] = BackgroundJob(job_id=job_id, thread=thread)
        thread.start()
        print(f"job: {job_id}")
        print(f"run: {prepared.run_id}")

    def _prepare_plan_step_run(self, plan_id: str):
        plan = self.app.db.get_plan(plan_id)
        if plan is None:
            print(f"plan not found: {plan_id}")
            return None
        step = self.app.db.get_current_plan_step(plan_id)
        if step is None:
            print("plan has no remaining step")
            return None
        self.app.db.update_plan_status(plan_id=plan_id, status="in_progress")
        self.app.db.update_plan_step_status(plan_id=plan_id, sequence_no=step.sequence_no, status="in_progress")
        self.app.db.append_plan_event(
            plan_id=plan_id,
            event_id=str(uuid4()),
            event_type="step_started",
            payload={"sequence_no": step.sequence_no, "title": step.title},
        )
        request = RunRequest(
            goal=f"{plan.goal}\n\nCurrent step {step.sequence_no}: {step.title}\n{step.details or ''}".strip(),
            backend_name=plan.backend_name,
            strategy_name=self._plan_step_strategy(plan.strategy_name),
            working_directory=Path(plan.working_directory),
            metadata={
                "domain": plan.domain,
                "plan_id": plan.id,
                "plan_step_no": step.sequence_no,
            },
        )
        prepared = self.app.start_run(request)
        self.app.db.append_event(
            run_id=prepared.run_id,
            event_id=str(uuid4()),
            event_type="plan_step_selected",
            payload={"plan_id": plan.id, "sequence_no": step.sequence_no, "title": step.title},
        )
        self.app.db.append_event(
            run_id=prepared.run_id,
            event_id=str(uuid4()),
            event_type="think",
            payload={
                "mode": "plan-step-execution",
                "notes": (
                    f"Executing plan step {step.sequence_no}: {step.title}. "
                    "Focus on the current step instead of the whole plan."
                ),
            },
        )
        return prepared, step

    def _finalize_plan_step_run(
        self,
        *,
        plan_id: str,
        step,
        run_id: str,
        run_error: Exception | None,
    ) -> None:
        self.last_run_id = run_id
        run = self.app.db.get_run(run_id)
        if run is not None:
            retry_events = [event for event in self.app.db.list_events(run_id) if event["event_type"] == "retry_scheduled"]
            if retry_events:
                self.app.db.append_plan_event(
                    plan_id=plan_id,
                    event_id=str(uuid4()),
                    event_type="step_retried",
                    payload={
                        "sequence_no": step.sequence_no,
                        "run_id": run_id,
                        "retries": len(retry_events),
                    },
                )
        if run and run.status == "done":
            self.app.db.update_plan_step_status(plan_id=plan_id, sequence_no=step.sequence_no, status="done")
            next_step = self.app.db.advance_plan(plan_id)
            if next_step is None:
                self.app.db.update_plan_status(plan_id=plan_id, status="done")
            self.current_plan_id = plan_id
            self.app.db.append_plan_event(
                plan_id=plan_id,
                event_id=str(uuid4()),
                event_type="step_completed",
                payload={"sequence_no": step.sequence_no, "run_id": run_id},
            )
        else:
            self.app.db.update_plan_step_status(plan_id=plan_id, sequence_no=step.sequence_no, status="failed")
            self.app.db.update_plan_status(plan_id=plan_id, status="blocked")
            self.app.db.append_plan_event(
                plan_id=plan_id,
                event_id=str(uuid4()),
                event_type="step_failed",
                payload={"sequence_no": step.sequence_no, "run_id": run_id},
            )
            if run is not None:
                self.app.db.append_event(
                    run_id=run_id,
                    event_id=str(uuid4()),
                    event_type="reflection",
                    payload={
                        "mode": "step-failure",
                        "notes": (
                            f"Plan step {step.sequence_no} did not complete cleanly. "
                            "Review the failed step, inspect the run output, and adjust the plan before retrying."
                        ),
                    },
                )

    def do_instructions(self, arg: str) -> None:
        cwd = Path(arg.strip() or Path.cwd())
        _print_instruction_bundle(cwd)

    def do_constitutions(self, arg: str) -> None:
        try:
            parts = shlex.split(arg)
        except ValueError as exc:
            print(f"parse error: {exc}")
            return
        if not parts:
            print("usage: /constitutions <domain>")
            return
        _print_constitution_bundle(parts[0], Path.cwd())

    def do_bench(self, arg: str) -> None:
        suite_path = Path(arg.strip() or default_benchmark_suite_path())
        summary = run_benchmark_suite(
            self.app,
            suite_path=suite_path,
            backend_name=self.backend,
            strategy_name=self.strategy,
            working_directory=Path.cwd(),
            context_providers=self.context_providers,
        )
        _print_benchmark_summary(summary)

    def do_benchmark_runs(self, arg: str) -> None:
        limit = int(arg.strip() or "20")
        for record in self.app.db.list_benchmark_runs(limit=limit):
            print(
                f"{record.id}\t{record.suite_name}\t{record.backend_name}\t"
                f"{record.strategy_name}\t{record.summary.get('pass_rate')}\t{record.created_at}"
            )

    def do_benchmark_compare(self, arg: str) -> None:
        parts = shlex.split(arg) if arg.strip() else []
        if len(parts) >= 2:
            left_id, right_id = parts[0], parts[1]
            left = self.app.db.get_benchmark_run(left_id)
            right = self.app.db.get_benchmark_run(right_id)
        elif len(parts) == 1:
            right = self.app.db.get_benchmark_run(parts[0])
            if right is None:
                print("benchmark run not found")
                return
            left = self.app.db.find_previous_benchmark_run(
                suite_name=right.suite_name,
                backend_name=right.backend_name,
                strategy_name=right.strategy_name,
                created_before=right.created_at,
            )
        else:
            records = self.app.db.list_benchmark_runs(limit=20)
            if not records:
                print("need at least one benchmark run to compare")
                return
            right = records[0]
            left = self.app.db.find_previous_benchmark_run(
                suite_name=right.suite_name,
                backend_name=right.backend_name,
                strategy_name=right.strategy_name,
                created_before=right.created_at,
            )
        if left is None or right is None:
            print("no comparable benchmark baseline found")
            return
        _print_benchmark_comparison(compare_benchmark_summaries(left.summary, right.summary))

    def do_approval_requests(self, arg: str) -> None:
        status = arg.strip() or "pending"
        if status == "all":
            status = None
        requests = self.app.db.list_approval_requests(status=status, limit=20)
        if not requests:
            print("no approval requests")
            return
        for request in requests:
            print(
                f"{request.id}\t{request.status}\t{request.tool_name}\t"
                f"{request.pattern}\tjob={request.job_id or '-'}\trun={request.run_id or '-'}"
            )

    def do_approve(self, arg: str) -> None:
        try:
            parts = shlex.split(arg)
        except ValueError as exc:
            print(f"parse error: {exc}")
            return
        if len(parts) < 2:
            print("usage: /approve <request-id> <approved|denied> [pattern|note]")
            return
        request_id = parts[0]
        decision = parts[1]
        extra = " ".join(parts[2:]).strip() if len(parts) > 2 else None
        record = self.app.db.get_approval_request(request_id)
        if record is None:
            print("approval request not found")
            return
        note = None
        approved_pattern = record.pattern
        if decision == "approved":
            if extra:
                approved_pattern = extra
            elif sys.stdin.isatty():
                approved_pattern = _input_with_prefill("allow pattern: ", record.pattern).strip() or record.pattern
            self.tool_approvals.remember(approved_pattern)
        else:
            note = extra or None
        if not self.app.db.resolve_approval_request(request_id=request_id, status=decision, resolution_note=note):
            print("approval request already resolved")
            return
        if record.job_id and decision in {"approved", "denied"}:
            self.app.db.request_shell_job_resume(job_id=record.job_id, reason=f"approval {decision}")
        if decision == "approved":
            print(f"{request_id}: approved ({approved_pattern})")
        else:
            print(f"{request_id}: denied")

    def do_tools(self, arg: str) -> None:
        del arg
        for tool in self.tool_registry.list_tools():
            print(f"{tool['name']}\t{tool['approval']}\t{tool['description']}")

    def do_approvals(self, arg: str) -> None:
        del arg
        patterns = self.tool_approvals.load_patterns()
        if not patterns:
            print("no stored approval patterns")
            return
        for pattern in patterns:
            print(pattern)

    def do_tool(self, arg: str) -> None:
        try:
            parts = shlex.split(arg)
        except ValueError as exc:
            print(f"parse error: {exc}")
            return
        if not parts:
            print("usage: /tool <tool-name> [argument]")
            return
        tool_name = parts[0]
        tool_arg = " ".join(parts[1:]) if len(parts) > 1 else ""
        approved = False
        definition = self.tool_registry.get_tool(tool_name)
        if definition is not None and definition.approval == "confirm":
            approved = _prompt_tool_approval(self.tool_approvals, tool_name, tool_arg)
            if not approved:
                print("tool canceled")
                return
        try:
            result = self.tool_registry.run(tool_name, tool_arg, Path.cwd(), approved=approved)
        except PermissionError as exc:
            print(str(exc))
            return
        except Exception as exc:
            print(f"tool failed: {exc}")
            return
        print(tool_result_json(result))

    def do_delegate(self, arg: str) -> None:
        try:
            parts = shlex.split(arg)
        except ValueError as exc:
            print(f"parse error: {exc}")
            return
        if not parts:
            print("usage: /delegate <goal> or /delegate <parent-run-id> <goal>")
            return
        parent_run_id: str | None = self.last_run_id
        goal_parts = parts
        possible_parent = self._resolve_run_id(parts[0]) or (parts[0] if self.app.db.get_run(parts[0]) else None)
        if possible_parent is not None and len(parts) > 1:
            parent_run_id = possible_parent
            goal_parts = parts[1:]
        goal = " ".join(goal_parts).strip()
        if not goal:
            print("delegate goal is required")
            return
        job_id, run_id = self._spawn_background_job(goal, parent_run_id=parent_run_id)
        print(f"job: {job_id}")
        if run_id:
            print(f"run: {run_id}")

    def do_interactions(self, arg: str) -> None:
        query = arg.strip() or None
        for interaction in self.app.db.list_interactions(limit=10, query=query):
            rating = interaction.rating or "-"
            domain = interaction.domain or "-"
            print(
                f"{interaction.id} [{rating}] {interaction.backend_name}/{interaction.strategy_name}/{domain} "
                f"{interaction.query_text}"
            )

    def do_show(self, arg: str) -> None:
        run_id = arg.strip()
        if not run_id:
            print("usage: /show <run_id>")
            return
        _print_run(self.app, run_id)

    def do_rate(self, arg: str) -> None:
        try:
            parts = shlex.split(arg)
        except ValueError as exc:
            print(f"parse error: {exc}")
            return
        if len(parts) < 3:
            print("usage: /rate <run|event> <id> <good|bad|edit|skip> [note]")
            return
        target_type, target_id, rating, *rest = parts
        note = " ".join(rest) if rest else None
        rating_id = self.app.rate(
            RatingRequest(
                target_type=target_type,
                target_id=target_id,
                rating=rating,
                note=note,
            )
        )
        print(f"rating saved: {rating_id}")

    def do_review(self, arg: str) -> None:
        limit = int(arg.strip() or "10")
        unrated = self.app.db.list_unrated_runs(limit=limit)
        for run in unrated:
            print(f"{run.id} [{run.status}] {run.goal}")

    def do_facts(self, arg: str) -> None:
        key = arg.strip() or None
        for fact in self.app.db.list_facts(limit=20, key=key):
            print(f"{fact.id} {fact.fact_key}={fact.fact_value} [{fact.status}]")

    def do_facts_sync(self, arg: str) -> None:
        del arg
        _sync_facts(self.app.db)
        print(f"synced {facts_path()}")

    def do_corrections(self, arg: str) -> None:
        query = arg.strip() or None
        for correction in self.app.db.list_corrections(limit=20, query=query):
            domain = correction.domain or "-"
            print(f"{correction.id} [{domain}/{correction.severity}] {correction.context}")

    def do_postmortems(self, arg: str) -> None:
        query = arg.strip() or None
        for postmortem in self.app.db.list_postmortems(limit=20, query=query):
            domain = postmortem.domain or "-"
            print(f"{postmortem.id} [{domain}/{postmortem.category}] {postmortem.summary}")

    def do_search(self, arg: str) -> None:
        query = arg.strip()
        if not query:
            print("usage: /search <query>")
            return
        for hit in self.app.db.search(query=query, kind="all", limit=10):
            domain = hit.domain or "-"
            print(f"{hit.source_type}:{hit.source_id} [{domain}] {hit.title}")

    def do_vector(self, arg: str) -> None:
        del arg
        print(self.app.db.vector_status())

    def do_index_status(self, arg: str) -> None:
        del arg
        for job in self.app.db.list_embedding_jobs(limit=20):
            print(f"{job.source_type}:{job.source_id} {job.model_name} {job.status}")

    def do_index_embeddings(self, arg: str) -> None:
        provider_name = arg.strip() or "hash"
        try:
            count = _index_embedding_jobs(
                self.app.db,
                provider=provider_name,
                limit=20,
                source_type=None,
                model_name=None,
            )
        except Exception as exc:
            print(f"indexing failed: {exc}")
            return
        print(f"indexed jobs: {count}")

    def do_exit(self, arg: str) -> bool:
        del arg
        return True

    def do_quit(self, arg: str) -> bool:
        del arg
        return True

    def _run_goal(self, goal: str) -> str:
        prepared = self.app.start_run(self._make_request(goal))
        try:
            self.app.execute_prepared_run(prepared, approve_tool=self._approve_tool_interactive)
        except Exception:
            pass
        return prepared.run_id

    def _make_request(self, goal: str) -> RunRequest:
        return RunRequest(
            goal=goal,
            backend_name=self.backend,
            strategy_name=self.strategy,
            working_directory=Path.cwd(),
            metadata={
                **({"domain": self.domain} if self.domain else {}),
                "context_providers": list(self.context_providers),
            },
        )

    def _spawn_background_job(self, goal: str, *, parent_run_id: str | None) -> tuple[str, str | None]:
        job_id = str(uuid4())[:8]

        def worker() -> None:
            try:
                request = self._make_request(goal)
                request.parent_run_id = parent_run_id
                prepared = self.app.start_run(request)
                self.app.db.attach_shell_job_run(job_id=job_id, run_id=prepared.run_id)
                self.app.execute_prepared_run(
                    prepared,
                    cancel_requested=lambda: self.app.db.is_shell_job_cancel_requested(job_id),
                    control_state=lambda: self.app.db.get_shell_job_control_state(job_id),
                    approve_tool=lambda tool_name, argument: self._approve_tool_for_job(
                        job_id,
                        prepared.run_id,
                        tool_name,
                        argument,
                    ),
                    operator_input=lambda: self._consume_job_inputs(job_id),
                )
                run = self.app.db.get_run(prepared.run_id)
                if run is not None and run.status == "canceled":
                    self.app.db.append_shell_job_event(
                        job_id=job_id,
                        event_id=str(uuid4()),
                        event_type="job_canceled",
                        payload={"reason": run.error_message or "run canceled"},
                    )
                    self.app.db.update_shell_job(job_id=job_id, status="canceled")
                    return
                self.app.db.update_shell_job(job_id=job_id, status="done")
                self.app.db.append_shell_job_event(
                    job_id=job_id,
                    event_id=str(uuid4()),
                    event_type="job_completed",
                    payload={"run_id": prepared.run_id},
                )
            except Exception as exc:
                self.jobs[job_id].error = str(exc)
                self.app.db.update_shell_job(job_id=job_id, status="failed", error_message=str(exc))
                self.app.db.append_shell_job_event(
                    job_id=job_id,
                    event_id=str(uuid4()),
                    event_type="job_failed",
                    payload={"error": str(exc)},
                )

        self.app.db.create_shell_job(
            job_id=job_id,
            goal=goal,
            backend_name=self.backend,
            strategy_name=self.strategy,
            domain=self.domain,
        )
        thread = threading.Thread(target=worker, daemon=True, name=f"orchestro-job-{job_id}")
        self.jobs[job_id] = BackgroundJob(job_id=job_id, thread=thread)
        thread.start()
        run_id: str | None = None
        while True:
            job = self.app.db.get_shell_job(job_id)
            if job and job.run_id:
                run_id = job.run_id
                break
            if not thread.is_alive():
                break
            time.sleep(0.01)
        return job_id, run_id

    def _create_plan(self, goal: str) -> str:
        plan_id = str(uuid4())
        draft = build_plan_draft(
            self.app,
            goal=goal,
            backend_name=self.backend,
            strategy_name=self.strategy,
            working_directory=Path.cwd(),
            domain=self.domain,
        )
        self.app.db.create_plan(
            plan_id=plan_id,
            goal=goal,
            backend_name=self.backend,
            strategy_name=self.strategy,
            working_directory=str(Path.cwd()),
            domain=self.domain,
            steps=draft.steps,
        )
        self.app.db.append_plan_event(
            plan_id=plan_id,
            event_id=str(uuid4()),
            event_type="plan_created",
            payload={
                "goal": goal,
                "backend": self.backend,
                "strategy": self.strategy,
                "domain": self.domain,
            },
        )
        self.app.db.append_plan_event(
            plan_id=plan_id,
            event_id=str(uuid4()),
            event_type="think",
            payload={"source": draft.source, "notes": draft.notes},
        )
        return plan_id

    def _approve_tool_interactive(self, tool_name: str, argument: str) -> bool:
        return _prompt_tool_approval(self.tool_approvals, tool_name, argument)

    def _approve_tool_noninteractive(self, tool_name: str, argument: str) -> bool:
        return self.tool_approvals.is_allowed(tool_name, argument)

    def _approve_tool_for_job(self, job_id: str, run_id: str, tool_name: str, argument: str) -> bool:
        if self.tool_approvals.is_allowed(tool_name, argument):
            return True
        pattern = approval_key(tool_name, argument)
        pending = self.app.db.get_pending_approval_request(
            job_id=job_id,
            run_id=run_id,
            tool_name=tool_name,
            argument=argument,
        )
        if pending is None:
            request_id = str(uuid4())
            self.app.db.create_approval_request(
                request_id=request_id,
                job_id=job_id,
                run_id=run_id,
                tool_name=tool_name,
                argument=argument,
                pattern=pattern,
            )
            self.app.db.append_shell_job_event(
                job_id=job_id,
                event_id=str(uuid4()),
                event_type="approval_requested",
                payload={"request_id": request_id, "tool": tool_name, "pattern": pattern},
            )
            self.app.db.append_event(
                run_id=run_id,
                event_id=str(uuid4()),
                event_type="approval_requested",
                payload={"request_id": request_id, "tool": tool_name, "pattern": pattern},
            )
            self.app.db.request_shell_job_pause(job_id=job_id, reason=f"approval pending for {pattern}")
            pending = self.app.db.get_approval_request(request_id)
        while True:
            current = self.app.db.get_approval_request(pending.id)
            if current is None:
                return False
            if current.status == "approved":
                return self.tool_approvals.is_allowed(tool_name, argument)
            if current.status == "denied":
                return False
            if self.app.db.is_shell_job_cancel_requested(job_id):
                return False
            time.sleep(0.2)

    def _consume_job_inputs(self, job_id: str) -> list[str]:
        records = self.app.db.consume_pending_shell_job_inputs(job_id=job_id)
        return [record.input_text for record in records]

    def _inject_job_input(
        self,
        *,
        job_id: str,
        run_id: str | None,
        note: str,
        resume: bool = False,
        replan: bool = False,
    ) -> None:
        input_id = str(uuid4())
        self.app.db.enqueue_shell_job_input(
            input_id=input_id,
            job_id=job_id,
            run_id=run_id,
            input_text=note,
        )
        self.app.db.append_shell_job_event(
            job_id=job_id,
            event_id=str(uuid4()),
            event_type="operator_input_queued",
            payload={"input_id": input_id, "resume": resume, "replan": replan},
        )
        if run_id:
            self.app.db.append_event(
                run_id=run_id,
                event_id=str(uuid4()),
                event_type="operator_input_queued",
                payload={"input_id": input_id, "note": note, "replan": replan},
            )
            if replan:
                self._replan_from_run(run_id=run_id, note=note)
        if resume:
            self.app.db.request_shell_job_resume(job_id=job_id, reason="operator input injected")

    def _replan_from_run(self, *, run_id: str, note: str) -> None:
        run = self.app.db.get_run(run_id)
        if run is None:
            return
        plan_id = run.metadata.get("plan_id")
        step_no = run.metadata.get("plan_step_no")
        if not plan_id:
            return
        try:
            step_sequence_no = int(step_no) if step_no is not None else None
            replan_plan_from_step(self.app, plan_id=plan_id, note=note, sequence_no=step_sequence_no)
            self.app.db.append_event(
                run_id=run_id,
                event_id=str(uuid4()),
                event_type="plan_replanned_from_operator",
                payload={"plan_id": plan_id, "sequence_no": step_sequence_no, "note": note},
            )
        except ValueError:
            return

    def _resolve_run_id(self, token: str) -> str | None:
        job = self.app.db.get_shell_job(token)
        if job is not None:
            return job.run_id
        run = self.app.db.get_run(token)
        if run is not None:
            return token
        return None

    def _resolve_job(self, token: str) -> object | None:
        job = self.app.db.get_shell_job(token)
        if job is not None:
            return job
        run = self.app.db.get_run(token)
        if run is None:
            return None
        return self.app.db.get_shell_job_by_run_id(run.id)

    def _request_from_run(self, run_id: str) -> RunRequest | None:
        run = self.app.db.get_run(run_id)
        if run is None:
            return None
        return RunRequest(
            goal=run.goal,
            backend_name=run.backend_name,
            strategy_name=run.strategy_name,
            working_directory=Path(run.working_directory),
            metadata=run.metadata,
        )

    def _next_backend(self, current_backend: str) -> str:
        order = ["vllm-fast", "vllm-balanced", "vllm-coding", "ollama-amd", "openai-compat", "mock"]
        available = [backend for backend in order if backend in self.app.available_backends()]
        if current_backend not in available:
            return self.backend
        current_index = available.index(current_backend)
        if current_index + 1 < len(available):
            return available[current_index + 1]
        return current_backend

    def _plan_step_strategy(self, strategy_name: str) -> str:
        if strategy_name in {"reflect-retry", "reflect-retry-once", "tool-loop"}:
            return strategy_name
        return "reflect-retry-once"


def _print_run(app: Orchestro, run_id: str) -> None:
    run = app.db.get_run(run_id)
    if run is None:
        print(f"run not found: {run_id}")
        return
    print(f"id: {run.id}")
    print(f"status: {run.status}")
    print(f"backend: {run.backend_name}")
    print(f"strategy: {run.strategy_name}")
    print(f"cwd: {run.working_directory}")
    print(f"goal: {run.goal}")
    if run.error_message:
        print(f"error: {run.error_message}")
    if run.final_output:
        print("output:")
        print(run.final_output)
    events = app.db.list_events(run_id)
    if events:
        print("events:")
        for event in events:
            print(f"  {event['sequence_no']}. {event['event_type']} {event['payload']}")


def _print_shell_job(app: Orchestro, job_id: str) -> None:
    job = app.db.get_shell_job(job_id)
    if job is None:
        print(f"job not found: {job_id}")
        return
    print(f"id: {job.id}")
    print(f"status: {job.status}")
    print(f"backend: {job.backend_name}")
    print(f"strategy: {job.strategy_name}")
    print(f"domain: {job.domain or '-'}")
    print(f"control_state: {job.control_state}")
    print(f"run_id: {job.run_id or '-'}")
    print(f"goal: {job.goal}")
    if job.cancel_requested_at:
        print(f"cancel_requested_at: {job.cancel_requested_at}")
    if job.cancel_reason:
        print(f"cancel_reason: {job.cancel_reason}")
    if job.control_reason:
        print(f"control_reason: {job.control_reason}")
    if job.error_message:
        print(f"error: {job.error_message}")
    events = app.db.list_shell_job_events(job.id)
    if events:
        print("job events:")
        for event in events:
            print(f"  {event.sequence_no}. {event.event_type} {event.payload}")
    inputs = app.db.list_shell_job_inputs(job_id=job.id, limit=20)
    if inputs:
        print("job inputs:")
        for item in inputs:
            print(f"  {item.created_at} [{item.status}] {item.input_text}")


def _print_instruction_bundle(cwd: Path) -> None:
    bundle = load_instruction_bundle(cwd)
    print(f"global_instructions: {global_instructions_path()}")
    print(f"cwd: {cwd.resolve()}")
    if not bundle.sources:
        print("no instruction files loaded")
        return
    for source in bundle.sources:
        print(f"{source.label}: {source.path}")
        print(source.content.strip() or "(empty)")


def _print_constitution_bundle(domain: str, cwd: Path) -> None:
    bundle = load_constitution_bundle(domain, cwd)
    print(f"domain: {domain}")
    print(f"cwd: {cwd.resolve()}")
    if not bundle.sources:
        print("no constitution files loaded")
        return
    for source in bundle.sources:
        print(f"{source.label}: {source.path}")
        print(source.content.strip() or "(empty)")


def _print_plan(app: Orchestro, plan_id: str) -> None:
    plan = app.db.get_plan(plan_id)
    if plan is None:
        print(f"plan not found: {plan_id}")
        return
    print(f"id: {plan.id}")
    print(f"status: {plan.status}")
    print(f"backend: {plan.backend_name}")
    print(f"strategy: {plan.strategy_name}")
    print(f"cwd: {plan.working_directory}")
    print(f"domain: {plan.domain or '-'}")
    print(f"current_step: {plan.current_step_no}")
    print(f"goal: {plan.goal}")
    print("steps:")
    for step in app.db.list_plan_steps(plan.id):
        marker = "->" if step.sequence_no == plan.current_step_no and plan.status != "done" else "  "
        detail = f" | {step.details}" if step.details else ""
        print(f"{marker} {step.sequence_no}. [{step.status}] {step.title}{detail}")
    events = app.db.list_plan_events(plan.id)
    if events:
        print("plan events:")
        for event in events:
            print(f"  {event.sequence_no}. {event.event_type} {event.payload}")


def _print_benchmark_summary(summary: dict[str, object]) -> None:
    print(f"id: {summary['id']}")
    print(f"suite: {summary['suite_name']}")
    print(f"backend: {summary['backend_name']}")
    print(f"strategy: {summary['strategy_name']}")
    print(f"passed: {summary['passed']}/{summary['total']} ({summary['pass_rate']})")
    print("results:")
    for result in summary["results"]:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"  {result['case_id']}: {status} [{result['run_id']}] {result['status']} {result['reason']}")


def _print_benchmark_comparison(comparison: dict[str, object]) -> None:
    print(f"left: {comparison['left_id']} ({comparison['left_suite']}, pass_rate={comparison['left_pass_rate']})")
    print(f"right: {comparison['right_id']} ({comparison['right_suite']}, pass_rate={comparison['right_pass_rate']})")
    print(f"delta_pass_rate: {comparison['delta_pass_rate']}")
    print(f"improved: {comparison['improved']}")
    print(f"regressed: {comparison['regressed']}")
    print(f"unchanged: {comparison['unchanged']}")
    print("cases:")
    for case in comparison["cases"]:
        print(
            f"  {case['case_id']}: {case['outcome']} "
            f"(left={case['left_status']}/{case['left_passed']}, right={case['right_status']}/{case['right_passed']})"
        )


def _prompt_tool_approval(store: ToolApprovalStore, tool_name: str, argument: str) -> bool:
    if store.is_allowed(tool_name, argument):
        return True
    key = approval_key(tool_name, argument)
    while True:
        response = input(
            f"approve tool '{key}'? [y]es/[n]o/[a]lways: "
        ).strip().lower()
        if response in {"y", "yes"}:
            return True
        if response in {"n", "no", ""}:
            return False
        if response in {"a", "always"}:
            pattern = _input_with_prefill(
                "allow all future pattern: ",
                key,
            ).strip()
            if not pattern:
                pattern = key
            store.remember(pattern)
            print(f"stored approval pattern: {pattern}")
            return True
        print("enter y, n, or a")


def _input_with_prefill(prompt: str, text: str) -> str:
    startup = getattr(readline, "set_startup_hook", None)
    if startup is None:
        return input(prompt)
    readline.set_startup_hook(lambda: readline.insert_text(text))
    try:
        return input(prompt)
    finally:
        readline.set_startup_hook(None)


def _edit_plan_step_text(*, title: str | None, details: str | None) -> tuple[str, str | None] | None:
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not editor:
        raise ValueError("VISUAL or EDITOR must be set to edit plan steps interactively")
    template = "\n".join(
        [
            "# First non-comment line becomes the title.",
            "# Remaining non-comment lines become details.",
            title or "",
            "",
            details or "",
        ]
    ).strip("\n") + "\n"
    with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False, encoding="utf-8") as handle:
        path = Path(handle.name)
        handle.write(template)
    try:
        completed = subprocess.run(
            ["bash", "-lc", f"{editor} {shlex.quote(str(path))}"],
            check=False,
        )
        if completed.returncode != 0:
            return None
        content = path.read_text(encoding="utf-8")
    finally:
        path.unlink(missing_ok=True)
    lines = [line for line in content.splitlines() if not line.lstrip().startswith("#")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        raise ValueError("plan step title cannot be empty")
    parsed_title = lines[0].strip()
    parsed_details = "\n".join(lines[1:]).strip() or None
    return parsed_title, parsed_details


def _parse_context_providers(raw: str) -> list[str]:
    allowed = {"instructions", "lexical", "semantic", "corrections", "interactions", "postmortems"}
    providers = [item.strip() for item in raw.split(",") if item.strip()]
    invalid = [item for item in providers if item not in allowed]
    if invalid:
        raise ValueError(f"unknown context providers: {', '.join(invalid)}")
    return providers


def create_app() -> Orchestro:
    return Orchestro(OrchestroDB(db_path()))


def _sync_facts(db: OrchestroDB) -> None:
    sync_facts_file(facts_path(), db.list_facts(limit=5000))


def _index_embedding_jobs(
    db: OrchestroDB,
    *,
    provider: str,
    limit: int,
    source_type: str | None,
    model_name: str | None,
) -> int:
    embedder = build_embedding_provider(provider)
    jobs = db.get_pending_embedding_jobs(limit=limit, source_type=source_type, model_name=model_name)
    count = 0
    for job in jobs:
        try:
            text = db.get_embedding_source_text(source_type=job.source_type, source_id=job.source_id)
            result = embedder.embed(text)
            db.upsert_embedding_vector(
                source_type=job.source_type,
                source_id=job.source_id,
                model_name=result.model_name,
                dimensions=result.dimensions,
                embedding_blob=result.embedding_blob,
            )
            db.mark_embedding_job_status(
                source_type=job.source_type,
                source_id=job.source_id,
                model_name=job.model_name,
                status="indexed",
                error_message=None,
            )
            count += 1
        except Exception as exc:
            db.mark_embedding_job_status(
                source_type=job.source_type,
                source_id=job.source_id,
                model_name=job.model_name,
                status="failed",
                error_message=str(exc),
            )
    return count


def _background_dispatch_grace_seconds() -> float:
    raw = os.environ.get("ORCHESTRO_BG_DISPATCH_GRACE_MS", "150")
    try:
        millis = max(0, int(raw))
    except ValueError:
        millis = 150
    return millis / 1000.0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    app = create_app()
    approvals = ToolApprovalStore(tool_approvals_path())

    if args.command == "ask":
        providers = _parse_context_providers(args.providers)
        prepared = app.start_run(
            RunRequest(
                goal=args.goal,
                backend_name=args.backend,
                strategy_name=args.strategy,
                working_directory=Path(args.cwd),
                metadata={
                    **({"domain": args.domain} if args.domain else {}),
                    "context_providers": providers,
                },
            )
        )
        exit_code = 0
        try:
            app.execute_prepared_run(
                prepared,
                approve_tool=lambda name, argument: _prompt_tool_approval(approvals, name, argument),
            )
        except Exception as exc:
            print(f"run failed: {exc}", file=sys.stderr)
            exit_code = 1
        print(prepared.run_id)
        _print_run(app, prepared.run_id)
        return exit_code

    if args.command == "shell":
        shell = OrchestroShell(
            app,
            backend=args.backend,
            strategy=args.strategy,
            domain=args.domain,
        )
        shell.context_providers = _parse_context_providers(args.providers)
        shell.cmdloop()
        return 0

    if args.command == "serve":
        import uvicorn

        uvicorn.run("orchestro.api:app", host=args.host, port=args.port, reload=False)
        return 0

    if args.command == "rate":
        rating_id = app.rate(
            RatingRequest(
                target_type=args.target_type,
                target_id=args.target_id,
                rating=args.rating,
                note=args.note,
            )
        )
        print(rating_id)
        return 0

    if args.command == "runs":
        for run in app.db.list_runs(limit=args.limit):
            print(f"{run.id}\t{run.status}\t{run.backend_name}\t{run.goal}")
        return 0

    if args.command == "plans":
        for plan in app.db.list_plans(limit=args.limit):
            print(
                f"{plan.id}\t{plan.status}\t{plan.current_step_no}\t"
                f"{plan.backend_name}\t{plan.domain or ''}\t{plan.goal}"
            )
        return 0

    if args.command == "plan-show":
        _print_plan(app, args.plan_id)
        return 0

    if args.command == "plan-step-add":
        try:
            if args.editor or args.title is None:
                edited = _edit_plan_step_text(title=None, details=args.details)
                if edited is None:
                    print("editor canceled")
                    return 1
                title, details = edited
            else:
                title, details = args.title, args.details
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        new_no = app.db.insert_plan_step(
            plan_id=args.plan_id,
            after_sequence_no=args.after_sequence_no,
            title=title,
            details=details,
        )
        app.db.append_plan_event(
            plan_id=args.plan_id,
            event_id=str(uuid4()),
            event_type="step_added",
            payload={"sequence_no": new_no, "title": title},
        )
        _print_plan(app, args.plan_id)
        return 0

    if args.command == "plan-step-edit":
        try:
            if args.editor or args.title is None:
                step = next((item for item in app.db.list_plan_steps(args.plan_id) if item.sequence_no == args.sequence_no), None)
                if step is None:
                    print("plan step not found")
                    return 1
                edited = _edit_plan_step_text(title=step.title, details=step.details)
                if edited is None:
                    print("editor canceled")
                    return 1
                title, details = edited
            else:
                title, details = args.title, args.details
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        updated = app.db.update_plan_step(
            plan_id=args.plan_id,
            sequence_no=args.sequence_no,
            title=title,
            details=details,
        )
        if not updated:
            print("plan step not found")
            return 1
        app.db.append_plan_event(
            plan_id=args.plan_id,
            event_id=str(uuid4()),
            event_type="step_edited",
            payload={"sequence_no": args.sequence_no, "title": title},
        )
        _print_plan(app, args.plan_id)
        return 0

    if args.command == "plan-step-drop":
        deleted = app.db.delete_plan_step(plan_id=args.plan_id, sequence_no=args.sequence_no)
        if not deleted:
            print("plan step not found")
            return 1
        app.db.append_plan_event(
            plan_id=args.plan_id,
            event_id=str(uuid4()),
            event_type="step_deleted",
            payload={"sequence_no": args.sequence_no},
        )
        _print_plan(app, args.plan_id)
        return 0

    if args.command == "plan-create":
        plan_id = str(uuid4())
        draft = build_plan_draft(
            app,
            goal=args.goal,
            backend_name=args.backend,
            strategy_name=args.strategy,
            working_directory=Path(args.cwd),
            domain=args.domain,
        )
        app.db.create_plan(
            plan_id=plan_id,
            goal=args.goal,
            backend_name=args.backend,
            strategy_name=args.strategy,
            working_directory=str(Path(args.cwd).resolve()),
            domain=args.domain,
            steps=draft.steps,
        )
        app.db.append_plan_event(
            plan_id=plan_id,
            event_id=str(uuid4()),
            event_type="plan_created",
            payload={
                "goal": args.goal,
                "backend": args.backend,
                "strategy": args.strategy,
                "domain": args.domain,
            },
        )
        app.db.append_plan_event(
            plan_id=plan_id,
            event_id=str(uuid4()),
            event_type="think",
            payload={"source": draft.source, "notes": draft.notes},
        )
        print(plan_id)
        _print_plan(app, plan_id)
        return 0

    if args.command == "plan-step-replan":
        try:
            replan_plan_from_step(
                app,
                plan_id=args.plan_id,
                note=args.note,
                sequence_no=args.sequence_no,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        _print_plan(app, args.plan_id)
        return 0

    if args.command == "plan-run":
        shell = OrchestroShell(app, backend="mock", strategy="direct", domain=None)
        shell.do_plan_run(args.plan_id)
        return 0

    if args.command == "bench":
        summary = run_benchmark_suite(
            app,
            suite_path=Path(args.suite),
            backend_name=args.backend,
            strategy_name=args.strategy,
            working_directory=Path(args.cwd),
            context_providers=_parse_context_providers(args.providers),
        )
        _print_benchmark_summary(summary)
        return 0

    if args.command == "benchmark-runs":
        for record in app.db.list_benchmark_runs(limit=args.limit):
            print(
                f"{record.id}\t{record.suite_name}\t{record.backend_name}\t"
                f"{record.strategy_name}\t{record.summary.get('pass_rate')}\t{record.created_at}"
            )
        return 0

    if args.command == "benchmark-compare":
        if args.left_id and args.right_id:
            left = app.db.get_benchmark_run(args.left_id)
            right = app.db.get_benchmark_run(args.right_id)
        elif args.left_id:
            right = app.db.get_benchmark_run(args.left_id)
            if right is None:
                print("benchmark run not found")
                return 1
            left = app.db.find_previous_benchmark_run(
                suite_name=right.suite_name,
                backend_name=right.backend_name,
                strategy_name=right.strategy_name,
                created_before=right.created_at,
            )
        else:
            records = app.db.list_benchmark_runs(limit=20)
            if not records:
                print("need at least one benchmark run to compare")
                return 1
            right = records[0]
            left = app.db.find_previous_benchmark_run(
                suite_name=right.suite_name,
                backend_name=right.backend_name,
                strategy_name=right.strategy_name,
                created_before=right.created_at,
            )
        if left is None or right is None:
            print("no comparable benchmark baseline found")
            return 1
        _print_benchmark_comparison(compare_benchmark_summaries(left.summary, right.summary))
        return 0

    if args.command == "approval-requests":
        status = None if args.status == "all" else args.status
        requests = app.db.list_approval_requests(status=status, limit=args.limit)
        if not requests:
            print("no approval requests")
            return 0
        for request in requests:
            print(
                f"{request.id}\t{request.status}\t{request.tool_name}\t{request.pattern}\t"
                f"job={request.job_id or '-'}\trun={request.run_id or '-'}"
            )
        return 0

    if args.command == "approval-resolve":
        record = app.db.get_approval_request(args.request_id)
        if record is None:
            print("approval request not found")
            return 1
        approved_pattern = (args.pattern or record.pattern).strip()
        if args.decision == "approved" and not approved_pattern:
            print("approval pattern cannot be empty")
            return 1
        if args.decision == "approved":
            approvals.remember(approved_pattern)
        if not app.db.resolve_approval_request(
            request_id=args.request_id,
            status=args.decision,
            resolution_note=args.note,
        ):
            print("approval request already resolved")
            return 1
        if record.job_id:
            app.db.request_shell_job_resume(job_id=record.job_id, reason=f"approval {args.decision}")
        if args.decision == "approved":
            print(f"{args.request_id}: approved ({approved_pattern})")
        else:
            print(f"{args.request_id}: denied")
        return 0

    if args.command == "children":
        for run in app.db.list_child_runs(args.run_id, limit=args.limit):
            print(
                f"{run.id}\t{run.status}\t{run.backend_name}\t"
                f"{run.strategy_name}\t{run.goal}"
            )
        return 0

    if args.command == "delegate":
        prepared = app.start_run(
            RunRequest(
                goal=args.goal,
                backend_name=args.backend,
                strategy_name=args.strategy,
                working_directory=Path(args.cwd),
                parent_run_id=args.parent_run_id,
                metadata={
                    **({"domain": args.domain} if args.domain else {}),
                    "context_providers": _parse_context_providers(args.providers),
                    "delegation_depth": 1,
                },
            )
        )
        exit_code = 0
        try:
            app.execute_prepared_run(
                prepared,
                approve_tool=lambda name, argument: _prompt_tool_approval(approvals, name, argument),
            )
        except Exception as exc:
            print(f"delegate failed: {exc}", file=sys.stderr)
            exit_code = 1
        print(prepared.run_id)
        _print_run(app, prepared.run_id)
        return exit_code

    if args.command == "tools":
        for tool in app.tools.list_tools():
            print(f"{tool['name']}\t{tool['approval']}\t{tool['description']}")
        return 0

    if args.command == "tool-approvals":
        patterns = approvals.load_patterns()
        if not patterns:
            print("no stored approval patterns")
            return 0
        for pattern in patterns:
            print(pattern)
        return 0

    if args.command == "tool-run":
        try:
            approved = args.approve or approvals.is_allowed(args.tool_name, args.argument)
            if not approved:
                definition = app.tools.get_tool(args.tool_name)
                if definition is not None and definition.approval == "confirm" and sys.stdin.isatty():
                    approved = _prompt_tool_approval(approvals, args.tool_name, args.argument)
            result = app.tools.run(args.tool_name, args.argument, Path(args.cwd), approved=approved)
        except PermissionError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except Exception as exc:
            print(f"tool failed: {exc}", file=sys.stderr)
            return 1
        print(tool_result_json(result))
        return 0

    if args.command == "constitutions-show":
        _print_constitution_bundle(args.domain, Path(args.cwd))
        return 0

    if args.command == "instructions-show":
        _print_instruction_bundle(Path(args.cwd))
        return 0

    if args.command == "shell-jobs":
        for job in app.db.list_shell_jobs(limit=args.limit):
            print(
                f"{job.id}\t{job.status}\t{job.backend_name}\t{job.strategy_name}\t"
                f"{job.domain or ''}\t{job.control_state}\t{job.run_id or ''}\t{job.goal}"
            )
        return 0

    if args.command == "shell-job-show":
        _print_shell_job(app, args.job_id)
        return 0

    if args.command == "shell-job-inject":
        job = app.db.get_shell_job(args.job_id)
        if job is None:
            print("shell job not found")
            return 1
        input_id = str(uuid4())
        app.db.enqueue_shell_job_input(
            input_id=input_id,
            job_id=job.id,
            run_id=job.run_id,
            input_text=args.note,
        )
        app.db.append_shell_job_event(
            job_id=job.id,
            event_id=str(uuid4()),
            event_type="operator_input_queued",
            payload={"input_id": input_id, "resume": args.resume, "replan": args.replan},
        )
        if job.run_id:
            app.db.append_event(
                run_id=job.run_id,
                event_id=str(uuid4()),
                event_type="operator_input_queued",
                payload={"input_id": input_id, "note": args.note, "replan": args.replan},
            )
            if args.replan:
                run = app.db.get_run(job.run_id)
                if run is not None and run.metadata.get("plan_id"):
                    try:
                        replan_plan_from_step(
                            app,
                            plan_id=run.metadata["plan_id"],
                            note=args.note,
                            sequence_no=int(run.metadata["plan_step_no"]) if run.metadata.get("plan_step_no") is not None else None,
                        )
                        app.db.append_event(
                            run_id=job.run_id,
                            event_id=str(uuid4()),
                            event_type="plan_replanned_from_operator",
                            payload={
                                "plan_id": run.metadata["plan_id"],
                                "sequence_no": run.metadata.get("plan_step_no"),
                                "note": args.note,
                            },
                        )
                    except ValueError:
                        pass
        if args.resume:
            app.db.request_shell_job_resume(job_id=job.id, reason="operator input injected")
        print(input_id)
        return 0

    if args.command == "interactions":
        for interaction in app.db.list_interactions(limit=args.limit, query=args.query):
            rating = interaction.rating or "-"
            domain = interaction.domain or ""
            print(
                f"{interaction.id}\t{rating}\t{interaction.backend_name}\t"
                f"{interaction.strategy_name}\t{domain}\t{interaction.query_text}"
            )
        return 0

    if args.command == "search":
        for hit in app.db.search(query=args.query, kind=args.kind, limit=args.limit):
            print(
                f"{hit.source_type}\t{hit.source_id}\t{hit.domain or ''}\t"
                f"{hit.score:.4f}\t{hit.title}\t{hit.snippet}"
            )
        return 0

    if args.command == "semantic-search":
        embedder = build_embedding_provider(args.provider)
        query_result = embedder.embed(args.query)
        for hit in app.db.semantic_search(
            query_embedding=query_result.embedding_blob,
            model_name=query_result.model_name,
            kind=args.kind,
            limit=args.limit,
        ):
            print(
                f"{hit.source_type}\t{hit.source_id}\t{hit.domain or ''}\t"
                f"{hit.score:.4f}\t{hit.title}\t{hit.snippet}"
            )
        return 0

    if args.command == "show":
        _print_run(app, args.run_id)
        return 0

    if args.command == "review":
        for run in app.db.list_unrated_runs(limit=args.limit):
            print(f"{run.id}\t{run.status}\t{run.backend_name}\t{run.goal}")
        return 0

    if args.command == "facts":
        for fact in app.db.list_facts(limit=args.limit, key=args.key):
            print(f"{fact.id}\t{fact.fact_key}\t{fact.fact_value}\t{fact.status}\t{fact.source or ''}")
        return 0

    if args.command == "fact-add":
        fact_id = str(uuid4())
        app.db.add_fact(
            fact_id=fact_id,
            fact_key=args.fact_key,
            fact_value=args.fact_value,
            source=args.source,
        )
        _sync_facts(app.db)
        print(fact_id)
        return 0

    if args.command == "facts-sync":
        _sync_facts(app.db)
        print(facts_path())
        return 0

    if args.command == "corrections":
        for correction in app.db.list_corrections(
            limit=args.limit,
            domain=args.domain,
            query=args.query,
        ):
            print(
                f"{correction.id}\t{correction.domain or ''}\t{correction.severity}\t"
                f"{correction.context}\t{correction.right_answer}"
            )
        return 0

    if args.command == "postmortems":
        for postmortem in app.db.list_postmortems(
            limit=args.limit,
            domain=args.domain,
            query=args.query,
        ):
            print(
                f"{postmortem.id}\t{postmortem.domain or ''}\t{postmortem.category}\t"
                f"{postmortem.summary}\t{postmortem.error_message}"
            )
        return 0

    if args.command == "vector-status":
        status = app.db.vector_status()
        for key, value in status.items():
            print(f"{key}\t{value}")
        return 0

    if args.command == "index-status":
        for job in app.db.list_embedding_jobs(
            limit=args.limit,
            source_type=args.source_type,
            status=args.status,
        ):
            print(
                f"{job.source_type}\t{job.source_id}\t{job.model_name}\t{job.status}\t"
                f"{job.updated_at}\t{job.error_message or ''}"
            )
        return 0

    if args.command == "index-embeddings":
        indexed = _index_embedding_jobs(
            app.db,
            provider=args.provider,
            limit=args.limit,
            source_type=args.source_type,
            model_name=args.model_name,
        )
        print(indexed)
        return 0

    if args.command == "queue-embeddings":
        queued = app.db.queue_embedding_jobs_for_model(
            model_name=args.model_name,
            source_type=args.source_type,
        )
        print(queued)
        return 0

    if args.command == "correction-add":
        correction_id = str(uuid4())
        app.db.add_correction(
            correction_id=correction_id,
            context=args.context,
            wrong_answer=args.wrong,
            right_answer=args.right,
            domain=args.domain,
            severity=args.severity,
            source_run_id=args.source_run_id,
        )
        print(correction_id)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
