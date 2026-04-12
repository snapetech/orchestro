from __future__ import annotations

import pytest

from orchestro.backend_profiles import (
    MODEL_ALIASES,
    build_default_backends,
    decide_auto_backend,
    resolve_alias,
)


def test_build_default_backends_returns_expected_names():
    backends = build_default_backends()
    expected = {"mock", "openai-compat", "subprocess-command", "vllm-fast", "vllm-balanced", "vllm-coding", "ollama-amd"}
    assert set(backends.keys()) == expected


def test_decide_auto_backend_coding_signals():
    decision = decide_auto_backend(
        "write a python function",
        strategy_name="direct",
        domain=None,
        available={"vllm-coding", "vllm-fast", "mock"},
    )
    assert decision.selected_backend == "vllm-coding"
    assert "coding" in decision.reason


def test_decide_auto_backend_hard_signals():
    decision = decide_auto_backend(
        "analyze the tradeoffs of this architecture",
        strategy_name="direct",
        domain=None,
        available={"vllm-balanced", "vllm-fast", "mock"},
    )
    assert decision.selected_backend == "vllm-balanced"
    assert "hard" in decision.reason


def test_decide_auto_backend_fallback_to_mock():
    decision = decide_auto_backend(
        "hello world",
        strategy_name="direct",
        domain=None,
        available={"mock"},
    )
    assert decision.selected_backend == "mock"
    assert "mock" in decision.reason


def test_resolve_alias_known():
    backends = build_default_backends()
    for alias in MODEL_ALIASES:
        backend_name, model_override = resolve_alias(alias, backends)
        assert backend_name in backends


def test_resolve_alias_unknown_raises():
    backends = build_default_backends()
    with pytest.raises(ValueError, match="unknown backend or alias"):
        resolve_alias("nonexistent-alias-xyz", backends)
