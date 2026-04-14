from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch, MagicMock
from urllib import error

import pytest

from orchestro.backend_profiles import (
    clear_backend_cooldowns,
    MODEL_ALIASES,
    build_default_backends,
    decide_auto_backend,
    get_backend_cooldown,
    is_backend_temporarily_unavailable_error,
    list_backend_cooldowns,
    mark_backend_temporarily_unavailable,
    reachable_backend_names,
    resolve_alias,
)


@pytest.fixture(autouse=True)
def clear_cooldowns():
    clear_backend_cooldowns()
    yield
    clear_backend_cooldowns()
from orchestro.backends.mock import MockBackend
from orchestro.models import RunRequest


def test_build_default_backends_returns_expected_names():
    backends = build_default_backends()
    expected = {
        "mock", "openai-compat", "subprocess-command",
        "vllm-fast", "vllm-balanced", "vllm-coding", "ollama-amd",
        "claude-code", "codex", "kilocode", "cursor",
        # Cloud API backends
        "openai-gpt4o", "openai-gpt4o-mini",
        "anthropic-haiku", "anthropic-sonnet", "anthropic-opus",
        "openrouter",
    }
    assert set(backends.keys()) == expected


def test_decide_auto_backend_coding_signals():
    decision = decide_auto_backend(
        "write a python function",
        strategy_name="direct",
        domain=None,
        available={"vllm-coding", "vllm-fast", "mock"},
    )
    assert decision.selected_backend == "vllm-coding"
    assert "code" in decision.reason or "coding" in decision.reason


def test_decide_auto_backend_hard_signals():
    decision = decide_auto_backend(
        "analyze the tradeoffs of this architecture",
        strategy_name="direct",
        domain=None,
        available={"vllm-balanced", "vllm-fast", "mock"},
    )
    assert decision.selected_backend == "vllm-balanced"
    assert "analysis" in decision.reason or "hard" in decision.reason


def test_decide_auto_backend_uses_model_hints_for_code():
    decision = decide_auto_backend(
        "write a python function",
        strategy_name="direct",
        domain=None,
        available={"openai-compat", "vllm-fast"},
        backend_models={
            "openai-compat": ["Qwen2.5-Coder-7B-Instruct"],
            "vllm-fast": ["Qwen/Qwen3-4B"],
        },
    )
    assert decision.selected_backend == "openai-compat"
    assert decision.selected_model == "Qwen2.5-Coder-7B-Instruct"
    assert "model" in decision.reason


def test_decide_auto_backend_explicit_hint_beats_data_driven(monkeypatch):
    monkeypatch.setattr("orchestro.backend_profiles.collect_routing_stats", lambda db, domain=None: {"mock": 100})
    monkeypatch.setattr("orchestro.backend_profiles.suggest_backend", lambda *args, **kwargs: "mock")

    decision = decide_auto_backend(
        "use claude to review this diff",
        strategy_name="direct",
        domain=None,
        available={"claude-code", "mock"},
        db=object(),
    )

    assert decision.selected_backend == "claude-code"
    assert decision.reason.startswith("alias_hint_") or decision.reason.startswith("agent_hint_")


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


def test_temporary_backend_error_detects_usage_limit():
    assert is_backend_temporarily_unavailable_error("You've hit your usage limit")
    assert is_backend_temporarily_unavailable_error("monthly cycle ends on 4/29/2026")
    assert not is_backend_temporarily_unavailable_error("syntax error in prompt")


def test_mark_backend_temporarily_unavailable_parses_reset_date():
    cooldown = mark_backend_temporarily_unavailable(
        "cursor",
        "Your usage limits will reset when your monthly cycle ends on 4/29/2026.",
        now=datetime(2026, 4, 13, tzinfo=UTC),
    )
    assert cooldown.backend_name == "cursor"
    assert cooldown.unavailable_until.startswith("2026-04-29")


def test_mark_backend_temporarily_unavailable_defaults_to_short_cooldown():
    now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=UTC)
    cooldown = mark_backend_temporarily_unavailable("claude-code", "You've hit your usage limit", now=now)
    assert cooldown.unavailable_until.startswith("2026-04-13T13:00:00")


