from __future__ import annotations

import json
from pathlib import Path

from orchestro.approvals import ToolApprovalStore, approval_key


# ---------------------------------------------------------------------------
# approval_key
# ---------------------------------------------------------------------------

class TestApprovalKey:
    def test_no_argument(self):
        assert approval_key("read_file", "") == "read_file"

    def test_whitespace_only_argument(self):
        assert approval_key("read_file", "   ") == "read_file"

    def test_with_argument(self):
        assert approval_key("read_file", "README.md") == "read_file README.md"

    def test_argument_stripped(self):
        assert approval_key("bash", "  echo hi  ") == "bash echo hi"

    def test_tool_only_no_trailing_space(self):
        key = approval_key("bash", "")
        assert not key.endswith(" ")


# ---------------------------------------------------------------------------
# ToolApprovalStore.load_patterns
# ---------------------------------------------------------------------------

class TestLoadPatterns:
    def test_returns_empty_when_file_missing(self, tmp_path: Path):
        store = ToolApprovalStore(path=tmp_path / "approvals.json")
        assert store.load_patterns() == []

    def test_returns_patterns_from_file(self, tmp_path: Path):
        p = tmp_path / "approvals.json"
        p.write_text(json.dumps({"allow": ["read_file *", "bash echo*"]}))
        store = ToolApprovalStore(path=p)
        assert store.load_patterns() == ["read_file *", "bash echo*"]

    def test_missing_allow_key_returns_empty(self, tmp_path: Path):
        p = tmp_path / "approvals.json"
        p.write_text(json.dumps({"other": []}))
        store = ToolApprovalStore(path=p)
        assert store.load_patterns() == []

    def test_non_string_items_coerced_to_str(self, tmp_path: Path):
        p = tmp_path / "approvals.json"
        p.write_text(json.dumps({"allow": [123, True]}))
        store = ToolApprovalStore(path=p)
        patterns = store.load_patterns()
        assert patterns == ["123", "True"]


# ---------------------------------------------------------------------------
# ToolApprovalStore.is_allowed
# ---------------------------------------------------------------------------

class TestIsAllowed:
    def test_exact_match(self, tmp_path: Path):
        p = tmp_path / "approvals.json"
        p.write_text(json.dumps({"allow": ["read_file README.md"]}))
        store = ToolApprovalStore(path=p)
        assert store.is_allowed("read_file", "README.md") is True

    def test_no_match(self, tmp_path: Path):
        p = tmp_path / "approvals.json"
        p.write_text(json.dumps({"allow": ["read_file README.md"]}))
        store = ToolApprovalStore(path=p)
        assert store.is_allowed("read_file", "secrets.env") is False

    def test_glob_wildcard_match(self, tmp_path: Path):
        p = tmp_path / "approvals.json"
        p.write_text(json.dumps({"allow": ["read_file *"]}))
        store = ToolApprovalStore(path=p)
        assert store.is_allowed("read_file", "anything.txt") is True

    def test_glob_prefix_match(self, tmp_path: Path):
        p = tmp_path / "approvals.json"
        p.write_text(json.dumps({"allow": ["bash echo*"]}))
        store = ToolApprovalStore(path=p)
        assert store.is_allowed("bash", "echo hello") is True
        assert store.is_allowed("bash", "rm -rf /") is False

    def test_tool_only_pattern(self, tmp_path: Path):
        p = tmp_path / "approvals.json"
        p.write_text(json.dumps({"allow": ["read_file"]}))
        store = ToolApprovalStore(path=p)
        assert store.is_allowed("read_file", "") is True
        assert store.is_allowed("read_file", "some_arg") is False

    def test_no_file_returns_false(self, tmp_path: Path):
        store = ToolApprovalStore(path=tmp_path / "missing.json")
        assert store.is_allowed("read_file", "foo") is False

    def test_case_sensitive_match(self, tmp_path: Path):
        p = tmp_path / "approvals.json"
        p.write_text(json.dumps({"allow": ["read_file README.md"]}))
        store = ToolApprovalStore(path=p)
        assert store.is_allowed("read_file", "readme.md") is False


# ---------------------------------------------------------------------------
# ToolApprovalStore.remember
# ---------------------------------------------------------------------------

class TestRemember:
    def test_creates_file_when_missing(self, tmp_path: Path):
        p = tmp_path / "sub" / "approvals.json"
        store = ToolApprovalStore(path=p)
        store.remember("read_file *")
        assert p.exists()
        data = json.loads(p.read_text())
        assert "read_file *" in data["allow"]

    def test_appends_to_existing(self, tmp_path: Path):
        p = tmp_path / "approvals.json"
        p.write_text(json.dumps({"allow": ["bash echo*"]}))
        store = ToolApprovalStore(path=p)
        store.remember("read_file *")
        data = json.loads(p.read_text())
        assert "bash echo*" in data["allow"]
        assert "read_file *" in data["allow"]

    def test_no_duplicate(self, tmp_path: Path):
        p = tmp_path / "approvals.json"
        p.write_text(json.dumps({"allow": ["read_file *"]}))
        store = ToolApprovalStore(path=p)
        store.remember("read_file *")
        data = json.loads(p.read_text())
        assert data["allow"].count("read_file *") == 1

    def test_written_as_sorted_keys(self, tmp_path: Path):
        p = tmp_path / "approvals.json"
        store = ToolApprovalStore(path=p)
        store.remember("bash *")
        raw = p.read_text()
        assert '"allow"' in raw  # sorted keys → allow appears

    def test_after_remember_is_allowed(self, tmp_path: Path):
        p = tmp_path / "approvals.json"
        store = ToolApprovalStore(path=p)
        store.remember("read_file README.md")
        assert store.is_allowed("read_file", "README.md") is True
