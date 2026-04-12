from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class CompactionResult:
    original_length: int
    compacted_length: int
    steps_compacted: int
    steps_preserved: int


_TOOL_NAME_RE = re.compile(r"^tool:\s*(.+)$", re.MULTILINE)
_FILE_PATH_RE = re.compile(r"(?:/[\w.\-]+)+|[\w.\-]+\.(?:py|js|ts|json|yaml|yml|toml|md|txt|sh|cfg|ini|html|css)")
_ERROR_RE = re.compile(r"(?:Error|Exception|Traceback|FAIL|FAILED|error)[:|\s].*", re.IGNORECASE)
_FIXED_RE = re.compile(r"(?:Fixed|Resolved|Corrected|Patched)[:|\s].*", re.IGNORECASE)
_NOTE_RE = re.compile(r"(?:Note|Important|Warning|TODO)[:|\s].*", re.IGNORECASE)
_CONFIG_RE = re.compile(r"\b\w+\s*[=:]\s*\S+")


def compact_tool_state(
    tool_state: list[str],
    preserve_recent: int = 3,
) -> tuple[list[str], CompactionResult]:
    if len(tool_state) <= preserve_recent:
        total = sum(len(s) for s in tool_state)
        return tool_state, CompactionResult(
            original_length=total,
            compacted_length=total,
            steps_compacted=0,
            steps_preserved=len(tool_state),
        )

    old = tool_state[:-preserve_recent]
    recent = tool_state[-preserve_recent:]
    original_length = sum(len(s) for s in tool_state)

    tools_used: list[str] = []
    files_seen: set[str] = set()
    errors: list[str] = []
    findings: list[str] = []

    for entry in old:
        for m in _TOOL_NAME_RE.finditer(entry):
            name = m.group(1).strip()
            if name not in tools_used:
                tools_used.append(name)
        files_seen.update(_FILE_PATH_RE.findall(entry))
        for m in _ERROR_RE.finditer(entry):
            line = m.group(0).strip()
            if len(line) > 200:
                line = line[:200] + "..."
            errors.append(line)
        ok_match = re.search(r"^ok:\s*(True|False)", entry, re.MULTILINE)
        if ok_match and ok_match.group(1) == "True":
            output_lines = entry.split("output:\n", 1)
            if len(output_lines) == 2:
                preview = output_lines[1].strip()
                if preview:
                    preview = preview[:120] + "..." if len(preview) > 120 else preview
                    findings.append(preview)

    n = len(old)
    parts = [f"Compacted summary of steps 1-{n}:"]
    parts.append(f"- Tool calls: {', '.join(tools_used) if tools_used else 'none'}")
    parts.append(f"- Files accessed: {', '.join(sorted(files_seen)) if files_seen else 'none'}")
    if findings:
        parts.append(f"- Key findings: {'; '.join(findings[:5])}")
    else:
        parts.append("- Key findings: none")
    if errors:
        parts.append(f"- Errors encountered: {'; '.join(errors[:5])}")
    else:
        parts.append("- Errors encountered: none")

    summary = "\n".join(parts)
    compacted = [summary] + recent
    compacted_length = sum(len(s) for s in compacted)

    return compacted, CompactionResult(
        original_length=original_length,
        compacted_length=compacted_length,
        steps_compacted=n,
        steps_preserved=preserve_recent,
    )


def should_compact(tool_state: list[str], *, max_context_chars: int = 24000) -> bool:
    return sum(len(s) for s in tool_state) > max_context_chars


def extract_memory_candidates(tool_state: list[str]) -> dict[str, list[str]]:
    facts: list[str] = []
    corrections: list[str] = []

    for entry in tool_state:
        for m in _ERROR_RE.finditer(entry):
            line = m.group(0).strip()
            if len(line) > 300:
                line = line[:300] + "..."
            facts.append(line)

        for m in _FIXED_RE.finditer(entry):
            line = m.group(0).strip()
            if len(line) > 300:
                line = line[:300] + "..."
            corrections.append(line)

        for m in _NOTE_RE.finditer(entry):
            line = m.group(0).strip()
            if len(line) > 300:
                line = line[:300] + "..."
            facts.append(line)

        for path in _FILE_PATH_RE.findall(entry):
            if "/" in path and len(path) > 3:
                facts.append(f"File referenced: {path}")

    seen_facts: set[str] = set()
    deduped_facts: list[str] = []
    for f in facts:
        if f not in seen_facts:
            seen_facts.add(f)
            deduped_facts.append(f)

    seen_corrections: set[str] = set()
    deduped_corrections: list[str] = []
    for c in corrections:
        if c not in seen_corrections:
            seen_corrections.add(c)
            deduped_corrections.append(c)

    return {"facts": deduped_facts, "corrections": deduped_corrections}
