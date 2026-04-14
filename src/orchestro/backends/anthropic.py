"""Anthropic Messages API backend.

Uses the native Anthropic Messages API rather than the OpenAI-compatible shim,
which avoids auth header differences (x-api-key vs Authorization: Bearer) and
correctly handles Anthropic's separate system field and max_tokens requirement.

Configuration via environment variables:
    ANTHROPIC_API_KEY   — required; your Anthropic API key
    ANTHROPIC_MODEL     — optional override (default: claude-sonnet-4-6)
    ANTHROPIC_MAX_TOKENS — optional; maximum completion tokens (default: 8192)
"""
from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Callable
from urllib import error, request

from orchestro.backends.base import Backend
from orchestro.models import BackendResponse, RunRequest

_DEFAULT_MODEL = "claude-sonnet-4-6"
_DEFAULT_MAX_TOKENS = 8192
_ANTHROPIC_VERSION = "2023-06-01"
_BASE_URL = "https://api.anthropic.com/v1"


class AnthropicBackend(Backend):
    """Native Anthropic Messages API backend with streaming support."""

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        max_tokens: int | None = None,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._max_tokens = max_tokens

    def _resolve_config(self) -> tuple[str, str, int]:
        model = self._model or os.environ.get("ANTHROPIC_MODEL", _DEFAULT_MODEL)
        api_key = self._api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        max_tokens = self._max_tokens or int(
            os.environ.get("ANTHROPIC_MAX_TOKENS", _DEFAULT_MAX_TOKENS)
        )
        return model, api_key, max_tokens

    def _headers(self, api_key: str) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
        }

    def _build_payload(self, request_run: RunRequest, *, stream: bool = False) -> dict:
        model, _, max_tokens = self._resolve_config()
        model = str(request_run.metadata.get("backend_model") or model)

        # Collect system content from stable_prefix + system_prompt.
        system_parts = []
        if request_run.stable_prefix:
            system_parts.append(request_run.stable_prefix)
        sp = request_run.system_prompt or "You are Orchestro's current backend. Keep answers concise and useful."
        system_parts.append(sp)
        system = "\n\n".join(system_parts)

        user_parts = [request_run.goal]
        if request_run.prompt_context:
            user_parts.append(request_run.prompt_context)
        user_content = "\n\n".join(user_parts)

        payload: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user_content}],
        }
        if stream:
            payload["stream"] = True
        return payload

    def run(self, request_run: RunRequest) -> BackendResponse:
        model, api_key, _ = self._resolve_config()
        model = str(request_run.metadata.get("backend_model") or model)
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. "
                "Export it or pass api_key= to AnthropicBackend()."
            )

        payload = self._build_payload(request_run)
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{_BASE_URL}/messages",
            data=body,
            headers=self._headers(api_key),
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Anthropic request failed: {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Anthropic request failed: {exc.reason}") from exc

        content_blocks = data.get("content", [])
        text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
        usage = data.get("usage", {})
        input_tokens = int(usage.get("input_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))
        cache_read = int(usage.get("cache_read_input_tokens", 0))
        cache_write = int(usage.get("cache_creation_input_tokens", 0))

        meta: dict[str, object] = {
            "backend": "anthropic",
            "model": model,
            "usage": usage,
            "stop_reason": data.get("stop_reason"),
        }
        return BackendResponse(
            output_text=text,
            metadata=meta,
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
        )

    def stream(self, request_run: RunRequest) -> Iterator[str]:
        """Yield text chunks as they arrive via SSE stream."""
        _, api_key, _ = self._resolve_config()
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")

        payload = self._build_payload(request_run, stream=True)
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{_BASE_URL}/messages",
            data=body,
            headers=self._headers(api_key),
            method="POST",
        )
        try:
            resp = request.urlopen(req, timeout=120)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Anthropic request failed: {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Anthropic request failed: {exc.reason}") from exc

        try:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if data_str in ("[DONE]", ""):
                    continue
                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                event_type = event.get("type", "")
                if event_type == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            yield text
        finally:
            resp.close()

    def run_streaming(
        self, request_run: RunRequest, *, on_chunk: Callable[[str], None] | None = None,
    ) -> BackendResponse:
        model, api_key, _ = self._resolve_config()
        model = str(request_run.metadata.get("backend_model") or model)
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")

        payload = self._build_payload(request_run, stream=True)
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{_BASE_URL}/messages",
            data=body,
            headers=self._headers(api_key),
            method="POST",
        )
        try:
            resp = request.urlopen(req, timeout=120)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Anthropic request failed: {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Anthropic request failed: {exc.reason}") from exc

        chunks: list[str] = []
        usage: dict[str, int] = {}
        stop_reason: str | None = None
        try:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if data_str in ("[DONE]", ""):
                    continue
                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                event_type = event.get("type", "")
                usage.update(_extract_stream_usage(event))
                if event_type == "message_delta":
                    stop_reason = event.get("delta", {}).get("stop_reason") or stop_reason
                elif event_type == "message_stop":
                    stop_reason = event.get("stop_reason") or stop_reason
                if event_type == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            chunks.append(text)
                            if on_chunk:
                                on_chunk(text)
        finally:
            resp.close()

        full_text = "".join(chunks)
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", max(1, len(full_text) // 4))
        total_tokens = prompt_tokens + completion_tokens
        cache_read_tokens = usage.get("cache_read_input_tokens", 0)
        cache_write_tokens = usage.get("cache_creation_input_tokens", 0)
        metadata: dict[str, object] = {
            "backend": "anthropic",
            "model": model,
            "streaming": True,
            "usage": {
                "input_tokens": prompt_tokens,
                "output_tokens": completion_tokens,
            },
        }
        if stop_reason:
            metadata["stop_reason"] = stop_reason
        return BackendResponse(
            output_text=full_text,
            metadata=metadata,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
        )

    def capabilities(self) -> dict[str, object]:
        model, _, _ = self._resolve_config()
        return {
            "streaming": True,
            "tool_use": False,
            "interactive_only": False,
            "api_style": "anthropic-messages",
            "model": model,
        }

    def is_available(self) -> bool:
        """Return True when the API key is configured."""
        _, api_key, _ = self._resolve_config()
        return bool(api_key)

    def list_models(self) -> list[str]:
        model, _, _ = self._resolve_config()
        return [model] if model else []


def make_anthropic_backend(model: str = _DEFAULT_MODEL, *, max_tokens: int = _DEFAULT_MAX_TOKENS) -> AnthropicBackend:
    return AnthropicBackend(model=model, max_tokens=max_tokens)


def _extract_stream_usage(event: dict) -> dict[str, int]:
    usage: dict[str, int] = {}
    candidates = [event.get("usage")]
    message = event.get("message")
    if isinstance(message, dict):
        candidates.append(message.get("usage"))
    delta = event.get("delta")
    if isinstance(delta, dict):
        candidates.append(delta.get("usage"))
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        for key in (
            "input_tokens",
            "output_tokens",
            "cache_read_input_tokens",
            "cache_creation_input_tokens",
        ):
            value = candidate.get(key)
            if value is not None:
                usage[key] = int(value)
    return usage
