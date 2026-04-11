from __future__ import annotations

import json
import os
from fnmatch import fnmatchcase
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from orchestro.models import RunRequest
from orchestro.orchestrator import Orchestro
from orchestro.paths import project_root
from orchestro.approvals import approval_key


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
    expected_backend: str | None = None
    expected_events: list[str] | None = None
    approval_pattern: str | None = None
    operator_note: str | None = None
    operator_note_after_approval: bool = False


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
            expected_backend=item.get("expected_backend"),
            expected_events=item.get("expected_events"),
            approval_pattern=item.get("approval_pattern"),
            operator_note=item.get("operator_note"),
            operator_note_after_approval=bool(item.get("operator_note_after_approval", False)),
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
            benchmark_controls = _BenchmarkControls(app=app, run_id=prepared.run_id, case=case)
            try:
                app.execute_prepared_run(
                    prepared,
                    approve_tool=benchmark_controls.approve_tool,
                    operator_input=benchmark_controls.consume_operator_notes,
                )
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


def compare_benchmark_summaries(left: dict[str, object], right: dict[str, object]) -> dict[str, object]:
    left_results = {item["case_id"]: item for item in left["results"]}
    right_results = {item["case_id"]: item for item in right["results"]}
    case_ids = sorted(set(left_results) | set(right_results))
    case_diffs: list[dict[str, object]] = []
    improved = 0
    regressed = 0
    unchanged = 0
    for case_id in case_ids:
        left_case = left_results.get(case_id)
        right_case = right_results.get(case_id)
        left_pass = bool(left_case["passed"]) if left_case else False
        right_pass = bool(right_case["passed"]) if right_case else False
        if left_case and right_case and left_pass == right_pass:
            outcome = "unchanged"
            unchanged += 1
        elif not left_pass and right_pass:
            outcome = "improved"
            improved += 1
        elif left_pass and not right_pass:
            outcome = "regressed"
            regressed += 1
        else:
            outcome = "changed"
        case_diffs.append(
            {
                "case_id": case_id,
                "outcome": outcome,
                "left_passed": left_pass,
                "right_passed": right_pass,
                "left_status": left_case["status"] if left_case else None,
                "right_status": right_case["status"] if right_case else None,
                "left_reason": left_case["reason"] if left_case else None,
                "right_reason": right_case["reason"] if right_case else None,
            }
        )
    return {
        "left_id": left["id"],
        "right_id": right["id"],
        "left_suite": left["suite_name"],
        "right_suite": right["suite_name"],
        "left_pass_rate": left["pass_rate"],
        "right_pass_rate": right["pass_rate"],
        "delta_pass_rate": round(float(right["pass_rate"]) - float(left["pass_rate"]), 4),
        "improved": improved,
        "regressed": regressed,
        "unchanged": unchanged,
        "cases": case_diffs,
    }


def evaluate_case(
    case: BenchmarkCase,
    run,
    output_text: str,
    events: list[dict[str, object]],
) -> tuple[bool, str]:
    if case.expected_status and (run is None or run.status != case.expected_status):
        actual = run.status if run else "missing"
        return False, f"expected status {case.expected_status!r}, got {actual!r}"
    if case.expected_backend and (run is None or run.backend_name != case.expected_backend):
        actual_backend = run.backend_name if run else "missing"
        return False, f"expected backend {case.expected_backend!r}, got {actual_backend!r}"
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


@dataclass(slots=True)
class _BenchmarkControls:
    app: Orchestro
    run_id: str
    case: BenchmarkCase
    note_queued: bool = False
    note_consumed: bool = False
    approval_seen: bool = False

    def approve_tool(self, tool_name: str, argument: str) -> bool:
        if not self.case.approval_pattern:
            return False
        key = approval_key(tool_name, argument)
        self.app.db.append_event(
            run_id=self.run_id,
            event_id=str(uuid4()),
            event_type="approval_requested",
            payload={"tool": tool_name, "pattern": key, "benchmark_pattern": self.case.approval_pattern},
        )
        self.approval_seen = True
        if self.case.operator_note and self.case.operator_note_after_approval and not self.note_queued:
            self.app.db.append_event(
                run_id=self.run_id,
                event_id=str(uuid4()),
                event_type="operator_input_queued",
                payload={"note": self.case.operator_note, "source": "benchmark"},
            )
            self.note_queued = True
        return fnmatchcase(key, self.case.approval_pattern)

    def consume_operator_notes(self) -> list[str]:
        if not self.case.operator_note or self.note_consumed:
            return []
        if self.case.operator_note_after_approval and not self.approval_seen:
            return []
        if not self.note_queued:
            self.app.db.append_event(
                run_id=self.run_id,
                event_id=str(uuid4()),
                event_type="operator_input_queued",
                payload={"note": self.case.operator_note, "source": "benchmark"},
            )
            self.note_queued = True
        self.note_consumed = True
        return [self.case.operator_note]


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


def run_benchmark_matrix(
    app: Orchestro,
    *,
    suite_path: Path,
    backend_names: list[str],
    strategy_name: str,
    working_directory: Path,
    context_providers: list[str] | None = None,
) -> dict[str, object]:
    summaries: list[dict[str, object]] = []
    for backend_name in backend_names:
        summaries.append(
            run_benchmark_suite(
                app,
                suite_path=suite_path,
                backend_name=backend_name,
                strategy_name=strategy_name,
                working_directory=working_directory,
                context_providers=context_providers,
            )
        )
    ranking = sorted(
        [
            {
                "id": summary["id"],
                "backend_name": summary["backend_name"],
                "strategy_name": summary["strategy_name"],
                "suite_name": summary["suite_name"],
                "pass_rate": summary["pass_rate"],
                "passed": summary["passed"],
                "total": summary["total"],
            }
            for summary in summaries
        ],
        key=lambda item: (-float(item["pass_rate"]), -int(item["passed"]), str(item["backend_name"])),
    )
    return {
        "suite_name": summaries[0]["suite_name"] if summaries else suite_path.stem,
        "strategy_name": strategy_name,
        "backends": backend_names,
        "ranking": ranking,
        "summaries": summaries,
    }
