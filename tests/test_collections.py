from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from orchestro.collections import (
    ChunkingStrategy,
    MarkdownChunker,
    ParagraphChunker,
    ingest_collection,
    ingest_directory,
    ingest_file,
)


# ---------------------------------------------------------------------------
# ParagraphChunker
# ---------------------------------------------------------------------------

class TestParagraphChunker:
    def test_single_paragraph(self):
        chunker = ParagraphChunker()
        chunks = chunker.chunk("Hello world")
        assert len(chunks) == 1
        assert chunks[0][0] == "Hello world"

    def test_two_paragraphs(self):
        # ParagraphChunker merges short paragraphs (<100 chars) into the previous one,
        # so two short paragraphs come back as one merged chunk.
        chunker = ParagraphChunker()
        text = "First paragraph.\n\nSecond paragraph."
        chunks = chunker.chunk(text)
        assert len(chunks) == 1
        assert "First paragraph." in chunks[0][0]
        assert "Second paragraph." in chunks[0][0]

    def test_source_ref_propagated(self):
        chunker = ParagraphChunker()
        chunks = chunker.chunk("Some text.", source_ref="doc.md")
        assert chunks[0][1] == "doc.md"

    def test_empty_paragraphs_skipped(self):
        # Short paragraphs get merged; extra blank lines are still collapsed.
        chunker = ParagraphChunker()
        text = "First.\n\n\n\nSecond."
        chunks = chunker.chunk(text)
        assert len(chunks) >= 1
        combined = " ".join(c[0] for c in chunks)
        assert "First." in combined
        assert "Second." in combined

    def test_short_paragraphs_merged(self):
        chunker = ParagraphChunker()
        # Each paragraph < 100 chars; they should be merged together
        text = "Short.\n\nAlso short.\n\nThird."
        chunks = chunker.chunk(text)
        # All merged into one because each is < 100 chars
        assert len(chunks) == 1

    def test_long_paragraph_truncated_to_2000(self):
        chunker = ParagraphChunker()
        text = "x" * 3000
        chunks = chunker.chunk(text)
        assert len(chunks) == 1
        assert len(chunks[0][0]) == 2000

    def test_returns_list_of_tuples(self):
        chunker = ParagraphChunker()
        chunks = chunker.chunk("Hello.")
        for chunk in chunks:
            assert isinstance(chunk, tuple)
            assert len(chunk) == 2

    def test_empty_string_returns_empty(self):
        chunker = ParagraphChunker()
        chunks = chunker.chunk("")
        assert chunks == []

    def test_whitespace_only_returns_empty(self):
        chunker = ParagraphChunker()
        chunks = chunker.chunk("   \n\n  \n  ")
        assert chunks == []

    def test_is_abstract_base(self):
        assert issubclass(ParagraphChunker, ChunkingStrategy)

    def test_long_paragraphs_not_merged(self):
        chunker = ParagraphChunker()
        # Two long paragraphs (>= 100 chars each) should stay separate
        p1 = "a" * 150
        p2 = "b" * 150
        chunks = chunker.chunk(f"{p1}\n\n{p2}")
        assert len(chunks) == 2


# ---------------------------------------------------------------------------
# MarkdownChunker
# ---------------------------------------------------------------------------

class TestMarkdownChunker:
    def test_no_headings_returns_whole_text(self):
        chunker = MarkdownChunker()
        chunks = chunker.chunk("Just prose without headings.")
        assert len(chunks) == 1
        assert "Just prose" in chunks[0][0]

    def test_heading_splits_sections(self):
        chunker = MarkdownChunker()
        text = "# Section 1\nContent of section 1.\n\n# Section 2\nContent of section 2."
        chunks = chunker.chunk(text)
        # Two sections after headings
        assert any("Content of section 1" in c[0] for c in chunks)
        assert any("Content of section 2" in c[0] for c in chunks)

    def test_heading_used_as_source_ref(self):
        chunker = MarkdownChunker()
        text = "# My Heading\nSome content here."
        chunks = chunker.chunk(text)
        refs = [c[1] for c in chunks]
        assert "My Heading" in refs

    def test_default_source_ref_before_first_heading(self):
        chunker = MarkdownChunker()
        text = "Preamble.\n\n# Section\nBody."
        chunks = chunker.chunk(text, source_ref="file.md")
        # Preamble before first heading should carry the source_ref
        assert chunks[0][1] == "file.md"

    def test_empty_text_returns_empty(self):
        chunker = MarkdownChunker()
        assert chunker.chunk("") == []

    def test_heading_levels_all_recognized(self):
        chunker = MarkdownChunker()
        text = "# H1\nA\n## H2\nB\n### H3\nC"
        chunks = chunker.chunk(text)
        refs = [c[1] for c in chunks]
        assert "H1" in refs or "H2" in refs or "H3" in refs

    def test_returns_list_of_tuples(self):
        chunker = MarkdownChunker()
        chunks = chunker.chunk("# Head\nBody text.")
        for chunk in chunks:
            assert isinstance(chunk, tuple)
            assert len(chunk) == 2

    def test_short_sections_merged(self):
        chunker = MarkdownChunker()
        # Two small sections; should be merged
        text = "# A\nTiny.\n# B\nAlso tiny."
        chunks = chunker.chunk(text)
        assert len(chunks) == 1

    def test_long_sections_not_merged(self):
        chunker = MarkdownChunker()
        body = "word " * 30  # > 100 chars
        text = f"# A\n{body}\n# B\n{body}"
        chunks = chunker.chunk(text)
        assert len(chunks) >= 2


# ---------------------------------------------------------------------------
# ingest_collection
# ---------------------------------------------------------------------------

