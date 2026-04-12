"""Tests for token pricing model in budget.py."""
from __future__ import annotations

import pytest

from orchestro.budget import estimate_cost, format_cost_line, _lookup_pricing


class TestLookupPricing:
    def test_local_vllm_is_free(self) -> None:
        prompt_rate, completion_rate = _lookup_pricing("vllm-fast")
        assert prompt_rate == 0.0
        assert completion_rate == 0.0

    def test_ollama_is_free(self) -> None:
        prompt_rate, completion_rate = _lookup_pricing("ollama-amd")
        assert prompt_rate == 0.0
        assert completion_rate == 0.0

    def test_mock_is_free(self) -> None:
        prompt_rate, completion_rate = _lookup_pricing("mock")
        assert prompt_rate == 0.0
        assert completion_rate == 0.0

    def test_unknown_backend_defaults_to_free(self) -> None:
        prompt_rate, completion_rate = _lookup_pricing("some-unknown-backend-xyz")
        assert prompt_rate == 0.0
        assert completion_rate == 0.0

    def test_claude_sonnet_has_nonzero_pricing(self) -> None:
        prompt_rate, completion_rate = _lookup_pricing("claude-sonnet")
        assert prompt_rate > 0.0
        assert completion_rate > 0.0

    def test_gpt4o_has_nonzero_pricing(self) -> None:
        prompt_rate, completion_rate = _lookup_pricing("gpt-4o")
        assert prompt_rate > 0.0
        assert completion_rate > 0.0

    def test_completion_more_expensive_than_prompt(self) -> None:
        # For most providers, completion tokens cost more than prompt tokens.
        for backend in ["claude-sonnet", "claude-opus", "gpt-4o"]:
            prompt_rate, completion_rate = _lookup_pricing(backend)
            assert completion_rate > prompt_rate, f"{backend}: completion should cost more"


class TestEstimateCost:
    def test_zero_tokens_is_zero_cost(self) -> None:
        cost = estimate_cost(prompt_tokens=0, completion_tokens=0, backend_name="claude-sonnet")
        assert cost == 0.0

    def test_local_backend_always_zero(self) -> None:
        cost = estimate_cost(
            prompt_tokens=100_000,
            completion_tokens=50_000,
            backend_name="ollama-local",
        )
        assert cost == 0.0

    def test_claude_sonnet_cost_calculation(self) -> None:
        # claude-sonnet: $3/1M prompt, $15/1M completion
        cost = estimate_cost(
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            backend_name="claude-sonnet",
        )
        assert abs(cost - 18.0) < 0.01  # $3 + $15 = $18

    def test_gpt4o_mini_cheaper_than_gpt4o(self) -> None:
        kwargs = dict(prompt_tokens=10_000, completion_tokens=5_000)
        mini_cost = estimate_cost(**kwargs, backend_name="gpt-4o-mini")
        full_cost = estimate_cost(**kwargs, backend_name="gpt-4o")
        assert mini_cost < full_cost

    def test_cost_scales_linearly(self) -> None:
        base = estimate_cost(prompt_tokens=1000, completion_tokens=500, backend_name="claude-sonnet")
        double = estimate_cost(prompt_tokens=2000, completion_tokens=1000, backend_name="claude-sonnet")
        assert abs(double - 2 * base) < 1e-9


class TestFormatCostLine:
    def test_local_backend_shows_free(self) -> None:
        line = format_cost_line(
            prompt_tokens=1000,
            completion_tokens=500,
            backend_name="vllm-fast",
        )
        assert "free" in line

    def test_cloud_backend_shows_dollar(self) -> None:
        line = format_cost_line(
            prompt_tokens=1000,
            completion_tokens=500,
            backend_name="claude-sonnet",
        )
        assert "$" in line

    def test_cache_tokens_shown_when_nonzero(self) -> None:
        line = format_cost_line(
            prompt_tokens=100,
            completion_tokens=50,
            cache_read_tokens=200,
            cache_write_tokens=100,
            backend_name="vllm-fast",
        )
        assert "cache_read" in line
        assert "cache_write" in line

    def test_cache_tokens_hidden_when_zero(self) -> None:
        line = format_cost_line(
            prompt_tokens=100,
            completion_tokens=50,
            backend_name="vllm-fast",
        )
        assert "cache_read" not in line

    def test_token_counts_in_output(self) -> None:
        line = format_cost_line(
            prompt_tokens=1234,
            completion_tokens=567,
            backend_name="vllm-fast",
        )
        assert "1,234" in line
        assert "567" in line
