from __future__ import annotations

import json
from pathlib import Path

from orchestro.lsp_client import (
    LSPConnection,
    LSPManager,
    LSPServerConfig,
    file_uri,
    language_for_file,
)


# ---------------------------------------------------------------------------
# file_uri
# ---------------------------------------------------------------------------

def test_file_uri_produces_correct_uri(tmp_path: Path):
    target = tmp_path / "src" / "main.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.touch()
    uri = file_uri(str(target))
    assert uri.startswith("file://")
    assert str(target.resolve()) in uri


def test_file_uri_absolute_path():
    uri = file_uri("/home/user/project/main.py")
    assert uri == "file:///home/user/project/main.py"


# ---------------------------------------------------------------------------
# language_for_file
# ---------------------------------------------------------------------------

def test_language_for_file_known_extensions():
    assert language_for_file("main.py") == "python"
    assert language_for_file("lib.rs") == "rust"
    assert language_for_file("index.ts") == "typescript"
    assert language_for_file("server.go") == "go"
    assert language_for_file("App.java") == "java"
    assert language_for_file("util.js") == "javascript"
    assert language_for_file("header.h") == "c"
    assert language_for_file("impl.cpp") == "cpp"
    assert language_for_file("impl.hpp") == "cpp"
    assert language_for_file("module.c") == "c"


def test_language_for_file_case_insensitive():
    assert language_for_file("MAIN.PY") == "python"
    assert language_for_file("Lib.RS") == "rust"


def test_language_for_file_unknown_extensions():
    assert language_for_file("notes.txt") is None
    assert language_for_file("data.csv") is None
    assert language_for_file("image.png") is None
    assert language_for_file("Makefile") is None
    assert language_for_file("config.yaml") is None


def test_language_for_file_no_extension():
    assert language_for_file("Dockerfile") is None


# ---------------------------------------------------------------------------
# LSPServerConfig
# ---------------------------------------------------------------------------

def test_lsp_server_config_defaults():
    cfg = LSPServerConfig(name="test-server", command="test-cmd")
    assert cfg.name == "test-server"
    assert cfg.command == "test-cmd"
    assert cfg.args == []
    assert cfg.languages == []
    assert cfg.root_uri == ""
    assert cfg.enabled is True


def test_lsp_server_config_with_all_fields():
    cfg = LSPServerConfig(
        name="pyright",
        command="pyright-langserver",
        args=["--stdio"],
        languages=["python"],
        root_uri="file:///project",
        enabled=False,
    )
    assert cfg.args == ["--stdio"]
    assert cfg.languages == ["python"]
    assert cfg.root_uri == "file:///project"
    assert cfg.enabled is False


# ---------------------------------------------------------------------------
# LSPConnection — no process
# ---------------------------------------------------------------------------

def test_lsp_connection_initial_state():
    cfg = LSPServerConfig(name="test", command="test-server")
    conn = LSPConnection(cfg)
    assert conn.process is None
    assert conn.capabilities == {}
    assert conn.last_error is None


def test_lsp_connection_start_returns_false_on_bad_command():
    cfg = LSPServerConfig(name="bad", command="nonexistent_lsp_server_xyz_12345")
    conn = LSPConnection(cfg)
    result = conn.start("/tmp")
    assert result is False
    assert conn.last_error


def test_lsp_connection_stop_when_no_process_is_safe():
    cfg = LSPServerConfig(name="test", command="test-server")
    conn = LSPConnection(cfg)
    conn.stop()  # should not raise


def test_lsp_connection_diagnostics_returns_empty_when_no_process():
    cfg = LSPServerConfig(name="test", command="test-server")
    conn = LSPConnection(cfg)
    result = conn.diagnostics("file:///foo.py")
    assert result == []


def test_lsp_connection_definition_returns_empty_when_no_process():
    cfg = LSPServerConfig(name="test", command="test-server")
    conn = LSPConnection(cfg)
    result = conn.definition("file:///foo.py", 0, 0)
    assert result == []


def test_lsp_connection_references_returns_empty_when_no_process():
    cfg = LSPServerConfig(name="test", command="test-server")
    conn = LSPConnection(cfg)
    result = conn.references("file:///foo.py", 0, 0)
    assert result == []


def test_lsp_connection_hover_returns_none_when_no_process():
    cfg = LSPServerConfig(name="test", command="test-server")
    conn = LSPConnection(cfg)
    result = conn.hover("file:///foo.py", 0, 0)
    assert result is None


def test_lsp_connection_document_symbols_returns_empty_when_no_process():
    cfg = LSPServerConfig(name="test", command="test-server")
    conn = LSPConnection(cfg)
    result = conn.document_symbols("file:///foo.py")
    assert result == []


