from __future__ import annotations

from pathlib import Path

import pytest

from orchestro.db import OrchestroDB
from orchestro.tools import ToolRegistry


@pytest.fixture()
def registry() -> ToolRegistry:
    return ToolRegistry()


@pytest.fixture()
def registry_with_db(tmp_db: OrchestroDB) -> ToolRegistry:
    return ToolRegistry(db=tmp_db)


def test_git_status_tool_exists_auto_approval(registry: ToolRegistry):
    tool = registry.get_tool("git_status")
    assert tool is not None
    assert tool.approval == "auto"


def test_git_diff_tool_exists_auto_approval(registry: ToolRegistry):
    tool = registry.get_tool("git_diff")
    assert tool is not None
    assert tool.approval == "auto"


def test_git_commit_tool_exists_confirm_approval(registry: ToolRegistry):
    tool = registry.get_tool("git_commit")
    assert tool is not None
    assert tool.approval == "confirm"


def test_run_tests_tool_exists_confirm_approval(registry: ToolRegistry):
    tool = registry.get_tool("run_tests")
    assert tool is not None
    assert tool.approval == "confirm"


def test_spawn_subagent_tool_exists_confirm_approval(registry: ToolRegistry):
    tool = registry.get_tool("spawn_subagent")
    assert tool is not None
    assert tool.approval == "confirm"


def test_search_memory_no_db_returns_memory_not_available(tmp_path: Path):
    reg = ToolRegistry(db=None)
    result = reg.run("search_memory", "some query", tmp_path)
    assert result.ok is False
    assert "memory not available" in result.output


def test_propose_fact_no_db_returns_memory_not_available(tmp_path: Path):
    reg = ToolRegistry(db=None)
    result = reg.run("propose_fact", "key value", tmp_path, approved=True)
    assert result.ok is False
    assert "memory not available" in result.output
