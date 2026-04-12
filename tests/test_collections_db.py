from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from orchestro.collections import MarkdownChunker, ingest_collection, ingest_file


def _coll_id() -> str:
    return str(uuid4())


class TestCreateAndGetCollection:
    def test_roundtrip(self, tmp_db):
        cid = _coll_id()
        tmp_db.create_collection(cid, name="docs", source_type="manual")
        coll = tmp_db.get_collection(cid)
        assert coll is not None
        assert coll.name == "docs"
        assert coll.source_type == "manual"

    def test_missing_collection_returns_none(self, tmp_db):
        assert tmp_db.get_collection("does-not-exist") is None


class TestAddAndSearchChunks:
    def test_add_chunk_and_search(self, tmp_db):
        cid = _coll_id()
        tmp_db.create_collection(cid, name="notes", source_type="manual")

        chunk_id = str(uuid4())
        tmp_db.add_collection_chunk(
            chunk_id=chunk_id,
            collection_id=cid,
            content="Orchestro is an AI orchestrator for local LLMs",
            source_ref="readme.md",
            sequence=0,
        )

        results = tmp_db.search_collections("orchestrator")
        assert len(results) >= 1
        assert any(r["chunk_id"] == chunk_id for r in results)

    def test_search_no_results(self, tmp_db):
        cid = _coll_id()
        tmp_db.create_collection(cid, name="empty", source_type="manual")
        results = tmp_db.search_collections("xyzzyzyzzyxyxz")
        assert results == []


class TestDeleteCollection:
    def test_delete_removes_collection_and_chunks(self, tmp_db):
        cid = _coll_id()
        tmp_db.create_collection(cid, name="removable", source_type="manual")
        tmp_db.add_collection_chunk(
            chunk_id=str(uuid4()),
            collection_id=cid,
            content="temporary content for deletion test",
            source_ref="tmp.md",
            sequence=0,
        )
        tmp_db.delete_collection(cid)
        assert tmp_db.get_collection(cid) is None
        results = tmp_db.search_collections("temporary content")
        assert not any(r["collection_id"] == cid for r in results)


class TestIngestFile:
    def test_ingest_markdown_file(self, tmp_db, tmp_path):
        cid = _coll_id()
        tmp_db.create_collection(cid, name="md-test", source_type="file")

        md_file = tmp_path / "sample.md"
        md_file.write_text(
            "# Introduction\n\n"
            "This is the intro paragraph with enough text to form a chunk.\n\n"
            "# Details\n\n"
            "Here are some details about the project that should be searchable.\n",
            encoding="utf-8",
        )

        count = ingest_file(tmp_db, cid, md_file)
        assert count >= 1

        results = tmp_db.search_collections("details")
        assert len(results) >= 1
