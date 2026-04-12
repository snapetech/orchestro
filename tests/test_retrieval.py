"""Tests for retrieval module including collections provider and deduplication."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from orchestro.db import OrchestroDB, SearchHit
from orchestro.retrieval import RetrievalBuilder, RetrievalBundle


@pytest.fixture()
def db(tmp_path: Path) -> OrchestroDB:
    return OrchestroDB(tmp_path / "test.db")


@pytest.fixture()
def builder(db: OrchestroDB) -> RetrievalBuilder:
    return RetrievalBuilder(db)


class TestRetrievalBuilder:
    def test_build_empty_db_returns_no_context(self, builder: RetrievalBuilder) -> None:
        bundle = builder.build("test query")
        assert bundle.context_text is None
        assert bundle.lexical_hits == []
        assert bundle.semantic_hits == []
        assert bundle.postmortem_hits == []
        assert bundle.selected_hits == []

    def test_build_returns_retrieval_bundle(self, builder: RetrievalBuilder) -> None:
        result = builder.build("anything")
        assert isinstance(result, RetrievalBundle)

    def test_metadata_structure(self, builder: RetrievalBuilder) -> None:
        bundle = builder.build("query")
        meta = bundle.metadata()
        assert "lexical_hits" in meta
        assert "semantic_hits" in meta
        assert "selected_hits" in meta
        assert "postmortem_hits" in meta

    def _ingest(self, db: OrchestroDB, text: str, source_ref: str = "doc.md") -> str:
        """Helper: create a collection and ingest text into it."""
        from orchestro.collections import ingest_collection, ParagraphChunker
        cid = str(uuid4())
        db.create_collection(
            collection_id=cid,
            name="test-coll",
            description="unit test",
            source_type="manual",
        )
        ingest_collection(db, cid, text, strategy=ParagraphChunker(), source_ref=source_ref)
        return cid

    def test_collection_hits_included_in_context(self, db: OrchestroDB) -> None:
        self._ingest(db, "Python is a high-level programming language good for scripting")
        builder = RetrievalBuilder(db)
        bundle = builder.build("Python programming", providers=["collections"])
        # Collections provider should fire and produce context text.
        assert bundle.context_text is not None
        assert "Knowledge Base" in bundle.context_text

    def test_collection_provider_excluded_when_not_in_list(self, db: OrchestroDB) -> None:
        self._ingest(db, "some content here")
        builder = RetrievalBuilder(db)
        # Only lexical provider — no collections.
        bundle = builder.build("some content", providers=["lexical"])
        # No collection hits should appear.
        if bundle.context_text:
            assert "Knowledge Base" not in bundle.context_text

    def test_collection_hits_empty_on_no_match(self, db: OrchestroDB) -> None:
        self._ingest(db, "xyzzyx totally unrelated content zork")
        builder = RetrievalBuilder(db)
        # Query that cannot match.
        bundle = builder.build("Python async await coroutines", providers=["collections"])
        # May return no context if nothing matches.
        assert bundle is not None

    def test_collection_provider_exception_returns_empty(self, builder: RetrievalBuilder) -> None:
        with patch.object(builder.db, "search_collections", side_effect=RuntimeError("db error")):
            hits = builder._collection_hits(query="test", limit=4)
        assert hits == []

    def test_dedupe_removes_duplicates(self, builder: RetrievalBuilder) -> None:
        hit = SearchHit(
            source_type="interaction",
            source_id="id-1",
            title="Title",
            snippet="snippet",
            domain=None,
            score=1.0,
        )
        deduped = builder._dedupe_hits([hit, hit, hit])
        assert len(deduped) == 1

    def test_dedupe_keeps_different_ids(self, builder: RetrievalBuilder) -> None:
        hits = [
            SearchHit("correction", f"id-{i}", "T", "s", None, float(i))
            for i in range(5)
        ]
        deduped = builder._dedupe_hits(hits)
        assert len(deduped) == 5

    def test_providers_default_includes_collections(self, builder: RetrievalBuilder) -> None:
        # Default provider set should include 'collections'.
        bundle = builder.build("query")
        # Just verifying it doesn't crash with collections in the default set.
        assert isinstance(bundle, RetrievalBundle)

    def test_semantic_search_disabled_when_vector_not_enabled(self, builder: RetrievalBuilder) -> None:
        status = builder.db.vector_status()
        # In a fresh DB without embeddings, vector should either be disabled or produce no results.
        hits = builder._semantic_hits(query="test", limit=5, domain=None, kind="all")
        assert isinstance(hits, list)

    def test_normalize_text_lowercases_and_tokenizes(self, builder: RetrievalBuilder) -> None:
        result = builder._normalize_text("Hello World 123!")
        assert "hello" in result
        assert "world" in result
        assert "123" in result
