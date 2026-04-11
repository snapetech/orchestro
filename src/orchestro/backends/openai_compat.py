from __future__ import annotations

import json
import os
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
        api_key = self._api_key or os.environ.get("ORCHESTRO_OPENAI_API_KEY", "dummy")
        return base_url, model, api_key

    def resolved_base_url(self) -> str:
        return self._resolve_config()[0]

    def resolved_model(self) -> str:
        return self._resolve_config()[1]

    def run(self, request_run: RunRequest) -> BackendResponse:
        base_url, model, api_key = self._resolve_config()
        if not base_url:
            raise RuntimeError("ORCHESTRO_OPENAI_BASE_URL is not set")
        if not model:
            raise RuntimeError("ORCHESTRO_OPENAI_MODEL is not set")

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "\n\n".join(
                        part
                        for part in [
                            "You are Orchestro's current backend. Keep answers concise and useful.",
                            request_run.system_prompt,
                            request_run.prompt_context,
                        ]
                        if part
                    ),
                },
                {"role": "user", "content": request_run.goal},
            ],
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
            with request.urlopen(req, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"backend request failed: {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"backend request failed: {exc.reason}") from exc

        content = data["choices"][0]["message"]["content"]
        return BackendResponse(
            output_text=content,
            metadata={
                "backend": self.name,
                "model": model,
                "usage": data.get("usage", {}),
            },
        )

    def capabilities(self) -> dict[str, object]:
        base_url, model, _ = self._resolve_config()
        return {
            "streaming": False,
            "tool_use": False,
            "interactive_only": False,
            "api_style": "openai-compatible",
            "base_url": base_url,
            "model": model,
        }
