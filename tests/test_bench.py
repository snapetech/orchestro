from __future__ import annotations

import json
from pathlib import Path

import pytest

from orchestro.bench import (
    BenchmarkCase,
    BenchmarkMetrics,
    compare_benchmark_summaries,
    compute_edit_distance,
    evaluate_case,
    load_benchmark_cases,
)


# ---------------------------------------------------------------------------
# compute_edit_distance
# ---------------------------------------------------------------------------

class TestComputeEditDistance:
    def test_identical_strings(self):
        assert compute_edit_distance("hello", "hello") == 1.0

    def test_completely_different(self):
        ratio = compute_edit_distance("abc", "xyz")
        assert 0.0 <= ratio < 1.0

    def test_both_empty(self):
        assert compute_edit_distance("", "") == 1.0

    def test_one_empty(self):
        ratio = compute_edit_distance("hello", "")
        assert 0.0 <= ratio < 1.0

    def test_partial_similarity(self):
        ratio = compute_edit_distance("hello world", "hello earth")
        assert 0.0 < ratio < 1.0

    def test_returns_float(self):
        result = compute_edit_distance("a", "b")
        assert isinstance(result, float)

    def test_symmetry(self):
        a = "foo bar baz"
        b = "foo quux baz"
        assert compute_edit_distance(a, b) == compute_edit_distance(b, a)

    def test_range_is_zero_to_one(self):
        for a, b in [("x", "y"), ("abc", "abc"), ("long text here", "short")]:
            r = compute_edit_distance(a, b)
            assert 0.0 <= r <= 1.0


# ---------------------------------------------------------------------------
# BenchmarkMetrics
# ---------------------------------------------------------------------------

class TestBenchmarkMetrics:
    def test_default_values(self):
        m = BenchmarkMetrics()
        assert m.total_cases == 0
        assert m.passed_cases == 0
        assert m.failed_cases == 0
        assert m.avg_tokens == 0.0
        assert m.tool_error_rate == 0.0
        assert m.quality_distribution == {}
        assert m.strategy_distribution == {}

    def test_can_set_fields(self):
        m = BenchmarkMetrics(total_cases=10, passed_cases=7)
        assert m.total_cases == 10
        assert m.passed_cases == 7


# ---------------------------------------------------------------------------
# BenchmarkCase
# ---------------------------------------------------------------------------

class TestBenchmarkCase:
    def test_required_fields(self):
        case = BenchmarkCase(id="c1", goal="Do X", match="contains", expected="result")
        assert case.id == "c1"
        assert case.goal == "Do X"
        assert case.match == "contains"
        assert case.expected == "result"

    def test_optional_fields_default_none(self):
        case = BenchmarkCase(id="c1", goal="g", match="m", expected="e")
        assert case.domain is None
        assert case.backend_name is None
        assert case.strategy_name is None
        assert case.providers is None
        assert case.env is None
        assert case.expected_status is None
        assert case.expected_backend is None
        assert case.expected_events is None
        assert case.expected_failure_category is None
        assert case.min_recovery_attempts is None
        assert case.approval_pattern is None
        assert case.operator_note is None
        assert case.operator_note_after_approval is False

    def test_full_case(self):
        case = BenchmarkCase(
            id="c2",
            goal="Build it",
            match="contains",
            expected="done",
            domain="coding",
            backend_name="mock",
            strategy_name="direct",
            providers=["lexical"],
            env={"KEY": "VAL"},
            expected_status="completed",
            expected_backend="mock",
            expected_events=["step_completed"],
            expected_failure_category=None,
            min_recovery_attempts=1,
            approval_pattern="*",
            operator_note="Note",
            operator_note_after_approval=True,
        )
        assert case.domain == "coding"
        assert case.env == {"KEY": "VAL"}
        assert case.expected_events == ["step_completed"]
        assert case.operator_note_after_approval is True


# ---------------------------------------------------------------------------
# load_benchmark_cases
# ---------------------------------------------------------------------------

