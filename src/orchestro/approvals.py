from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path


def approval_key(tool_name: str, argument: str) -> str:
    suffix = f" {argument.strip()}" if argument.strip() else ""
    return f"{tool_name}{suffix}"


@dataclass(slots=True)
class ToolApprovalStore:
    path: Path

    def load_patterns(self) -> list[str]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        values = payload.get("allow", [])
        return [str(item) for item in values]

    def is_allowed(self, tool_name: str, argument: str) -> bool:
        key = approval_key(tool_name, argument)
        return any(fnmatch.fnmatchcase(key, pattern) for pattern in self.load_patterns())

    def remember(self, pattern: str) -> None:
        patterns = self.load_patterns()
        if pattern not in patterns:
            patterns.append(pattern)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"allow": patterns}, indent=2, sort_keys=True), encoding="utf-8")
