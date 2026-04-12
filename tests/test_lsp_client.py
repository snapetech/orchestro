from __future__ import annotations

from pathlib import Path

from orchestro.lsp_client import (
    LSPManager,
    LSPServerConfig,
    file_uri,
    language_for_file,
)


def test_file_uri_produces_correct_uri(tmp_path: Path):
    target = tmp_path / "src" / "main.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.touch()
    uri = file_uri(str(target))
    assert uri.startswith("file://")
    assert str(target.resolve()) in uri


def test_language_for_file_known_extensions():
    assert language_for_file("main.py") == "python"
    assert language_for_file("lib.rs") == "rust"
    assert language_for_file("index.ts") == "typescript"
    assert language_for_file("server.go") == "go"
    assert language_for_file("App.java") == "java"
    assert language_for_file("util.js") == "javascript"
    assert language_for_file("header.h") == "c"
    assert language_for_file("impl.cpp") == "cpp"


def test_language_for_file_unknown_extensions():
    assert language_for_file("notes.txt") is None
    assert language_for_file("data.csv") is None
    assert language_for_file("image.png") is None
    assert language_for_file("Makefile") is None


def test_lsp_server_config_defaults():
    cfg = LSPServerConfig(name="test-server", command="test-cmd")
    assert cfg.name == "test-server"
    assert cfg.command == "test-cmd"
    assert cfg.args == []
    assert cfg.languages == []
    assert cfg.root_uri == ""
    assert cfg.enabled is True


def test_lsp_manager_load_config_nonexistent_path(tmp_path: Path):
    manager = LSPManager()
    configs = manager.load_config(tmp_path / "does_not_exist")
    assert configs == []
