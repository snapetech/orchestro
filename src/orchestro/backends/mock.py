from __future__ import annotations

from textwrap import shorten

from orchestro.backends.base import Backend
from orchestro.models import BackendResponse, RunRequest


class MockBackend(Backend):
    name = "mock"

    def run(self, request: RunRequest) -> BackendResponse:
        prompt = request.goal.strip()
        preview = shorten(prompt.replace("\n", " "), width=120, placeholder="...")
        context_preview = None
        if request.prompt_context:
            context_preview = shorten(
                request.prompt_context.replace("\n", " "),
                width=120,
                placeholder="...",
            )
        return BackendResponse(
            output_text=(
                "Mock backend response\n"
                f"strategy: {request.strategy_name}\n"
                f"cwd: {request.working_directory}\n"
                f"prompt: {preview}\n"
                f"context: {context_preview or '-'}"
            ),
            metadata={
                "backend": self.name,
                "prompt_length": len(prompt),
                "has_prompt_context": bool(request.prompt_context),
            },
        )
