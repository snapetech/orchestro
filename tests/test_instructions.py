from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from orchestro.instructions import (
    InstructionBundle,
    InstructionSource,
    find_project_instructions,
    load_instruction_bundle,
)


class TestInstructionSource:
    def test_fields(self):
        s = InstructionSource(label="global", path=Path("/g.md"), content="Be concise.")
        assert s.label == "global"
        assert s.path == Path("/g.md")
        assert s.content == "Be concise."


class TestInstructionBundle:
    def test_text_none_when_no_sources(self):
        bundle = InstructionBundle(sources=[])
        assert bundle.text is None

    def test_text_none_when_all_sources_blank(self):
        sources = [
            InstructionSource(label="global", path=Path("/g.md"), content="   \n "),
        ]
        bundle = InstructionBundle(sources=sources)
        assert bundle.text is None

    def test_text_combines_sources(self):
        sources = [
            InstructionSource(label="global", path=Path("/g.md"), content="Global rule."),
            InstructionSource(label="project", path=Path("/p.md"), content="Project rule."),
        ]
        bundle = InstructionBundle(sources=sources)
        text = bundle.text
        assert text is not None
        assert "Global rule." in text
        assert "Project rule." in text

    def test_text_includes_label_and_path(self):
        sources = [
            InstructionSource(label="global", path=Path("/g.md"), content="Content here."),
        ]
        bundle = InstructionBundle(sources=sources)
        text = bundle.text
        assert text is not None
        assert "[global:" in text
        assert "g.md" in text

    def test_text_separated_by_blank_line(self):
        sources = [
            InstructionSource(label="a", path=Path("/a.md"), content="First."),
            InstructionSource(label="b", path=Path("/b.md"), content="Second."),
        ]
        bundle = InstructionBundle(sources=sources)
        text = bundle.text
        assert text is not None
        assert "\n\n" in text

    def test_blank_sources_skipped_in_text(self):
        sources = [
            InstructionSource(label="empty", path=Path("/e.md"), content=""),
            InstructionSource(label="real", path=Path("/r.md"), content="Real content."),
        ]
        bundle = InstructionBundle(sources=sources)
        text = bundle.text
        assert text is not None
        assert "empty" not in text
        assert "Real content." in text

    def test_metadata_structure(self):
        sources = [
            InstructionSource(label="global", path=Path("/g.md"), content="Hello"),
        ]
        bundle = InstructionBundle(sources=sources)
        meta = bundle.metadata()
        assert len(meta["sources"]) == 1
        assert meta["sources"][0]["label"] == "global"
        assert meta["sources"][0]["characters"] == 5

    def test_metadata_empty_sources(self):
        bundle = InstructionBundle(sources=[])
        assert bundle.metadata()["sources"] == []


class TestFindProjectInstructions:
    def test_finds_orchestro_md_in_cwd(self, tmp_path: Path):
        (tmp_path / "ORCHESTRO.md").write_text("# Project instructions")
        result = find_project_instructions(tmp_path)
        assert result is not None
        assert result.name == "ORCHESTRO.md"

    def test_finds_in_parent_directory(self, tmp_path: Path):
        child = tmp_path / "sub" / "project"
        child.mkdir(parents=True)
        (tmp_path / "ORCHESTRO.md").write_text("# Rules")
        result = find_project_instructions(child)
        assert result is not None
        assert result.name == "ORCHESTRO.md"

    def test_returns_none_when_not_found(self, tmp_path: Path):
        result = find_project_instructions(tmp_path / "no_such_dir")
        assert result is None

    def test_closest_ancestor_wins(self, tmp_path: Path):
        inner = tmp_path / "inner"
        inner.mkdir()
        (tmp_path / "ORCHESTRO.md").write_text("outer")
        (inner / "ORCHESTRO.md").write_text("inner")
        result = find_project_instructions(inner)
        assert result is not None
        assert result.read_text() == "inner"


class TestLoadInstructionBundle:
    def test_empty_when_no_files(self, tmp_path: Path):
        with patch("orchestro.instructions.global_instructions_path", return_value=tmp_path / "no.md"):
            bundle = load_instruction_bundle(tmp_path / "empty")
        assert bundle.text is None
        assert bundle.sources == []

    def test_loads_global_instructions(self, tmp_path: Path):
        global_md = tmp_path / "global.md"
        global_md.write_text("# Global instructions")
        with patch("orchestro.instructions.global_instructions_path", return_value=global_md):
            bundle = load_instruction_bundle(tmp_path / "cwd")
        assert bundle.text is not None
        assert "# Global instructions" in bundle.text
        assert any(s.label == "global" for s in bundle.sources)

    def test_loads_project_instructions(self, tmp_path: Path):
        (tmp_path / "ORCHESTRO.md").write_text("# Project instructions")
        with patch("orchestro.instructions.global_instructions_path", return_value=tmp_path / "no.md"):
            bundle = load_instruction_bundle(tmp_path)
        assert bundle.text is not None
        assert "# Project instructions" in bundle.text
        assert any(s.label == "project" for s in bundle.sources)

    def test_global_loaded_before_project(self, tmp_path: Path):
        global_md = tmp_path / "global.md"
        global_md.write_text("Global content.")
        (tmp_path / "ORCHESTRO.md").write_text("Project content.")
        with patch("orchestro.instructions.global_instructions_path", return_value=global_md):
            bundle = load_instruction_bundle(tmp_path)
        assert bundle.text is not None
        text = bundle.text
        assert text.index("Global content.") < text.index("Project content.")
