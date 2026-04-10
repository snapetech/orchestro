from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from orchestro.paths import global_constitutions_dir


@dataclass(slots=True)
class ConstitutionSource:
    label: str
    path: str
    content: str


@dataclass(slots=True)
class ConstitutionBundle:
    domain: str
    text: str
    sources: list[ConstitutionSource]

    def metadata(self) -> dict[str, object]:
        return {
            "domain": self.domain,
            "sources": [
                {"label": source.label, "path": source.path}
                for source in self.sources
            ],
        }


def load_constitution_bundle(domain: str | None, cwd: Path) -> ConstitutionBundle:
    if not domain:
        return ConstitutionBundle(domain="", text="", sources=[])
    sources: list[ConstitutionSource] = []
    project_path = find_project_constitution(domain, cwd)
    if project_path is not None:
        sources.append(
            ConstitutionSource(
                label="project",
                path=str(project_path),
                content=project_path.read_text(encoding="utf-8"),
            )
        )
    global_path = global_constitutions_dir() / f"{domain}.md"
    if global_path.exists():
        sources.append(
            ConstitutionSource(
                label="global",
                path=str(global_path),
                content=global_path.read_text(encoding="utf-8"),
            )
        )
    text = "\n\n".join(source.content.strip() for source in sources if source.content.strip())
    return ConstitutionBundle(domain=domain, text=text, sources=sources)


def find_project_constitution(domain: str, cwd: Path) -> Path | None:
    for candidate in [cwd.resolve(), *cwd.resolve().parents]:
        path = candidate / "constitutions" / f"{domain}.md"
        if path.exists():
            return path
    return None
