from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from orchestro.backends.base import BackendProcessResult
from orchestro.backends.subprocess_command import SubprocessCommandBackend, SubprocessHandle
from orchestro.models import RunRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _request(
    goal: str = "test goal",
    strategy_name: str = "direct",
    system_prompt: str | None = None,
    prompt_context: str | None = None,
    metadata: dict | None = None,
    parent_run_id: str | None = None,
    working_directory: str | Path | None = None,
) -> RunRequest:
    req = RunRequest(
        goal=goal,
        backend_name="subprocess-command",
        strategy_name=strategy_name,
        system_prompt=system_prompt,
        prompt_context=prompt_context,
        metadata=metadata or {},
        parent_run_id=parent_run_id,
    )
    if working_directory is not None:
        req = RunRequest(
            goal=goal,
            backend_name="subprocess-command",
            strategy_name=strategy_name,
            system_prompt=system_prompt,
            prompt_context=prompt_context,
            metadata=metadata or {},
            parent_run_id=parent_run_id,
            working_directory=Path(working_directory),
        )
    return req


# ---------------------------------------------------------------------------
# _resolved_command / _resolved_shell
# ---------------------------------------------------------------------------

class TestResolvedCommand:
    def test_constructor_takes_priority(self, monkeypatch):
        monkeypatch.setenv("ORCHESTRO_SUBPROCESS_COMMAND", "env-cmd")
        backend = SubprocessCommandBackend(command="ctor-cmd")
        assert backend._resolved_command() == "ctor-cmd"

    def test_env_var_fallback(self, monkeypatch):
        monkeypatch.setenv("ORCHESTRO_SUBPROCESS_COMMAND", "env-cmd")
        backend = SubprocessCommandBackend()
        assert backend._resolved_command() == "env-cmd"

    def test_empty_when_neither_set(self, monkeypatch):
        monkeypatch.delenv("ORCHESTRO_SUBPROCESS_COMMAND", raising=False)
        backend = SubprocessCommandBackend()
        assert backend._resolved_command() == ""

    def test_shell_constructor_flag(self):
        backend = SubprocessCommandBackend(shell=True)
        assert backend._resolved_shell() is True

    def test_shell_env_flag_true(self, monkeypatch):
        monkeypatch.setenv("ORCHESTRO_SUBPROCESS_SHELL", "true")
        backend = SubprocessCommandBackend()
        assert backend._resolved_shell() is True

    def test_shell_env_flag_1(self, monkeypatch):
        monkeypatch.setenv("ORCHESTRO_SUBPROCESS_SHELL", "1")
        backend = SubprocessCommandBackend()
        assert backend._resolved_shell() is True

    def test_shell_env_flag_false_by_default(self, monkeypatch):
        monkeypatch.delenv("ORCHESTRO_SUBPROCESS_SHELL", raising=False)
        backend = SubprocessCommandBackend()
        assert backend._resolved_shell() is False


# ---------------------------------------------------------------------------
# start() — returns None when no command configured
# ---------------------------------------------------------------------------

class TestStart:
    def test_returns_none_when_no_command(self, monkeypatch, tmp_path):
        monkeypatch.delenv("ORCHESTRO_SUBPROCESS_COMMAND", raising=False)
        backend = SubprocessCommandBackend()
        result = backend.start(_request(working_directory=tmp_path))
        assert result is None

    def test_returns_handle_when_command_set(self, tmp_path):
        backend = SubprocessCommandBackend(command="echo hello")
        handle = backend.start(_request(working_directory=tmp_path))
        assert handle is not None
        handle.wait()  # clean up

    def test_handle_is_subprocess_handle(self, tmp_path):
        backend = SubprocessCommandBackend(command="echo hi")
        handle = backend.start(_request(working_directory=tmp_path))
        assert isinstance(handle, SubprocessHandle)
        handle.wait()


# ---------------------------------------------------------------------------
# run() — success and failure paths
# ---------------------------------------------------------------------------

