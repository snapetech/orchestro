from __future__ import annotations

from orchestro import cli
from orchestro import lsp_client
from orchestro import mcp_client
from orchestro.backends.mock import MockBackend
from orchestro.orchestrator import Orchestro
from orchestro.plugins import PluginMetadata


def _make_app(tmp_db):
    return Orchestro(db=tmp_db, backends={"mock": MockBackend()})


def test_backends_command_lists_mock_backend(tmp_db, monkeypatch, capsys):
    monkeypatch.setattr(cli, "create_app", lambda: _make_app(tmp_db))

    exit_code = cli.main(["backends"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "mock" in captured.out


def test_ask_command_runs_with_mock_backend(tmp_db, monkeypatch, capsys):
    monkeypatch.setattr(cli, "create_app", lambda: _make_app(tmp_db))

    exit_code = cli.main(["ask", "Say hello from CLI", "--backend", "mock"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Mock backend response" in captured.out
    assert "Say hello from CLI" in captured.out


def test_ask_command_unknown_backend_returns_error(tmp_db, monkeypatch, capsys):
    monkeypatch.setattr(cli, "create_app", lambda: _make_app(tmp_db))

    exit_code = cli.main(["ask", "fail", "--backend", "missing-backend"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "unknown backend" in captured.err


def test_ask_command_model_alias_persists_backend_model(tmp_db, monkeypatch, capsys):
    app = _make_app(tmp_db)
    monkeypatch.setattr(cli, "create_app", lambda: app)
    monkeypatch.setattr(cli, "resolve_alias", lambda alias, backends: ("mock", "special-model"))

    exit_code = cli.main(["ask", "Say hello from CLI", "--model", "smart"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Mock backend response" in captured.out
    run = app.db.list_runs(limit=1)[0]
    assert run.metadata["backend_model"] == "special-model"


def test_shell_command_uses_app_tool_registry_and_model_override(tmp_db, monkeypatch):
    app = _make_app(tmp_db)
    monkeypatch.setattr(cli, "create_app", lambda: app)

    captured: dict[str, object] = {}

    class FakeEmbeddingWorker:
        def __init__(self, db):
            assert db is app.db

        def start(self):
            return None

        def stop(self):
            return None

    class FakeShell:
        def __init__(self, app_arg, *, backend, strategy, domain, backend_model=None):
            captured["app"] = app_arg
            captured["backend"] = backend
            captured["backend_model"] = backend_model
            captured["strategy"] = strategy
            captured["domain"] = domain
            captured["tool_registry"] = app_arg.tools
            self.context_providers = []

        def cmdloop(self):
            return None

    monkeypatch.setattr(cli, "resolve_alias", lambda alias, backends: ("mock", "shell-model"))
    monkeypatch.setattr(cli, "OrchestroShell", FakeShell)
    monkeypatch.setattr("orchestro.scheduler.EmbeddingWorker", FakeEmbeddingWorker)

    exit_code = cli.main(["shell", "--model", "smart"])

    assert exit_code == 0
    assert captured["app"] is app
    assert captured["backend"] == "mock"
    assert captured["backend_model"] == "shell-model"
    assert captured["tool_registry"] is app.tools


def test_facts_command_lists_stored_fact(tmp_db, monkeypatch, capsys):
    tmp_db.add_fact(
        fact_id="fact-1",
        fact_key="capital",
        fact_value="Paris",
        source="cli-test",
        status="accepted",
    )
    monkeypatch.setattr(cli, "create_app", lambda: _make_app(tmp_db))

    exit_code = cli.main(["facts"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "capital" in captured.out
    assert "Paris" in captured.out


def test_plugins_command_shows_load_and_hook_errors(tmp_db, monkeypatch, capsys):
    app = _make_app(tmp_db)
    app.plugins.loaded.append(PluginMetadata(name="demo-plugin", version="1.2.3"))
    app.plugins.load_errors = [{"plugin": "broken", "error": "import boom"}]
    app.plugins.hooks.last_errors = [{"hook": "pre_run", "plugin": "demo-plugin", "error": "hook boom"}]
    monkeypatch.setattr(cli, "create_app", lambda: app)

    exit_code = cli.main(["plugins"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "demo-plugin" in captured.out
    assert "load errors:" in captured.out
    assert "import boom" in captured.out
    assert "hook errors:" in captured.out
    assert "hook boom" in captured.out


def test_mcp_status_command_shows_degraded_details(tmp_db, monkeypatch, capsys):
    monkeypatch.setattr(cli, "create_app", lambda: _make_app(tmp_db))

    class FakeManager:
        def __init__(self):
            self.connections = {}

        def load_config(self):
            return [object()]

        def start_all(self, configs):
            self.connections = {}

        def status(self):
            return {
                "connected": [],
                "degraded": ["bad-server"],
                "degraded_details": {"bad-server": "initialize request failed"},
                "tool_count": 0,
            }

        def stop_all(self):
            return None

    monkeypatch.setattr(mcp_client, "MCPClientManager", FakeManager)

    exit_code = cli.main(["mcp-status"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "degraded:  bad-server" in captured.out
    assert "initialize request failed" in captured.out


def test_lsp_status_command_shows_degraded_details(tmp_db, monkeypatch, capsys):
    monkeypatch.setattr(cli, "create_app", lambda: _make_app(tmp_db))

    class FakeLSPManager:
        def load_config(self):
            return [
                type(
                    "Cfg",
                    (),
                    {
                        "name": "pyright",
                        "command": "pyright-langserver",
                        "args": ["--stdio"],
                        "languages": ["python"],
                        "enabled": True,
                    },
                )()
            ]

        def status(self):
            return {
                "configured": ["pyright"],
                "active": {},
                "degraded": ["pyright"],
                "degraded_details": {"pyright": "initialize request failed"},
                "supported_languages": ["python"],
            }

        def supported_languages(self):
            return ["python"]

    monkeypatch.setattr(lsp_client, "LSPManager", FakeLSPManager)

    exit_code = cli.main(["lsp-status"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "degraded servers: pyright" in captured.out
    assert "initialize request failed" in captured.out
