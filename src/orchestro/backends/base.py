from __future__ import annotations

from abc import ABC, abstractmethod

from orchestro.models import BackendResponse, RunRequest


class Backend(ABC):
    name: str

    @abstractmethod
    def run(self, request: RunRequest) -> BackendResponse:
        raise NotImplementedError

    def capabilities(self) -> dict[str, object]:
        return {
            "streaming": False,
            "tool_use": False,
            "interactive_only": False,
        }
