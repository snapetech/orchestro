from __future__ import annotations

from pathlib import Path
from orchestro.git_changes import (
    MAX_STORED_PATCH_CHARS,
    _truncate_patch,
    collect_git_changes,
    git_capture,
    summarize_git_delta,
)


# ---------------------------------------------------------------------------
# _truncate_patch
# ---------------------------------------------------------------------------

class TestTruncatePatch:
    def test_empty_text(self):
        result = _truncate_patch("")
        assert result == {"text": "", "truncated": False, "original_length": 0}

    def test_short_text_not_truncated(self):
        result = _truncate_patch("small diff")
        assert result["truncated"] is False
        assert result["text"] == "small diff"
        assert result["original_length"] == len("small diff")

    def test_long_text_truncated(self):
        big = "x" * (MAX_STORED_PATCH_CHARS + 1000)
        result = _truncate_patch(big)
        assert result["truncated"] is True
        assert len(result["text"]) == MAX_STORED_PATCH_CHARS
        assert result["original_length"] == len(big)

    def test_exactly_at_limit_not_truncated(self):
        at_limit = "a" * MAX_STORED_PATCH_CHARS
        result = _truncate_patch(at_limit)
        assert result["truncated"] is False


# ---------------------------------------------------------------------------
# git_capture
# ---------------------------------------------------------------------------

class TestGitCapture:
    def test_returns_tuple_of_code_stdout_stderr(self, tmp_path: Path):
        code, out, err = git_capture(tmp_path, ["--version"])
        assert isinstance(code, int)
        assert isinstance(out, str)
        assert isinstance(err, str)

    def test_nonzero_code_on_bad_command(self, tmp_path: Path):
        code, out, err = git_capture(tmp_path, ["this-command-does-not-exist"])
        assert code != 0

    def test_stdout_rstripped(self, tmp_path: Path):
        code, out, _ = git_capture(tmp_path, ["--version"])
        assert not out.endswith("\n")


# ---------------------------------------------------------------------------
# collect_git_changes
# ---------------------------------------------------------------------------

class TestCollectGitChanges:
    def test_non_git_dir_returns_ok_false(self, tmp_path: Path):
        # tmp_path is not a git repo
        result = collect_git_changes(tmp_path)
        # May or may not be inside a git repo depending on host; just assert shape
        if not result["ok"]:
            assert "error" in result
            assert "cwd" in result

    def test_git_repo_returns_ok_true(self):
        # Use the actual repo root (we know it's a git repo)
        import subprocess
        repo = Path(
            subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
        )
        result = collect_git_changes(repo)
        assert result["ok"] is True
        assert "branch" in result
        assert "status_lines" in result
        assert "changed_files" in result
        assert "unstaged_files" in result
        assert "staged_files" in result
        assert "diff_stat" in result
        assert "diff_patch" in result

    def test_git_repo_branch_is_string_or_none(self):
        import subprocess
        repo = Path(
            subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
        )
        result = collect_git_changes(repo)
        if result["ok"]:
            assert result["branch"] is None or isinstance(result["branch"], str)

    def test_git_repo_diff_patch_has_shape(self):
        import subprocess
        repo = Path(
            subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
        )
        result = collect_git_changes(repo)
        if result["ok"]:
            patch = result["diff_patch"]
            assert isinstance(patch, dict)
            assert "text" in patch
            assert "truncated" in patch
            assert "original_length" in patch


# ---------------------------------------------------------------------------
# summarize_git_delta
# ---------------------------------------------------------------------------

class TestSummarizeGitDelta:
    def _state(self, changed: list[str], branch: str = "main") -> dict:
        return {
            "ok": True,
            "branch": branch,
            "changed_files": changed,
            "unstaged_files": changed,
            "staged_files": [],
            "diff_stat": "",
            "staged_diff_stat": "",
            "diff_patch": {"text": "", "truncated": False, "original_length": 0},
            "staged_diff_patch": {"text": "", "truncated": False, "original_length": 0},
            "repo_root": "/repo",
        }

    def test_returns_none_when_start_none(self):
        assert summarize_git_delta(None, self._state(["a.py"])) is None

    def test_returns_none_when_end_none(self):
        assert summarize_git_delta(self._state(["a.py"]), None) is None

    def test_returns_none_when_start_not_ok(self):
        bad = {"ok": False}
        assert summarize_git_delta(bad, self._state([])) is None

    def test_added_files_detected(self):
        start = self._state(["a.py"])
        end = self._state(["a.py", "b.py"])
        delta = summarize_git_delta(start, end)
        assert delta is not None
        assert "b.py" in delta["added_files"]

    def test_removed_files_detected(self):
        start = self._state(["a.py", "b.py"])
        end = self._state(["a.py"])
        delta = summarize_git_delta(start, end)
        assert delta is not None
        assert "b.py" in delta["removed_files"]

    def test_persistent_files(self):
        start = self._state(["a.py", "b.py"])
        end = self._state(["a.py", "c.py"])
        delta = summarize_git_delta(start, end)
        assert delta is not None
        assert "a.py" in delta["persistent_files"]

    def test_ok_flag_set(self):
        delta = summarize_git_delta(self._state([]), self._state([]))
        assert delta is not None
        assert delta["ok"] is True

    def test_branch_info_included(self):
        start = self._state([], branch="feature")
        end = self._state([], branch="main")
        delta = summarize_git_delta(start, end)
        assert delta is not None
        assert delta["branch_start"] == "feature"
        assert delta["branch_end"] == "main"

    def test_counts_match(self):
        start = self._state(["a.py", "b.py"])
        end = self._state(["a.py", "b.py", "c.py"])
        delta = summarize_git_delta(start, end)
        assert delta is not None
        assert delta["start_changed_count"] == 2
        assert delta["end_changed_count"] == 3