class TestRun:
    def test_run_missing_command_raises(self, monkeypatch, tmp_path):
        monkeypatch.delenv("ORCHESTRO_SUBPROCESS_COMMAND", raising=False)
        backend = SubprocessCommandBackend()
        with pytest.raises(RuntimeError, match="ORCHESTRO_SUBPROCESS_COMMAND is not set"):
            backend.run(_request(working_directory=tmp_path))

    def test_run_success_captures_stdout(self, tmp_path):
        backend = SubprocessCommandBackend(command="echo subprocess_output")
        resp = backend.run(_request(working_directory=tmp_path))
        assert resp.output_text == "subprocess_output"

    def test_run_nonzero_exit_raises(self, tmp_path):
        backend = SubprocessCommandBackend(command="bash -c 'exit 1'")
        with pytest.raises(RuntimeError, match="subprocess backend failed"):
            backend.run(_request(working_directory=tmp_path))

    def test_run_stderr_included_in_error(self, tmp_path):
        backend = SubprocessCommandBackend(command="bash -c 'echo err >&2; exit 1'")
        with pytest.raises(RuntimeError, match="err"):
            backend.run(_request(working_directory=tmp_path))

    def test_run_metadata_includes_backend_name(self, tmp_path):
        backend = SubprocessCommandBackend(command="echo ok")
        resp = backend.run(_request(working_directory=tmp_path))
        assert resp.metadata["backend"] == "subprocess-command"
        assert resp.metadata["exit_code"] == 0


# ---------------------------------------------------------------------------
# Environment variable injection
# ---------------------------------------------------------------------------

class TestRequestEnv:
    def test_goal_injected(self, tmp_path):
        backend = SubprocessCommandBackend(
            command="bash -c 'printf \"%s\" \"$ORCHESTRO_GOAL\"'"
        )
        resp = backend.run(_request(goal="my task", working_directory=tmp_path))
        assert resp.output_text == "my task"

    def test_strategy_injected(self, tmp_path):
        backend = SubprocessCommandBackend(
            command="bash -c 'printf \"%s\" \"$ORCHESTRO_STRATEGY\"'"
        )
        resp = backend.run(_request(strategy_name="tool-loop", working_directory=tmp_path))
        assert resp.output_text == "tool-loop"

    def test_system_prompt_injected(self, tmp_path):
        backend = SubprocessCommandBackend(
            command="bash -c 'printf \"%s\" \"$ORCHESTRO_SYSTEM_PROMPT\"'"
        )
        resp = backend.run(_request(system_prompt="Be brief.", working_directory=tmp_path))
        assert resp.output_text == "Be brief."

    def test_prompt_context_injected(self, tmp_path):
        backend = SubprocessCommandBackend(
            command="bash -c 'printf \"%s\" \"$ORCHESTRO_PROMPT_CONTEXT\"'"
        )
        resp = backend.run(_request(prompt_context="Here is context.", working_directory=tmp_path))
        assert resp.output_text == "Here is context."

    def test_domain_injected_from_metadata(self, tmp_path):
        backend = SubprocessCommandBackend(
            command="bash -c 'printf \"%s\" \"$ORCHESTRO_DOMAIN\"'"
        )
        resp = backend.run(_request(metadata={"domain": "coding"}, working_directory=tmp_path))
        assert resp.output_text == "coding"

    def test_domain_empty_string_when_absent(self, tmp_path):
        backend = SubprocessCommandBackend(
            command="bash -c 'printf \"%s\" \"$ORCHESTRO_DOMAIN\"'"
        )
        resp = backend.run(_request(metadata={}, working_directory=tmp_path))
        assert resp.output_text == ""

    def test_parent_run_id_injected(self, tmp_path):
        backend = SubprocessCommandBackend(
            command="bash -c 'printf \"%s\" \"$ORCHESTRO_PARENT_RUN_ID\"'"
        )
        resp = backend.run(_request(parent_run_id="abc-123", working_directory=tmp_path))
        assert resp.output_text == "abc-123"

    def test_parent_run_id_empty_when_none(self, tmp_path):
        backend = SubprocessCommandBackend(
            command="bash -c 'printf \"%s\" \"$ORCHESTRO_PARENT_RUN_ID\"'"
        )
        resp = backend.run(_request(parent_run_id=None, working_directory=tmp_path))
        assert resp.output_text == ""

    def test_workdir_injected(self, tmp_path):
        backend = SubprocessCommandBackend(
            command="bash -c 'printf \"%s\" \"$ORCHESTRO_WORKDIR\"'"
        )
        resp = backend.run(_request(working_directory=tmp_path))
        assert resp.output_text == str(tmp_path)


