from __future__ import annotations

from pathlib import Path

from orchestro.db import FactRecord
from orchestro.facts_file import render_facts, sync_facts_file


def _fact(
    fact_key: str,
    fact_value: str,
    status: str = "accepted",
    source: str | None = None,
    updated_at: str = "2026-01-01T00:00:00",
) -> FactRecord:
    return FactRecord(
        id="test-id",
        fact_key=fact_key,
        fact_value=fact_value,
        source=source,
        status=status,
        created_at="2026-01-01T00:00:00",
        updated_at=updated_at,
    )


class TestRenderFacts:
    def test_header_always_present(self):
        output = render_facts([])
        assert "# Facts" in output

    def test_no_accepted_shows_placeholder(self):
        output = render_facts([])
        assert "_No accepted facts yet._" in output

    def test_only_proposed_shows_placeholder(self):
        fact = _fact("key", "value", status="proposed")
        output = render_facts([fact])
        assert "_No accepted facts yet._" in output

    def test_accepted_fact_rendered(self):
        fact = _fact("preference", "Use short responses")
        output = render_facts([fact])
        assert "## preference" in output
        assert "- Use short responses" in output

    def test_source_appended_in_parens(self):
        fact = _fact("style", "Concise", source="user-feedback")
        output = render_facts([fact])
        assert "(user-feedback)" in output

    def test_no_source_no_parens(self):
        fact = _fact("style", "Concise", source=None)
        output = render_facts([fact])
        assert "(" not in output.split("## style")[1].split("##")[0]

    def test_groups_by_fact_key(self):
        facts = [
            _fact("style", "Be brief"),
            _fact("style", "Use bullets"),
            _fact("tone", "Professional"),
        ]
        output = render_facts(facts)
        assert output.index("## style") < output.index("## tone")
        assert "Be brief" in output
        assert "Use bullets" in output
        assert "Professional" in output

    def test_keys_sorted_alphabetically(self):
        facts = [
            _fact("zebra", "z value"),
            _fact("apple", "a value"),
            _fact("mango", "m value"),
        ]
        output = render_facts(facts)
        assert output.index("## apple") < output.index("## mango") < output.index("## zebra")

    def test_within_group_sorted_by_updated_at_descending(self):
        facts = [
            _fact("key", "older value", updated_at="2026-01-01T00:00:00"),
            _fact("key", "newer value", updated_at="2026-06-01T00:00:00"),
        ]
        output = render_facts(facts)
        # newer should appear first within the group
        assert output.index("newer value") < output.index("older value")

    def test_denied_facts_excluded(self):
        facts = [
            _fact("key", "accepted value", status="accepted"),
            _fact("key", "denied value", status="denied"),
        ]
        output = render_facts(facts)
        assert "accepted value" in output
        assert "denied value" not in output

    def test_output_is_valid_markdown(self):
        fact = _fact("domain", "coding")
        output = render_facts([fact])
        lines = output.splitlines()
        assert lines[0] == "# Facts"


class TestSyncFactsFile:
    def test_writes_file(self, tmp_path: Path):
        p = tmp_path / "facts.md"
        sync_facts_file(p, [_fact("k", "v")])
        assert p.exists()
        assert "## k" in p.read_text()

    def test_overwrites_existing(self, tmp_path: Path):
        p = tmp_path / "facts.md"
        p.write_text("old content")
        sync_facts_file(p, [_fact("newkey", "newval")])
        content = p.read_text()
        assert "old content" not in content
        assert "newkey" in content

    def test_empty_list_writes_placeholder(self, tmp_path: Path):
        p = tmp_path / "facts.md"
        sync_facts_file(p, [])
        assert "_No accepted facts yet._" in p.read_text()
