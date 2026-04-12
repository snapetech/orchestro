from __future__ import annotations

import json
import os
from datetime import datetime
from difflib import SequenceMatcher
from fnmatch import fnmatchcase
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from orchestro.models import RunRequest
from orchestro.orchestrator import Orchestro
from orchestro.paths import project_root
from orchestro.approvals import approval_key

if TYPE_CHECKING:
    from orchestro.db import OrchestroDB


def compute_edit_distance(original: str, edited: str) -> float:
    """Return a similarity ratio between 0.0 (completely different) and 1.0 (identical).

    Uses difflib.SequenceMatcher which computes a Levenshtein-like ratio:
    ``1 - (edit_ops / max(len(a), len(b)))``.
    """
    if not original and not edited:
        return 1.0
    return SequenceMatcher(None, original, edited).ratio()


@dataclass(slots=True)
class BenchmarkMetrics:
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    avg_tokens: float = 0.0
    total_tokens: int = 0
    avg_steps: float = 0.0
    tool_call_count: int = 0
    tool_error_count: int = 0
    tool_error_rate: float = 0.0
    verification_attempts: int = 0
    verification_passes: int = 0
    verification_pass_rate: float = 0.0
    recovery_attempts: int = 0
    avg_wall_seconds: float = 0.0
    avg_edit_distance: float = 0.0
    quality_distribution: dict[str, int] = field(default_factory=dict)
    strategy_distribution: dict[str, int] = field(default_factory=dict)


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
    prompt_context: str | None = None
    expected_status: str | None = None
    expected_backend: str | None = None
    expected_events: list[str] | None = None
    expected_failure_category: str | None = None
    min_recovery_attempts: int | None = None
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
            prompt_context=item.get("prompt_context"),
            expected_status=item.get("expected_status"),
            expected_backend=item.get("expected_backend"),
            expected_events=item.get("expected_events"),
            expected_failure_category=item.get("expected_failure_category"),
            min_recovery_attempts=item.get("min_recovery_attempts"),
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
        case_providers = case.providers if case.providers is not None else (context_providers or [
            "instructions",
            "lexical",
            "semantic",
            "corrections",
            "interactions",
            "postmortems",
        ])
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
                    prompt_context=case.prompt_context,
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
    run_ids = [result.run_id for result in results]
    suite_metrics = collect_suite_metrics(app.db, results, run_ids)
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
        "metrics": _metrics_to_dict(suite_metrics),
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
    comparison: dict[str, object] = {
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
    left_metrics = left.get("metrics")
    right_metrics = right.get("metrics")
    if left_metrics and right_metrics:
        comparison["metric_deltas"] = _compute_metric_deltas(left_metrics, right_metrics)
    return comparison


def _compute_metric_deltas(
    left_m: dict[str, object],
    right_m: dict[str, object],
) -> list[dict[str, object]]:
    deltas: list[dict[str, object]] = []
    rate_fields = [
        ("tool_error_rate", "tool error rate", True),
        ("verification_pass_rate", "verification pass rate", False),
        ("avg_edit_distance", "avg edit distance", False),
    ]
    for key, label, lower_is_better in rate_fields:
        lv = float(left_m.get(key, 0))
        rv = float(right_m.get(key, 0))
        diff = rv - lv
        if lower_is_better:
            direction = "improved" if diff < 0 else "regressed" if diff > 0 else "unchanged"
        else:
            direction = "improved" if diff > 0 else "regressed" if diff < 0 else "unchanged"
        deltas.append({
            "metric": label,
            "left": round(lv, 4),
            "right": round(rv, 4),
            "delta": round(diff, 4),
            "direction": direction,
        })
    numeric_fields = [
        ("avg_tokens", "avg tokens", True),
        ("avg_steps", "avg steps", True),
        ("avg_wall_seconds", "avg wall seconds", True),
        ("recovery_attempts", "recovery attempts", True),
        ("total_tokens", "total tokens", True),
    ]
    for key, label, lower_is_better in numeric_fields:
        lv = float(left_m.get(key, 0))
        rv = float(right_m.get(key, 0))
        diff = rv - lv
        if lower_is_better:
            direction = "improved" if diff < 0 else "regressed" if diff > 0 else "unchanged"
        else:
            direction = "improved" if diff > 0 else "regressed" if diff < 0 else "unchanged"
        deltas.append({
            "metric": label,
            "left": round(lv, 2),
            "right": round(rv, 2),
            "delta": round(diff, 2),
            "direction": direction,
        })
    return deltas


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
    if case.expected_failure_category and (run is None or run.failure_category != case.expected_failure_category):
        actual_category = run.failure_category if run else "missing"
        return False, f"expected failure category {case.expected_failure_category!r}, got {actual_category!r}"
    if case.min_recovery_attempts is not None and (run is None or run.recovery_attempts < case.min_recovery_attempts):
        actual_attempts = run.recovery_attempts if run else "missing"
        return False, f"expected recovery attempts >= {case.min_recovery_attempts}, got {actual_attempts!r}"
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


def collect_run_metrics(db: OrchestroDB, run_id: str) -> dict[str, object]:
    events = db.list_events(run_id)
    run = db.get_run(run_id)
    tool_calls = 0
    tool_errors = 0
    verification_attempts = 0
    verification_passes = 0
    recovery_attempts = 0
    context_compactions = 0
    step_count = 0
    for event in events:
        etype = event["event_type"]
        if etype == "tool_called":
            tool_calls += 1
        elif etype == "tool_result":
            if not event.get("payload", {}).get("ok", True):
                tool_errors += 1
        elif etype == "verification_attempted":
            verification_attempts += 1
        elif etype == "verification_passed":
            verification_passes += 1
        elif etype == "recovery_attempted":
            recovery_attempts += 1
        elif etype == "context_compacted":
            context_compactions += 1
        elif etype in {"step_completed", "plan_execute_step_completed"}:
            step_count += 1
    wall_seconds = 0.0
    if run and run.created_at and run.completed_at:
        try:
            t0 = datetime.fromisoformat(run.created_at)
            t1 = datetime.fromisoformat(run.completed_at)
            wall_seconds = max((t1 - t0).total_seconds(), 0.0)
        except (ValueError, TypeError):
            pass
    edit_distances: list[float] = []
    event_ratings = db.list_event_ratings(run_id)
    for entry in event_ratings:
        rating_info = entry.get("rating")
        if rating_info and rating_info.get("note"):
            payload = entry.get("payload", {})
            original = payload.get("output", "") or payload.get("text", "")
            if original:
                edit_distances.append(compute_edit_distance(original, rating_info["note"]))
    corrections = db.list_corrections(query=run_id) if run else []
    for corr in corrections:
        if corr.wrong_answer and corr.right_answer:
            edit_distances.append(compute_edit_distance(corr.wrong_answer, corr.right_answer))
    avg_edit_distance = round(sum(edit_distances) / len(edit_distances), 4) if edit_distances else 0.0

    return {
        "tool_calls": tool_calls,
        "tool_errors": tool_errors,
        "verification_attempts": verification_attempts,
        "verification_passes": verification_passes,
        "recovery_attempts": recovery_attempts,
        "context_compactions": context_compactions,
        "step_count": step_count,
        "prompt_tokens": run.prompt_tokens if run else 0,
        "completion_tokens": run.completion_tokens if run else 0,
        "total_tokens": run.total_tokens if run else 0,
        "quality_level": run.quality_level if run else "unverified",
        "strategy_name": run.strategy_name if run else "",
        "wall_seconds": wall_seconds,
        "status": run.status if run else "missing",
        "avg_edit_distance": avg_edit_distance,
    }


def collect_suite_metrics(
    db: OrchestroDB,
    results: list[BenchmarkResult],
    run_ids: list[str],
) -> BenchmarkMetrics:
    metrics = BenchmarkMetrics()
    metrics.total_cases = len(results)
    metrics.passed_cases = sum(1 for r in results if r.passed)
    metrics.failed_cases = metrics.total_cases - metrics.passed_cases

    total_wall = 0.0
    total_steps = 0
    edit_distance_values: list[float] = []
    for run_id in run_ids:
        rm = collect_run_metrics(db, run_id)
        metrics.tool_call_count += rm["tool_calls"]
        metrics.tool_error_count += rm["tool_errors"]
        metrics.verification_attempts += rm["verification_attempts"]
        metrics.verification_passes += rm["verification_passes"]
        metrics.recovery_attempts += rm["recovery_attempts"]
        metrics.total_tokens += rm["total_tokens"]
        total_wall += rm["wall_seconds"]
        total_steps += rm["step_count"]
        if rm["avg_edit_distance"] > 0:
            edit_distance_values.append(rm["avg_edit_distance"])

        ql = rm["quality_level"]
        metrics.quality_distribution[ql] = metrics.quality_distribution.get(ql, 0) + 1
        sn = rm["strategy_name"]
        if sn:
            metrics.strategy_distribution[sn] = metrics.strategy_distribution.get(sn, 0) + 1

    n = metrics.total_cases or 1
    metrics.avg_tokens = round(metrics.total_tokens / n, 1)
    metrics.avg_steps = round(total_steps / n, 2)
    metrics.avg_wall_seconds = round(total_wall / n, 2)
    metrics.tool_error_rate = round(
        metrics.tool_error_count / metrics.tool_call_count, 4,
    ) if metrics.tool_call_count else 0.0
    metrics.verification_pass_rate = round(
        metrics.verification_passes / metrics.verification_attempts, 4,
    ) if metrics.verification_attempts else 0.0
    metrics.avg_edit_distance = round(
        sum(edit_distance_values) / len(edit_distance_values), 4,
    ) if edit_distance_values else 0.0
    return metrics


def format_metrics_report(metrics: BenchmarkMetrics) -> str:
    pct = lambda v: f"{v * 100:.1f}%"  # noqa: E731
    lines = [
        "benchmark metrics",
        "─" * 40,
        f"  cases       : {metrics.passed_cases}/{metrics.total_cases} passed, {metrics.failed_cases} failed",
        f"  avg tokens  : {metrics.avg_tokens:.0f} (total {metrics.total_tokens})",
        f"  avg steps   : {metrics.avg_steps}",
        f"  avg wall    : {metrics.avg_wall_seconds:.1f}s",
        f"  tool calls  : {metrics.tool_call_count} ({metrics.tool_error_count} errors, {pct(metrics.tool_error_rate)})",
        f"  verification: {metrics.verification_passes}/{metrics.verification_attempts} ({pct(metrics.verification_pass_rate)})",
        f"  recoveries  : {metrics.recovery_attempts}",
        f"  edit dist   : {metrics.avg_edit_distance:.4f}",
    ]
    if metrics.quality_distribution:
        parts = ", ".join(f"{k}={v}" for k, v in sorted(metrics.quality_distribution.items()))
        lines.append(f"  quality     : {parts}")
    if metrics.strategy_distribution:
        parts = ", ".join(f"{k}={v}" for k, v in sorted(metrics.strategy_distribution.items()))
        lines.append(f"  strategies  : {parts}")
    lines.append("─" * 40)
    return "\n".join(lines)


def _metrics_to_dict(metrics: BenchmarkMetrics) -> dict[str, object]:
    return {
        "total_cases": metrics.total_cases,
        "passed_cases": metrics.passed_cases,
        "failed_cases": metrics.failed_cases,
        "avg_tokens": metrics.avg_tokens,
        "total_tokens": metrics.total_tokens,
        "avg_steps": metrics.avg_steps,
        "tool_call_count": metrics.tool_call_count,
        "tool_error_count": metrics.tool_error_count,
        "tool_error_rate": metrics.tool_error_rate,
        "verification_attempts": metrics.verification_attempts,
        "verification_passes": metrics.verification_passes,
        "verification_pass_rate": metrics.verification_pass_rate,
        "recovery_attempts": metrics.recovery_attempts,
        "avg_wall_seconds": metrics.avg_wall_seconds,
        "avg_edit_distance": metrics.avg_edit_distance,
        "quality_distribution": metrics.quality_distribution,
        "strategy_distribution": metrics.strategy_distribution,
    }


def _dict_to_metrics(d: dict[str, object]) -> BenchmarkMetrics:
    return BenchmarkMetrics(
        total_cases=int(d.get("total_cases", 0)),
        passed_cases=int(d.get("passed_cases", 0)),
        failed_cases=int(d.get("failed_cases", 0)),
        avg_tokens=float(d.get("avg_tokens", 0.0)),
        total_tokens=int(d.get("total_tokens", 0)),
        avg_steps=float(d.get("avg_steps", 0.0)),
        tool_call_count=int(d.get("tool_call_count", 0)),
        tool_error_count=int(d.get("tool_error_count", 0)),
        tool_error_rate=float(d.get("tool_error_rate", 0.0)),
        verification_attempts=int(d.get("verification_attempts", 0)),
        verification_passes=int(d.get("verification_passes", 0)),
        verification_pass_rate=float(d.get("verification_pass_rate", 0.0)),
        recovery_attempts=int(d.get("recovery_attempts", 0)),
        avg_wall_seconds=float(d.get("avg_wall_seconds", 0.0)),
        avg_edit_distance=float(d.get("avg_edit_distance", 0.0)),
        quality_distribution=dict(d.get("quality_distribution") or {}),
        strategy_distribution=dict(d.get("strategy_distribution") or {}),
    )


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
