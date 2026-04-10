from __future__ import annotations

import json
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


@dataclass(slots=True)
class BenchmarkResult:
    case_id: str
    passed: bool
    run_id: str
    output_excerpt: str
    reason: str


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
        run_id = app.run(
            RunRequest(
                goal=case.goal,
                backend_name=backend_name,
                strategy_name=strategy_name,
                working_directory=working_directory,
                metadata={
                    "domain": case.domain,
                    "context_providers": context_providers
                    or ["instructions", "lexical", "semantic", "corrections", "interactions"],
                },
            )
        )
        run = app.db.get_run(run_id)
        output_text = (run.final_output or "") if run else ""
        passed, reason = evaluate_case(case, output_text)
        results.append(
            BenchmarkResult(
                case_id=case.id,
                passed=passed,
                run_id=run_id,
                output_excerpt=output_text[:240],
                reason=reason,
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


def evaluate_case(case: BenchmarkCase, output_text: str) -> tuple[bool, str]:
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
