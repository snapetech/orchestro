from __future__ import annotations

import argparse
import cmd
import os
import shlex
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from orchestro.db import OrchestroDB
from orchestro.embeddings import build_embedding_provider
from orchestro.facts_file import sync_facts_file
from orchestro.instructions import load_instruction_bundle
from orchestro.models import RatingRequest, RunRequest
from orchestro.orchestrator import Orchestro
from orchestro.paths import db_path, facts_path, global_instructions_path
from orchestro.planner import build_plan_draft


VALID_RATINGS = {"good", "bad", "edit", "skip"}


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
    ask_parser.add_argument("--backend", default="mock", help="Backend name.")
    ask_parser.add_argument("--strategy", default="direct", help="Strategy name.")
    ask_parser.add_argument("--cwd", default=str(Path.cwd()), help="Working directory.")
    ask_parser.add_argument("--domain", default=None, help="Optional domain label.")

    shell_parser = subparsers.add_parser("shell", help="Launch the Orchestro shell.")
    shell_parser.add_argument("--backend", default="mock", help="Default backend.")
    shell_parser.add_argument("--strategy", default="direct", help="Default strategy.")
    shell_parser.add_argument("--domain", default=None, help="Default domain label.")

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

    plan_create_parser = subparsers.add_parser("plan-create", help="Create a plan for a goal.")
    plan_create_parser.add_argument("goal")
    plan_create_parser.add_argument("--backend", default="mock")
    plan_create_parser.add_argument("--strategy", default="direct")
    plan_create_parser.add_argument("--cwd", default=str(Path.cwd()))
    plan_create_parser.add_argument("--domain", default=None)

    instructions_parser = subparsers.add_parser("instructions-show", help="Show loaded Orchestro instruction files.")
    instructions_parser.add_argument("--cwd", default=str(Path.cwd()), help="Working directory to resolve project instructions from.")

    shell_jobs_parser = subparsers.add_parser("shell-jobs", help="List persisted shell jobs.")
    shell_jobs_parser.add_argument("--limit", type=int, default=20)

    shell_job_show_parser = subparsers.add_parser("shell-job-show", help="Show one shell job and its events.")
    shell_job_show_parser.add_argument("job_id")

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
        self.backend = backend
        self.strategy = strategy
        self.domain = domain
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

    def do_backend(self, arg: str) -> None:
        value = arg.strip()
        if not value:
            print(f"current backend: {self.backend}")
            return
        self.backend = value
        print(f"backend set to {self.backend}")

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

    def do_plan_run(self, arg: str) -> None:
        plan_id = arg.strip() or self.current_plan_id
        if not plan_id:
            print("usage: /plan_run <plan-id>")
            return
        plan = self.app.db.get_plan(plan_id)
        if plan is None:
            print(f"plan not found: {plan_id}")
            return
        step = self.app.db.get_current_plan_step(plan_id)
        if step is None:
            print("plan has no remaining step")
            return
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
        run_error: Exception | None = None
        try:
            self.app.execute_prepared_run(prepared)
        except Exception as exc:
            run_error = exc
        self.last_run_id = prepared.run_id
        run = self.app.db.get_run(prepared.run_id)
        if run is not None:
            retry_events = [event for event in self.app.db.list_events(prepared.run_id) if event["event_type"] == "retry_scheduled"]
            if retry_events:
                self.app.db.append_plan_event(
                    plan_id=plan_id,
                    event_id=str(uuid4()),
                    event_type="step_retried",
                    payload={
                        "sequence_no": step.sequence_no,
                        "run_id": prepared.run_id,
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
                payload={"sequence_no": step.sequence_no, "run_id": prepared.run_id},
            )
        else:
            self.app.db.update_plan_step_status(plan_id=plan_id, sequence_no=step.sequence_no, status="failed")
            self.app.db.update_plan_status(plan_id=plan_id, status="blocked")
            self.app.db.append_plan_event(
                plan_id=plan_id,
                event_id=str(uuid4()),
                event_type="step_failed",
                payload={"sequence_no": step.sequence_no, "run_id": prepared.run_id},
            )
            if run is not None:
                self.app.db.append_event(
                    run_id=prepared.run_id,
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
        print(f"run: {prepared.run_id}")
        _print_run(self.app, prepared.run_id)
        if run_error is not None:
            print(f"plan step failed: {run_error}")

    def do_instructions(self, arg: str) -> None:
        cwd = Path(arg.strip() or Path.cwd())
        _print_instruction_bundle(cwd)

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
        return self.app.run(self._make_request(goal))

    def _make_request(self, goal: str) -> RunRequest:
        return RunRequest(
            goal=goal,
            backend_name=self.backend,
            strategy_name=self.strategy,
            working_directory=Path.cwd(),
            metadata={"domain": self.domain} if self.domain else {},
        )

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
        order = ["mock", "openai-compat"]
        available = [backend for backend in order if backend in self.app.available_backends()]
        if current_backend not in available:
            return self.backend
        current_index = available.index(current_backend)
        if current_index + 1 < len(available):
            return available[current_index + 1]
        return current_backend

    def _plan_step_strategy(self, strategy_name: str) -> str:
        if strategy_name in {"reflect-retry", "reflect-retry-once"}:
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

    if args.command == "ask":
        run_id = app.run(
            RunRequest(
                goal=args.goal,
                backend_name=args.backend,
                strategy_name=args.strategy,
                working_directory=Path(args.cwd),
                metadata={"domain": args.domain} if args.domain else {},
            )
        )
        print(run_id)
        _print_run(app, run_id)
        return 0

    if args.command == "shell":
        OrchestroShell(
            app,
            backend=args.backend,
            strategy=args.strategy,
            domain=args.domain,
        ).cmdloop()
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
