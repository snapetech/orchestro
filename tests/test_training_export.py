from __future__ import annotations

import json

from orchestro.training_export import (
    ExportConfig,
    PreferenceExample,
    collect_preference_pairs,
    export_jsonl,
    export_sft,
    export_stats,
)


class TestCollectPreferencePairs:
    def test_empty_db_returns_empty(self, tmp_db):
        config = ExportConfig()
        pairs = collect_preference_pairs(tmp_db, config)
        assert pairs == []


class TestExportJsonl:
    def test_writes_correct_format(self, tmp_path):
        examples = [
            PreferenceExample(
                prompt="What is 2+2?",
                chosen="4",
                rejected="5",
                domain="math",
                source="rating",
            ),
            PreferenceExample(
                prompt="Capital of France?",
                chosen="Paris",
                rejected=None,
                domain="geography",
                source="rating",
            ),
        ]
        output = tmp_path / "export.jsonl"
        count = export_jsonl(examples, output)
        assert count == 2
        lines = output.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        record = json.loads(lines[0])
        assert record["prompt"] == "What is 2+2?"
        assert record["chosen"] == "4"
        assert record["rejected"] == "5"
        assert record["domain"] == "math"


class TestExportSft:
    def test_writes_chat_format(self, tmp_path):
        examples = [
            PreferenceExample(prompt="Explain gravity", chosen="Gravity is a force.", source="rating"),
        ]
        output = tmp_path / "sft.jsonl"
        count = export_sft(examples, output)
        assert count == 1
        record = json.loads(output.read_text(encoding="utf-8").strip())
        assert "messages" in record
        msgs = record["messages"]
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Explain gravity"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["content"] == "Gravity is a force."


class TestExportStats:
    def test_returns_expected_keys(self):
        examples = [
            PreferenceExample(prompt="q1", chosen="a1", rejected="a2", domain="d", source="rating"),
            PreferenceExample(prompt="q2", chosen="a3", rejected=None, domain="d", source="correction"),
        ]
        stats = export_stats(examples)
        assert stats["total"] == 2
        assert stats["paired"] == 1
        assert stats["unpaired"] == 1
        assert "by_source" in stats
        assert "by_domain" in stats
        assert stats["by_source"]["rating"] == 1
        assert stats["by_source"]["correction"] == 1
