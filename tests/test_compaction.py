from __future__ import annotations

from orchestro.compaction import (
    CompactionResult,
    compact_tool_state,
    extract_memory_candidates,
    should_compact,
)


# ---------------------------------------------------------------------------
# should_compact
# ---------------------------------------------------------------------------

def test_should_compact_false_under_limit():
    entries = ["short"] * 3
    assert should_compact(entries, max_context_chars=1000) is False


def test_should_compact_true_over_limit():
    entries = ["x" * 500] * 10
    assert should_compact(entries, max_context_chars=1000) is True


def test_should_compact_exactly_at_limit():
    # 10 entries of 100 chars = exactly 1000, not over
    entries = ["x" * 100] * 10
    assert should_compact(entries, max_context_chars=1000) is False


def test_should_compact_empty_is_false():
    assert should_compact([], max_context_chars=100) is False


# ---------------------------------------------------------------------------
# compact_tool_state
# ---------------------------------------------------------------------------

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
    assert result.steps_preserved == 2


def test_compact_tool_state_exactly_preserve_recent_returns_as_is():
    entries = ["a", "b", "c"]
    compacted, result = compact_tool_state(entries, preserve_recent=3)
    assert compacted == entries
    assert result.steps_compacted == 0


def test_compact_tool_state_returns_compaction_result():
    entries = ["x" * 100] * 10
    _, result = compact_tool_state(entries, preserve_recent=3)
    assert isinstance(result, CompactionResult)
    assert result.original_length > result.compacted_length
    assert result.steps_compacted == 7
    assert result.steps_preserved == 3


def test_compact_tool_state_summary_contains_tool_names():
    entries = [
        "tool: bash\noutput:\nhi\nok: True",
        "tool: read_file\noutput:\ncontent\nok: True",
        "tool: rg\noutput:\nresult\nok: True",
        "recent1",
        "recent2",
        "recent3",
    ]
    compacted, _ = compact_tool_state(entries, preserve_recent=3)
    summary = compacted[0]
    assert "bash" in summary
    assert "read_file" in summary


def test_compact_tool_state_summary_contains_error_info():
    entries = [
        "tool: bash\nError: permission denied\nok: False",
        "r1",
        "r2",
        "r3",
    ]
    compacted, _ = compact_tool_state(entries, preserve_recent=3)
    summary = compacted[0]
    assert "permission denied" in summary


def test_compact_tool_state_summary_captures_file_paths():
    entries = [
        "Accessing /home/user/project/main.py for refactoring",
        "recent1",
        "recent2",
        "recent3",
    ]
    compacted, _ = compact_tool_state(entries, preserve_recent=3)
    summary = compacted[0]
    assert "main.py" in summary or "/home/user/project/main.py" in summary


def test_compact_tool_state_preserves_order_of_recent():
    entries = [f"old {i}" for i in range(5)] + ["keep1", "keep2", "keep3"]
    compacted, _ = compact_tool_state(entries, preserve_recent=3)
    assert compacted[1] == "keep1"
    assert compacted[2] == "keep2"
    assert compacted[3] == "keep3"


# ---------------------------------------------------------------------------
# extract_memory_candidates
# ---------------------------------------------------------------------------

def test_extract_memory_candidates_finds_errors():
    entries = [
        "tool: bash\nError: file not found\nok: False",
        "tool: read_file\nFixed: corrected the path\nok: True",
    ]
    candidates = extract_memory_candidates(entries)
    assert any("file not found" in f for f in candidates["facts"])
    assert any("corrected the path" in c for c in candidates["corrections"])


def test_extract_memory_candidates_returns_dict_keys():
    candidates = extract_memory_candidates([])
    assert "facts" in candidates
    assert "corrections" in candidates


def test_extract_memory_candidates_deduplicates_facts():
    entries = [
        "Error: same error message",
        "Error: same error message",
    ]
    candidates = extract_memory_candidates(entries)
    facts = [f for f in candidates["facts"] if "same error message" in f]
    assert len(facts) == 1


def test_extract_memory_candidates_finds_file_paths():
    entries = ["Loading /etc/config/settings.yaml for processing"]
    candidates = extract_memory_candidates(entries)
    assert any("/etc/config/settings.yaml" in f for f in candidates["facts"])


def test_extract_memory_candidates_finds_notes():
    entries = ["Note: always use utf-8 encoding for this file"]
    candidates = extract_memory_candidates(entries)
    assert any("utf-8" in f for f in candidates["facts"])


def test_extract_memory_candidates_empty_input():
    candidates = extract_memory_candidates([])
    assert candidates["facts"] == []
    assert candidates["corrections"] == []
