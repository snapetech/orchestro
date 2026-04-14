from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch
from urllib import error

import pytest

from orchestro.embeddings import (
    EmbeddingResult,
    HashEmbeddingProvider,
    OpenAICompatEmbeddingProvider,
    build_embedding_provider,
)


class TestEmbeddingResult:
    def test_fields(self):
        r = EmbeddingResult(model_name="test-model", dimensions=4, embedding_blob=b"\x00" * 16)
        assert r.model_name == "test-model"
        assert r.dimensions == 4
        assert len(r.embedding_blob) == 16


class TestHashEmbeddingProvider:
    def test_default_dimensions(self):
        p = HashEmbeddingProvider()
        assert p.dimensions == 256

    def test_default_model_name(self):
        p = HashEmbeddingProvider()
        assert "hash" in p.model_name or "debug" in p.model_name

    def test_embed_returns_result(self):
        p = HashEmbeddingProvider(dimensions=16)
        result = p.embed("hello world")
        assert isinstance(result, EmbeddingResult)
        assert result.dimensions == 16

    def test_embed_blob_has_correct_byte_length(self):
        # Each float32 is 4 bytes
        p = HashEmbeddingProvider(dimensions=32)
        result = p.embed("test")
        assert len(result.embedding_blob) == 32 * 4

    def test_same_text_same_embedding(self):
        p = HashEmbeddingProvider(dimensions=16)
        r1 = p.embed("hello")
        r2 = p.embed("hello")
        assert r1.embedding_blob == r2.embedding_blob

    def test_different_text_different_embedding(self):
        p = HashEmbeddingProvider(dimensions=64)
        r1 = p.embed("hello")
        r2 = p.embed("world")
        assert r1.embedding_blob != r2.embedding_blob

    def test_custom_dimensions(self):
        for dim in [8, 64, 128, 512]:
            p = HashEmbeddingProvider(dimensions=dim)
            result = p.embed("text")
            assert result.dimensions == dim
            assert len(result.embedding_blob) == dim * 4

    def test_custom_model_name(self):
        p = HashEmbeddingProvider(model_name="my-hash-model")
        result = p.embed("text")
        assert result.model_name == "my-hash-model"

    def test_empty_string_embeds(self):
        p = HashEmbeddingProvider(dimensions=16)
        result = p.embed("")
        assert len(result.embedding_blob) == 16 * 4

    def test_long_text_embeds(self):
        p = HashEmbeddingProvider(dimensions=32)
        result = p.embed("x" * 10000)
        assert result.dimensions == 32


class TestOpenAICompatEmbeddingProvider:
    def _mock_response(self, embedding: list[float]) -> MagicMock:
        cm = MagicMock()
        cm.__enter__ = lambda s: s
        cm.__exit__ = MagicMock(return_value=False)
        data = {"data": [{"embedding": embedding}]}
        cm.read.return_value = json.dumps(data).encode()
        return cm

    def test_missing_base_url_raises(self, monkeypatch):
        monkeypatch.delenv("ORCHESTRO_EMBED_BASE_URL", raising=False)
        p = OpenAICompatEmbeddingProvider(model_name="m")
        with pytest.raises(RuntimeError, match="ORCHESTRO_EMBED_BASE_URL"):
            p.embed("hello")

    def test_missing_model_raises(self, monkeypatch):
        monkeypatch.delenv("ORCHESTRO_EMBED_MODEL", raising=False)
        p = OpenAICompatEmbeddingProvider(base_url="http://host/v1")
        with pytest.raises(RuntimeError, match="ORCHESTRO_EMBED_MODEL"):
            p.embed("hello")

    def test_successful_embed(self):
        embedding = [0.1, 0.2, 0.3, 0.4]
        p = OpenAICompatEmbeddingProvider(base_url="http://host/v1", model_name="m")
        with patch("orchestro.embeddings.request.urlopen", return_value=self._mock_response(embedding)):
            result = p.embed("test text")
        assert result.dimensions == 4
        assert result.model_name == "m"

    def test_env_base_url_used(self, monkeypatch):
        monkeypatch.setenv("ORCHESTRO_EMBED_BASE_URL", "http://env-host/v1")
        monkeypatch.setenv("ORCHESTRO_EMBED_MODEL", "env-model")
        p = OpenAICompatEmbeddingProvider()
        assert p.base_url == "http://env-host/v1"
        assert p.model_name == "env-model"

    def test_trailing_slash_stripped(self):
        p = OpenAICompatEmbeddingProvider(base_url="http://host/v1/")
        assert not p.base_url.endswith("/")

    def test_http_error_raises_runtime(self):
        p = OpenAICompatEmbeddingProvider(base_url="http://host/v1", model_name="m")
        exc = error.HTTPError("url", 503, "Service Unavailable", {}, io.BytesIO(b"down"))  # type: ignore[arg-type]
        with patch("orchestro.embeddings.request.urlopen", side_effect=exc):
            with pytest.raises(RuntimeError, match="503"):
                p.embed("test")

    def test_url_error_raises_runtime(self):
        p = OpenAICompatEmbeddingProvider(base_url="http://host/v1", model_name="m")
        exc = error.URLError("connection refused")
        with patch("orchestro.embeddings.request.urlopen", side_effect=exc):
            with pytest.raises(RuntimeError, match="connection refused"):
                p.embed("test")


class TestBuildEmbeddingProvider:
    def test_hash_provider(self):
        p = build_embedding_provider("hash")
        assert isinstance(p, HashEmbeddingProvider)

    def test_openai_compat_provider(self):
        p = build_embedding_provider("openai-compat")
        assert isinstance(p, OpenAICompatEmbeddingProvider)

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="unknown embedding provider"):
            build_embedding_provider("nonexistent")
