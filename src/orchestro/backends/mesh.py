"""Orchestro Mesh backend.

Speaks to an Orchestro Mesh gateway over its OpenAI-compatible /v1 surface
while also tagging requests with mesh-specific routing fields (sensitivity,
task_class) and capturing the mesh request_id back into BackendResponse
metadata so verifier outcomes can be reported as feedback.

Configuration (env or constructor):
- ORCHESTRO_MESH_GATEWAY_URL: the gateway base, e.g. http://127.0.0.1:8765/v1
- ORCHESTRO_MESH_TOKEN: bearer token accepted by the gateway
- ORCHESTRO_MESH_REQUESTER: the X-Orchestro-Requester identity, when the
  gateway is in mesh_token mode (per-user api_tokens override this).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any, Callable
from urllib import error, request

from orchestro.backends.base import Backend
from orchestro.models import BackendResponse, RunRequest


class MeshBackend(Backend):
    name = "mesh"

    def __init__(
        self,
        *,
        gateway_url: str | None = None,
        token: str | None = None,
        requester: str | None = None,
        model: str | None = None,
        default_sensitivity: str = "public",
        default_task_class: str = "chat",
        timeout_s: float = 120.0,
    ) -> None:
        self._gateway_url = gateway_url
        self._token = token
        self._requester = requester
        self._model = model
        self._default_sensitivity = default_sensitivity
        self._default_task_class = default_task_class
        self._timeout_s = timeout_s

    def _resolve(self) -> tuple[str, str | None, str | None, str | None]:
        gateway_url = (
            self._gateway_url
            or os.environ.get("ORCHESTRO_MESH_GATEWAY_URL")
            or ""
        ).rstrip("/")
        # Allow URLs that end in /v1 or just the host; normalize to include /v1.
        if gateway_url and not gateway_url.endswith("/v1"):
            gateway_url = f"{gateway_url}/v1"
        token = self._token or os.environ.get("ORCHESTRO_MESH_TOKEN")
        requester = self._requester or os.environ.get("ORCHESTRO_MESH_REQUESTER")
        model = self._model or os.environ.get("ORCHESTRO_MESH_MODEL")
        return gateway_url, token, requester, model

    def _headers(self, token: str | None, requester: str | None) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if requester:
            headers["X-Orchestro-Requester"] = requester
        return headers

    @staticmethod
    def _build_messages(run_request: RunRequest) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if run_request.stable_prefix:
            messages.append({"role": "system", "content": run_request.stable_prefix})
        system_parts = [
            "You are Orchestro's current backend, running on the Orchestro Mesh.",
            run_request.system_prompt,
        ]
        system = "\n\n".join(p for p in system_parts if p)
        if system:
            messages.append({"role": "system", "content": system})
        user_parts = [run_request.goal]
        if run_request.prompt_context:
            user_parts.append(run_request.prompt_context)
        messages.append({"role": "user", "content": "\n\n".join(user_parts)})
        return messages

    def _build_payload(self, run_request: RunRequest, model: str | None, stream: bool) -> dict[str, Any]:
        meta = run_request.metadata or {}
        sensitivity = str(meta.get("mesh_sensitivity") or self._default_sensitivity)
        task_class = str(meta.get("mesh_task_class") or self._default_task_class)
        backend_model = str(meta.get("backend_model") or model or "")
        payload: dict[str, Any] = {
            "messages": self._build_messages(run_request),
            "sensitivity": sensitivity,
            "task_class": task_class,
            "stream": stream,
        }
        if backend_model:
            payload["model"] = backend_model
        if "max_tokens" in meta:
            payload["max_tokens"] = int(meta["max_tokens"])
        for key in ("temperature", "top_p", "tools", "tool_choice", "response_format"):
            if key in meta:
                payload[key] = meta[key]
        return payload

    def run(self, request_run: RunRequest) -> BackendResponse:
        gateway_url, token, requester, model = self._resolve()
        if not gateway_url:
            raise RuntimeError("ORCHESTRO_MESH_GATEWAY_URL is not set")

        payload = self._build_payload(request_run, model, stream=False)
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{gateway_url}/chat/completions",
            data=body,
            headers=self._headers(token, requester),
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self._timeout_s) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"mesh request failed: {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"mesh request failed: {exc.reason}") from exc

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        mesh_meta = data.get("orchestro_mesh", {}) or {}
        return BackendResponse(
            output_text=content,
            metadata={
                "backend": self.name,
                "model": mesh_meta.get("model_id") or payload.get("model"),
                "usage": usage,
                "mesh_request_id": mesh_meta.get("request_id"),
                "mesh_node_id": mesh_meta.get("node_id"),
                "mesh_model_id": mesh_meta.get("model_id"),
                "mesh_attempts": mesh_meta.get("attempts"),
                "mesh_credit_cost": mesh_meta.get("credit_cost"),
                "mesh_gateway_url": gateway_url,
                "mesh_token": token,
                "mesh_requester": requester,
            },
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )

    def stream(self, request_run: RunRequest) -> Iterator[str]:
        gateway_url, token, requester, model = self._resolve()
        if not gateway_url:
            raise RuntimeError("ORCHESTRO_MESH_GATEWAY_URL is not set")
        payload = self._build_payload(request_run, model, stream=True)
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{gateway_url}/chat/completions",
            data=body,
            headers=self._headers(token, requester),
            method="POST",
        )
        try:
            resp = request.urlopen(req, timeout=self._timeout_s)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"mesh request failed: {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"mesh request failed: {exc.reason}") from exc
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
                delta = choices[0].get("delta") or choices[0].get("message") or {}
                content = delta.get("content")
                if isinstance(content, str) and content:
                    yield content
        finally:
            resp.close()

    def run_streaming(
        self,
        request_run: RunRequest,
        *,
        on_chunk: Callable[[str], None] | None = None,
    ) -> BackendResponse:
        chunks: list[str] = []
        for chunk in self.stream(request_run):
            chunks.append(chunk)
            if on_chunk:
                on_chunk(chunk)
        full_text = "".join(chunks)
        completion_tokens = max(1, len(full_text) // 4)
        return BackendResponse(
            output_text=full_text,
            metadata={"backend": self.name, "streaming": True},
            prompt_tokens=0,
            completion_tokens=completion_tokens,
            total_tokens=completion_tokens,
        )

    def capabilities(self) -> dict[str, object]:
        gateway_url, _, requester, model = self._resolve()
        return {
            "streaming": True,
            "tool_use": True,
            "interactive_only": False,
            "api_style": "openai-compatible-mesh",
            "gateway_url": gateway_url,
            "requester": requester,
            "model": model,
        }

    def list_models(self) -> list[str]:
        gateway_url, token, _, model = self._resolve()
        discovered: list[str] = []
        if gateway_url:
            req = request.Request(
                f"{gateway_url}/models",
                headers={"Authorization": f"Bearer {token}"} if token else {},
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
