from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Callable

from orchestro.models import BackendResponse, RunRequest


@dataclass(slots=True)
class BackendProcessResult:
    exit_code: int
    stdout_text: str
    stderr_text: str


class BackendProcess(ABC):
    @abstractmethod
    def poll(self) -> int | None:
        raise NotImplementedError

    @abstractmethod
    def wait(self) -> BackendProcessResult:
        raise NotImplementedError

    @abstractmethod
    def terminate(self) -> None:
        raise NotImplementedError

    def pause(self) -> None:
        raise NotImplementedError("process pause is not supported")

    def resume(self) -> None:
        raise NotImplementedError("process resume is not supported")


class Backend(ABC):
    name: str

    @abstractmethod
    def run(self, request: RunRequest) -> BackendResponse:
        raise NotImplementedError

    def start(self, request: RunRequest) -> BackendProcess | None:
        del request
        return None

    def response_from_process(self, request: RunRequest, result: BackendProcessResult) -> BackendResponse:
        del request, result
        raise NotImplementedError("backend does not support subprocess execution")

    def stream(self, request: RunRequest) -> Iterator[str]:
        raise NotImplementedError("streaming is not supported by this backend")

    def run_streaming(
        self, request: RunRequest, *, on_chunk: Callable[[str], None] | None = None,
    ) -> BackendResponse:
        return self.run(request)

    def capabilities(self) -> dict[str, object]:
        return {
            "streaming": False,
            "tool_use": False,
            "interactive_only": False,
            "subprocess_control": False,
        }
