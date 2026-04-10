from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from typing import Mapping

from orchestro.backends.base import Backend, BackendProcess, BackendProcessResult
from orchestro.models import BackendResponse, RunRequest


@dataclass(slots=True)
class SubprocessHandle(BackendProcess):
    process: subprocess.Popen[str]

    def poll(self) -> int | None:
        return self.process.poll()

    def wait(self) -> BackendProcessResult:
        stdout_text, stderr_text = self.process.communicate()
        return BackendProcessResult(
            exit_code=int(self.process.returncode or 0),
            stdout_text=stdout_text,
            stderr_text=stderr_text,
        )

    def terminate(self) -> None:
        if self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=2)


class SubprocessCommandBackend(Backend):
    name = "subprocess-command"

    def __init__(self, *, command: str | None = None, shell: bool = False) -> None:
        self.command = command or os.environ.get("ORCHESTRO_SUBPROCESS_COMMAND", "")
        self.shell = shell or os.environ.get("ORCHESTRO_SUBPROCESS_SHELL", "").lower() in {"1", "true", "yes"}

    def run(self, request: RunRequest) -> BackendResponse:
        handle = self.start(request)
        if handle is None:
            raise RuntimeError("ORCHESTRO_SUBPROCESS_COMMAND is not set")
        result = handle.wait()
        return self.response_from_process(request, result)

    def start(self, request: RunRequest) -> BackendProcess | None:
        if not self.command:
            return None
        env = os.environ.copy()
        env.update(self._request_env(request))
        argv: str | list[str]
        if self.shell:
            argv = self.command
        else:
            argv = shlex.split(self.command)
        process = subprocess.Popen(
            argv,
            cwd=str(request.working_directory),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=self.shell,
        )
        return SubprocessHandle(process=process)

    def response_from_process(self, request: RunRequest, result: BackendProcessResult) -> BackendResponse:
        if result.exit_code != 0:
            stderr_preview = result.stderr_text.strip() or f"exit code {result.exit_code}"
            raise RuntimeError(f"subprocess backend failed: {stderr_preview}")
        return BackendResponse(
            output_text=result.stdout_text.strip(),
            metadata={
                "backend": self.name,
                "command": self.command,
                "exit_code": result.exit_code,
                "stderr": result.stderr_text.strip(),
                "has_prompt_context": bool(request.prompt_context),
            },
        )

    def capabilities(self) -> dict[str, object]:
        return {
            "streaming": False,
            "tool_use": False,
            "interactive_only": False,
            "subprocess_control": True,
            "shell": self.shell,
            "command_configured": bool(self.command),
        }

    def _request_env(self, request: RunRequest) -> Mapping[str, str]:
        metadata_domain = request.metadata.get("domain")
        return {
            "ORCHESTRO_GOAL": request.goal,
            "ORCHESTRO_STRATEGY": request.strategy_name,
            "ORCHESTRO_SYSTEM_PROMPT": request.system_prompt or "",
            "ORCHESTRO_PROMPT_CONTEXT": request.prompt_context or "",
            "ORCHESTRO_WORKDIR": str(request.working_directory),
            "ORCHESTRO_PARENT_RUN_ID": request.parent_run_id or "",
            "ORCHESTRO_DOMAIN": "" if metadata_domain is None else str(metadata_domain),
        }
