from __future__ import annotations

import io
import json
from typing import Any
from unittest.mock import MagicMock, patch
from urllib import error

import pytest

from orchestro.backends.openai_compat import OpenAICompatBackend
from orchestro.models import RunRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _request(
    goal: str = "test goal",
    system_prompt: str | None = None,
    prompt_context: str | None = None,
    stable_prefix: str | None = None,
    strategy_name: str = "direct",
    metadata: dict[str, Any] | None = None,
) -> RunRequest:
    return RunRequest(
        goal=goal,
        backend_name="openai-compat",
        system_prompt=system_prompt,
        prompt_context=prompt_context,
        stable_prefix=stable_prefix,
        strategy_name=strategy_name,
        metadata=metadata or {},
    )


def _make_response_body(
    content: str = "hello",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    total_tokens: int = 15,
    extra_usage: dict[str, Any] | None = None,
) -> bytes:
    usage: dict[str, Any] = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }
    if extra_usage:
        usage.update(extra_usage)
    data = {
        "choices": [{"message": {"content": content}}],
        "usage": usage,
    }
    return json.dumps(data).encode("utf-8")


def _mock_urlopen(body: bytes):
    """Return a context-manager mock that reads the given bytes."""
    cm = MagicMock()
    cm.__enter__ = lambda s: s
    cm.__exit__ = MagicMock(return_value=False)
    cm.read.return_value = body
    return cm


# ---------------------------------------------------------------------------
# _build_messages
# ---------------------------------------------------------------------------

class TestBuildMessages:
    def test_no_system_no_prefix(self):
        req = _request()
        msgs = OpenAICompatBackend._build_messages(req)
        roles = [m["role"] for m in msgs]
        assert roles == ["system", "user"]
        assert "orchestro" in msgs[0]["content"].lower()
        assert req.goal in msgs[1]["content"]

    def test_stable_prefix_prepended_as_system(self):
        req = _request(stable_prefix="Cached instructions here.")
        msgs = OpenAICompatBackend._build_messages(req)
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == "Cached instructions here."
        # The second system message is the regular one
        assert msgs[1]["role"] == "system"
        assert msgs[2]["role"] == "user"

    def test_system_prompt_merged_into_system_message(self):
        req = _request(system_prompt="Be concise.")
        msgs = OpenAICompatBackend._build_messages(req)
        system_msg = next(m for m in msgs if m["role"] == "system")
        assert "Be concise." in system_msg["content"]

    def test_prompt_context_appended_to_user_message(self):
        req = _request(prompt_context="Context here.")
        msgs = OpenAICompatBackend._build_messages(req)
        user_msg = next(m for m in msgs if m["role"] == "user")
        assert "Context here." in user_msg["content"]
        assert req.goal in user_msg["content"]

    def test_empty_system_prompt_not_doubled_newline(self):
        req = _request(system_prompt="")
        msgs = OpenAICompatBackend._build_messages(req)
        system_msg = next(m for m in msgs if m["role"] == "system")
        assert not system_msg["content"].startswith("\n\n")

    def test_full_combination(self):
        req = _request(
            goal="my goal",
            system_prompt="Sys.",
            prompt_context="Ctx.",
            stable_prefix="Prefix.",
        )
        msgs = OpenAICompatBackend._build_messages(req)
        assert msgs[0]["content"] == "Prefix."
        assert "Sys." in msgs[1]["content"]
        assert "my goal" in msgs[2]["content"]
        assert "Ctx." in msgs[2]["content"]


# ---------------------------------------------------------------------------
# Config resolution
# ---------------------------------------------------------------------------

