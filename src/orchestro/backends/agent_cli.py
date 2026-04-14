"""
agent_cli.py — Backend implementations for external AI agent CLI tools.

Each AgentCLIBackend wraps an installed CLI binary (claude, codex, kilocode,
cursor) using a consistent interface.  The binary is invoked as a subprocess;
its stdout becomes the run output.

Health checking is done via shutil.which — no live network call is needed.
If the binary is absent the backend is simply not included in the reachable
set and routing skips it.

Named factory functions return pre-configured instances:

    make_claude_code_backend()   — claude --print  (Claude Code CLI)
    make_codex_backend()         — codex exec --full-auto
    make_kilocode_backend()      — kilocode run --auto
    make_cursor_backend()        — cursor-agent --print --mode ask

Each can be further customised via environment variables documented in
.env.example under the "Agent CLI backends" section.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Callable

from orchestro.backends.base import Backend, BackendProcessResult
from orchestro.models import BackendResponse, RunRequest


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class AgentCLIBackend(Backend):
    """Delegate a run to an installed AI agent CLI tool."""

    # Subclasses or instances that set name as a class attribute are fine;
    # constructor-provided name takes priority.
    name: str = "agent-cli"

    def __init__(
        self,
        *,
        name: str,
        binary: str,
        argv_builder: Callable[[RunRequest], list[str]],
        task_strengths: set[str] | None = None,
        model_discovery: Callable[[str], list[str]] | None = None,
        timeout: int = 300,
    ) -> None:
        self.name = name
        self._binary = binary
        self._argv_builder = argv_builder
        self._task_strengths: set[str] = task_strengths or set()
        self._model_discovery = model_discovery
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return True if the CLI binary exists on PATH."""
        return shutil.which(self._binary) is not None

    def resolved_binary(self) -> str:
        """Return the full path to the binary, or just the name if not found."""
        return shutil.which(self._binary) or self._binary

    # ------------------------------------------------------------------
    # Backend interface
    # ------------------------------------------------------------------

    def run(self, request: RunRequest) -> BackendResponse:
        if not self.is_available():
            raise RuntimeError(
                f"Agent CLI backend '{self.name}' requires '{self._binary}' on PATH. "
                f"Install it or configure a different backend."
            )
        argv = [self._binary, *self._argv_builder(request)]
        env = os.environ.copy()
        # Expose request fields so advanced wrappers can read them.
        env.update({
            "ORCHESTRO_GOAL": request.goal,
            "ORCHESTRO_STRATEGY": request.strategy_name,
            "ORCHESTRO_SYSTEM_PROMPT": request.system_prompt or "",
            "ORCHESTRO_PROMPT_CONTEXT": request.prompt_context or "",
        })
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                env=env,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Agent CLI '{self.name}' timed out after {self._timeout}s"
            ) from exc

        result = BackendProcessResult(
            exit_code=proc.returncode,
            stdout_text=proc.stdout,
            stderr_text=proc.stderr,
        )
        return self._response_from_result(request, result)

    def capabilities(self) -> dict[str, object]:
        return {
            "streaming": False,
            "tool_use": True,
            "interactive_only": False,
            "subprocess_control": False,
            "binary": self._binary,
            "available": self.is_available(),
            "task_strengths": sorted(self._task_strengths),
        }

    def list_models(self) -> list[str]:
        if self._model_discovery is None:
            return []
        try:
            return self._model_discovery(self._binary)
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _response_from_result(
        self, request: RunRequest, result: BackendProcessResult
    ) -> BackendResponse:
        if result.exit_code != 0:
            stderr = result.stderr_text.strip() or f"exit code {result.exit_code}"
            raise RuntimeError(f"Agent CLI '{self.name}' failed: {stderr}")
        output = result.stdout_text.strip()
        return BackendResponse(
            output_text=output,
            metadata={
                "backend": self.name,
                "binary": self._binary,
                "exit_code": result.exit_code,
                "stderr": result.stderr_text.strip(),
                "has_prompt_context": bool(request.prompt_context),
            },
        )


# ---------------------------------------------------------------------------
# argv builders
# ---------------------------------------------------------------------------

def _claude_code_argv(request: RunRequest) -> list[str]:
    """Build argv for claude --print.

    If a system prompt is present it is prepended to the goal text, since
    the non-interactive (--print) mode does not expose a separate --system
    flag in all release versions.
    """
    # Allow the user to override the print flag via env (e.g. for future
    # claude CLI versions that change the flag name).
    print_flag = os.environ.get("ORCHESTRO_CLAUDE_PRINT_FLAG", "--print")
    argv: list[str] = [print_flag]
    backend_model = str(request.metadata.get("backend_model") or "").strip()
    if backend_model:
        argv.extend(["--model", backend_model])

    # claude supports --output-format for machine-readable output.
    output_fmt = os.environ.get("ORCHESTRO_CLAUDE_OUTPUT_FORMAT", "text")
    if output_fmt != "text":
        argv.extend(["--output-format", output_fmt])

    # Compose the prompt text from system + goal + context.
    parts: list[str] = []
    if request.system_prompt:
        parts.append(request.system_prompt)
    parts.append(request.goal)
    if request.prompt_context:
        parts.append(request.prompt_context)
    argv.append("\n\n".join(parts))
    return argv


