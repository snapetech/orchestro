"""Tests for AgentCLIBackend and its named factory functions.

All tests mock shutil.which and subprocess.run — no real CLI tools required.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from orchestro.backends.agent_cli import (
    AgentCLIBackend,
    _claude_code_argv,
    _codex_argv,
    _cursor_argv,
    _kilocode_argv,
    make_claude_code_backend,
    make_codex_backend,
    make_cursor_backend,
    make_kilocode_backend,
)
from orchestro.models import RunRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _request(
    goal: str = "write a sort function",
    system_prompt: str | None = None,
    prompt_context: str | None = None,
    strategy_name: str = "direct",
    metadata: dict | None = None,
) -> RunRequest:
    return RunRequest(
        goal=goal,
        backend_name="agent-cli",
        system_prompt=system_prompt,
        prompt_context=prompt_context,
        strategy_name=strategy_name,
        metadata=metadata or {},
    )


def _completed(stdout: str = "great output", returncode: int = 0) -> MagicMock:
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = ""
    return result


def _make_backend(
    binary: str = "fakecli",
    argv_builder=None,
    task_strengths: set[str] | None = None,
) -> AgentCLIBackend:
    if argv_builder is None:
        argv_builder = lambda req: [req.goal]  # noqa: E731
    return AgentCLIBackend(
        name="fake",
        binary=binary,
        argv_builder=argv_builder,
        task_strengths=task_strengths,
    )


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------

class TestIsAvailable:
    def test_true_when_binary_on_path(self):
        backend = _make_backend(binary="myagent")
        with patch("orchestro.backends.agent_cli.shutil.which", return_value="/usr/bin/myagent"):
            assert backend.is_available() is True

    def test_false_when_binary_missing(self):
        backend = _make_backend(binary="notinstalled")
        with patch("orchestro.backends.agent_cli.shutil.which", return_value=None):
            assert backend.is_available() is False

    def test_resolved_binary_returns_full_path(self):
        backend = _make_backend(binary="myagent")
        with patch("orchestro.backends.agent_cli.shutil.which", return_value="/usr/local/bin/myagent"):
            assert backend.resolved_binary() == "/usr/local/bin/myagent"

    def test_resolved_binary_falls_back_to_name_when_missing(self):
        backend = _make_backend(binary="myagent")
        with patch("orchestro.backends.agent_cli.shutil.which", return_value=None):
            assert backend.resolved_binary() == "myagent"


# ---------------------------------------------------------------------------
# run() — success and error paths
# ---------------------------------------------------------------------------

class TestRun:
    def test_raises_when_binary_missing(self):
        backend = _make_backend(binary="notfound")
        with patch("orchestro.backends.agent_cli.shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="on PATH"):
                backend.run(_request())

    def test_output_text_from_stdout(self):
        backend = _make_backend(binary="myagent")
        with patch("orchestro.backends.agent_cli.shutil.which", return_value="/usr/bin/myagent"):
            with patch("orchestro.backends.agent_cli.subprocess.run", return_value=_completed("hello output")):
                resp = backend.run(_request())
        assert resp.output_text == "hello output"

    def test_stdout_stripped(self):
        backend = _make_backend(binary="myagent")
        with patch("orchestro.backends.agent_cli.shutil.which", return_value="/usr/bin/myagent"):
            with patch("orchestro.backends.agent_cli.subprocess.run", return_value=_completed("  output  \n")):
                resp = backend.run(_request())
        assert resp.output_text == "output"

    def test_nonzero_exit_raises(self):
        backend = _make_backend(binary="myagent")
        result = _completed(stdout="", returncode=1)
        result.stderr = "something went wrong"
        with patch("orchestro.backends.agent_cli.shutil.which", return_value="/usr/bin/myagent"):
            with patch("orchestro.backends.agent_cli.subprocess.run", return_value=result):
                with pytest.raises(RuntimeError, match="something went wrong"):
                    backend.run(_request())

    def test_nonzero_exit_no_stderr_uses_exit_code(self):
        backend = _make_backend(binary="myagent")
        result = _completed(stdout="", returncode=2)
        result.stderr = ""
        with patch("orchestro.backends.agent_cli.shutil.which", return_value="/usr/bin/myagent"):
            with patch("orchestro.backends.agent_cli.subprocess.run", return_value=result):
                with pytest.raises(RuntimeError, match="exit code 2"):
                    backend.run(_request())

    def test_timeout_raises_runtime(self):
        backend = _make_backend(binary="myagent")
        with patch("orchestro.backends.agent_cli.shutil.which", return_value="/usr/bin/myagent"):
            with patch(
                "orchestro.backends.agent_cli.subprocess.run",
                side_effect=subprocess.TimeoutExpired("myagent", 300),
            ):
                with pytest.raises(RuntimeError, match="timed out"):
                    backend.run(_request())

    def test_metadata_includes_backend_name(self):
        backend = AgentCLIBackend(
            name="my-agent",
            binary="myagent",
            argv_builder=lambda req: [req.goal],
        )
        with patch("orchestro.backends.agent_cli.shutil.which", return_value="/usr/bin/myagent"):
            with patch("orchestro.backends.agent_cli.subprocess.run", return_value=_completed("ok")):
                resp = backend.run(_request())
        assert resp.metadata["backend"] == "my-agent"
        assert resp.metadata["binary"] == "myagent"
        assert resp.metadata["exit_code"] == 0

    def test_argv_builder_called_with_request(self):
        calls: list[RunRequest] = []

        def builder(req: RunRequest) -> list[str]:
            calls.append(req)
            return ["--goal", req.goal]

        backend = AgentCLIBackend(name="x", binary="myagent", argv_builder=builder)
        req = _request(goal="my task")
        with patch("orchestro.backends.agent_cli.shutil.which", return_value="/usr/bin/myagent"):
            with patch("orchestro.backends.agent_cli.subprocess.run", return_value=_completed("done")) as mock_run:
                backend.run(req)
        called_argv = mock_run.call_args[0][0]
        assert called_argv == ["myagent", "--goal", "my task"]

    def test_env_includes_orchestro_goal(self):
        backend = _make_backend(binary="myagent")
        req = _request(goal="do a thing", system_prompt="Be helpful.")
        with patch("orchestro.backends.agent_cli.shutil.which", return_value="/usr/bin/myagent"):
            with patch("orchestro.backends.agent_cli.subprocess.run", return_value=_completed("ok")) as mock_run:
                backend.run(req)
        env = mock_run.call_args[1]["env"]
        assert env["ORCHESTRO_GOAL"] == "do a thing"
        assert env["ORCHESTRO_SYSTEM_PROMPT"] == "Be helpful."

    def test_stdin_is_devnull(self):
        backend = _make_backend(binary="myagent")
        with patch("orchestro.backends.agent_cli.shutil.which", return_value="/usr/bin/myagent"):
            with patch("orchestro.backends.agent_cli.subprocess.run", return_value=_completed("ok")) as mock_run:
                backend.run(_request())
        assert mock_run.call_args[1]["stdin"] == subprocess.DEVNULL


# ---------------------------------------------------------------------------
# capabilities()
# ---------------------------------------------------------------------------

class TestCapabilities:
    def test_available_reflected(self):
        backend = _make_backend(binary="myagent", task_strengths={"code"})
        with patch("orchestro.backends.agent_cli.shutil.which", return_value="/usr/bin/myagent"):
            caps = backend.capabilities()
        assert caps["available"] is True
        assert caps["tool_use"] is True
        assert caps["streaming"] is False
        assert "code" in caps["task_strengths"]

    def test_unavailable_reflected(self):
        backend = _make_backend(binary="notfound")
        with patch("orchestro.backends.agent_cli.shutil.which", return_value=None):
            caps = backend.capabilities()
        assert caps["available"] is False

    def test_task_strengths_sorted(self):
        backend = _make_backend(task_strengths={"creative", "code", "analysis"})
        with patch("orchestro.backends.agent_cli.shutil.which", return_value="/usr/bin/x"):
            caps = backend.capabilities()
        assert caps["task_strengths"] == sorted(["creative", "code", "analysis"])


# ---------------------------------------------------------------------------
# argv builders — _claude_code_argv
# ---------------------------------------------------------------------------

class TestClaudeCodeArgv:
    def test_print_flag_present(self):
        argv = _claude_code_argv(_request(goal="hello"))
        assert "--print" in argv

    def test_goal_in_argv(self):
        argv = _claude_code_argv(_request(goal="sort a list"))
        assert any("sort a list" in a for a in argv)

    def test_system_prompt_prepended(self):
        argv = _claude_code_argv(_request(goal="goal", system_prompt="Be terse."))
        goal_arg = argv[-1]
        assert "Be terse." in goal_arg
        assert "goal" in goal_arg
        assert goal_arg.index("Be terse.") < goal_arg.index("goal")

    def test_prompt_context_appended(self):
        argv = _claude_code_argv(_request(goal="goal", prompt_context="Context here."))
        goal_arg = argv[-1]
        assert "Context here." in goal_arg
        assert goal_arg.index("goal") < goal_arg.index("Context here.")

    def test_no_system_no_context(self):
        argv = _claude_code_argv(_request(goal="just goal"))
        goal_arg = argv[-1]
        assert goal_arg == "just goal"

    def test_custom_print_flag_via_env(self, monkeypatch):
        monkeypatch.setenv("ORCHESTRO_CLAUDE_PRINT_FLAG", "-p")
        argv = _claude_code_argv(_request(goal="hi"))
        assert "-p" in argv
        assert "--print" not in argv

    def test_output_format_added_when_set(self, monkeypatch):
        monkeypatch.setenv("ORCHESTRO_CLAUDE_OUTPUT_FORMAT", "json")
        argv = _claude_code_argv(_request(goal="hi"))
        assert "--output-format" in argv
        idx = argv.index("--output-format")
        assert argv[idx + 1] == "json"

    def test_no_output_format_flag_when_text(self, monkeypatch):
        monkeypatch.setenv("ORCHESTRO_CLAUDE_OUTPUT_FORMAT", "text")
        argv = _claude_code_argv(_request(goal="hi"))
        assert "--output-format" not in argv

    def test_backend_model_flag_added(self):
        argv = _claude_code_argv(_request(goal="hi", metadata={"backend_model": "sonnet-4"}))
        assert "--model" in argv
        assert "sonnet-4" in argv


# ---------------------------------------------------------------------------
# argv builders — _codex_argv
# ---------------------------------------------------------------------------

class TestCodexArgv:
    def test_exec_subcommand_present(self):
        argv = _codex_argv(_request(goal="hello"))
        assert argv[0] == "exec"
        assert "--full-auto" in argv

    def test_goal_in_argv(self):
        argv = _codex_argv(_request(goal="write tests"))
        assert any("write tests" in a for a in argv)

    def test_custom_sandbox_mode_via_env(self, monkeypatch):
        monkeypatch.setenv("ORCHESTRO_CODEX_APPROVAL_MODE", "workspace-write")
        argv = _codex_argv(_request(goal="hi"))
        idx = argv.index("--sandbox")
        assert argv[idx + 1] == "workspace-write"

    def test_system_prompt_merged(self):
        argv = _codex_argv(_request(goal="goal", system_prompt="Sys."))
        last = argv[-1]
        assert "Sys." in last and "goal" in last

    def test_backend_model_flag_added(self):
        argv = _codex_argv(_request(goal="hi", metadata={"backend_model": "gpt-5.4"}))
        assert "--model" in argv
        assert "gpt-5.4" in argv


# ---------------------------------------------------------------------------
# argv builders — _kilocode_argv
# ---------------------------------------------------------------------------

class TestKilocodeArgv:
    def test_run_subcommand_present(self):
        argv = _kilocode_argv(_request(goal="hi"))
        assert argv[0] == "run"
        assert "--auto" in argv

    def test_goal_in_argv(self):
        argv = _kilocode_argv(_request(goal="my task"))
        assert any("my task" in a for a in argv)

    def test_system_prompt_merged(self):
        argv = _kilocode_argv(_request(goal="goal", system_prompt="Sys."))
        last = argv[-1]
        assert "Sys." in last and "goal" in last

    def test_backend_model_flag_added(self):
        argv = _kilocode_argv(_request(goal="hi", metadata={"backend_model": "openai/gpt-5"}))
        assert "--model" in argv
        assert "openai/gpt-5" in argv


# ---------------------------------------------------------------------------
# argv builders — _cursor_argv
# ---------------------------------------------------------------------------

class TestCursorArgv:
    def test_print_mode_flags_present(self):
        argv = _cursor_argv(_request(goal="hi"))
        assert "--print" in argv
        assert "--mode" in argv
        idx = argv.index("--mode")
        assert argv[idx + 1] == "ask"

    def test_goal_in_argv(self):
        argv = _cursor_argv(_request(goal="fix bug"))
        assert any("fix bug" in a for a in argv)

    def test_extra_args_via_env(self, monkeypatch):
        monkeypatch.setenv("ORCHESTRO_CURSOR_EXTRA_ARGS", "--model gpt-4o")
        argv = _cursor_argv(_request(goal="hi"))
        assert "--model" in argv
        assert "gpt-4o" in argv

    def test_no_extra_args_by_default(self, monkeypatch):
        monkeypatch.delenv("ORCHESTRO_CURSOR_EXTRA_ARGS", raising=False)
        argv = _cursor_argv(_request(goal="hi"))
        assert "--print" in argv
        assert "--mode" in argv

    def test_backend_model_flag_added(self):
        argv = _cursor_argv(_request(goal="hi", metadata={"backend_model": "sonnet-4"}))
        assert "--model" in argv
        assert "sonnet-4" in argv


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------

class TestFactories:
    def test_make_claude_code_backend_name(self):
        b = make_claude_code_backend()
        assert b.name == "claude-code"
        assert b._binary == "claude"

    def test_make_claude_code_backend_custom_binary(self, monkeypatch):
        monkeypatch.setenv("ORCHESTRO_CLAUDE_BINARY", "/opt/claude/bin/claude")
        b = make_claude_code_backend()
        assert b._binary == "/opt/claude/bin/claude"

    def test_make_codex_backend_name(self):
        b = make_codex_backend()
        assert b.name == "codex"
        assert b._binary == "codex"

    def test_make_codex_backend_custom_binary(self, monkeypatch):
        monkeypatch.setenv("ORCHESTRO_CODEX_BINARY", "/usr/local/bin/codex")
        b = make_codex_backend()
        assert b._binary == "/usr/local/bin/codex"

    def test_make_kilocode_backend_name(self):
        b = make_kilocode_backend()
        assert b.name == "kilocode"
        assert b._binary == "kilocode"

    def test_make_kilocode_backend_custom_binary(self, monkeypatch):
        monkeypatch.setenv("ORCHESTRO_KILOCODE_BINARY", "kilo")
        b = make_kilocode_backend()
        assert b._binary == "kilo"

    def test_make_cursor_backend_name(self):
        b = make_cursor_backend()
        assert b.name == "cursor"
        assert b._binary == "cursor-agent"

    def test_make_cursor_backend_custom_binary(self, monkeypatch):
        monkeypatch.setenv("ORCHESTRO_CURSOR_BINARY", "/Applications/Cursor.app/cursor")
        b = make_cursor_backend()
        assert b._binary == "/Applications/Cursor.app/cursor"

    def test_all_factories_have_code_strength(self):
        for factory in [make_claude_code_backend, make_codex_backend, make_kilocode_backend, make_cursor_backend]:
            b = factory()
            assert "code" in b._task_strengths, f"{b.name} missing 'code' strength"

    def test_claude_code_has_analysis_and_creative_strength(self):
        b = make_claude_code_backend()
        assert "analysis" in b._task_strengths
        assert "creative" in b._task_strengths


# ---------------------------------------------------------------------------
# Routing and profile integration
# ---------------------------------------------------------------------------

class TestRoutingIntegration:
    def test_build_default_backends_includes_all_four(self):
        from orchestro.backend_profiles import build_default_backends
        backends = build_default_backends()
        assert "claude-code" in backends
        assert "codex" in backends
        assert "kilocode" in backends
        assert "cursor" in backends

    def test_all_four_are_agent_cli_backends(self):
        from orchestro.backend_profiles import build_default_backends
        backends = build_default_backends()
        for name in ["claude-code", "codex", "kilocode", "cursor"]:
            assert isinstance(backends[name], AgentCLIBackend)

    def test_reachable_when_binary_present(self):
        from urllib import error as urlerror
        from orchestro.backend_profiles import build_default_backends, reachable_backend_names
        backends = build_default_backends()
        with patch("orchestro.backends.agent_cli.shutil.which", return_value="/usr/bin/claude"):
            with patch("orchestro.backend_profiles.request.urlopen", side_effect=urlerror.URLError("refused")):
                reachable = reachable_backend_names(backends)
        assert "claude-code" in reachable

    def test_not_reachable_when_binary_absent(self):
        from urllib import error as urlerror
        from orchestro.backend_profiles import build_default_backends, reachable_backend_names
        backends = build_default_backends()
        with patch("orchestro.backends.agent_cli.shutil.which", return_value=None):
            with patch("orchestro.backend_profiles.request.urlopen", side_effect=urlerror.URLError("refused")):
                reachable = reachable_backend_names(backends)
        assert "claude-code" not in reachable
        assert "codex" not in reachable

    def test_decide_auto_backend_explicit_agent_hint(self):
        from orchestro.backend_profiles import decide_auto_backend
        decision = decide_auto_backend(
            "use claude-code to write this function",
            strategy_name="direct",
            domain=None,
            available={"claude-code", "mock"},
        )
        assert decision.selected_backend == "claude-code"

    def test_decide_auto_backend_agent_cli_preferred_for_coding(self):
        from orchestro.backend_profiles import decide_auto_backend
        decision = decide_auto_backend(
            "write a python function",
            strategy_name="direct",
            domain=None,
            available={"claude-code", "vllm-coding", "mock"},
        )
        assert decision.selected_backend == "claude-code"

    def test_decide_auto_backend_falls_back_to_vllm_when_no_agent_available(self):
        from orchestro.backend_profiles import decide_auto_backend
        decision = decide_auto_backend(
            "write a python function",
            strategy_name="direct",
            domain=None,
            available={"vllm-coding", "mock"},
        )
        assert decision.selected_backend == "vllm-coding"

    def test_aliases_resolve_to_agent_cli_backends(self):
        from orchestro.backend_profiles import build_default_backends, resolve_alias
        backends = build_default_backends()
        for alias, expected_backend in [
            ("claude", "claude-code"),
            ("claude-cli", "claude-code"),
            ("codex", "codex"),
            ("kilo", "kilocode"),
            ("kilocode", "kilocode"),
            ("cursor", "cursor"),
        ]:
            backend_name, _ = resolve_alias(alias, backends)
            assert backend_name == expected_backend, f"alias '{alias}' should resolve to '{expected_backend}'"

    def test_routing_task_hints_include_agent_clis(self):
        from orchestro.routing import _BACKEND_TASK_HINTS
        assert "code" in _BACKEND_TASK_HINTS["claude-code"]
        assert "code" in _BACKEND_TASK_HINTS["codex"]
        assert "code" in _BACKEND_TASK_HINTS["kilocode"]
        assert "code" in _BACKEND_TASK_HINTS["cursor"]
        assert "analysis" in _BACKEND_TASK_HINTS["claude-code"]
