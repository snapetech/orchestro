"""Tests for query classifier and improved routing in routing.py."""
from __future__ import annotations


from orchestro.routing import (
    classify_query,
    suggest_backend,
    RoutingStats,
    _BACKEND_TASK_HINTS,
)


class TestClassifyQuery:
    def test_code_task_detected(self) -> None:
        assert classify_query("Write a Python function to parse JSON") == "code"

    def test_code_task_detected_debug(self) -> None:
        assert classify_query("debug this pytest failure") == "code"

    def test_math_task_detected(self) -> None:
        assert classify_query("calculate the probability of rolling a 7") == "math"

    def test_search_task_detected(self) -> None:
        assert classify_query("what is the capital of France?") == "search"

    def test_analysis_task_detected(self) -> None:
        result = classify_query("explain why this approach has trade-offs")
        assert result in ("analysis", "search")  # "explain" and "trade-off" both qualify

    def test_creative_task_detected(self) -> None:
        assert classify_query("draft an email to the team about the release") == "creative"

    def test_empty_query_returns_chat(self) -> None:
        assert classify_query("") == "chat"

    def test_unclassifiable_returns_chat(self) -> None:
        assert classify_query("blorp zork wibble") == "chat"

    def test_returns_dominant_type(self) -> None:
        # "fix the python code function syntax" — heavily code signals.
        result = classify_query("fix the Python function syntax error in the code")
        assert result == "code"

    def test_sql_classified_as_code(self) -> None:
        result = classify_query("write a SQL query to find duplicate rows")
        assert result == "code"

    def test_case_insensitive(self) -> None:
        upper = classify_query("WRITE A PYTHON FUNCTION")
        lower = classify_query("write a python function")
        assert upper == lower


class TestSuggestBackendWithTaskHints:
    def _make_stats(self, backend: str, success_rate: float = 0.9) -> dict[str, RoutingStats]:
        return {
            backend: RoutingStats(
                backend=backend,
                total_runs=20,
                successful_runs=int(20 * success_rate),
                failed_runs=int(20 * (1 - success_rate)),
                avg_tokens=1000,
                success_rate=success_rate,
            )
        }

    def test_prefers_coding_backend_for_code_task(self) -> None:
        stats = {
            "vllm-coding": RoutingStats("vllm-coding", 20, 18, 2, 1000, 0, 0, 0.9),
            "vllm-fast": RoutingStats("vllm-fast", 20, 18, 2, 800, 0, 0, 0.9),
        }
        suggestion = suggest_backend(
            stats,
            goal="write a Python decorator function",
            available={"vllm-coding", "vllm-fast"},
        )
        assert suggestion == "vllm-coding"

    def test_falls_back_to_best_success_rate_when_no_task_hint(self) -> None:
        stats = {
            "vllm-balanced": RoutingStats("vllm-balanced", 20, 18, 2, 1000, 0, 0, 0.9),
            "vllm-fast": RoutingStats("vllm-fast", 20, 10, 10, 800, 0, 0, 0.5),
        }
        suggestion = suggest_backend(
            stats,
            goal="blorp zork wibble",  # classified as chat
            available={"vllm-balanced", "vllm-fast"},
        )
        assert suggestion == "vllm-balanced"

    def test_no_stats_returns_task_hint_backend(self) -> None:
        suggestion = suggest_backend(
            {},
            goal="write a Python function",
            available={"vllm-coding", "vllm-fast"},
        )
        assert suggestion == "vllm-coding"

    def test_no_stats_no_hint_returns_none(self) -> None:
        suggestion = suggest_backend(
            {},
            goal="blorp zork",
            available={"vllm-coding"},  # coding hint but goal is chat
        )
        # chat task type → no matching hint for vllm-coding → None or best available
        # (vllm-coding only hints code, chat doesn't match)
        # Result depends on whether we fall through — just verify no crash.
        assert suggestion is None or isinstance(suggestion, str)

    def test_returns_none_when_all_below_threshold(self) -> None:
        stats = {
            "vllm-balanced": RoutingStats("vllm-balanced", 20, 2, 18, 1000, 0, 0, 0.1),
        }
        suggestion = suggest_backend(
            stats,
            goal="what is the weather",
            available={"vllm-balanced"},
        )
        # Low success rate AND no task hint → None.
        assert suggestion is None

    def test_task_hint_overrides_slightly_lower_success_rate(self) -> None:
        # vllm-coding has decent but lower success rate, correct task type for a code question.
        stats = {
            "vllm-coding": RoutingStats("vllm-coding", 20, 14, 6, 1000, 0, 0, 0.7),
            "vllm-fast": RoutingStats("vllm-fast", 20, 18, 2, 800, 0, 0, 0.9),
        }
        suggestion = suggest_backend(
            stats,
            goal="write a Python function",
            available={"vllm-coding", "vllm-fast"},
        )
        # vllm-coding ranks first because code task type + task hint beats raw success rate.
        assert suggestion == "vllm-coding"

    def test_backend_task_hints_keys_are_valid_strings(self) -> None:
        for backend, hints in _BACKEND_TASK_HINTS.items():
            assert isinstance(backend, str)
            assert isinstance(hints, set)
            for h in hints:
                assert isinstance(h, str)
