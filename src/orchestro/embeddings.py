from __future__ import annotations

import hashlib
import json
import os
import struct
from dataclasses import dataclass
from urllib import error, request

try:
    from sqlite_vec import serialize_float32 as _serialize_float32
except ImportError:
    def _serialize_float32(values: list[float]) -> bytes:
        # Keep the embedding providers usable when sqlite-vec is unavailable.
        return struct.pack(f"<{len(values)}f", *values)


@dataclass(slots=True)
class EmbeddingResult:
    model_name: str
    dimensions: int
    embedding_blob: bytes


class HashEmbeddingProvider:
    def __init__(self, *, dimensions: int = 256, model_name: str = "debug-hash-256") -> None:
        self.dimensions = dimensions
        self.model_name = model_name

    def embed(self, text: str) -> EmbeddingResult:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        seed = digest
        while len(values) < self.dimensions:
            seed = hashlib.sha256(seed + text.encode("utf-8")).digest()
            for idx in range(0, len(seed), 4):
                chunk = seed[idx : idx + 4]
                if len(chunk) < 4:
                    continue
                value = int.from_bytes(chunk, "big", signed=False)
                values.append((value / 2147483648.0) - 1.0)
                if len(values) >= self.dimensions:
                    break
        return EmbeddingResult(
            model_name=self.model_name,
            dimensions=self.dimensions,
            embedding_blob=_serialize_float32(values),
        )


class OpenAICompatEmbeddingProvider:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model_name: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("ORCHESTRO_EMBED_BASE_URL", "")).rstrip("/")
        self.model_name = model_name or os.environ.get("ORCHESTRO_EMBED_MODEL", "")
        self.api_key = api_key or os.environ.get("ORCHESTRO_EMBED_API_KEY", "dummy")

    def embed(self, text: str) -> EmbeddingResult:
        if not self.base_url:
            raise RuntimeError("ORCHESTRO_EMBED_BASE_URL is not set")
        if not self.model_name:
            raise RuntimeError("ORCHESTRO_EMBED_MODEL is not set")
        payload = {"model": self.model_name, "input": text}
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/embeddings",
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
            raise RuntimeError(f"embedding request failed: {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"embedding request failed: {exc.reason}") from exc

        embedding = data["data"][0]["embedding"]
        return EmbeddingResult(
            model_name=self.model_name,
            dimensions=len(embedding),
            embedding_blob=_serialize_float32(embedding),
        )


def build_embedding_provider(provider: str):
    if provider == "hash":
        return HashEmbeddingProvider()
    if provider == "openai-compat":
        return OpenAICompatEmbeddingProvider()
    raise ValueError(f"unknown embedding provider: {provider}")
