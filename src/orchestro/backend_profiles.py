from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import http.client
import re
from typing import TYPE_CHECKING
from urllib import error, request

from orchestro.backends import (
    AgentCLIBackend,
    AnthropicBackend,
    Backend,
    MockBackend,
    OpenAICompatBackend,
    SubprocessCommandBackend,
    make_claude_code_backend,
    make_codex_backend,
    make_cursor_backend,
    make_kilocode_backend,
)
from orchestro.routing import collect_routing_stats, suggest_backend

if TYPE_CHECKING:
    from orchestro.db import OrchestroDB


MODEL_ALIASES: dict[str, dict[str, str | None]] = {
    "fast": {"backend": "vllm-fast", "model": None},
    "smart": {"backend": "vllm-balanced", "model": None},
    "balanced": {"backend": "vllm-balanced", "model": None},
    "code": {"backend": "vllm-coding", "model": None},
    "coding": {"backend": "vllm-coding", "model": None},
    "local": {"backend": "ollama-amd", "model": None},
    # External agent CLI aliases
    "claude": {"backend": "claude-code", "model": None},
    "claude-cli": {"backend": "claude-code", "model": None},
    "codex": {"backend": "codex", "model": None},
    "kilo": {"backend": "kilocode", "model": None},
    "kilocode": {"backend": "kilocode", "model": None},
    "cursor": {"backend": "cursor", "model": None},
    # Cloud API aliases — resolved to env-var-configured backends
    "gpt-4o": {"backend": "openai-gpt4o", "model": None},
    "gpt-4o-mini": {"backend": "openai-gpt4o-mini", "model": None},
    "haiku": {"backend": "anthropic-haiku", "model": None},
    "sonnet": {"backend": "anthropic-sonnet", "model": None},
    "opus": {"backend": "anthropic-opus", "model": None},
    "openrouter": {"backend": "openrouter", "model": None},
}

_BACKEND_TASK_HINTS: dict[str, set[str]] = {
    "vllm-coding": {"code"},
    "ollama-code": {"code"},
    "vllm-fast": {"search", "creative"},
    "vllm-balanced": {"analysis", "math", "search", "code"},
    "ollama-amd": {"creative"},
    "claude-code": {"code", "analysis", "creative"},
    "codex": {"code"},
    "kilocode": {"code"},
    "cursor": {"code", "analysis"},
}


def resolve_alias(name: str, backends: dict[str, Backend]) -> tuple[str, str | None]:
    lowered = name.lower().strip()
    if lowered in MODEL_ALIASES:
        entry = MODEL_ALIASES[lowered]
        backend_name = entry["backend"]
        if backend_name not in backends:
            available = ", ".join(sorted(backends))
            raise ValueError(
                f"alias '{lowered}' maps to backend '{backend_name}' which is not configured. "
                f"available backends: {available}"
            )
        return backend_name, entry["model"]
    if lowered in backends:
        return lowered, None
    available_backends = ", ".join(sorted(backends))
    available_aliases = ", ".join(sorted(MODEL_ALIASES))
    raise ValueError(
        f"unknown backend or alias '{name}'. "
        f"aliases: {available_aliases}. backends: {available_backends}"
    )


@dataclass(slots=True)
class AutoBackendDecision:
    selected_backend: str
    selected_model: str | None
    preferred_backend: str | None
    reason: str
    reachable: list[str]


@dataclass(slots=True)
class BackendCooldown:
    backend_name: str
    reason: str
    unavailable_until: str


_TEMPORARILY_UNAVAILABLE: dict[str, BackendCooldown] = {}


