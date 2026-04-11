from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

MAX_STORED_PATCH_CHARS = 12000


def git_capture(cwd: Path, args: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.returncode, completed.stdout.rstrip(), completed.stderr.strip()


def collect_git_changes(cwd: Path) -> dict[str, object]:
    code, root_out, root_err = git_capture(cwd, ["rev-parse", "--show-toplevel"])
    if code != 0:
        return {"ok": False, "error": root_err or "not a git repository", "cwd": str(cwd)}
    repo_root = root_out.splitlines()[0].strip() if root_out else str(cwd)
    _, branch_out, _ = git_capture(cwd, ["branch", "--show-current"])
    _, status_out, _ = git_capture(cwd, ["status", "--short"])
    _, stat_out, _ = git_capture(cwd, ["diff", "--stat"])
    _, staged_stat_out, _ = git_capture(cwd, ["diff", "--cached", "--stat"])
    _, patch_out, _ = git_capture(cwd, ["diff", "--no-ext-diff"])
    _, staged_patch_out, _ = git_capture(cwd, ["diff", "--cached", "--no-ext-diff"])
    _, names_out, _ = git_capture(cwd, ["diff", "--name-only"])
    _, staged_names_out, _ = git_capture(cwd, ["diff", "--cached", "--name-only"])
    status_lines = [line.rstrip() for line in status_out.splitlines() if line.strip()]
    changed_files: list[str] = []
    for line in status_lines:
        if len(line) >= 4:
            changed_files.append(line[3:].strip())
        else:
            changed_files.append(line.strip())
    unstaged_files = [line.strip() for line in names_out.splitlines() if line.strip()]
    staged_files = [line.strip() for line in staged_names_out.splitlines() if line.strip()]
    return {
        "ok": True,
        "cwd": str(cwd),
        "repo_root": repo_root,
        "branch": branch_out or None,
        "status_lines": status_lines,
        "changed_files": changed_files,
        "unstaged_files": unstaged_files,
        "staged_files": staged_files,
        "diff_stat": stat_out,
        "staged_diff_stat": staged_stat_out,
        "diff_patch": _truncate_patch(patch_out),
        "staged_diff_patch": _truncate_patch(staged_patch_out),
    }


def summarize_git_delta(start: dict[str, Any] | None, end: dict[str, Any] | None) -> dict[str, object] | None:
    if not start or not end:
        return None
    if not bool(start.get("ok")) or not bool(end.get("ok")):
        return None
    start_files = set(str(item) for item in start.get("changed_files", []))
    end_files = set(str(item) for item in end.get("changed_files", []))
    return {
        "ok": True,
        "repo_root": end.get("repo_root") or start.get("repo_root"),
        "branch_start": start.get("branch"),
        "branch_end": end.get("branch"),
        "start_changed_count": len(start_files),
        "end_changed_count": len(end_files),
        "added_files": sorted(end_files - start_files),
        "removed_files": sorted(start_files - end_files),
        "persistent_files": sorted(start_files & end_files),
        "end_changed_files": list(end.get("changed_files", [])),
        "end_unstaged_files": list(end.get("unstaged_files", [])),
        "end_staged_files": list(end.get("staged_files", [])),
        "end_diff_stat": end.get("diff_stat"),
        "end_staged_diff_stat": end.get("staged_diff_stat"),
        "end_diff_patch": end.get("diff_patch"),
        "end_staged_diff_patch": end.get("staged_diff_patch"),
    }


def _truncate_patch(text: str) -> dict[str, object]:
    if not text:
        return {"text": "", "truncated": False, "original_length": 0}
    if len(text) <= MAX_STORED_PATCH_CHARS:
        return {"text": text, "truncated": False, "original_length": len(text)}
    return {
        "text": text[:MAX_STORED_PATCH_CHARS],
        "truncated": True,
        "original_length": len(text),
    }
