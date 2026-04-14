from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Callable
from urllib import error, request

from orchestro.backends.base import Backend
from orchestro.models import BackendResponse, RunRequest


class OpenAICompatBackend(Backend):
    name = "openai-compat"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._base_url = base_url
        self._model = model
        self._api_key = api_key

    def _resolve_config(self) -> tuple[str, str, str]:
        base_url = (self._base_url or os.environ.get("ORCHESTRO_OPENAI_BASE_URL", "")).rstrip("/")
        model = self._model or os.environ.get("ORCHESTRO_OPENAI_MODEL", "")
        # API key resolution: explicit > orchestro-specific env > well-known standard env vars.
        api_key = (
            self._api_key
            or os.environ.get("ORCHESTRO_OPENAI_API_KEY", "")
        )
        if not api_key:
            # Auto-select the right standard key based on the target URL.
            if "anthropic.com" in base_url:
                api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            elif "openrouter.ai" in base_url:
                api_key = os.environ.get("OPENROUTER_API_KEY", "")
            else:
                api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            api_key = "dummy"
        return base_url, model, api_key

    def resolved_base_url(self) -> str:
        return self._resolve_config()[0]

    def resolved_model(self) -> str:
        return self._resolve_config()[1]

    def run(self, request_run: RunRequest) -> BackendResponse:
        base_url, model, api_key = self._resolve_config()
        model = str(request_run.metadata.get("backend_model") or model)
        if not base_url:
            raise RuntimeError("ORCHESTRO_OPENAI_BASE_URL is not set")
        if not model:
            raise RuntimeError("ORCHESTRO_OPENAI_MODEL is not set")

        messages = self._build_messages(request_run)
        payload = {"model": model, "messages": messages}
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{base_url}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"backend request failed: {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"backend request failed: {exc.reason}") from exc

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        cache_stats: dict[str, object] = {
            "stable_prefix_used": request_run.stable_prefix is not None,
            "stable_prefix_length": len(request_run.stable_prefix) if request_run.stable_prefix else 0,
        }
        cached_tokens = usage.get("prompt_tokens_details", {}).get("cached_tokens")
        if cached_tokens is not None:
            cache_stats["cached_tokens"] = cached_tokens
        cache_read_raw = usage.get("cache_read_input_tokens")
        cache_write_raw = usage.get("cache_creation_input_tokens")
        cache_read_tokens = int(cache_read_raw) if cache_read_raw is not None else 0
        cache_write_tokens = int(cache_write_raw) if cache_write_raw is not None else 0
        if cache_read_raw is not None:
            cache_stats["cache_read_input_tokens"] = cache_read_raw
        if cache_write_raw is not None:
            cache_stats["cache_creation_input_tokens"] = cache_write_raw
        meta: dict[str, object] = {
            "backend": self.name,
            "model": model,
            "usage": usage,
            "cache_stats": cache_stats,
        }
        if cache_read_raw is not None:
            meta["cache_read_input_tokens"] = cache_read_raw
        if cache_write_raw is not None:
            meta["cache_creation_input_tokens"] = cache_write_raw
        return BackendResponse(
            output_text=content,
            metadata=meta,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
        )

    def stream(self, request_run: RunRequest) -> Iterator[str]:
        """Yield response chunks as they arrive from the backend."""
        base_url, model, api_key = self._resolve_config()
        model = str(request_run.metadata.get("backend_model") or model)
        if not base_url:
            raise RuntimeError("ORCHESTRO_OPENAI_BASE_URL is not set")
        if not model:
            raise RuntimeError("ORCHESTRO_OPENAI_MODEL is not set")

        messages = self._build_messages(request_run)
        payload = {"model": model, "messages": messages, "stream": True}
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{base_url}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            resp = request.urlopen(req, timeout=120)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"backend request failed: {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"backend request failed: {exc.reason}") from exc

        try:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data: "):
                    continue
                data_str = line[len("data: "):]
                if data_str == "[DONE]":
                    break
                try:
                    chunk_data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                choices = chunk_data.get("choices")
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield content
        finally:
            resp.close()

    def run_streaming(
        self, request_run: RunRequest, *, on_chunk: Callable[[str], None] | None = None,
    ) -> BackendResponse:
        """Run with streaming, calling on_chunk for real-time output."""
        chunks: list[str] = []
        usage: dict[str, int] = {}
        base_url, model, api_key = self._resolve_config()
        model = str(request_run.metadata.get("backend_model") or model)
        if not base_url:
            raise RuntimeError("ORCHESTRO_OPENAI_BASE_URL is not set")
        if not model:
            raise RuntimeError("ORCHESTRO_OPENAI_MODEL is not set")
        messages = self._build_messages(request_run)
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{base_url}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            resp = request.urlopen(req, timeout=120)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"backend request failed: {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"backend request failed: {exc.reason}") from exc
        try:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data: "):
                    continue
                data_str = line[len("data: "):]
                if data_str == "[DONE]":
                    break
                try:
                    chunk_data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                chunk_usage = chunk_data.get("usage")
                if isinstance(chunk_usage, dict):
                    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                        value = chunk_usage.get(key)
                        if value is not None:
                            usage[key] = int(value)
                    details = chunk_usage.get("prompt_tokens_details", {})
                    cached = details.get("cached_tokens") if isinstance(details, dict) else None
                    if cached is not None:
                        usage["cached_tokens"] = int(cached)
                    for key in ("cache_read_input_tokens", "cache_creation_input_tokens"):
                        value = chunk_usage.get(key)
                        if value is not None:
                            usage[key] = int(value)
                choices = chunk_data.get("choices")
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                content = delta.get("content")
                if content:
                    chunks.append(content)
                    if on_chunk:
                        on_chunk(content)
        finally:
            resp.close()
        full_text = "".join(chunks)
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", max(1, len(full_text) // 4))
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
        cache_read_tokens = usage.get("cache_read_input_tokens", 0)
        cache_write_tokens = usage.get("cache_creation_input_tokens", 0)
        cache_stats: dict[str, object] = {}
        if "cached_tokens" in usage:
            cache_stats["cached_tokens"] = usage["cached_tokens"]
        return BackendResponse(
            output_text=full_text,
            metadata={
                "backend": self.name,
                "model": model,
                "streaming": True,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                },
                "cache_stats": cache_stats,
            },
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
        )

    @staticmethod
    def _build_messages(request_run: RunRequest) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if request_run.stable_prefix:
            messages.append({"role": "system", "content": request_run.stable_prefix})
        system_content = "\n\n".join(
            part
            for part in [
                "You are Orchestro's current backend. Keep answers concise and useful.",
                request_run.system_prompt,
            ]
            if part
        )
        messages.append({"role": "system", "content": system_content})
        user_parts = [request_run.goal]
        if request_run.prompt_context:
            user_parts.append(request_run.prompt_context)
        messages.append({"role": "user", "content": "\n\n".join(user_parts)})
        return messages

    def capabilities(self) -> dict[str, object]:
        base_url, model, _ = self._resolve_config()
        return {
            "streaming": True,
            "tool_use": False,
            "interactive_only": False,
            "api_style": "openai-compatible",
            "base_url": base_url,
            "model": model,
        }

    def list_models(self) -> list[str]:
        base_url, model, api_key = self._resolve_config()
        discovered: list[str] = []
        if base_url:
            req = request.Request(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
                method="GET",
            )
            try:
                with request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode("utf-8"))
                discovered = [
                    item["id"]
                    for item in data.get("data", [])
                    if isinstance(item, dict) and item.get("id")
                ]
            except Exception:
                discovered = []
        if model and model not in discovered:
            discovered.insert(0, model)
        return discovered
