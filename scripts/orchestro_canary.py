#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from orchestro.backend_profiles import list_backend_cooldowns
from orchestro.backends.base import Backend
from orchestro.cli import create_app
from orchestro.models import BackendResponse, RunRequest


class InjectedUsageLimitBackend(Backend):
    def __init__(self, *, name: str, wrapped: Backend, message: str) -> None:
        self.name = name
        self._wrapped = wrapped
        self._message = message

    def run(self, request: RunRequest) -> BackendResponse:
        raise RuntimeError(self._message)

    def capabilities(self) -> dict[str, object]:
        return self._wrapped.capabilities()

    def list_models(self) -> list[str]:
        return self._wrapped.list_models()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an Orchestro daily-driver canary.")
    parser.add_argument("--backend", default="auto", help="Backend name to run, or auto.")
    parser.add_argument("--goal", default="Reply with a short canary acknowledgement.", help="Goal to execute.")
    parser.add_argument("--strategy", default="direct", help="Strategy name.")
    parser.add_argument("--cwd", default=".", help="Working directory.")
    parser.add_argument("--home", default=None, help="Optional ORCHESTRO_HOME override.")
    parser.add_argument(
        "--inject-limit",
        default=None,
        help="Backend name to mark as usage-limited for this canary run.",
    )
    parser.add_argument(
        "--inject-limit-message",
        default="You've hit your usage limit. Monthly cycle ends on 4/29/2026.",
        help="Error text used with --inject-limit.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.home:
        os.environ["ORCHESTRO_HOME"] = str(Path(args.home).expanduser())

    app = create_app()
    if args.inject_limit:
        if args.inject_limit not in app.backends:
            print(f"unknown backend for --inject-limit: {args.inject_limit}", file=sys.stderr)
            return 2
        app.backends[args.inject_limit] = InjectedUsageLimitBackend(
            name=args.inject_limit,
            wrapped=app.backends[args.inject_limit],
            message=args.inject_limit_message,
        )

    cwd = Path(args.cwd).resolve()
    statuses_before = app.backend_statuses()
    tool_result = app.tools.run("pwd", "", cwd)

    prepared = app.start_run(
        RunRequest(
            goal=args.goal,
            backend_name=args.backend,
            strategy_name=args.strategy,
            working_directory=cwd,
        )
    )

    exit_code = 0
    error_message = None
    try:
        app.execute_prepared_run(prepared)
    except Exception as exc:  # pragma: no cover - canary is intended for manual execution
        error_message = str(exc)
        exit_code = 1

    run = app.db.get_run(prepared.run_id)
    events = app.db.list_events(prepared.run_id)
    event_types = [event["event_type"] for event in events]
    auto_route = next((event["payload"] for event in events if event["event_type"] == "backend_auto_routed"), None)
    reroute = [event["payload"] for event in events if event["event_type"] == "backend_auto_rerouted"]
    cooldowns = {
        name: {
            "reason": cooldown.reason,
            "unavailable_until": cooldown.unavailable_until,
        }
        for name, cooldown in list_backend_cooldowns().items()
    }

    payload = {
        "ok": exit_code == 0 and run is not None and run.status == "done",
        "run_id": prepared.run_id,
        "backend": args.backend,
        "goal": args.goal,
        "status_before": statuses_before,
        "tool_check": {
            "ok": tool_result.ok,
            "output": tool_result.output,
            "metadata": tool_result.metadata,
        },
        "run": {
            "status": run.status if run else None,
            "backend_name": run.backend_name if run else None,
            "final_output": run.final_output if run else None,
            "error_message": run.error_message if run else error_message,
        },
        "events": {
            "types": event_types,
            "auto_route": auto_route,
            "reroutes": reroute,
        },
        "cooldowns": cooldowns,
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"ok: {payload['ok']}")
        print(f"run_id: {prepared.run_id}")
        print(f"tool_check: {tool_result.output}")
        print(f"run_status: {payload['run']['status']}")
        if auto_route:
            print(
                "auto_route: "
                f"{auto_route.get('selected_backend')} "
                f"reason={auto_route.get('reason')} "
                f"model={auto_route.get('selected_model') or '-'}"
            )
        for reroute_payload in reroute:
            print(
                "reroute: "
                f"{reroute_payload.get('from_backend')} -> {reroute_payload.get('to_backend')} "
                f"until={reroute_payload.get('unavailable_until')}"
            )
        if payload["run"]["error_message"]:
            print(f"error: {payload['run']['error_message']}")
        if cooldowns:
            print(f"cooldowns: {json.dumps(cooldowns, sort_keys=True)}")
        final_output = payload["run"]["final_output"]
        if final_output:
            print("final_output:")
            print(final_output)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
