from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(slots=True)
class ToolResult:
    ok: bool
    output: str
    metadata: dict[str, object]


@dataclass(slots=True)
class ToolDefinition:
    name: str
    description: str
    runner: Callable[[str, Path], ToolResult]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {
            "pwd": ToolDefinition("pwd", "Print the working directory.", self._run_pwd),
            "ls": ToolDefinition("ls", "List files in the working directory.", self._run_ls),
            "read_file": ToolDefinition("read_file", "Read a file relative to the working directory.", self._run_read_file),
            "rg": ToolDefinition("rg", "Search text recursively with ripgrep.", self._run_rg),
            "bash": ToolDefinition("bash", "Run a shell command in the working directory.", self._run_bash),
        }

    def list_tools(self) -> list[dict[str, str]]:
        return [
            {"name": tool.name, "description": tool.description}
            for tool in sorted(self._tools.values(), key=lambda item: item.name)
        ]

    def run(self, name: str, argument: str, cwd: Path) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"unknown tool: {name}")
        return tool.runner(argument, cwd)

    def _run_pwd(self, argument: str, cwd: Path) -> ToolResult:
        del argument
        return ToolResult(ok=True, output=str(cwd.resolve()), metadata={"cwd": str(cwd.resolve())})

    def _run_ls(self, argument: str, cwd: Path) -> ToolResult:
        target = (cwd / argument).resolve() if argument else cwd.resolve()
        entries = sorted(path.name for path in target.iterdir())
        return ToolResult(ok=True, output="\n".join(entries), metadata={"path": str(target), "count": len(entries)})

    def _run_read_file(self, argument: str, cwd: Path) -> ToolResult:
        if not argument:
            raise ValueError("read_file requires a relative path")
        target = (cwd / argument).resolve()
        output = target.read_text(encoding="utf-8")
        return ToolResult(ok=True, output=output, metadata={"path": str(target), "characters": len(output)})

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
        return ToolResult(
            ok=ok,
            output=output.strip(),
            metadata={"returncode": completed.returncode, "query": argument},
        )

    def _run_bash(self, argument: str, cwd: Path) -> ToolResult:
        if not argument:
            raise ValueError("bash requires a command string")
        completed = subprocess.run(
            ["bash", "-lc", argument],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            check=False,
        )
        output = completed.stdout
        if completed.stderr:
            output = f"{output}\n[stderr]\n{completed.stderr}".strip()
        return ToolResult(
            ok=completed.returncode == 0,
            output=output.strip(),
            metadata={"returncode": completed.returncode, "command": argument},
        )


def tool_result_payload(result: ToolResult) -> dict[str, object]:
    return {
        "ok": result.ok,
        "output": result.output,
        "metadata": result.metadata,
    }


def tool_result_json(result: ToolResult) -> str:
    return json.dumps(tool_result_payload(result), sort_keys=True, indent=2)
