from __future__ import annotations

from orchestro.routing import RoutingStats, format_routing_report, suggest_backend


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
