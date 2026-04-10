from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from orchestro.models import RunRequest
from orchestro.orchestrator import Orchestro
from orchestro.paths import project_root


@dataclass(slots=True)
class BenchmarkCase:
    id: str
    goal: str
    match: str
    expected: str
    domain: str | None = None
    backend_name: str | None = None
    strategy_name: str | None = None
    providers: list[str] | None = None
    env: dict[str, str] | None = None
    expected_status: str | None = None
    expected_events: list[str] | None = None


@dataclass(slots=True)
class BenchmarkResult:
    case_id: str
    passed: bool
    run_id: str
    output_excerpt: str
    reason: str
    status: str


def default_benchmark_suite_path() -> Path:
    return project_root() / "benchmarks" / "default.json"


def load_benchmark_cases(path: Path) -> tuple[str, list[BenchmarkCase]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    suite_name = str(payload.get("suite", path.stem))
    cases = [
        BenchmarkCase(
            id=item["id"],
            goal=item["goal"],
            match=item["match"],
            expected=item["expected"],
            domain=item.get("domain"),
            backend_name=item.get("backend"),
            strategy_name=item.get("strategy"),
            providers=item.get("providers"),
            env=item.get("env"),
            expected_status=item.get("expected_status"),
            expected_events=item.get("expected_events"),
        )
        for item in payload.get("cases", [])
    ]
    return suite_name, cases


def run_benchmark_suite(
    app: Orchestro,
    *,
    suite_path: Path,
    backend_name: str,
    strategy_name: str,
    working_directory: Path,
    context_providers: list[str] | None = None,
) -> dict[str, object]:
    suite_name, cases = load_benchmark_cases(suite_path)
    results: list[BenchmarkResult] = []
    for case in cases:
        case_backend = case.backend_name or backend_name
        case_strategy = case.strategy_name or strategy_name
        case_providers = case.providers or context_providers or [
            "instructions",
            "lexical",
            "semantic",
            "corrections",
            "interactions",
            "postmortems",
        ]
        with temporary_env(case.env):
            prepared = app.start_run(
                RunRequest(
                    goal=case.goal,
                    backend_name=case_backend,
                    strategy_name=case_strategy,
                    working_directory=working_directory,
                    metadata={
                        "domain": case.domain,
                        "context_providers": case_providers,
                    },
                )
            )
            try:
                app.execute_prepared_run(prepared)
            except Exception:
                pass
        run_id = prepared.run_id
        run = app.db.get_run(run_id)
        output_text = (run.final_output or "") if run else ""
        events = app.db.list_events(run_id)
        passed, reason = evaluate_case(case, run, output_text, events)
        results.append(
            BenchmarkResult(
                case_id=case.id,
                passed=passed,
                run_id=run_id,
                output_excerpt=output_text[:240],
                reason=reason,
                status=run.status if run else "missing",
            )
        )
    passed_count = sum(1 for result in results if result.passed)
    summary = {
        "id": str(uuid4()),
        "suite_name": suite_name,
        "suite_path": str(suite_path),
        "backend_name": backend_name,
        "strategy_name": strategy_name,
        "total": len(results),
        "passed": passed_count,
        "failed": len(results) - passed_count,
        "pass_rate": 0 if not results else round(passed_count / len(results), 4),
        "results": [
            {
                "case_id": result.case_id,
                "passed": result.passed,
                "run_id": result.run_id,
                "output_excerpt": result.output_excerpt,
                "reason": result.reason,
                "status": result.status,
            }
            for result in results
        ],
    }
    app.db.add_benchmark_run(
        benchmark_run_id=summary["id"],
        suite_name=suite_name,
        backend_name=backend_name,
        strategy_name=strategy_name,
        summary=summary,
    )
    return summary


def evaluate_case(
    case: BenchmarkCase,
    run,
    output_text: str,
    events: list[dict[str, object]],
) -> tuple[bool, str]:
    if case.expected_status and (run is None or run.status != case.expected_status):
        actual = run.status if run else "missing"
        return False, f"expected status {case.expected_status!r}, got {actual!r}"
    if case.expected_events:
        seen = {str(event["event_type"]) for event in events}
        missing = [event_type for event_type in case.expected_events if event_type not in seen]
        if missing:
            return False, f"missing events: {', '.join(missing)}"
    match = case.match
    if match == "contains":
        passed = case.expected in output_text
        return passed, f"expected substring {case.expected!r}"
    if match == "not_contains":
        passed = case.expected not in output_text
        return passed, f"forbid substring {case.expected!r}"
    if match == "equals":
        passed = output_text.strip() == case.expected.strip()
        return passed, "expected exact normalized equality"
    raise ValueError(f"unsupported benchmark match type: {match}")


@contextmanager
def temporary_env(env: dict[str, str] | None):
    if not env:
        yield
        return
    previous: dict[str, str | None] = {key: os.environ.get(key) for key in env}
    try:
        for key, value in env.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
