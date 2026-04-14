from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from orchestro.constitutions import (
    ConstitutionBundle,
    ConstitutionSource,
    find_project_constitution,
    load_constitution_bundle,
)


class TestConstitutionSource:
    def test_fields(self):
        s = ConstitutionSource(label="project", path="/some/path.md", content="# Rules\n")
        assert s.label == "project"
        assert s.path == "/some/path.md"
        assert s.content == "# Rules\n"


class TestConstitutionBundle:
    def test_metadata_structure(self):
        sources = [
            ConstitutionSource(label="project", path="/p.md", content="A"),
            ConstitutionSource(label="global", path="/g.md", content="B"),
        ]
        bundle = ConstitutionBundle(domain="coding", text="A\n\nB", sources=sources)
        meta = bundle.metadata()
        assert meta["domain"] == "coding"
        assert len(meta["sources"]) == 2
        assert meta["sources"][0]["label"] == "project"
        assert meta["sources"][1]["label"] == "global"

    def test_empty_bundle(self):
        bundle = ConstitutionBundle(domain="", text="", sources=[])
        assert bundle.text == ""
        assert bundle.metadata()["sources"] == []


class TestFindProjectConstitution:
    def test_finds_constitutions_dir_in_cwd(self, tmp_path: Path):
        (tmp_path / "constitutions").mkdir()
        (tmp_path / "constitutions" / "coding.md").write_text("# Coding rules")
        result = find_project_constitution("coding", tmp_path)
        assert result is not None
        assert result.name == "coding.md"

    def test_finds_in_parent_directory(self, tmp_path: Path):
        parent = tmp_path
        child = tmp_path / "sub" / "project"
        child.mkdir(parents=True)
        (parent / "constitutions").mkdir()
        (parent / "constitutions" / "coding.md").write_text("# Rules")
        result = find_project_constitution("coding", child)
        assert result is not None
        assert result.name == "coding.md"

    def test_returns_none_when_not_found(self, tmp_path: Path):
        result = find_project_constitution("nonexistent", tmp_path)
        assert result is None

    def test_domain_specific_file_only(self, tmp_path: Path):
        (tmp_path / "constitutions").mkdir()
        (tmp_path / "constitutions" / "coding.md").write_text("# Coding")
        # looking for "writing" should not return "coding.md"
        result = find_project_constitution("writing", tmp_path)
        assert result is None

    def test_closest_ancestor_wins(self, tmp_path: Path):
        # Set up constitutions at two levels — inner should win
        outer = tmp_path
        inner = tmp_path / "inner"
        inner.mkdir()
        (outer / "constitutions").mkdir()
        (outer / "constitutions" / "coding.md").write_text("outer")
        (inner / "constitutions").mkdir()
        (inner / "constitutions" / "coding.md").write_text("inner")
        result = find_project_constitution("coding", inner)
        assert result is not None
        assert result.read_text() == "inner"


class TestLoadConstitutionBundle:
    def test_no_domain_returns_empty(self, tmp_path: Path):
        bundle = load_constitution_bundle(None, tmp_path)
        assert bundle.text == ""
        assert bundle.domain == ""
        assert bundle.sources == []

    def test_loads_project_constitution(self, tmp_path: Path):
        (tmp_path / "constitutions").mkdir()
        (tmp_path / "constitutions" / "coding.md").write_text("# Project rules")
        with patch("orchestro.constitutions.global_constitutions_dir", return_value=tmp_path / "no_global"):
            bundle = load_constitution_bundle("coding", tmp_path)
        assert "# Project rules" in bundle.text
        assert any(s.label == "project" for s in bundle.sources)

    def test_loads_global_constitution(self, tmp_path: Path):
        global_dir = tmp_path / "global_constitutions"
        global_dir.mkdir()
        (global_dir / "coding.md").write_text("# Global rules")
        with patch("orchestro.constitutions.global_constitutions_dir", return_value=global_dir):
            bundle = load_constitution_bundle("coding", tmp_path / "empty_cwd")
        assert "# Global rules" in bundle.text
        assert any(s.label == "global" for s in bundle.sources)

    def test_merges_project_and_global(self, tmp_path: Path):
        (tmp_path / "constitutions").mkdir()
        (tmp_path / "constitutions" / "coding.md").write_text("Project rule.")
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / "coding.md").write_text("Global rule.")
        with patch("orchestro.constitutions.global_constitutions_dir", return_value=global_dir):
            bundle = load_constitution_bundle("coding", tmp_path)
        assert "Project rule." in bundle.text
        assert "Global rule." in bundle.text
        assert len(bundle.sources) == 2

    def test_empty_text_when_no_files(self, tmp_path: Path):
        with patch("orchestro.constitutions.global_constitutions_dir", return_value=tmp_path / "no_dir"):
            bundle = load_constitution_bundle("coding", tmp_path / "no_constitutions")
        assert bundle.text == ""
        assert bundle.sources == []

    def test_domain_set_on_bundle(self, tmp_path: Path):
        with patch("orchestro.constitutions.global_constitutions_dir", return_value=tmp_path / "no_dir"):
            bundle = load_constitution_bundle("devops", tmp_path)
        assert bundle.domain == "devops"

    def test_strips_blank_sources_from_text(self, tmp_path: Path):
        (tmp_path / "constitutions").mkdir()
        (tmp_path / "constitutions" / "coding.md").write_text("   \n  ")  # blank content
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / "coding.md").write_text("Real content.")
        with patch("orchestro.constitutions.global_constitutions_dir", return_value=global_dir):
            bundle = load_constitution_bundle("coding", tmp_path)
        assert bundle.text.strip() == "Real content."
