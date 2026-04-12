from orchestro.commands import CommandMeta, CommandRegistry, build_default_registry


def test_register_and_resolve():
    reg = CommandRegistry()
    meta = CommandMeta(name="runs", category="runs", help="List runs")
    reg.register(meta)
    assert reg.resolve("runs") is meta


def test_alias_resolution():
    reg = CommandRegistry()
    meta = CommandMeta(name="runs", aliases=("history",), category="runs", help="List runs")
    reg.register(meta)
    assert reg.resolve("history") is meta


def test_list_commands_by_category():
    reg = CommandRegistry()
    reg.register(CommandMeta(name="runs", category="runs", help="List runs"))
    reg.register(CommandMeta(name="show", category="runs", help="Show run"))
    reg.register(CommandMeta(name="bench", category="benchmarks", help="Run benchmarks"))
    runs_cmds = reg.list_commands(category="runs")
    assert len(runs_cmds) == 2
    assert all(c.category == "runs" for c in runs_cmds)


def test_build_default_registry_returns_non_empty():
    reg = build_default_registry()
    commands = reg.list_commands()
    assert len(commands) > 30
    assert len(reg.categories()) > 5