def build_default_backends() -> dict[str, Backend]:
    backends: dict[str, Backend] = {
        "mock": MockBackend(),
        "openai-compat": OpenAICompatBackend(),
        "subprocess-command": SubprocessCommandBackend(),
        "vllm-fast": OpenAICompatBackend(
            base_url="http://127.0.0.1:8000/v1",
            model="Qwen/Qwen3-4B",
        ),
        "vllm-balanced": OpenAICompatBackend(
            base_url="http://127.0.0.1:8001/v1",
            model="Qwen/Qwen3-8B-FP8",
        ),
        "vllm-coding": OpenAICompatBackend(
            base_url="http://127.0.0.1:8002/v1",
            model="Qwen/Qwen3-4B",
        ),
        "ollama-amd": OpenAICompatBackend(
            base_url="http://127.0.0.1:11434/v1",
            model="qwen2.5-coder:7b",
        ),
        # External agent CLI backends — always registered; health-checked via
        # shutil.which so they only appear in the reachable set when installed.
        "claude-code": make_claude_code_backend(),
        "codex": make_codex_backend(),
        "kilocode": make_kilocode_backend(),
        "cursor": make_cursor_backend(),
        # Cloud API backends — always registered; health-checked by whether
        # the required API key env var is set (non-empty).
        "openai-gpt4o": OpenAICompatBackend(
            base_url="https://api.openai.com/v1",
            model="gpt-4o",
        ),
        "openai-gpt4o-mini": OpenAICompatBackend(
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
        ),
        "anthropic-haiku": AnthropicBackend(model="claude-haiku-4-5-20251001"),
        "anthropic-sonnet": AnthropicBackend(model="claude-sonnet-4-6"),
        "anthropic-opus": AnthropicBackend(model="claude-opus-4-6"),
        "openrouter": OpenAICompatBackend(
            base_url="https://openrouter.ai/api/v1",
        ),
    }
    return backends


def _model_task_hints(models: list[str]) -> set[str]:
    hints: set[str] = set()
    for model in models:
        lowered = model.lower()
        if any(token in lowered for token in ("coder", "code")):
            hints.add("code")
        if any(token in lowered for token in ("haiku", "mini", "4b", "3b", "fast")):
            hints.update({"search", "creative"})
        if any(token in lowered for token in ("sonnet", "opus", "gpt-5", "8b", "balanced")):
            hints.update({"analysis", "math", "search"})
    return hints


def _backend_task_hints(
    backend_name: str,
    backend_models: dict[str, list[str]] | None = None,
) -> set[str]:
    hints = set(_BACKEND_TASK_HINTS.get(backend_name, set()))
    if backend_models:
        hints.update(_model_task_hints(backend_models.get(backend_name, [])))
    return hints


def _preferred_backends_for_task(
    *,
    task_type: str,
    available: set[str],
    backend_models: dict[str, list[str]] | None = None,
) -> list[str]:
    preferred: list[str] = []
    for backend_name in sorted(available):
        if task_type in _backend_task_hints(backend_name, backend_models):
            preferred.append(backend_name)
    return preferred


def _select_model_for_task(
    backend_name: str,
    *,
    goal: str,
    backend_models: dict[str, list[str]] | None,
) -> str | None:
    if not backend_models:
        return None
    models = backend_models.get(backend_name, [])
    if not models:
        return None
    lowered_goal = goal.lower()
    coding_signals = ("code", "python", "javascript", "typescript", "sql", "bug", "test", "function", "class")
    analysis_signals = ("analyze", "analyse", "compare", "tradeoff", "architecture", "explain", "why")
    search_signals = ("find", "search", "lookup", "list", "show me")
    preferred_tokens: tuple[str, ...]
    if any(signal in lowered_goal for signal in coding_signals):
        preferred_tokens = ("coder", "code")
    elif any(signal in lowered_goal for signal in analysis_signals):
        preferred_tokens = ("opus", "sonnet", "gpt-5", "8b", "balanced")
    elif any(signal in lowered_goal for signal in search_signals):
        preferred_tokens = ("haiku", "mini", "4b", "fast")
    else:
        preferred_tokens = ()
    for model in models:
        lowered = model.lower()
        if preferred_tokens and any(token in lowered for token in preferred_tokens):
            return model
    return models[0]


