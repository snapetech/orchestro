from __future__ import annotations

from pathlib import Path

import pytest

from orchestro.tools import ToolRegistry


@pytest.fixture()
def registry() -> ToolRegistry:
    return ToolRegistry()


EXPECTED_TOOLS = {"pwd", "ls", "read_file", "rg", "bash", "think", "edit_file"}


def test_all_expected_tools_registered(registry: ToolRegistry):
    names = {t["name"] for t in registry.list_tools()}
    assert EXPECTED_TOOLS.issubset(names)


def test_think_returns_ok(registry: ToolRegistry, tmp_path: Path):
    result = registry.run("think", "planning next step", tmp_path)
    assert result.ok is True
    assert "planning next step" in result.output


def test_edit_file_successful(registry: ToolRegistry, tmp_path: Path):
    target = tmp_path / "hello.txt"
    target.write_text("Hello World\n", encoding="utf-8")
    argument = "hello.txt\n<<<SEARCH\nHello World\n===\nHello Universe\n>>>SEARCH"
    result = registry.run("edit_file", argument, tmp_path, approved=True)
    assert result.ok is True
    assert target.read_text(encoding="utf-8") == "Hello Universe\n"


def test_edit_file_missing_file(registry: ToolRegistry, tmp_path: Path):
    argument = "nonexistent.txt\n<<<SEARCH\nfoo\n===\nbar\n>>>SEARCH"
    result = registry.run("edit_file", argument, tmp_path, approved=True)
    assert result.ok is False
    assert "not found" in result.output


def test_edit_file_search_text_not_found(registry: ToolRegistry, tmp_path: Path):
    target = tmp_path / "data.txt"
    target.write_text("apples and oranges\n", encoding="utf-8")
    argument = "data.txt\n<<<SEARCH\nbananas\n===\ngrapes\n>>>SEARCH"
    result = registry.run("edit_file", argument, tmp_path, approved=True)
    assert result.ok is False
    assert "not found" in result.output


def test_pwd_returns_cwd(registry: ToolRegistry, tmp_path: Path):
    result = registry.run("pwd", "", tmp_path)
    assert result.ok is True
    assert result.output == str(tmp_path.resolve())


def test_ls_lists_files(registry: ToolRegistry, tmp_path: Path):
    (tmp_path / "alpha.txt").touch()
    (tmp_path / "beta.txt").touch()
    (tmp_path / "gamma").mkdir()
    result = registry.run("ls", "", tmp_path)
    assert result.ok is True
    assert "alpha.txt" in result.output
    assert "beta.txt" in result.output
    assert "gamma" in result.output
