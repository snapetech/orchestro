from __future__ import annotations

from pathlib import Path

import pytest

from orchestro.plugins import (
    ALL_HOOKS,
    CONTINUE,
    HOOK_ON_FAILURE,
    HOOK_POST_RUN,
    HOOK_POST_TOOL,
    HOOK_PRE_RUN,
    HOOK_PRE_TOOL,
    HookResult,
    HookRunner,
    PluginManager,
)


# ---------------------------------------------------------------------------
# HookResult
# ---------------------------------------------------------------------------

def test_hook_result_defaults():
    r = HookResult("continue")
    assert r.action == "continue"
    assert r.reason == ""
    assert r.data is None


def test_continue_sentinel_is_continue():
    assert CONTINUE.action == "continue"


# ---------------------------------------------------------------------------
# HookRunner
# ---------------------------------------------------------------------------

def test_hook_runner_no_handlers_returns_continue():
    runner = HookRunner()
    result = runner.run(HOOK_PRE_RUN, {})
    assert result == CONTINUE


def test_hook_runner_runs_handlers_in_order():
    runner = HookRunner()
    call_order: list[int] = []
    runner.on(HOOK_PRE_RUN, lambda ctx: call_order.append(1), plugin_name="p1")
    runner.on(HOOK_PRE_RUN, lambda ctx: call_order.append(2), plugin_name="p2")
    runner.run(HOOK_PRE_RUN, {})
    assert call_order == [1, 2]


def test_hook_runner_abort_stops_execution():
    runner = HookRunner()
    runner.on(HOOK_PRE_RUN, lambda ctx: HookResult("abort", reason="blocked"), plugin_name="blocker")
    after_called = []
    runner.on(HOOK_PRE_RUN, lambda ctx: after_called.append(1), plugin_name="after")
    result = runner.run(HOOK_PRE_RUN, {})
    assert result.action == "abort"
    assert result.reason == "blocked"
    assert after_called == []  # handler after abort should not run


def test_hook_runner_modify_updates_context():
    runner = HookRunner()
    runner.on(
        HOOK_PRE_RUN,
        lambda ctx: HookResult("modify", data={"injected": True}),
        plugin_name="injector",
    )
    ctx: dict = {}
    runner.run(HOOK_PRE_RUN, ctx)
    assert ctx.get("injected") is True


def test_hook_runner_unknown_hook_raises():
    runner = HookRunner()
    with pytest.raises(ValueError, match="Unknown hook"):
        runner.on("nonexistent_hook", lambda ctx: None, plugin_name="x")


def test_hook_runner_handler_exception_does_not_propagate():
    runner = HookRunner()
    def bad_handler(ctx):
        raise RuntimeError("oops")
    runner.on(HOOK_PRE_RUN, bad_handler, plugin_name="bad")
    result = runner.run(HOOK_PRE_RUN, {})
    assert result == CONTINUE  # exception swallowed; continues
    assert runner.last_errors == [{"hook": HOOK_PRE_RUN, "plugin": "bad", "error": "oops"}]


def test_hook_runner_list_handlers_empty():
    runner = HookRunner()
    assert runner.list_handlers() == {}


def test_hook_runner_list_handlers_shows_registered():
    runner = HookRunner()
    runner.on(HOOK_PRE_RUN, lambda ctx: None, plugin_name="p1")
    runner.on(HOOK_POST_RUN, lambda ctx: None, plugin_name="p2")
    listing = runner.list_handlers()
    assert HOOK_PRE_RUN in listing
    assert "p1" in listing[HOOK_PRE_RUN]
    assert HOOK_POST_RUN in listing
    assert "p2" in listing[HOOK_POST_RUN]


def test_all_hook_names_are_defined():
    expected = {HOOK_PRE_RUN, HOOK_POST_RUN, HOOK_PRE_TOOL, HOOK_POST_TOOL, HOOK_ON_FAILURE}
    assert expected.issubset(ALL_HOOKS)


# ---------------------------------------------------------------------------
# PluginManager — empty / no dir
# ---------------------------------------------------------------------------

def test_plugin_manager_empty_dir_loads_nothing(tmp_path: Path):
    pm = PluginManager(plugins_dir=tmp_path)
    pm.load_all()
    assert pm.loaded == []


def test_plugin_manager_none_dir_loads_nothing():
    pm = PluginManager(plugins_dir=None)
    pm.load_all()
    assert pm.loaded == []


# ---------------------------------------------------------------------------
# PluginManager — loading real plugins from files
# ---------------------------------------------------------------------------

def test_plugin_manager_loads_plugin_with_register(tmp_path: Path):
    plugin_src = """\
from orchestro.plugins import HOOK_PRE_RUN, HookResult, PluginMetadata

METADATA = PluginMetadata(name="test-plugin", version="1.0.0")

def register(hooks):
    hooks.on(HOOK_PRE_RUN, lambda ctx: None, plugin_name="test-plugin")
"""
    (tmp_path / "my_plugin.py").write_text(plugin_src)
    pm = PluginManager(plugins_dir=tmp_path)
    pm.load_all()
    assert len(pm.loaded) == 1
    assert pm.loaded[0].name == "test-plugin"
    assert pm.loaded[0].version == "1.0.0"


def test_plugin_manager_skips_underscore_files(tmp_path: Path):
    (tmp_path / "_internal.py").write_text("# internal")
    pm = PluginManager(plugins_dir=tmp_path)
    pm.load_all()
    assert pm.loaded == []


def test_plugin_manager_skips_non_py_files(tmp_path: Path):
    (tmp_path / "README.md").write_text("docs")
    pm = PluginManager(plugins_dir=tmp_path)
    pm.load_all()
    assert pm.loaded == []


def test_plugin_manager_plugin_without_metadata_gets_stem_name(tmp_path: Path):
    plugin_src = "def register(hooks):\n    pass\n"
    (tmp_path / "minimal_plugin.py").write_text(plugin_src)
    pm = PluginManager(plugins_dir=tmp_path)
    pm.load_all()
    assert len(pm.loaded) == 1
    assert pm.loaded[0].name == "minimal_plugin"


def test_plugin_manager_plugin_without_register_still_loads(tmp_path: Path):
    (tmp_path / "no_register.py").write_text("x = 42\n")
    pm = PluginManager(plugins_dir=tmp_path)
    pm.load_all()
    # Loaded with stem as name; no crash
    assert len(pm.loaded) == 1


def test_plugin_manager_broken_plugin_is_skipped(tmp_path: Path):
    (tmp_path / "broken.py").write_text("raise RuntimeError('import error')\n")
    pm = PluginManager(plugins_dir=tmp_path)
    pm.load_all()
    assert pm.loaded == []
    assert pm.load_errors == [{"plugin": "broken", "error": "import error"}]


def test_plugin_manager_hooks_registered_by_plugin_are_runnable(tmp_path: Path):
    plugin_src = """\
from orchestro.plugins import HOOK_PRE_RUN, HookResult

def register(hooks):
    hooks.on(HOOK_PRE_RUN, lambda ctx: HookResult("abort", reason="denied"), plugin_name="gatekeeper")
"""
    (tmp_path / "gatekeeper.py").write_text(plugin_src)
    pm = PluginManager(plugins_dir=tmp_path)
    pm.load_all()
    result = pm.hooks.run(HOOK_PRE_RUN, {})
    assert result.action == "abort"
    assert result.reason == "denied"