def test_lsp_connection_workspace_symbols_returns_empty_when_no_process():
    cfg = LSPServerConfig(name="test", command="test-server")
    conn = LSPConnection(cfg)
    result = conn.workspace_symbols("MyClass")
    assert result == []


# ---------------------------------------------------------------------------
# LSPManager
# ---------------------------------------------------------------------------

def test_lsp_manager_load_config_nonexistent_path(tmp_path: Path):
    manager = LSPManager()
    configs = manager.load_config(tmp_path / "does_not_exist")
    assert configs == []


def test_lsp_manager_load_config_reads_servers(tmp_path: Path):
    config_data = {
        "servers": [
            {
                "name": "pyright",
                "command": "pyright-langserver",
                "args": ["--stdio"],
                "languages": ["python"],
                "enabled": True,
            }
        ]
    }
    (tmp_path / "lsp_servers.json").write_text(json.dumps(config_data))
    manager = LSPManager()
    configs = manager.load_config(tmp_path)
    assert len(configs) == 1
    assert configs[0].name == "pyright"
    assert configs[0].languages == ["python"]


def test_lsp_manager_load_config_disabled_not_in_language_map(tmp_path: Path):
    config_data = {
        "servers": [
            {
                "name": "disabled-server",
                "command": "some-server",
                "languages": ["python"],
                "enabled": False,
            }
        ]
    }
    (tmp_path / "lsp_servers.json").write_text(json.dumps(config_data))
    manager = LSPManager()
    manager.load_config(tmp_path)
    # Disabled server should not be in language map
    conn = manager.get_connection("python", "/tmp")
    assert conn is None


def test_lsp_manager_supported_languages_empty_initially():
    manager = LSPManager()
    assert manager.supported_languages() == []


def test_lsp_manager_supported_languages_from_config(tmp_path: Path):
    config_data = {
        "servers": [
            {"name": "s1", "command": "cmd1", "languages": ["python", "rust"], "enabled": True},
            {"name": "s2", "command": "cmd2", "languages": ["typescript"], "enabled": True},
        ]
    }
    (tmp_path / "lsp_servers.json").write_text(json.dumps(config_data))
    manager = LSPManager()
    manager.load_config(tmp_path)
    langs = manager.supported_languages()
    assert "python" in langs
    assert "rust" in langs
    assert "typescript" in langs


def test_lsp_manager_supported_languages_excludes_disabled(tmp_path: Path):
    config_data = {
        "servers": [
            {"name": "active", "command": "c1", "languages": ["go"], "enabled": True},
            {"name": "disabled", "command": "c2", "languages": ["java"], "enabled": False},
        ]
    }
    (tmp_path / "lsp_servers.json").write_text(json.dumps(config_data))
    manager = LSPManager()
    manager.load_config(tmp_path)
    langs = manager.supported_languages()
    assert "go" in langs
    assert "java" not in langs


def test_lsp_manager_status_initially_empty():
    manager = LSPManager()
    status = manager.status()
    assert status["configured"] == []
    assert status["active"] == {}
    assert status["degraded"] == []
    assert status["degraded_details"] == {}
    assert status["supported_languages"] == []


def test_lsp_manager_status_after_config(tmp_path: Path):
    config_data = {
        "servers": [{"name": "pyright", "command": "pyright-langserver", "languages": ["python"], "enabled": True}]
    }
    (tmp_path / "lsp_servers.json").write_text(json.dumps(config_data))
    manager = LSPManager()
    manager.load_config(tmp_path)
    status = manager.status()
    assert "pyright" in status["configured"]


def test_lsp_manager_get_connection_unknown_language_returns_none():
    manager = LSPManager()
    conn = manager.get_connection("unknown_language_xyz", "/tmp")
    assert conn is None


def test_lsp_manager_stop_all_empty_is_safe():
    manager = LSPManager()
    manager.stop_all()  # should not raise
    assert manager.connections == {}


def test_lsp_manager_failed_start_goes_to_degraded(tmp_path: Path):
    config_data = {
        "servers": [
            {
                "name": "bad-server",
                "command": "nonexistent_lsp_xyz",
                "languages": ["python"],
                "enabled": True,
            }
        ]
    }
    (tmp_path / "lsp_servers.json").write_text(json.dumps(config_data))
    manager = LSPManager()
    manager.load_config(tmp_path)
    conn = manager.get_connection("python", str(tmp_path))
    assert conn is None
    assert "bad-server" in manager.degraded
    assert "bad-server" in manager.degraded_details
