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
        self.base_url = (base_url or os.environ.get("ORCHESTRO_OPENAI_BASE_URL", "")).rstrip("/")
        self.model = model or os.environ.get("ORCHESTRO_OPENAI_MODEL", "")
        self.api_key = api_key or os.environ.get("ORCHESTRO_OPENAI_API_KEY", "dummy")

    def run(self, request_run: RunRequest) -> BackendResponse:
        if not self.base_url:
            raise RuntimeError("ORCHESTRO_OPENAI_BASE_URL is not set")
        if not self.model:
            raise RuntimeError("ORCHESTRO_OPENAI_MODEL is not set")

        payload = {
            "model": self.model,
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
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
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
                "model": self.model,
                "usage": data.get("usage", {}),
            },
        )

    def capabilities(self) -> dict[str, object]:
        return {
            "streaming": False,
            "tool_use": False,
            "interactive_only": False,
            "api_style": "openai-compatible",
        }