def decide_auto_backend(
    goal: str,
    *,
    strategy_name: str,
    domain: str | None,
    available: set[str],
    backend_models: dict[str, list[str]] | None = None,
    db: OrchestroDB | None = None,
) -> AutoBackendDecision:
    lowered = goal.lower()
    reachable = sorted(available)
    preferred_backend: str | None = None

    for alias, entry in MODEL_ALIASES.items():
        if alias in lowered and entry["backend"] in available:
            return AutoBackendDecision(
                entry["backend"],
                _select_model_for_task(entry["backend"], goal=goal, backend_models=backend_models),
                entry["backend"],
                f"alias_hint_{alias}",
                reachable,
            )

    coding_signals = {
        "code",
        "python",
        "typescript",
        "javascript",
        "bug",
        "stack trace",
        "test",
        "refactor",
        "function",
        "class",
        "file",
        "diff",
        "regex",
        "sql",
    }
    hard_signals = {
        "analyze",
        "reason",
        "compare",
        "tradeoff",
        "architecture",
        "plan",
        "investigate",
        "debug",
        "why",
        "long",
        "deep",
    }

    # Agent CLI backends take priority when explicitly hinted or installed and
    # the task type matches their declared strengths.
    agent_cli_preference_order = ["claude-code", "codex", "kilocode", "cursor"]
    for agent_name in agent_cli_preference_order:
        if agent_name not in available:
            continue
        if agent_name in lowered or f"use {agent_name.replace('-', ' ')}" in lowered:
            return AutoBackendDecision(
                agent_name,
                _select_model_for_task(agent_name, goal=goal, backend_models=backend_models),
                agent_name,
                f"agent_hint_{agent_name}",
                reachable,
            )

    if db is not None:
        stats = collect_routing_stats(db, domain=domain)
        suggestion = suggest_backend(
            stats,
            goal=goal,
            domain=domain,
            available=available,
            backend_models=backend_models,
        )
        if suggestion:
            return AutoBackendDecision(
                suggestion,
                _select_model_for_task(suggestion, goal=goal, backend_models=backend_models),
                suggestion,
                "data_driven",
                sorted(available),
            )

    if domain == "coding" or any(signal in lowered for signal in coding_signals):
        preferred_backends = _preferred_backends_for_task(
            task_type="code",
            available=available,
            backend_models=backend_models,
        )
        if preferred_backends:
            preferred_backend = preferred_backends[0]
            return AutoBackendDecision(
                preferred_backends[0],
                _select_model_for_task(preferred_backends[0], goal=goal, backend_models=backend_models),
                preferred_backend,
                "task_and_model_hints_code",
                reachable,
            )
        preferred_backend = "vllm-coding"
        if "vllm-coding" in available:
            return AutoBackendDecision(
                "vllm-coding",
                _select_model_for_task("vllm-coding", goal=goal, backend_models=backend_models),
                preferred_backend,
                "coding_signals",
                reachable,
            )
        if "vllm-fast" in available:
            return AutoBackendDecision(
                "vllm-fast",
                _select_model_for_task("vllm-fast", goal=goal, backend_models=backend_models),
                preferred_backend,
                "coding_fallback_fast",
                reachable,
            )

    if strategy_name in {"tool-loop", "reflect-retry", "reflect-retry-once"}:
        preferred_backend = preferred_backend or "vllm-fast"
        if "vllm-fast" in available:
            return AutoBackendDecision(
                "vllm-fast",
                _select_model_for_task("vllm-fast", goal=goal, backend_models=backend_models),
                preferred_backend,
                "agentic_strategy",
                reachable,
            )

    if any(signal in lowered for signal in hard_signals) and "vllm-balanced" in available:
        preferred_backends = _preferred_backends_for_task(
            task_type="analysis",
            available=available,
            backend_models=backend_models,
        )
        if preferred_backends:
            preferred_backend = preferred_backends[0]
            return AutoBackendDecision(
                preferred_backends[0],
                _select_model_for_task(preferred_backends[0], goal=goal, backend_models=backend_models),
                preferred_backend,
                "task_and_model_hints_analysis",
                reachable,
            )
        preferred_backend = "vllm-balanced"
        return AutoBackendDecision(
            "vllm-balanced",
            _select_model_for_task("vllm-balanced", goal=goal, backend_models=backend_models),
            preferred_backend,
            "hard_signals",
            reachable,
        )

    for candidate in ("vllm-fast", "vllm-balanced", "ollama-amd", "openai-compat", "mock"):
        if candidate in available:
            if preferred_backend and candidate != preferred_backend:
                reason = "preferred_unavailable_fallback"
            elif candidate == "mock":
                reason = "fallback_mock"
            else:
                reason = "fallback_order"
            return AutoBackendDecision(
                candidate,
                _select_model_for_task(candidate, goal=goal, backend_models=backend_models),
                preferred_backend,
                reason,
                reachable,
            )
    raise ValueError("no usable backend profiles are configured")


