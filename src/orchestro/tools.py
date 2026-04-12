from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable
from uuid import uuid4

from orchestro.bash_analysis import analyze_bash_command
from orchestro.tasks import TaskPacket, validate_task_packet

if TYPE_CHECKING:
    from orchestro.db import OrchestroDB
    from orchestro.lsp_client import LSPManager

MAX_TOOL_OUTPUT_CHARS = 12000
MAX_READ_FILE_CHARS = 20000
DEFAULT_BASH_TIMEOUT_SEC = 20


@dataclass(slots=True)
class ToolResult:
    ok: bool
    output: str
    metadata: dict[str, object]
    confidence: float | None = None


@dataclass(slots=True)
class ToolDefinition:
    name: str
    description: str
    approval: str
    runner: Callable[[str, Path], ToolResult]


class ToolRegistry:
    def __init__(self, db: OrchestroDB | None = None, *, lsp_manager: LSPManager | None = None) -> None:
        self.db = db
        self._lsp_manager = lsp_manager
        self._current_run_id: str | None = None
        self._tools: dict[str, ToolDefinition] = {
            "bash": ToolDefinition("bash", "Run a shell command in the working directory.", "confirm", self._run_bash),
            "edit_file": ToolDefinition(
                "edit_file",
                "Apply a search-replace edit to a file. Argument format: filepath\\n<<<SEARCH\\nold text\\n===\\nnew text\\n>>>SEARCH",
                "confirm",
                self._run_edit_file,
            ),
            "git_commit": ToolDefinition(
                "git_commit",
                "Create a git commit. Argument is the commit message. Only staged changes are committed.",
                "confirm",
                self._run_git_commit,
            ),
            "git_diff": ToolDefinition(
                "git_diff",
                "Show git diff. Argument is optional: a file path, --staged, or --cached.",
                "auto",
                self._run_git_diff,
            ),
            "git_status": ToolDefinition(
                "git_status",
                "Show the git status of the working directory.",
                "auto",
                self._run_git_status,
            ),
            "ls": ToolDefinition("ls", "List files in the working directory.", "auto", self._run_ls),
            "pwd": ToolDefinition("pwd", "Print the working directory.", "auto", self._run_pwd),
            "read_file": ToolDefinition("read_file", "Read a file relative to the working directory.", "auto", self._run_read_file),
            "rg": ToolDefinition("rg", "Search text recursively with ripgrep.", "auto", self._run_rg),
            "run_tests": ToolDefinition(
                "run_tests",
                "Run the project test suite. Argument is optional: a specific test path or command.",
                "confirm",
                self._run_tests,
            ),
            "think": ToolDefinition(
                "think",
                "Record a structured reasoning step. The argument is your internal reasoning text. This helps you organize complex multi-step thinking.",
                "auto",
                self._run_think,
            ),
            "tool_search": ToolDefinition(
                "tool_search",
                "Search available tools by keyword. Returns matching tools with descriptions.",
                "auto",
                self._run_tool_search,
            ),
            "search_memory": ToolDefinition(
                "search_memory",
                "Search Orchestro memory for relevant prior interactions, corrections, and facts. Argument is the search query.",
                "auto",
                self._run_search_memory,
            ),
            "propose_fact": ToolDefinition(
                "propose_fact",
                "Propose a new fact for the operator to review. Format: key value [--source source]",
                "confirm",
                self._run_propose_fact,
            ),
            "propose_correction": ToolDefinition(
                "propose_correction",
                "Propose a correction. Format: context|||wrong_answer|||right_answer [|||domain]",
                "confirm",
                self._run_propose_correction,
            ),
            "spawn_subagent": ToolDefinition(
                "spawn_subagent",
                'Spawn a sub-agent to handle a subtask. Argument is JSON: {"objective": "...", "scope": "...", "acceptance_tests": ["..."], "max_wall_time": 900}',
                "confirm",
                self._run_spawn_subagent,
            ),
        }
        if self._lsp_manager and self._lsp_manager.supported_languages():
            self._register_lsp_tools()

    def _register_lsp_tools(self) -> None:
        langs = ", ".join(self._lsp_manager.supported_languages())  # type: ignore[union-attr]
        self._tools["lsp_diagnostics"] = ToolDefinition(
            "lsp_diagnostics",
            f"Get diagnostics for a file. Argument: file path. Languages: {langs}",
            "auto",
            self._run_lsp_diagnostics,
        )
        self._tools["lsp_definition"] = ToolDefinition(
            "lsp_definition",
            f"Find definition of symbol. Argument: file:line:col. Languages: {langs}",
            "auto",
            self._run_lsp_definition,
        )
        self._tools["lsp_references"] = ToolDefinition(
            "lsp_references",
            f"Find all references. Argument: file:line:col. Languages: {langs}",
            "auto",
            self._run_lsp_references,
        )
        self._tools["lsp_hover"] = ToolDefinition(
            "lsp_hover",
            f"Get type/doc info. Argument: file:line:col. Languages: {langs}",
            "auto",
            self._run_lsp_hover,
        )
        self._tools["lsp_symbols"] = ToolDefinition(
            "lsp_symbols",
            f"List symbols in a file. Argument: file path. Languages: {langs}",
            "auto",
            self._run_lsp_symbols,
        )
        self._tools["lsp_workspace_symbols"] = ToolDefinition(
            "lsp_workspace_symbols",
            f"Search symbols across project. Argument: query string. Languages: {langs}",
            "auto",
            self._run_lsp_workspace_symbols,
        )

    def _parse_file_line_col(self, argument: str) -> tuple[str, int, int]:
        parts = argument.rsplit(":", 2)
        if len(parts) < 3:
            raise ValueError("expected file:line:col")
        return parts[0], int(parts[1]), int(parts[2])

    def _get_lsp_connection(self, file_path: str, cwd: Path) -> tuple:
        from orchestro.lsp_client import file_uri, language_for_file

        lang = language_for_file(file_path)
        if not lang:
            raise ValueError(f"no language mapping for {file_path}")
        conn = self._lsp_manager.get_connection(lang, str(cwd))  # type: ignore[union-attr]
        if conn is None:
            raise ValueError(f"no LSP server available for {lang}")
        resolved = str((cwd / file_path).resolve()) if not Path(file_path).is_absolute() else file_path
        uri = file_uri(resolved)
        return conn, uri

    def _run_lsp_diagnostics(self, argument: str, cwd: Path) -> ToolResult:
        if not argument:
            raise ValueError("lsp_diagnostics requires a file path")
        conn, uri = self._get_lsp_connection(argument.strip(), cwd)
        items = conn.diagnostics(uri)
        if not items:
            return ToolResult(ok=True, output="no diagnostics", metadata={"file": argument})
        lines = []
        for d in items:
            rng = d.get("range", {}).get("start", {})
            severity = {1: "error", 2: "warning", 3: "info", 4: "hint"}.get(d.get("severity", 0), "unknown")
            lines.append(f"{rng.get('line', 0)+1}:{rng.get('character', 0)}: {severity}: {d.get('message', '')}")
        output = "\n".join(lines)
        return ToolResult(ok=True, output=output, metadata={"file": argument, "count": len(items)})

    def _run_lsp_definition(self, argument: str, cwd: Path) -> ToolResult:
        file_path, line, col = self._parse_file_line_col(argument.strip())
        conn, uri = self._get_lsp_connection(file_path, cwd)
        results = conn.definition(uri, line - 1, col)
        if not results:
            return ToolResult(ok=True, output="no definition found", metadata={})
        return ToolResult(ok=True, output=json.dumps(results, indent=2), metadata={"count": len(results)})

    def _run_lsp_references(self, argument: str, cwd: Path) -> ToolResult:
        file_path, line, col = self._parse_file_line_col(argument.strip())
        conn, uri = self._get_lsp_connection(file_path, cwd)
        results = conn.references(uri, line - 1, col)
        if not results:
            return ToolResult(ok=True, output="no references found", metadata={})
        return ToolResult(ok=True, output=json.dumps(results, indent=2), metadata={"count": len(results)})

    def _run_lsp_hover(self, argument: str, cwd: Path) -> ToolResult:
        file_path, line, col = self._parse_file_line_col(argument.strip())
        conn, uri = self._get_lsp_connection(file_path, cwd)
        result = conn.hover(uri, line - 1, col)
        if result is None:
            return ToolResult(ok=True, output="no hover info", metadata={})
        contents = result.get("contents", "")
        if isinstance(contents, dict):
            text = contents.get("value", str(contents))
        elif isinstance(contents, list):
            text = "\n".join(c.get("value", str(c)) if isinstance(c, dict) else str(c) for c in contents)
        else:
            text = str(contents)
        return ToolResult(ok=True, output=text, metadata={})

    def _run_lsp_symbols(self, argument: str, cwd: Path) -> ToolResult:
        if not argument:
            raise ValueError("lsp_symbols requires a file path")
        conn, uri = self._get_lsp_connection(argument.strip(), cwd)
        symbols = conn.document_symbols(uri)
        if not symbols:
            return ToolResult(ok=True, output="no symbols found", metadata={"file": argument})
        return ToolResult(ok=True, output=json.dumps(symbols, indent=2), metadata={"file": argument, "count": len(symbols)})

    def _run_lsp_workspace_symbols(self, argument: str, cwd: Path) -> ToolResult:
        if not argument:
            raise ValueError("lsp_workspace_symbols requires a query string")
        query = argument.strip()
        if not self._lsp_manager:
            return ToolResult(ok=False, output="no LSP manager", metadata={})
        all_symbols: list[dict] = []
        for lang in self._lsp_manager.supported_languages():
            conn = self._lsp_manager.get_connection(lang, str(cwd))
            if conn:
                all_symbols.extend(conn.workspace_symbols(query))
        if not all_symbols:
            return ToolResult(ok=True, output="no symbols found", metadata={"query": query})
        return ToolResult(ok=True, output=json.dumps(all_symbols, indent=2), metadata={"query": query, "count": len(all_symbols)})

    def list_tools(self) -> list[dict[str, str]]:
        return [
            {"name": tool.name, "description": tool.description, "approval": tool.approval}
            for tool in sorted(self._tools.values(), key=lambda item: item.name)
        ]

    def run(
        self,
        name: str,
        argument: str,
        cwd: Path,
        *,
        approved: bool = False,
        run_id: str | None = None,
    ) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"unknown tool: {name}")
        if tool.approval == "confirm" and not approved:
            raise PermissionError(f"tool requires approval: {name}")
        self._current_run_id = run_id
        try:
            return tool.runner(argument, cwd.resolve())
        finally:
            self._current_run_id = None

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
        risk = analyze_bash_command(argument)
        if risk.level == "deny":
            return ToolResult(
                ok=False,
                output=f"Command blocked: {'; '.join(risk.reasons)}",
                metadata={"command": argument, "bash_risk": "deny", "reasons": risk.reasons},
            )
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
            metadata: dict[str, object] = {
                "timeout_sec": DEFAULT_BASH_TIMEOUT_SEC, "command": argument, "truncated": truncated,
            }
            if risk.level == "warn":
                metadata["bash_risk"] = "warn"
                metadata["bash_risk_reasons"] = risk.reasons
            return ToolResult(ok=False, output=output, metadata=metadata)
        output = completed.stdout
        if completed.stderr:
            output = f"{output}\n[stderr]\n{completed.stderr}".strip()
        output, truncated = self._truncate_output(output.strip())
        metadata = {"returncode": completed.returncode, "command": argument, "truncated": truncated}
        if risk.level == "warn":
            metadata["bash_risk"] = "warn"
            metadata["bash_risk_reasons"] = risk.reasons
        return ToolResult(
            ok=completed.returncode == 0,
            output=output,
            metadata=metadata,
        )

    def _run_tests(self, argument: str, cwd: Path) -> ToolResult:
        if argument:
            cmd = argument
        else:
            cmd = "pytest -q || make test || python -m unittest discover"
        try:
            completed = subprocess.run(
                ["bash", "-lc", cmd],
                cwd=str(cwd),
                text=True,
                capture_output=True,
                check=False,
                timeout=60,
            )
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "").strip()
            if exc.stderr:
                output = f"{output}\n[stderr]\n{exc.stderr}".strip()
            output, truncated = self._truncate_output(output)
            return ToolResult(ok=False, output=output, metadata={"timeout_sec": 60, "command": cmd, "truncated": truncated})
        output = completed.stdout
        if completed.stderr:
            output = f"{output}\n[stderr]\n{completed.stderr}".strip()
        output, truncated = self._truncate_output(output.strip())
        return ToolResult(
            ok=completed.returncode == 0,
            output=output,
            metadata={"returncode": completed.returncode, "command": cmd, "truncated": truncated},
        )

    def _run_think(self, argument: str, cwd: Path) -> ToolResult:
        del cwd
        return ToolResult(ok=True, output=f"Thought recorded: {argument[:200]}", metadata={})

    def _run_tool_search(self, argument: str, cwd: Path) -> ToolResult:
        del cwd
        query = argument.strip()
        keywords = [part for part in query.split() if part]
        tools = self.list_tools()
        matches: list[dict[str, str]] = []
        for tool in tools:
            name_l = tool["name"].lower()
            desc_l = tool["description"].lower()
            if keywords and any(kw.lower() in name_l or kw.lower() in desc_l for kw in keywords):
                matches.append(tool)
        if matches:
            lines = [
                f"{t['name']}: {t['description']} (approval: {t['approval']})" for t in matches
            ]
            output = "\n".join(lines)
        else:
            all_names = ", ".join(t["name"] for t in tools)
            output = f"No tools matching '{query}' found. Available tools: {all_names}"
        return ToolResult(ok=True, output=output, metadata={"query": query, "match_count": len(matches)})

    def _run_edit_file(self, argument: str, cwd: Path) -> ToolResult:
        parts = argument.split("\n")
        if len(parts) < 2:
            return ToolResult(ok=False, output="invalid edit_file argument format", metadata={})
        filepath = parts[0].strip()
        body = "\n".join(parts[1:])
        if "<<<SEARCH" not in body or ">>>SEARCH" not in body or "\n===\n" not in body:
            return ToolResult(ok=False, output="invalid edit_file argument format", metadata={})
        search_start = body.index("<<<SEARCH") + len("<<<SEARCH\n")
        search_end = body.index("\n===\n")
        replace_start = search_end + len("\n===\n")
        replace_end = body.index("\n>>>SEARCH")
        old_text = body[search_start:search_end]
        new_text = body[replace_start:replace_end]
        try:
            target = self._resolve_within_workspace(cwd, filepath)
        except ValueError as exc:
            return ToolResult(ok=False, output=str(exc), metadata={})
        if not target.is_file():
            return ToolResult(ok=False, output="file not found", metadata={"path": filepath})
        content = target.read_text(encoding="utf-8")
        count = content.count(old_text)
        if count == 0:
            return ToolResult(ok=False, output="search text not found in file", metadata={"path": filepath})
        if count > 1:
            return ToolResult(
                ok=False,
                output=f"search text is ambiguous (found {count} occurrences)",
                metadata={"path": filepath, "occurrences": count},
            )
        content = content.replace(old_text, new_text, 1)
        target.write_text(content, encoding="utf-8")
        return ToolResult(
            ok=True,
            output=f"Applied edit to {filepath}: replaced {len(old_text)} characters",
            metadata={"path": str(target), "old_length": len(old_text), "new_length": len(new_text)},
        )

    def _run_git_commit(self, argument: str, cwd: Path) -> ToolResult:
        if not argument:
            raise ValueError("git_commit requires a commit message")
        try:
            completed = subprocess.run(
                ["git", "commit", "-m", argument],
                cwd=str(cwd),
                text=True,
                capture_output=True,
                check=False,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, output="git commit timed out", metadata={"message": argument})
        output = completed.stdout
        if completed.stderr:
            output = f"{output}\n[stderr]\n{completed.stderr}".strip()
        return ToolResult(
            ok=completed.returncode == 0,
            output=output.strip(),
            metadata={"returncode": completed.returncode, "message": argument},
        )

    def _run_git_diff(self, argument: str, cwd: Path) -> ToolResult:
        args = ["git", "diff"]
        if argument:
            args.extend(argument.split())
        try:
            completed = subprocess.run(
                args,
                cwd=str(cwd),
                text=True,
                capture_output=True,
                check=False,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, output="git diff timed out", metadata={"argument": argument})
        output = completed.stdout if completed.stdout else completed.stderr
        output, truncated = self._truncate_output(output.strip())
        return ToolResult(
            ok=completed.returncode == 0,
            output=output,
            metadata={"returncode": completed.returncode, "argument": argument, "truncated": truncated},
        )

    def _run_git_status(self, argument: str, cwd: Path) -> ToolResult:
        del argument
        try:
            completed = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(cwd),
                text=True,
                capture_output=True,
                check=False,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, output="git status timed out", metadata={})
        output = completed.stdout if completed.stdout else completed.stderr
        return ToolResult(
            ok=completed.returncode == 0,
            output=output.strip(),
            metadata={"returncode": completed.returncode},
        )

    def _run_search_memory(self, argument: str, cwd: Path) -> ToolResult:
        del cwd
        if self.db is None:
            return ToolResult(ok=False, output="memory not available", metadata={})
        query = argument.strip()
        if not query:
            return ToolResult(ok=False, output="search_memory requires a query", metadata={})
        hits = self.db.search(query=query, limit=10)
        if not hits:
            return ToolResult(ok=True, output="no results found", metadata={"query": query, "count": 0})
        lines = [f"[{h.source_type}] {h.title}: {h.snippet[:200]}" for h in hits]
        return ToolResult(ok=True, output="\n".join(lines), metadata={"query": query, "count": len(hits)})

    def _run_propose_fact(self, argument: str, cwd: Path) -> ToolResult:
        del cwd
        if self.db is None:
            return ToolResult(ok=False, output="memory not available", metadata={})
        text = argument.strip()
        if not text:
            return ToolResult(ok=False, output="propose_fact requires: key value [--source source]", metadata={})
        source: str | None = None
        if "--source " in text:
            idx = text.index("--source ")
            source = text[idx + len("--source "):].strip()
            text = text[:idx].strip()
        parts = text.split(None, 1)
        if len(parts) < 2:
            return ToolResult(ok=False, output="propose_fact requires both a key and a value", metadata={})
        key, value = parts[0], parts[1]
        fact_id = str(uuid4())
        self.db.add_fact(fact_id=fact_id, fact_key=key, fact_value=value, source=source, status="proposed")
        return ToolResult(
            ok=True,
            output=f"Fact proposed: {key} = {value}",
            metadata={"fact_id": fact_id, "key": key, "source": source},
        )

    def _run_propose_correction(self, argument: str, cwd: Path) -> ToolResult:
        del cwd
        if self.db is None:
            return ToolResult(ok=False, output="memory not available", metadata={})
        parts = argument.split("|||")
        if len(parts) < 3:
            return ToolResult(
                ok=False,
                output="propose_correction requires: context|||wrong_answer|||right_answer [|||domain]",
                metadata={},
            )
        context = parts[0].strip()
        wrong_answer = parts[1].strip()
        right_answer = parts[2].strip()
        domain = parts[3].strip() if len(parts) > 3 else None
        if not context or not wrong_answer or not right_answer:
            return ToolResult(ok=False, output="context, wrong_answer, and right_answer must be non-empty", metadata={})
        correction_id = str(uuid4())
        self.db.add_correction(
            correction_id=correction_id,
            context=context,
            wrong_answer=wrong_answer,
            right_answer=right_answer,
            domain=domain,
            severity="medium",
            source_run_id=None,
        )
        return ToolResult(
            ok=True,
            output=f"Correction proposed: {context[:80]}",
            metadata={"correction_id": correction_id, "domain": domain},
        )

    def _run_spawn_subagent(self, argument: str, cwd: Path) -> ToolResult:
        del cwd
        try:
            data = json.loads(argument.strip() or "{}")
        except json.JSONDecodeError as exc:
            return ToolResult(ok=False, output=f"invalid JSON: {exc}", metadata={})
        if not isinstance(data, dict):
            return ToolResult(ok=False, output="argument must be a JSON object", metadata={})
        if "objective" not in data:
            return ToolResult(ok=False, output="missing required field: objective", metadata={})
        try:
            packet = self._task_packet_from_spawn_json(data)
        except ValueError as exc:
            return ToolResult(ok=False, output=str(exc), metadata={})
        errors = validate_task_packet(packet)
        if errors:
            return ToolResult(
                ok=False,
                output="validation failed: " + "; ".join(errors),
                metadata={"errors": errors},
            )
        task_id = str(uuid4())
        status = "validated"
        if self.db is not None and self._current_run_id is not None:
            packet_json = json.dumps(asdict(packet), sort_keys=True)
            self.db.create_task(
                task_id=task_id,
                parent_run_id=self._current_run_id,
                objective=packet.objective,
                packet_json=packet_json,
            )
            status = "created"
        metadata: dict[str, object] = {"task_id": task_id, "status": status}
        return ToolResult(
            ok=True,
            output=json.dumps({"task_id": task_id, "status": status}, sort_keys=True),
            metadata=metadata,
        )

    @staticmethod
    def _task_packet_from_spawn_json(data: dict) -> TaskPacket:
        objective = data["objective"]
        if not isinstance(objective, str):
            objective = str(objective)
        scope = data.get("scope")
        if scope is not None and not isinstance(scope, str):
            scope = str(scope)
        acceptance_tests = data.get("acceptance_tests")
        if acceptance_tests is not None:
            if not isinstance(acceptance_tests, list):
                raise ValueError("acceptance_tests must be a list")
            acceptance_tests = [str(t) for t in acceptance_tests]
        context = data.get("context")
        if context is not None and not isinstance(context, dict):
            raise ValueError("context must be a JSON object")
        commit_policy = str(data.get("commit_policy", "none"))
        escalation_policy = str(data.get("escalation_policy", "escalate"))
        max_wall_time = int(data["max_wall_time"]) if "max_wall_time" in data else 900
        reporting = str(data.get("reporting", "summary"))
        return TaskPacket(
            objective=objective,
            scope=scope,
            acceptance_tests=acceptance_tests,
            commit_policy=commit_policy,
            escalation_policy=escalation_policy,
            max_wall_time=max_wall_time,
            context=context,
            reporting=reporting,
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
    payload: dict[str, object] = {
        "ok": result.ok,
        "output": result.output,
        "metadata": result.metadata,
    }
    if result.confidence is not None:
        payload["confidence"] = result.confidence
    return payload


def tool_result_json(result: ToolResult) -> str:
    return json.dumps(tool_result_payload(result), sort_keys=True, indent=2)
