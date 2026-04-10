from __future__ import annotations

import argparse
import cmd
import shlex
import sys
from pathlib import Path
from uuid import uuid4

from orchestro.db import OrchestroDB
from orchestro.embeddings import build_embedding_provider
from orchestro.facts_file import sync_facts_file
from orchestro.models import RatingRequest, RunRequest
from orchestro.orchestrator import Orchestro
from orchestro.paths import db_path, facts_path


VALID_RATINGS = {"good", "bad", "edit", "skip"}


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

    def default(self, line: str) -> bool | None:
        stripped = line.strip()
        if not stripped:
            return None
        if stripped.startswith("/"):
            return self.onecmd(stripped[1:])
        run_id = self._run_goal(stripped)
        print(f"run: {run_id}")
        _print_run(self.app, run_id)
        return None

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
        return self.app.run(
            RunRequest(
                goal=goal,
                backend_name=self.backend,
                strategy_name=self.strategy,
                working_directory=Path.cwd(),
                metadata={"domain": self.domain} if self.domain else {},
            )
        )


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