def resolve_auto_backend(goal: str, *, strategy_name: str, domain: str | None, available: set[str]) -> str:
    return decide_auto_backend(
        goal,
        strategy_name=strategy_name,
        domain=domain,
        available=available,
    ).selected_backend


def is_backend_temporarily_unavailable_error(error_text: str) -> bool:
    lowered = error_text.lower()
    patterns = (
        "usage limit",
        "usage limits",
        "hit your usage limit",
        "limit reached",
        "rate limit",
        "quota",
        "credit balance is too low",
        "monthly cycle ends",
    )
    return any(pattern in lowered for pattern in patterns)


def _parse_backend_unavailable_until(error_text: str, *, now: datetime | None = None) -> datetime:
    current = now or datetime.now(UTC)
    date_match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", error_text)
    if date_match:
        month, day, year = map(int, date_match.groups())
        return datetime(year, month, day, 23, 59, 59, tzinfo=UTC)
    return current + timedelta(hours=1)


def mark_backend_temporarily_unavailable(
    backend_name: str,
    error_text: str,
    *,
    now: datetime | None = None,
) -> BackendCooldown:
    until = _parse_backend_unavailable_until(error_text, now=now)
    cooldown = BackendCooldown(
        backend_name=backend_name,
        reason=error_text,
        unavailable_until=until.isoformat(),
    )
    _TEMPORARILY_UNAVAILABLE[backend_name] = cooldown
    return cooldown


def get_backend_cooldown(backend_name: str, *, now: datetime | None = None) -> BackendCooldown | None:
    cooldown = _TEMPORARILY_UNAVAILABLE.get(backend_name)
    if cooldown is None:
        return None
    current = now or datetime.now(UTC)
    until = datetime.fromisoformat(cooldown.unavailable_until)
    if until <= current:
        _TEMPORARILY_UNAVAILABLE.pop(backend_name, None)
        return None
    return cooldown


def list_backend_cooldowns(*, now: datetime | None = None) -> dict[str, BackendCooldown]:
    current = now or datetime.now(UTC)
    active: dict[str, BackendCooldown] = {}
    for name in list(_TEMPORARILY_UNAVAILABLE):
        cooldown = get_backend_cooldown(name, now=current)
        if cooldown is not None:
            active[name] = cooldown
    return active


def clear_backend_cooldowns() -> None:
    _TEMPORARILY_UNAVAILABLE.clear()


_CLOUD_BASE_URLS: dict[str, str] = {
    "https://api.openai.com": "OPENAI_API_KEY",
    "https://openrouter.ai": "OPENROUTER_API_KEY",
}


def reachable_backend_names(backends: dict[str, Backend]) -> set[str]:
    import os as _os
    reachable: set[str] = set()
    cooldowns = list_backend_cooldowns()
    for name, backend in backends.items():
        if name in cooldowns:
            continue
        # Agent CLI backends: available if binary is on PATH.
        if isinstance(backend, AgentCLIBackend):
            if backend.is_available():
                reachable.add(name)
            continue
        # Native Anthropic backend: reachable when ANTHROPIC_API_KEY is set.
        if isinstance(backend, AnthropicBackend):
            if backend.is_available():
                reachable.add(name)
            continue
        # OpenAI-compatible backends.
        if isinstance(backend, OpenAICompatBackend):
            base_url = backend.resolved_base_url()
            if not base_url:
                continue
            # Cloud API backends: reachable when the relevant API key is set.
            for cloud_prefix, env_var in _CLOUD_BASE_URLS.items():
                if base_url.startswith(cloud_prefix):
                    if _os.environ.get(env_var, "").strip():
                        reachable.add(name)
                    break
            else:
                # Local OpenAI-compat backends: health-check via /health endpoint.
                health_url = f"{base_url.removesuffix('/v1')}/health"
                try:
                    with request.urlopen(health_url, timeout=1):
                        reachable.add(name)
                except (error.URLError, error.HTTPError, TimeoutError, http.client.HTTPException, OSError):
                    pass
            continue
        # All other backends (mock, subprocess-command) are always reachable.
        reachable.add(name)
    return reachable
