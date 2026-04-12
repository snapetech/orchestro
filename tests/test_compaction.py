from __future__ import annotations

from orchestro.compaction import (
    compact_tool_state,
    extract_memory_candidates,
    should_compact,
)


def test_should_compact_false_under_limit():
    entries = ["short"] * 3
    assert should_compact(entries, max_context_chars=1000) is False


def test_should_compact_true_over_limit():
    entries = ["x" * 500] * 10
    assert should_compact(entries, max_context_chars=1000) is True


def test_compact_tool_state_preserves_recent():
    entries = [f"step {i}" for i in range(10)]
    compacted, result = compact_tool_state(entries, preserve_recent=3)
    assert compacted[-3:] == entries[-3:]
    assert result.steps_preserved == 3
    assert result.steps_compacted == 7


def test_compact_tool_state_few_entries_returns_as_is():
    entries = ["a", "b"]
    compacted, result = compact_tool_state(entries, preserve_recent=3)
    assert compacted == entries
    assert result.steps_compacted == 0


def test_extract_memory_candidates_finds_errors():
    entries = [
        "tool: bash\nError: file not found\nok: False",
        "tool: read_file\nFixed: corrected the path\nok: True",
    ]
    candidates = extract_memory_candidates(entries)
    assert any("file not found" in f for f in candidates["facts"])
    assert any("corrected the path" in c for c in candidates["corrections"])
