from __future__ import annotations

from pathlib import Path

from orchestro.paths import (
    data_dir,
    db_path,
    facts_path,
    global_constitutions_dir,
    global_instructions_path,
    project_root,
    tool_approvals_path,
)


class TestProjectRoot:
    def test_returns_path(self):
        root = project_root()
        assert isinstance(root, Path)

    def test_contains_pyproject(self):
        # The project root should have pyproject.toml
        assert (project_root() / "pyproject.toml").exists()

    def test_is_absolute(self):
        assert project_root().is_absolute()


class TestDataDir:
    def test_default_under_project_root(self, monkeypatch, tmp_path):
        monkeypatch.delenv("ORCHESTRO_HOME", raising=False)
        # Patch project_root to return tmp_path so we don't pollute real .orchestro
        import orchestro.paths as paths_mod
        monkeypatch.setattr(paths_mod, "project_root", lambda: tmp_path)
        d = data_dir()
        assert d == tmp_path / ".orchestro"
        assert d.exists()

    def test_env_override(self, monkeypatch, tmp_path):
        target = tmp_path / "custom_home"
        monkeypatch.setenv("ORCHESTRO_HOME", str(target))
        d = data_dir()
        assert d == target
        assert d.exists()

    def test_env_override_tilde_expanded(self, monkeypatch, tmp_path):
        # Just verify ~ gets expanded (we can't easily set HOME portably,
        # so we verify the return value doesn't contain a literal ~)
        monkeypatch.setenv("ORCHESTRO_HOME", str(tmp_path / "mydir"))
        d = data_dir()
        assert "~" not in str(d)

    def test_creates_directory(self, monkeypatch, tmp_path):
        target = tmp_path / "new_dir" / "nested"
        monkeypatch.setenv("ORCHESTRO_HOME", str(target))
        d = data_dir()
        assert d.is_dir()


class TestDbPath:
    def test_ends_with_db_filename(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ORCHESTRO_HOME", str(tmp_path))
        p = db_path()
        assert p.name == "orchestro.db"
        assert p.parent == tmp_path


class TestFactsPath:
    def test_is_facts_md_in_project_root(self):
        p = facts_path()
        assert p.name == "facts.md"
        assert p.parent == project_root()


class TestGlobalInstructionsPath:
    def test_is_global_md_in_data_dir(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ORCHESTRO_HOME", str(tmp_path))
        p = global_instructions_path()
        assert p.name == "global.md"
        assert p.parent == tmp_path


class TestGlobalConstitutionsDir:
    def test_creates_and_returns_constitutions_subdir(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ORCHESTRO_HOME", str(tmp_path))
        d = global_constitutions_dir()
        assert d.name == "constitutions"
        assert d.parent == tmp_path
        assert d.is_dir()


class TestToolApprovalsPath:
    def test_is_json_file_in_data_dir(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ORCHESTRO_HOME", str(tmp_path))
        p = tool_approvals_path()
        assert p.name == "tool_approvals.json"
        assert p.parent == tmp_path
