from __future__ import annotations

import io
import json
from unittest.mock import patch
from urllib import error

import pytest

from orchestro.backends.anthropic import AnthropicBackend
from orchestro.models import RunRequest


def _request(metadata: dict[str, object] | None = None) -> RunRequest:
    return RunRequest(
        goal="test goal",
        backend_name="anthropic",
        metadata=metadata or {},
    )


class FakeStreamResponse:
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines
        self.closed = False

    def __iter__(self):
        return iter(self._lines)

    def close(self):
        self.closed = True


def _event(data: dict[str, object]) -> bytes:
    return f"data: {json.dumps(data)}\n".encode("utf-8")


def test_run_streaming_uses_backend_model_override():
    backend = AnthropicBackend(model="default-model", api_key="test-key")
    lines = [
        _event({"type": "content_block_delta", "delta": {"type": "text_delta", "text": "hello"}}),
        b"data: [DONE]\n",
    ]
    with patch("orchestro.backends.anthropic.request.urlopen", return_value=FakeStreamResponse(lines)) as mock_urlopen:
        backend.run_streaming(_request(metadata={"backend_model": "override-model"}))

    req = mock_urlopen.call_args[0][0]
    payload = json.loads(req.data.decode("utf-8"))
    assert payload["model"] == "override-model"


def test_run_streaming_collects_usage_from_events():
    backend = AnthropicBackend(model="claude-test", api_key="test-key")
    lines = [
        _event(
            {
                "type": "message_start",
                "message": {
                    "usage": {
                        "input_tokens": 12,
                        "cache_read_input_tokens": 3,
                    }
                },
            }
        ),
        _event({"type": "content_block_delta", "delta": {"type": "text_delta", "text": "hello"}}),
        _event(
            {
                "type": "message_delta",
                "delta": {
                    "stop_reason": "end_turn",
                    "usage": {
                        "output_tokens": 7,
                        "cache_creation_input_tokens": 2,
                    },
                },
            }
        ),
        b"data: [DONE]\n",
    ]
    with patch("orchestro.backends.anthropic.request.urlopen", return_value=FakeStreamResponse(lines)):
        response = backend.run_streaming(_request())

    assert response.output_text == "hello"
    assert response.prompt_tokens == 12
    assert response.completion_tokens == 7
    assert response.total_tokens == 19
    assert response.cache_read_tokens == 3
    assert response.cache_write_tokens == 2
    assert response.metadata["usage"] == {"input_tokens": 12, "output_tokens": 7}
    assert response.metadata["stop_reason"] == "end_turn"


def test_run_streaming_falls_back_to_estimated_output_tokens():
    backend = AnthropicBackend(model="claude-test", api_key="test-key")
    lines = [
        _event({"type": "content_block_delta", "delta": {"type": "text_delta", "text": "abcdefgh"}}),
        b"data: [DONE]\n",
    ]
    with patch("orchestro.backends.anthropic.request.urlopen", return_value=FakeStreamResponse(lines)):
        response = backend.run_streaming(_request())

    assert response.prompt_tokens == 0
    assert response.completion_tokens >= 1
    assert response.total_tokens == response.completion_tokens


def test_run_streaming_http_error_raises_runtime():
    backend = AnthropicBackend(model="claude-test", api_key="test-key")
    exc = error.HTTPError("url", 429, "Too Many Requests", {}, io.BytesIO(b"quota"))  # type: ignore[arg-type]

    with patch("orchestro.backends.anthropic.request.urlopen", side_effect=exc):
        with pytest.raises(RuntimeError, match="429"):
            backend.run_streaming(_request())
