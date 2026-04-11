from __future__ import annotations

import http.client
from urllib import error, request

from orchestro.backends import Backend, MockBackend, OpenAICompatBackend, SubprocessCommandBackend


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


def resolve_auto_backend(goal: str, *, strategy_name: str, domain: str | None, available: set[str]) -> str:
    lowered = goal.lower()
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
        if "vllm-coding" in available:
            return "vllm-coding"
        if "vllm-fast" in available:
            return "vllm-fast"

    if strategy_name in {"tool-loop", "reflect-retry", "reflect-retry-once"}:
        if "vllm-fast" in available:
            return "vllm-fast"

    if any(signal in lowered for signal in hard_signals) and "vllm-balanced" in available:
        return "vllm-balanced"

    for candidate in ("vllm-fast", "vllm-balanced", "ollama-amd", "openai-compat", "mock"):
        if candidate in available:
            return candidate
    raise ValueError("no usable backend profiles are configured")


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
