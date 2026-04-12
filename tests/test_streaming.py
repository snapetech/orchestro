from __future__ import annotations

from orchestro.backends.mock import MockBackend
from orchestro.models import BackendResponse, RunRequest


class TestMockBackendRunStreaming:
    def test_streaming_falls_back_to_run(self):
        backend = MockBackend()
        request = RunRequest(goal="Hello", backend_name="mock")
        chunks: list[str] = []
        response = backend.run_streaming(request, on_chunk=lambda c: chunks.append(c))
        assert isinstance(response, BackendResponse)
        assert "Mock backend response" in response.output_text


class TestBackendResponseStreamingMetadata:
    def test_response_with_streaming_metadata(self):
        response = BackendResponse(
            output_text="streamed result",
            metadata={"streaming": True, "chunks_received": 5},
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )
        assert response.output_text == "streamed result"
        assert response.metadata["streaming"] is True
        assert response.metadata["chunks_received"] == 5
        assert response.prompt_tokens == 10
        assert response.completion_tokens == 20
        assert response.total_tokens == 30
