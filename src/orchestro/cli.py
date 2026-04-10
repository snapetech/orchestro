from __future__ import annotations

import argparse
import cmd
import shlex
import sys
from pathlib import Path

from orchestro.db import OrchestroDB
from orchestro.models import RatingRequest, RunRequest
from orchestro.orchestrator import Orchestro
from orchestro.paths import db_path


VALID_RATINGS = {"good", "bad", "edit", "skip"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orchestro")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask_parser = subparsers.add_parser("ask", help="Run one query through Orchestro.")
    ask_parser.add_argument("goal", help="Prompt or goal to execute.")
    ask_parser.add_argument("--backend", default="mock", help="Backend name.")
    ask_parser.add_argument("--strategy", default="direct", help="Strategy name.")
    ask_parser.add_argument("--cwd", default=str(Path.cwd()), help="Working directory.")

    shell_parser = subparsers.add_parser("shell", help="Launch the Orchestro shell.")
    shell_parser.add_argument("--backend", default="mock", help="Default backend.")
    shell_parser.add_argument("--strategy", default="direct", help="Default strategy.")

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

    show_parser = subparsers.add_parser("show", help="Show one run and its events.")
    show_parser.add_argument("run_id")

    review_parser = subparsers.add_parser("review", help="Show unrated runs.")
    review_parser.add_argument("--limit", type=int, default=10)

    return parser


class OrchestroShell(cmd.Cmd):
    intro = "Orchestro shell. Type /help for commands, or enter a prompt to run it."
    prompt = "orchestro> "

    def __init__(self, app: Orchestro, *, backend: str, strategy: str) -> None:
        super().__init__()
        self.app = app
        self.backend = backend
        self.strategy = strategy

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

    def do_backends(self, arg: str) -> None:
        del arg
        for name, caps in self.app.available_backends().items():
            print(f"{name}: {caps}")

    def do_runs(self, arg: str) -> None:
        limit = int(arg.strip() or "10")
        for run in self.app.db.list_runs(limit=limit):
            print(f"{run.id} [{run.status}] {run.backend_name}/{run.strategy_name} {run.goal}")

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
            )
        )
        print(run_id)
        _print_run(app, run_id)
        return 0

    if args.command == "shell":
        OrchestroShell(app, backend=args.backend, strategy=args.strategy).cmdloop()
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

    if args.command == "show":
        _print_run(app, args.run_id)
        return 0

    if args.command == "review":
        for run in app.db.list_unrated_runs(limit=args.limit):
            print(f"{run.id}\t{run.status}\t{run.backend_name}\t{run.goal}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
