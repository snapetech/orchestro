from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

MAX_TOOL_OUTPUT_CHARS = 12000
MAX_READ_FILE_CHARS = 20000
DEFAULT_BASH_TIMEOUT_SEC = 20


@dataclass(slots=True)
class ToolResult:
    ok: bool
    output: str
    metadata: dict[str, object]


@dataclass(slots=True)
class ToolDefinition:
    name: str
    description: str
    approval: str
    runner: Callable[[str, Path], ToolResult]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {
            "pwd": ToolDefinition("pwd", "Print the working directory.", "auto", self._run_pwd),
            "ls": ToolDefinition("ls", "List files in the working directory.", "auto", self._run_ls),
            "read_file": ToolDefinition("read_file", "Read a file relative to the working directory.", "auto", self._run_read_file),
            "rg": ToolDefinition("rg", "Search text recursively with ripgrep.", "auto", self._run_rg),
            "bash": ToolDefinition("bash", "Run a shell command in the working directory.", "confirm", self._run_bash),
        }

    def list_tools(self) -> list[dict[str, str]]:
        return [
            {"name": tool.name, "description": tool.description, "approval": tool.approval}
            for tool in sorted(self._tools.values(), key=lambda item: item.name)
        ]

    def run(self, name: str, argument: str, cwd: Path, *, approved: bool = False) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"unknown tool: {name}")
        if tool.approval == "confirm" and not approved:
            raise PermissionError(f"tool requires approval: {name}")
        return tool.runner(argument, cwd.resolve())

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def _run_pwd(self, argument: str, cwd: Path) -> ToolResult:
        del argument
        return ToolResult(ok=True, output=str(cwd.resolve()), metadata={"cwd": str(cwd.resolve())})

    def _run_ls(self, argument: str, cwd: Path) -> ToolResult:
        target = self._resolve_within_workspace(cwd, argument) if argument else cwd.resolve()
        entries = sorted(path.name for path in target.iterdir())
        return ToolResult(ok=True, output="\n".join(entries), metadata={"path": str(target), "count": len(entries)})

    def _run_read_file(self, argument: str, cwd: Path) -> ToolResult:
        if not argument:
            raise ValueError("read_file requires a relative path")
        target = self._resolve_within_workspace(cwd, argument)
        output = target.read_text(encoding="utf-8")
        truncated = len(output) > MAX_READ_FILE_CHARS
        safe_output = output[:MAX_READ_FILE_CHARS]
        return ToolResult(
            ok=True,
            output=safe_output,
            metadata={"path": str(target), "characters": len(output), "truncated": truncated},
        )

    def _run_rg(self, argument: str, cwd: Path) -> ToolResult:
        if not argument:
            raise ValueError("rg requires a search pattern")
        completed = subprocess.run(
            ["rg", "--line-number", "--color", "never", argument, str(cwd)],
            text=True,
            capture_output=True,
            check=False,
        )
        ok = completed.returncode in {0, 1}
        output = completed.stdout if completed.stdout else completed.stderr
        output, truncated = self._truncate_output(output.strip())
        return ToolResult(
            ok=ok,
            output=output,
            metadata={"returncode": completed.returncode, "query": argument, "truncated": truncated},
        )

    def _run_bash(self, argument: str, cwd: Path) -> ToolResult:
        if not argument:
            raise ValueError("bash requires a command string")
        try:
            completed = subprocess.run(
                ["bash", "-lc", argument],
                cwd=str(cwd),
                text=True,
                capture_output=True,
                check=False,
                timeout=DEFAULT_BASH_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "").strip()
            if exc.stderr:
                output = f"{output}\n[stderr]\n{exc.stderr}".strip()
            output, truncated = self._truncate_output(output)
            return ToolResult(
                ok=False,
                output=output,
                metadata={"timeout_sec": DEFAULT_BASH_TIMEOUT_SEC, "command": argument, "truncated": truncated},
            )
        output = completed.stdout
        if completed.stderr:
            output = f"{output}\n[stderr]\n{completed.stderr}".strip()
        output, truncated = self._truncate_output(output.strip())
        return ToolResult(
            ok=completed.returncode == 0,
            output=output,
            metadata={"returncode": completed.returncode, "command": argument, "truncated": truncated},
        )

    def _resolve_within_workspace(self, cwd: Path, argument: str) -> Path:
        target = (cwd / argument).resolve()
        try:
            target.relative_to(cwd.resolve())
        except ValueError as exc:
            raise ValueError("path escapes the working directory") from exc
        return target

    def _truncate_output(self, text: str) -> tuple[str, bool]:
        if len(text) <= MAX_TOOL_OUTPUT_CHARS:
            return text, False
        return text[:MAX_TOOL_OUTPUT_CHARS], True


def tool_result_payload(result: ToolResult) -> dict[str, object]:
    return {
        "ok": result.ok,
        "output": result.output,
        "metadata": result.metadata,
    }


def tool_result_json(result: ToolResult) -> str:
    return json.dumps(tool_result_payload(result), sort_keys=True, indent=2)