class TestConfigResolution:
    def test_constructor_values_take_priority(self, monkeypatch):
        monkeypatch.setenv("ORCHESTRO_OPENAI_BASE_URL", "http://env:8000/v1")
        monkeypatch.setenv("ORCHESTRO_OPENAI_MODEL", "env-model")
        backend = OpenAICompatBackend(
            base_url="http://ctor:9000/v1",
            model="ctor-model",
            api_key="ctor-key",
        )
        assert backend.resolved_base_url() == "http://ctor:9000/v1"
        assert backend.resolved_model() == "ctor-model"

    def test_env_var_fallback(self, monkeypatch):
        monkeypatch.setenv("ORCHESTRO_OPENAI_BASE_URL", "http://env:8000/v1")
        monkeypatch.setenv("ORCHESTRO_OPENAI_MODEL", "env-model")
        backend = OpenAICompatBackend()
        assert backend.resolved_base_url() == "http://env:8000/v1"
        assert backend.resolved_model() == "env-model"

    def test_trailing_slash_stripped(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1/")
        assert not backend.resolved_base_url().endswith("/")


# ---------------------------------------------------------------------------
# run() — success and error paths
# ---------------------------------------------------------------------------

class TestRun:
    def test_missing_base_url_raises(self, monkeypatch):
        monkeypatch.delenv("ORCHESTRO_OPENAI_BASE_URL", raising=False)
        backend = OpenAICompatBackend(model="m")
        with pytest.raises(RuntimeError, match="ORCHESTRO_OPENAI_BASE_URL"):
            backend.run(_request())

    def test_missing_model_raises(self, monkeypatch):
        monkeypatch.delenv("ORCHESTRO_OPENAI_MODEL", raising=False)
        backend = OpenAICompatBackend(base_url="http://host:8000/v1")
        with pytest.raises(RuntimeError, match="ORCHESTRO_OPENAI_MODEL"):
            backend.run(_request())

    def test_successful_response(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
        body = _make_response_body("the answer")
        with patch("orchestro.backends.openai_compat.request.urlopen", return_value=_mock_urlopen(body)):
            resp = backend.run(_request())
        assert resp.output_text == "the answer"
        assert resp.prompt_tokens == 10
        assert resp.completion_tokens == 5
        assert resp.total_tokens == 15

    def test_backend_model_override_used_in_payload(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="default-model")
        body = _make_response_body("the answer")
        with patch("orchestro.backends.openai_compat.request.urlopen", return_value=_mock_urlopen(body)) as mock_urlopen:
            backend.run(_request(metadata={"backend_model": "override-model"}))
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["model"] == "override-model"

    def test_http_error_raises_runtime(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
        exc = error.HTTPError("url", 503, "Service Unavailable", {}, io.BytesIO(b"down"))  # type: ignore[arg-type]
        with patch("orchestro.backends.openai_compat.request.urlopen", side_effect=exc):
            with pytest.raises(RuntimeError, match="503"):
                backend.run(_request())

    def test_url_error_raises_runtime(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
        exc = error.URLError("connection refused")
        with patch("orchestro.backends.openai_compat.request.urlopen", side_effect=exc):
            with pytest.raises(RuntimeError, match="connection refused"):
                backend.run(_request())

    def test_cache_read_tokens_extracted(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
        body = _make_response_body(extra_usage={"cache_read_input_tokens": 200})
        with patch("orchestro.backends.openai_compat.request.urlopen", return_value=_mock_urlopen(body)):
            resp = backend.run(_request())
        assert resp.cache_read_tokens == 200

    def test_cache_write_tokens_extracted(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
        body = _make_response_body(extra_usage={"cache_creation_input_tokens": 512})
        with patch("orchestro.backends.openai_compat.request.urlopen", return_value=_mock_urlopen(body)):
            resp = backend.run(_request())
        assert resp.cache_write_tokens == 512

    def test_prompt_tokens_details_cached_tokens_captured(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
        body = _make_response_body(
            extra_usage={"prompt_tokens_details": {"cached_tokens": 100}}
        )
        with patch("orchestro.backends.openai_compat.request.urlopen", return_value=_mock_urlopen(body)):
            resp = backend.run(_request())
        assert resp.metadata["cache_stats"]["cached_tokens"] == 100

    def test_no_cache_fields_defaults_to_zero(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
        body = _make_response_body()
        with patch("orchestro.backends.openai_compat.request.urlopen", return_value=_mock_urlopen(body)):
            resp = backend.run(_request())
        assert resp.cache_read_tokens == 0
        assert resp.cache_write_tokens == 0

    def test_stable_prefix_tracked_in_metadata(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
        body = _make_response_body()
        req = _request(stable_prefix="PREFIX")
        with patch("orchestro.backends.openai_compat.request.urlopen", return_value=_mock_urlopen(body)):
            resp = backend.run(req)
        cs = resp.metadata["cache_stats"]
        assert cs["stable_prefix_used"] is True
        assert cs["stable_prefix_length"] == len("PREFIX")

    def test_metadata_includes_backend_and_model(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="mymodel")
        body = _make_response_body()
        with patch("orchestro.backends.openai_compat.request.urlopen", return_value=_mock_urlopen(body)):
            resp = backend.run(_request())
        assert resp.metadata["backend"] == "openai-compat"
        assert resp.metadata["model"] == "mymodel"


# ---------------------------------------------------------------------------
# stream() — SSE parsing
# ---------------------------------------------------------------------------

def _sse_lines(*contents: str | None, done: bool = True) -> list[bytes]:
    """Build raw SSE lines as the backend would receive them."""
    lines = []
    for content in contents:
        if content is None:
            chunk = {"choices": [{"delta": {}}]}
        else:
            chunk = {"choices": [{"delta": {"content": content}}]}
        lines.append(f"data: {json.dumps(chunk)}\n".encode())
    if done:
        lines.append(b"data: [DONE]\n")
    return lines


class FakeStreamResponse:
    """Mimics a urllib response iterable over raw SSE lines."""
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines
        self._closed = False

    def __iter__(self):
        return iter(self._lines)

    def close(self):
        self._closed = True


class TestStream:
    def test_yields_content_chunks(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
        lines = _sse_lines("hello", " world")
        with patch("orchestro.backends.openai_compat.request.urlopen", return_value=FakeStreamResponse(lines)):
            chunks = list(backend.stream(_request()))
        assert chunks == ["hello", " world"]

    def test_done_sentinel_stops_iteration(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
        lines = _sse_lines("part1", done=True)
        # Add extra data after DONE — should not be yielded
        lines.append(b"data: {\"choices\": [{\"delta\": {\"content\": \"EXTRA\"}}]}\n")
        with patch("orchestro.backends.openai_compat.request.urlopen", return_value=FakeStreamResponse(lines)):
            chunks = list(backend.stream(_request()))
        assert "EXTRA" not in chunks

    def test_non_data_lines_skipped(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
        raw = [
            b"event: message\n",
            b"data: " + json.dumps({"choices": [{"delta": {"content": "ok"}}]}).encode() + b"\n",
            b"data: [DONE]\n",
        ]
        with patch("orchestro.backends.openai_compat.request.urlopen", return_value=FakeStreamResponse(raw)):
            chunks = list(backend.stream(_request()))
        assert chunks == ["ok"]

    def test_malformed_json_chunk_skipped(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
        raw = [
            b"data: not-json\n",
            b"data: " + json.dumps({"choices": [{"delta": {"content": "fine"}}]}).encode() + b"\n",
            b"data: [DONE]\n",
        ]
        with patch("orchestro.backends.openai_compat.request.urlopen", return_value=FakeStreamResponse(raw)):
            chunks = list(backend.stream(_request()))
        assert chunks == ["fine"]

    def test_empty_delta_produces_no_chunk(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
        lines = _sse_lines(None, "real")  # first delta has no content key
        with patch("orchestro.backends.openai_compat.request.urlopen", return_value=FakeStreamResponse(lines)):
            chunks = list(backend.stream(_request()))
        assert chunks == ["real"]

    def test_stream_missing_base_url_raises(self, monkeypatch):
        monkeypatch.delenv("ORCHESTRO_OPENAI_BASE_URL", raising=False)
        backend = OpenAICompatBackend(model="m")
        with pytest.raises(RuntimeError, match="ORCHESTRO_OPENAI_BASE_URL"):
            list(backend.stream(_request()))

    def test_stream_http_error_raises(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
        exc = error.HTTPError("url", 500, "Internal Server Error", {}, io.BytesIO(b"err"))  # type: ignore[arg-type]
        with patch("orchestro.backends.openai_compat.request.urlopen", side_effect=exc):
            with pytest.raises(RuntimeError, match="500"):
                list(backend.stream(_request()))

    def test_response_closed_after_streaming(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
        fake = FakeStreamResponse(_sse_lines("hi"))
        with patch("orchestro.backends.openai_compat.request.urlopen", return_value=fake):
            list(backend.stream(_request()))
        assert fake._closed is True


# ---------------------------------------------------------------------------
# run_streaming()
# ---------------------------------------------------------------------------

class TestRunStreaming:
    def test_accumulates_chunks_into_output_text(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
        lines = _sse_lines("hello", " world")
        with patch("orchestro.backends.openai_compat.request.urlopen", return_value=FakeStreamResponse(lines)):
            resp = backend.run_streaming(_request())
        assert resp.output_text == "hello world"

    def test_on_chunk_called_for_each_piece(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
        lines = _sse_lines("a", "b", "c")
        received: list[str] = []
        with patch("orchestro.backends.openai_compat.request.urlopen", return_value=FakeStreamResponse(lines)):
            backend.run_streaming(_request(), on_chunk=received.append)
        assert received == ["a", "b", "c"]

    def test_on_chunk_none_is_safe(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
        lines = _sse_lines("x")
        with patch("orchestro.backends.openai_compat.request.urlopen", return_value=FakeStreamResponse(lines)):
            resp = backend.run_streaming(_request(), on_chunk=None)
        assert resp.output_text == "x"

    def test_metadata_includes_streaming_flag(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
        lines = _sse_lines("ok")
        with patch("orchestro.backends.openai_compat.request.urlopen", return_value=FakeStreamResponse(lines)):
            resp = backend.run_streaming(_request())
        assert resp.metadata.get("streaming") is True

    def test_completion_tokens_estimated_from_text_length(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
        # 100 chars → at least 1 token
        text = "x" * 100
        lines = _sse_lines(text)
        with patch("orchestro.backends.openai_compat.request.urlopen", return_value=FakeStreamResponse(lines)):
            resp = backend.run_streaming(_request())
        assert resp.completion_tokens >= 1


# ---------------------------------------------------------------------------
# capabilities()
# ---------------------------------------------------------------------------

class TestCapabilities:
    def test_returns_expected_keys(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="m")
        caps = backend.capabilities()
        assert caps["streaming"] is True
        assert caps["tool_use"] is False
        assert caps["api_style"] == "openai-compatible"

    def test_base_url_and_model_reflected(self):
        backend = OpenAICompatBackend(base_url="http://host:8000/v1", model="mymodel")
        caps = backend.capabilities()
        assert "host" in caps["base_url"]
        assert caps["model"] == "mymodel"
