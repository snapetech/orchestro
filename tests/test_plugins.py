from __future__ import annotations

from orchestro.plugins import CONTINUE, HookResult, HookRunner, PluginManager, HOOK_PRE_RUN


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
    runner.on(HOOK_PRE_RUN, lambda ctx: HookResult("continue"), plugin_name="after")
    result = runner.run(HOOK_PRE_RUN, {})
    assert result.action == "abort"
    assert result.reason == "blocked"


def test_plugin_manager_empty_dir_loads_nothing(tmp_path):
    pm = PluginManager(plugins_dir=tmp_path)
    pm.load_all()
    assert pm.loaded == []
