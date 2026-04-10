from __future__ import annotations

from textwrap import shorten

from orchestro.backends.base import Backend
from orchestro.models import BackendResponse, RunRequest


class MockBackend(Backend):
    name = "mock"

    def run(self, request: RunRequest) -> BackendResponse:
        prompt = request.goal.strip()
        preview = shorten(prompt.replace("\n", " "), width=120, placeholder="...")
        return BackendResponse(
            output_text=(
                "Mock backend response\n"
                f"strategy: {request.strategy_name}\n"
                f"cwd: {request.working_directory}\n"
                f"prompt: {preview}"
            ),
            metadata={
                "backend": self.name,
                "prompt_length": len(prompt),
            },
        )