def test_get_backend_cooldown_expires_entries():
    mark_backend_temporarily_unavailable(
        "cursor",
        "Your usage limits will reset when your monthly cycle ends on 4/29/2026.",
        now=datetime(2026, 4, 13, tzinfo=UTC),
    )
    active = get_backend_cooldown("cursor", now=datetime(2026, 4, 20, tzinfo=UTC))
    assert active is not None
    expired = get_backend_cooldown("cursor", now=datetime(2026, 4, 30, tzinfo=UTC))
    assert expired is None


# ---------------------------------------------------------------------------
# reachable_backend_names
# ---------------------------------------------------------------------------

class TestReachableBackendNames:
    def test_mock_always_reachable(self):
        backends = {"mock": MockBackend()}
        reachable = reachable_backend_names(backends)
        assert "mock" in reachable

    def test_openai_compat_reachable_when_health_200(self):
        backends = build_default_backends()
        cm = MagicMock()
        cm.__enter__ = lambda s: s
        cm.__exit__ = MagicMock(return_value=False)
        with patch("orchestro.backend_profiles.request.urlopen", return_value=cm):
            reachable = reachable_backend_names(backends)
        assert "vllm-fast" in reachable
        assert "vllm-balanced" in reachable

    def test_openai_compat_not_reachable_on_url_error(self):
        backends = build_default_backends()
        with patch(
            "orchestro.backend_profiles.request.urlopen",
            side_effect=error.URLError("refused"),
        ):
            reachable = reachable_backend_names(backends)
        # Only non-HTTP backends (mock, subprocess-command) should be reachable
        assert "vllm-fast" not in reachable
        assert "mock" in reachable

    def test_openai_compat_not_reachable_on_os_error(self):
        backends = build_default_backends()
        with patch(
            "orchestro.backend_profiles.request.urlopen",
            side_effect=OSError("connection reset"),
        ):
            reachable = reachable_backend_names(backends)
        assert "vllm-fast" not in reachable

    def test_empty_base_url_backend_skipped(self, monkeypatch):
        from orchestro.backends.openai_compat import OpenAICompatBackend
        monkeypatch.delenv("ORCHESTRO_OPENAI_BASE_URL", raising=False)
        backends = {"openai-compat": OpenAICompatBackend()}  # no URL configured
        # Should not raise, just not include it
        reachable = reachable_backend_names(backends)
        assert "openai-compat" not in reachable

    def test_temporarily_unavailable_backend_not_reachable(self):
        backends = {"mock": MockBackend()}
        mark_backend_temporarily_unavailable("mock", "You've hit your usage limit")
        reachable = reachable_backend_names(backends)
        assert "mock" not in reachable
        assert "mock" in list_backend_cooldowns()


# ---------------------------------------------------------------------------
# MockBackend unit tests
# ---------------------------------------------------------------------------

class TestMockBackend:
    def test_run_returns_mock_response(self):
        backend = MockBackend()
        req = RunRequest(goal="hello", backend_name="mock")
        resp = backend.run(req)
        assert "Mock backend response" in resp.output_text

    def test_run_includes_strategy(self):
        backend = MockBackend()
        req = RunRequest(goal="hi", backend_name="mock", strategy_name="tool-loop")
        resp = backend.run(req)
        assert "tool-loop" in resp.output_text

    def test_run_includes_prompt_preview(self):
        backend = MockBackend()
        req = RunRequest(goal="what is 2+2", backend_name="mock")
        resp = backend.run(req)
        assert "what is 2+2" in resp.output_text

    def test_run_includes_context_preview(self):
        backend = MockBackend()
        req = RunRequest(goal="hi", backend_name="mock", prompt_context="Some context here")
        resp = backend.run(req)
        assert "Some context here" in resp.output_text

    def test_run_context_dash_when_absent(self):
        backend = MockBackend()
        req = RunRequest(goal="hi", backend_name="mock")
        resp = backend.run(req)
        assert "context: -" in resp.output_text

    def test_metadata_includes_backend_name(self):
        backend = MockBackend()
        req = RunRequest(goal="hi", backend_name="mock")
        resp = backend.run(req)
        assert resp.metadata["backend"] == "mock"

    def test_run_streaming_falls_back_to_run(self):
        backend = MockBackend()
        req = RunRequest(goal="stream test", backend_name="mock")
        chunks: list[str] = []
        resp = backend.run_streaming(req, on_chunk=chunks.append)
        assert "Mock backend response" in resp.output_text