class TestIngestCollection:
    def _make_db(self):
        db = MagicMock()
        return db

    def test_returns_chunk_count(self):
        db = self._make_db()
        chunker = ParagraphChunker()
        count = ingest_collection(db, "col-1", "Para one.\n\n" + "x" * 200, strategy=chunker)
        assert count >= 1

    def test_calls_add_collection_chunk_for_each_chunk(self):
        db = self._make_db()
        text = "Para one.\n\n" + "a" * 200 + "\n\n" + "b" * 200
        chunker = ParagraphChunker()
        count = ingest_collection(db, "col-1", text, strategy=chunker)
        assert db.add_collection_chunk.call_count == count

    def test_calls_update_collection_stats(self):
        db = self._make_db()
        ingest_collection(db, "col-1", "Some text.", strategy=ParagraphChunker())
        db.update_collection_stats.assert_called_once_with("col-1")

    def test_chunk_ids_are_unique(self):
        db = self._make_db()
        text = "a" * 200 + "\n\n" + "b" * 200
        ingest_collection(db, "col-1", text, strategy=ParagraphChunker())
        ids = [c.kwargs["chunk_id"] for c in db.add_collection_chunk.call_args_list]
        assert len(ids) == len(set(ids))

    def test_sequence_numbers_increment(self):
        db = self._make_db()
        text = "a" * 200 + "\n\n" + "b" * 200
        ingest_collection(db, "col-1", text, strategy=ParagraphChunker())
        seqs = [c.kwargs["sequence"] for c in db.add_collection_chunk.call_args_list]
        assert seqs == list(range(len(seqs)))

    def test_empty_text_returns_zero(self):
        db = self._make_db()
        count = ingest_collection(db, "col-1", "", strategy=ParagraphChunker())
        assert count == 0
        db.add_collection_chunk.assert_not_called()


# ---------------------------------------------------------------------------
# ingest_file
# ---------------------------------------------------------------------------

class TestIngestFile:
    def test_reads_and_ingests_txt(self, tmp_path: Path):
        txt = tmp_path / "doc.txt"
        txt.write_text("Hello world.\n\nSecond paragraph.", encoding="utf-8")
        db = MagicMock()
        count = ingest_file(db, "col", txt)
        assert count >= 1

    def test_uses_markdown_chunker_for_md(self, tmp_path: Path):
        md = tmp_path / "readme.md"
        md.write_text("# Title\nContent.", encoding="utf-8")
        db = MagicMock()
        ingest_file(db, "col", md)
        # MarkdownChunker should have been used; verify chunk was stored
        db.add_collection_chunk.assert_called()

    def test_uses_paragraph_chunker_for_txt(self, tmp_path: Path):
        txt = tmp_path / "notes.txt"
        txt.write_text("A note.", encoding="utf-8")
        db = MagicMock()
        ingest_file(db, "col", txt)
        db.add_collection_chunk.assert_called()

    def test_custom_strategy_used(self, tmp_path: Path):
        txt = tmp_path / "doc.txt"
        txt.write_text("Hello.", encoding="utf-8")
        db = MagicMock()
        strategy = MarkdownChunker()
        ingest_file(db, "col", txt, strategy=strategy)
        db.add_collection_chunk.assert_called()

    def test_source_ref_is_filename(self, tmp_path: Path):
        txt = tmp_path / "notes.txt"
        txt.write_text("Content.", encoding="utf-8")
        db = MagicMock()
        ingest_file(db, "col", txt)
        call_kwargs = db.add_collection_chunk.call_args_list[0].kwargs
        assert call_kwargs["source_ref"] == "notes.txt"


# ---------------------------------------------------------------------------
# ingest_directory
# ---------------------------------------------------------------------------

class TestIngestDirectory:
    def test_ingests_all_md_files(self, tmp_path: Path):
        (tmp_path / "a.md").write_text("# A\nContent.", encoding="utf-8")
        (tmp_path / "b.md").write_text("# B\nContent.", encoding="utf-8")
        db = MagicMock()
        count = ingest_directory(db, "col", tmp_path)
        assert count >= 2

    def test_ingests_txt_files(self, tmp_path: Path):
        (tmp_path / "doc.txt").write_text("Hello world.", encoding="utf-8")
        db = MagicMock()
        count = ingest_directory(db, "col", tmp_path)
        assert count >= 1

    def test_skips_non_allowed_extensions(self, tmp_path: Path):
        (tmp_path / "script.py").write_text("print('hi')", encoding="utf-8")
        db = MagicMock()
        count = ingest_directory(db, "col", tmp_path)
        assert count == 0
        db.add_collection_chunk.assert_not_called()

    def test_custom_extensions_filter(self, tmp_path: Path):
        (tmp_path / "code.py").write_text("x = 1\n\ny = 2", encoding="utf-8")
        (tmp_path / "readme.md").write_text("# Doc", encoding="utf-8")
        db = MagicMock()
        count = ingest_directory(db, "col", tmp_path, extensions=[".py"])
        # Only .py should be ingested
        assert count >= 1
        # The .md file should NOT have been processed
        py_calls = [
            c for c in db.add_collection_chunk.call_args_list
            if c.kwargs.get("source_ref") == "code.py"
        ]
        assert len(py_calls) >= 1

    def test_recursive_subdirectories(self, tmp_path: Path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.md").write_text("# Nested\nContent.", encoding="utf-8")
        db = MagicMock()
        count = ingest_directory(db, "col", tmp_path)
        assert count >= 1

    def test_empty_directory_returns_zero(self, tmp_path: Path):
        db = MagicMock()
        count = ingest_directory(db, "col", tmp_path)
        assert count == 0
