from __future__ import annotations

from dataclasses import dataclass
import http.client
from typing import TYPE_CHECKING
from urllib import error, request

from orchestro.backends import Backend, MockBackend, OpenAICompatBackend, SubprocessCommandBackend
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
    preferred_backend: str | None
    reason: str
    reachable: list[str]


def build_default_backends() -> dict[str, Backend]:
    return {
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
    }


def decide_auto_backend(
    goal: str,
    *,
    strategy_name: str,
    domain: str | None,
    available: set[str],
    db: OrchestroDB | None = None,
) -> AutoBackendDecision:
    if db is not None:
        stats = collect_routing_stats(db, domain=domain)
        suggestion = suggest_backend(stats, goal=goal, domain=domain, available=available)
        if suggestion:
            return AutoBackendDecision(suggestion, suggestion, "data_driven", sorted(available))

    lowered = goal.lower()
    reachable = sorted(available)
    preferred_backend: str | None = None

    for alias, entry in MODEL_ALIASES.items():
        if alias in lowered and entry["backend"] in available:
            return AutoBackendDecision(entry["backend"], entry["backend"], f"alias_hint_{alias}", reachable)

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

    if domain == "coding" or any(signal in lowered for signal in coding_signals):
        preferred_backend = "vllm-coding"
        if "vllm-coding" in available:
            return AutoBackendDecision("vllm-coding", preferred_backend, "coding_signals", reachable)
        if "vllm-fast" in available:
            return AutoBackendDecision("vllm-fast", preferred_backend, "coding_fallback_fast", reachable)

    if strategy_name in {"tool-loop", "reflect-retry", "reflect-retry-once"}:
        preferred_backend = preferred_backend or "vllm-fast"
        if "vllm-fast" in available:
            return AutoBackendDecision("vllm-fast", preferred_backend, "agentic_strategy", reachable)

    if any(signal in lowered for signal in hard_signals) and "vllm-balanced" in available:
        preferred_backend = "vllm-balanced"
        return AutoBackendDecision("vllm-balanced", preferred_backend, "hard_signals", reachable)

    for candidate in ("vllm-fast", "vllm-balanced", "ollama-amd", "openai-compat", "mock"):
        if candidate in available:
            if preferred_backend and candidate != preferred_backend:
                reason = "preferred_unavailable_fallback"
            elif candidate == "mock":
                reason = "fallback_mock"
            else:
                reason = "fallback_order"
            return AutoBackendDecision(candidate, preferred_backend, reason, reachable)
    raise ValueError("no usable backend profiles are configured")


def resolve_auto_backend(goal: str, *, strategy_name: str, domain: str | None, available: set[str]) -> str:
    return decide_auto_backend(
        goal,
        strategy_name=strategy_name,
        domain=domain,
        available=available,
    ).selected_backend


def reachable_backend_names(backends: dict[str, Backend]) -> set[str]:
    reachable: set[str] = set()
    for name, backend in backends.items():
        if not isinstance(backend, OpenAICompatBackend):
            reachable.add(name)
            continue
        base_url = backend.resolved_base_url()
        if not base_url:
            continue
        health_url = f"{base_url.removesuffix('/v1')}/health"
        try:
            with request.urlopen(health_url, timeout=1):
                reachable.add(name)
        except (error.URLError, error.HTTPError, TimeoutError, http.client.HTTPException, OSError):
            continue
    return reachable