class TestLoadBenchmarkCases:
    def _write_suite(self, tmp_path: Path, payload: dict) -> Path:
        p = tmp_path / "suite.json"
        p.write_text(json.dumps(payload), encoding="utf-8")
        return p

    def test_returns_suite_name_and_cases(self, tmp_path: Path):
        payload = {
            "suite": "My Suite",
            "cases": [
                {"id": "c1", "goal": "Do X", "match": "contains", "expected": "X"},
            ],
        }
        p = self._write_suite(tmp_path, payload)
        name, cases = load_benchmark_cases(p)
        assert name == "My Suite"
        assert len(cases) == 1
        assert cases[0].id == "c1"

    def test_suite_name_defaults_to_stem(self, tmp_path: Path):
        payload = {"cases": []}
        p = self._write_suite(tmp_path, payload)
        name, cases = load_benchmark_cases(p)
        assert name == "suite"
        assert cases == []

    def test_optional_fields_are_loaded(self, tmp_path: Path):
        payload = {
            "suite": "S",
            "cases": [
                {
                    "id": "c1",
                    "goal": "g",
                    "match": "contains",
                    "expected": "e",
                    "domain": "coding",
                    "backend": "mock",
                    "strategy": "direct",
                    "expected_status": "completed",
                    "min_recovery_attempts": 2,
                }
            ],
        }
        p = self._write_suite(tmp_path, payload)
        _, cases = load_benchmark_cases(p)
        case = cases[0]
        assert case.domain == "coding"
        assert case.backend_name == "mock"
        assert case.strategy_name == "direct"
        assert case.expected_status == "completed"
        assert case.min_recovery_attempts == 2

    def test_multiple_cases(self, tmp_path: Path):
        payload = {
            "suite": "S",
            "cases": [
                {"id": f"c{i}", "goal": f"g{i}", "match": "contains", "expected": f"e{i}"}
                for i in range(5)
            ],
        }
        p = self._write_suite(tmp_path, payload)
        _, cases = load_benchmark_cases(p)
        assert len(cases) == 5


# ---------------------------------------------------------------------------
# evaluate_case
# ---------------------------------------------------------------------------

class TestEvaluateCase:
    def _case(self, **kwargs) -> BenchmarkCase:
        defaults = dict(id="c1", goal="g", match="contains", expected="result")
        defaults.update(kwargs)
        return BenchmarkCase(**defaults)

    def _run(self, **kwargs):
        run = type("Run", (), {
            "status": "completed",
            "backend_name": "mock",
            "failure_category": None,
            "recovery_attempts": 0,
        })()
        for k, v in kwargs.items():
            setattr(run, k, v)
        return run

    def test_contains_match_passes(self):
        case = self._case(match="contains", expected="result")
        run = self._run()
        passed, reason = evaluate_case(case, run, "got result here", [])
        assert passed is True

    def test_contains_match_fails(self):
        case = self._case(match="contains", expected="missing")
        run = self._run()
        passed, reason = evaluate_case(case, run, "nothing relevant", [])
        assert passed is False

    def test_not_contains_match_passes(self):
        case = self._case(match="not_contains", expected="bad word")
        run = self._run()
        passed, reason = evaluate_case(case, run, "clean output", [])
        assert passed is True

    def test_not_contains_match_fails(self):
        case = self._case(match="not_contains", expected="bad")
        run = self._run()
        passed, reason = evaluate_case(case, run, "has bad content", [])
        assert passed is False

    def test_equals_match_passes(self):
        case = self._case(match="equals", expected="exact")
        run = self._run()
        passed, reason = evaluate_case(case, run, "exact", [])
        assert passed is True

    def test_equals_match_fails(self):
        case = self._case(match="equals", expected="exact")
        run = self._run()
        passed, reason = evaluate_case(case, run, "not exact", [])
        assert passed is False

    def test_equals_strips_whitespace(self):
        case = self._case(match="equals", expected="result")
        run = self._run()
        passed, _ = evaluate_case(case, run, "  result  ", [])
        assert passed is True

    def test_expected_status_mismatch_fails(self):
        case = self._case(expected_status="completed")
        run = self._run(status="failed")
        passed, reason = evaluate_case(case, run, "result", [])
        assert passed is False
        assert "expected status" in reason

    def test_expected_backend_mismatch_fails(self):
        case = self._case(expected_backend="vllm-coding")
        run = self._run(backend_name="mock")
        passed, reason = evaluate_case(case, run, "result", [])
        assert passed is False

    def test_expected_events_missing_fails(self):
        case = self._case(expected_events=["step_completed"])
        run = self._run()
        events = [{"event_type": "plan_started"}]
        passed, reason = evaluate_case(case, run, "result", events)
        assert passed is False
        assert "step_completed" in reason

    def test_expected_events_all_present_passes(self):
        case = self._case(expected_events=["step_completed"])
        run = self._run()
        events = [{"event_type": "step_completed"}]
        passed, _ = evaluate_case(case, run, "result", events)
        assert passed is True

    def test_min_recovery_attempts_fails(self):
        case = self._case(min_recovery_attempts=3)
        run = self._run(recovery_attempts=1)
        passed, reason = evaluate_case(case, run, "result", [])
        assert passed is False

    def test_min_recovery_attempts_passes(self):
        case = self._case(min_recovery_attempts=2)
        run = self._run(recovery_attempts=2)
        passed, _ = evaluate_case(case, run, "result", [])
        assert passed is True

    def test_unsupported_match_raises(self):
        case = self._case(match="wildcard")
        run = self._run()
        with pytest.raises(ValueError, match="unsupported"):
            evaluate_case(case, run, "output", [])