def _codex_argv(request: RunRequest) -> list[str]:
    """Build argv for codex exec in non-interactive mode."""
    argv: list[str] = ["exec"]
    execution_mode = os.environ.get("ORCHESTRO_CODEX_APPROVAL_MODE", "full-auto")
    if execution_mode == "full-auto":
        argv.append("--full-auto")
    elif execution_mode:
        argv.extend(["--sandbox", execution_mode])
    backend_model = str(request.metadata.get("backend_model") or "").strip()
    if backend_model:
        argv.extend(["--model", backend_model])

    parts: list[str] = []
    if request.system_prompt:
        parts.append(request.system_prompt)
    parts.append(request.goal)
    if request.prompt_context:
        parts.append(request.prompt_context)
    argv.append("\n\n".join(parts))
    return argv


def _kilocode_argv(request: RunRequest) -> list[str]:
    """Build argv for kilocode run --auto."""
    argv: list[str] = ["run", "--auto"]
    backend_model = str(request.metadata.get("backend_model") or "").strip()
    if backend_model:
        argv.extend(["--model", backend_model])

    parts: list[str] = []
    if request.system_prompt:
        parts.append(request.system_prompt)
    parts.append(request.goal)
    if request.prompt_context:
        parts.append(request.prompt_context)
    argv.append("\n\n".join(parts))
    return argv


def _cursor_argv(request: RunRequest) -> list[str]:
    """Build argv for cursor-agent in non-interactive print mode.

    Set ORCHESTRO_CURSOR_EXTRA_ARGS to append additional flags, e.g.:
        ORCHESTRO_CURSOR_EXTRA_ARGS="--model gpt-4o"
    """
    argv: list[str] = ["--print", "--mode", "ask"]
    backend_model = str(request.metadata.get("backend_model") or "").strip()
    if backend_model:
        argv.extend(["--model", backend_model])

    extra = os.environ.get("ORCHESTRO_CURSOR_EXTRA_ARGS", "")
    if extra:
        import shlex
        argv.extend(shlex.split(extra))

    parts: list[str] = []
    if request.system_prompt:
        parts.append(request.system_prompt)
    parts.append(request.goal)
    if request.prompt_context:
        parts.append(request.prompt_context)
    argv.append("\n\n".join(parts))
    return argv


def _extract_model_tokens(text: str) -> list[str]:
    seen: list[str] = []
    for match in re.findall(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.:-]+|(?:gpt|claude|sonnet|opus|haiku)[A-Za-z0-9_.:-]*", text):
        if match not in seen:
            seen.append(match)
    return seen


def _discover_cursor_models(binary: str) -> list[str]:
    proc = subprocess.run(
        [binary, "models"],
        capture_output=True,
        text=True,
        timeout=20,
        stdin=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        return []
    return _extract_model_tokens(proc.stdout)


def _discover_kilocode_models(binary: str) -> list[str]:
    proc = subprocess.run(
        [binary, "models"],
        capture_output=True,
        text=True,
        timeout=20,
        stdin=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        return []
    return _extract_model_tokens(proc.stdout)


# ---------------------------------------------------------------------------
# Named factories
# ---------------------------------------------------------------------------

def make_claude_code_backend(*, timeout: int = 300) -> AgentCLIBackend:
    """Return a backend that delegates to the Claude Code CLI (``claude``)."""
    binary = os.environ.get("ORCHESTRO_CLAUDE_BINARY", "claude")
    return AgentCLIBackend(
        name="claude-code",
        binary=binary,
        argv_builder=_claude_code_argv,
        task_strengths={"code", "analysis", "creative"},
        timeout=timeout,
    )


def make_codex_backend(*, timeout: int = 300) -> AgentCLIBackend:
    """Return a backend that delegates to the Codex CLI (``codex``)."""
    binary = os.environ.get("ORCHESTRO_CODEX_BINARY", "codex")
    return AgentCLIBackend(
        name="codex",
        binary=binary,
        argv_builder=_codex_argv,
        task_strengths={"code"},
        timeout=timeout,
    )


def make_kilocode_backend(*, timeout: int = 300) -> AgentCLIBackend:
    """Return a backend that delegates to the Kilocode CLI (``kilocode``)."""
    binary = os.environ.get("ORCHESTRO_KILOCODE_BINARY", "kilocode")
    return AgentCLIBackend(
        name="kilocode",
        binary=binary,
        argv_builder=_kilocode_argv,
        task_strengths={"code"},
        model_discovery=_discover_kilocode_models,
        timeout=timeout,
    )


def make_cursor_backend(*, timeout: int = 300) -> AgentCLIBackend:
    """Return a backend that delegates to Cursor Agent (``cursor-agent``)."""
    binary = os.environ.get("ORCHESTRO_CURSOR_BINARY", "cursor-agent")
    return AgentCLIBackend(
        name="cursor",
        binary=binary,
        argv_builder=_cursor_argv,
        task_strengths={"code", "analysis"},
        model_discovery=_discover_cursor_models,
        timeout=timeout,
    )