# ---------------------------------------------------------------------------
# response_from_process()
# ---------------------------------------------------------------------------

class TestResponseFromProcess:
    def test_success_result(self):
        backend = SubprocessCommandBackend(command="echo ok")
        result = BackendProcessResult(exit_code=0, stdout_text="good output\n", stderr_text="")
        resp = backend.response_from_process(_request(), result)
        assert resp.output_text == "good output"

    def test_failure_result_raises(self):
        backend = SubprocessCommandBackend(command="bad-cmd")
        result = BackendProcessResult(exit_code=2, stdout_text="", stderr_text="something failed")
        with pytest.raises(RuntimeError, match="something failed"):
            backend.response_from_process(_request(), result)

    def test_failure_with_no_stderr_uses_exit_code_message(self):
        backend = SubprocessCommandBackend(command="bad-cmd")
        result = BackendProcessResult(exit_code=127, stdout_text="", stderr_text="")
        with pytest.raises(RuntimeError, match="exit code 127"):
            backend.response_from_process(_request(), result)

    def test_metadata_has_prompt_context_flag(self):
        backend = SubprocessCommandBackend(command="echo ok")
        result = BackendProcessResult(exit_code=0, stdout_text="out", stderr_text="")
        resp = backend.response_from_process(_request(prompt_context="ctx"), result)
        assert resp.metadata["has_prompt_context"] is True

    def test_metadata_no_prompt_context(self):
        backend = SubprocessCommandBackend(command="echo ok")
        result = BackendProcessResult(exit_code=0, stdout_text="out", stderr_text="")
        resp = backend.response_from_process(_request(), result)
        assert resp.metadata["has_prompt_context"] is False


# ---------------------------------------------------------------------------
# SubprocessHandle lifecycle
# ---------------------------------------------------------------------------

class TestSubprocessHandle:
    def _start_echo(self, msg: str = "hi") -> SubprocessHandle:
        process = subprocess.Popen(
            ["echo", msg],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
        )
        return SubprocessHandle(process=process)

    def test_wait_returns_result(self):
        handle = self._start_echo("hello")
        result = handle.wait()
        assert result.exit_code == 0
        assert "hello" in result.stdout_text

    def test_poll_returns_none_while_running(self):
        # Sleep briefly so we can catch it mid-run
        process = subprocess.Popen(
            ["sleep", "10"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
        handle = SubprocessHandle(process=process)
        assert handle.poll() is None
        handle.terminate()

    def test_poll_returns_exit_code_after_done(self):
        handle = self._start_echo("done")
        handle.wait()
        assert handle.poll() == 0

    def test_terminate_kills_process(self):
        process = subprocess.Popen(
            ["sleep", "60"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
        handle = SubprocessHandle(process=process)
        handle.terminate()
        assert process.poll() is not None

    def test_terminate_is_safe_when_already_done(self):
        handle = self._start_echo("done")
        handle.wait()
        # Should not raise
        handle.terminate()

    def test_pause_and_resume(self):
        process = subprocess.Popen(
            ["sleep", "60"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
        handle = SubprocessHandle(process=process)
        handle.pause()
        # After SIGSTOP, verify process is stopped or still running (OS-dependent).
        os.waitpid(process.pid, os.WNOHANG | os.WUNTRACED)
        handle.resume()
        handle.terminate()


# ---------------------------------------------------------------------------
# capabilities()
# ---------------------------------------------------------------------------

class TestCapabilities:
    def test_subprocess_control_true(self):
        backend = SubprocessCommandBackend()
        caps = backend.capabilities()
        assert caps["subprocess_control"] is True
        assert caps["pause_resume"] is True

    def test_command_configured_false_when_none(self, monkeypatch):
        monkeypatch.delenv("ORCHESTRO_SUBPROCESS_COMMAND", raising=False)
        backend = SubprocessCommandBackend()
        caps = backend.capabilities()
        assert caps["command_configured"] is False

    def test_command_configured_true_when_set(self):
        backend = SubprocessCommandBackend(command="echo hi")
        caps = backend.capabilities()
        assert caps["command_configured"] is True
