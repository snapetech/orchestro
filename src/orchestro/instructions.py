from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from orchestro.paths import global_instructions_path


@dataclass(slots=True)
class InstructionSource:
    label: str
    path: Path
    content: str


@dataclass(slots=True)
class InstructionBundle:
    sources: list[InstructionSource]

    @property
    def text(self) -> str | None:
        parts = []
        for source in self.sources:
            stripped = source.content.strip()
            if not stripped:
                continue
            parts.append(f"[{source.label}: {source.path}]\n{stripped}")
        if not parts:
            return None
        return "\n\n".join(parts)

    def metadata(self) -> dict[str, object]:
        return {
            "sources": [
                {
                    "label": source.label,
                    "path": str(source.path),
                    "characters": len(source.content),
                }
                for source in self.sources
            ]
        }


def load_instruction_bundle(working_directory: Path) -> InstructionBundle:
    sources: list[InstructionSource] = []

    global_path = global_instructions_path()
    if global_path.exists():
        sources.append(
            InstructionSource(
                label="global",
                path=global_path,
                content=global_path.read_text(encoding="utf-8"),
            )
        )

    project_path = find_project_instructions(working_directory)
    if project_path is not None:
        sources.append(
            InstructionSource(
                label="project",
                path=project_path,
                content=project_path.read_text(encoding="utf-8"),
            )
        )

    return InstructionBundle(sources=sources)


def find_project_instructions(working_directory: Path) -> Path | None:
    current = working_directory.resolve()
    for candidate_dir in [current, *current.parents]:
        candidate = candidate_dir / "ORCHESTRO.md"
        if candidate.exists():
            return candidate
    return None