# ---------------------------------------------------------------------------
# compare_benchmark_summaries
# ---------------------------------------------------------------------------

class TestCompareBenchmarkSummaries:
    def _summary(self, cases: list[dict], pass_rate: float = 0.5) -> dict:
        return {
            "id": "sum-1",
            "suite_name": "suite",
            "pass_rate": pass_rate,
            "metrics": {},
            "results": cases,
        }

    def _result(self, case_id: str, passed: bool, status: str = "completed") -> dict:
        return {
            "case_id": case_id,
            "passed": passed,
            "status": status,
            "reason": "ok" if passed else "fail",
        }

    def test_improved_detected(self):
        left = self._summary([self._result("c1", False)])
        right = self._summary([self._result("c1", True)])
        cmp = compare_benchmark_summaries(left, right)
        assert cmp["improved"] == 1
        assert cmp["regressed"] == 0

    def test_regressed_detected(self):
        left = self._summary([self._result("c1", True)])
        right = self._summary([self._result("c1", False)])
        cmp = compare_benchmark_summaries(left, right)
        assert cmp["regressed"] == 1
        assert cmp["improved"] == 0

    def test_unchanged_detected(self):
        left = self._summary([self._result("c1", True)])
        right = self._summary([self._result("c1", True)])
        cmp = compare_benchmark_summaries(left, right)
        assert cmp["unchanged"] == 1

    def test_delta_pass_rate(self):
        left = self._summary([], pass_rate=0.5)
        right = self._summary([], pass_rate=0.75)
        cmp = compare_benchmark_summaries(left, right)
        assert abs(cmp["delta_pass_rate"] - 0.25) < 0.001

    def test_cases_list_in_output(self):
        left = self._summary([self._result("c1", True), self._result("c2", False)])
        right = self._summary([self._result("c1", True), self._result("c2", True)])
        cmp = compare_benchmark_summaries(left, right)
        assert len(cmp["cases"]) == 2

    def test_new_case_in_right_only(self):
        left = self._summary([self._result("c1", True)])
        right = self._summary([self._result("c1", True), self._result("c2", True)])
        cmp = compare_benchmark_summaries(left, right)
        case_ids = [c["case_id"] for c in cmp["cases"]]
        assert "c2" in case_ids

    def test_suite_info_preserved(self):
        left = self._summary([])
        right = self._summary([])
        cmp = compare_benchmark_summaries(left, right)
        assert "left_suite" in cmp
        assert "right_suite" in cmp
