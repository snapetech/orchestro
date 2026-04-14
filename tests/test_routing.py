from __future__ import annotations

from orchestro.routing import (
    RoutingStats,
    classify_query,
    format_routing_report,
    suggest_backend,
)


# ---------------------------------------------------------------------------
# classify_query
# ---------------------------------------------------------------------------

def test_classify_query_code_keywords():
    assert classify_query("write a function to parse JSON") == "code"


def test_classify_query_math_keywords():
    result = classify_query("calculate the derivative of x squared")
    assert result == "math"


def test_classify_query_search_keywords():
    result = classify_query("find all examples of list comprehensions")
    assert result in ("search", "code")  # "list" could match code too


def test_classify_query_analysis_keywords():
    result = classify_query("analyze the pros and cons of this approach")
    assert result == "analysis"


def test_classify_query_no_signals_returns_chat():
    result = classify_query("hello there how are you")
    assert result == "chat"


def test_classify_query_returns_string():
    assert isinstance(classify_query("anything"), str)


# ---------------------------------------------------------------------------
# RoutingStats
# ---------------------------------------------------------------------------

def test_routing_stats_defaults():
    s = RoutingStats(backend="mock")
    assert s.total_runs == 0
    assert s.successful_runs == 0
    assert s.failed_runs == 0
    assert s.avg_tokens == 0.0
    assert s.positive_ratings == 0
    assert s.negative_ratings == 0
    assert s.success_rate == 0.0


# ---------------------------------------------------------------------------
# suggest_backend
# ---------------------------------------------------------------------------

def test_suggest_backend_returns_none_with_no_stats():
    result = suggest_backend({}, goal="test", available={"gpt-4"})
    assert result is None


def test_suggest_backend_picks_highest_success_rate():
    stats = {
        "gpt-4": RoutingStats(backend="gpt-4", total_runs=10, successful_runs=9, success_rate=0.9),
        "claude": RoutingStats(backend="claude", total_runs=10, successful_runs=7, success_rate=0.7),
    }
    result = suggest_backend(stats, goal="test", available={"gpt-4", "claude"})
    assert result == "gpt-4"


def test_suggest_backend_returns_none_below_threshold():
    stats = {
        "bad-backend": RoutingStats(backend="bad-backend", total_runs=10, successful_runs=4, success_rate=0.4),
    }
    result = suggest_backend(stats, goal="test", available={"bad-backend"})
    assert result is None


def test_suggest_backend_only_considers_available():
    stats = {
        "gpt-4": RoutingStats(backend="gpt-4", total_runs=10, successful_runs=9, success_rate=0.9),
        "claude": RoutingStats(backend="claude", total_runs=10, successful_runs=8, success_rate=0.8),
    }
    # gpt-4 not in available set
    result = suggest_backend(stats, goal="test", available={"claude"})
    assert result == "claude"


def test_suggest_backend_task_hint_preferred_for_code():
    # vllm-coding has a hint for "code" tasks and should be preferred even with
    # slightly lower success rate, since it matches the task type.
    stats = {
        "vllm-coding": RoutingStats(backend="vllm-coding", total_runs=10, successful_runs=8, success_rate=0.8),
        "vllm-fast": RoutingStats(backend="vllm-fast", total_runs=10, successful_runs=9, success_rate=0.9),
    }
    result = suggest_backend(stats, goal="write a function", available={"vllm-coding", "vllm-fast"})
    assert result == "vllm-coding"


def test_suggest_backend_empty_available():
    stats = {
        "mock": RoutingStats(backend="mock", total_runs=10, successful_runs=9, success_rate=0.9),
    }
    result = suggest_backend(stats, goal="test", available=set())
    assert result is None


def test_suggest_backend_uses_model_hints_for_code():
    stats = {
        "openai-compat": RoutingStats(backend="openai-compat", total_runs=10, successful_runs=0, success_rate=0.8),
        "vllm-fast": RoutingStats(backend="vllm-fast", total_runs=10, successful_runs=0, success_rate=0.8),
    }
    result = suggest_backend(
        stats,
        goal="write a function",
        available={"openai-compat", "vllm-fast"},
        backend_models={"openai-compat": ["Qwen2.5-Coder-7B-Instruct"], "vllm-fast": ["Qwen/Qwen3-4B"]},
    )
    assert result == "openai-compat"


# ---------------------------------------------------------------------------
# format_routing_report
# ---------------------------------------------------------------------------

def test_format_routing_report_produces_readable_output():
    stats = {
        "gpt-4": RoutingStats(
            backend="gpt-4",
            total_runs=20,
            successful_runs=18,
            failed_runs=2,
            avg_tokens=1500.0,
            positive_ratings=5,
            negative_ratings=1,
            success_rate=0.9,
        ),
    }
    report = format_routing_report(stats)
    assert "gpt-4" in report
    assert "Backend" in report


def test_format_routing_report_empty_stats():
    report = format_routing_report({})
    assert "No routing stats" in report


def test_format_routing_report_multiple_backends():
    stats = {
        "a": RoutingStats(backend="a", total_runs=10, successful_runs=9, success_rate=0.9),
        "b": RoutingStats(backend="b", total_runs=10, successful_runs=6, success_rate=0.6),
    }
    report = format_routing_report(stats)
    assert "a" in report
    assert "b" in report
