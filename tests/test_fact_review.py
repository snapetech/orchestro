"""Tests for fact proposal review workflow."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from orchestro.db import OrchestroDB


@pytest.fixture()
def db(tmp_path: Path) -> OrchestroDB:
    return OrchestroDB(tmp_path / "test.db")


def _add_fact(db: OrchestroDB, key: str, value: str, status: str = "accepted") -> str:
    fid = str(uuid4())
    db.add_fact(fact_id=fid, fact_key=key, fact_value=value, source="test", status=status)
    return fid


class TestFactStatusMethods:
    def test_get_fact_returns_record(self, db: OrchestroDB) -> None:
        fid = _add_fact(db, "lang", "Python")
        fact = db.get_fact(fid)
        assert fact is not None
        assert fact.fact_key == "lang"
        assert fact.fact_value == "Python"

    def test_get_fact_missing_returns_none(self, db: OrchestroDB) -> None:
        assert db.get_fact("does-not-exist") is None

    def test_list_facts_by_status_accepted(self, db: OrchestroDB) -> None:
        _add_fact(db, "a", "1", status="accepted")
        _add_fact(db, "b", "2", status="proposed")
        _add_fact(db, "c", "3", status="accepted")
        results = db.list_facts_by_status("accepted")
        keys = {f.fact_key for f in results}
        assert "a" in keys
        assert "c" in keys
        assert "b" not in keys

    def test_list_facts_by_status_proposed(self, db: OrchestroDB) -> None:
        _add_fact(db, "x", "proposed-val", status="proposed")
        _add_fact(db, "y", "accepted-val", status="accepted")
        results = db.list_facts_by_status("proposed")
        assert len(results) == 1
        assert results[0].fact_key == "x"

    def test_list_facts_by_status_empty(self, db: OrchestroDB) -> None:
        assert db.list_facts_by_status("proposed") == []

    def test_update_fact_status_to_accepted(self, db: OrchestroDB) -> None:
        fid = _add_fact(db, "mykey", "myval", status="proposed")
        ok = db.update_fact_status(fid, "accepted")
        assert ok is True
        fact = db.get_fact(fid)
        assert fact is not None
        assert fact.status == "accepted"

    def test_update_fact_status_to_denied(self, db: OrchestroDB) -> None:
        fid = _add_fact(db, "mykey", "myval", status="proposed")
        db.update_fact_status(fid, "denied")
        fact = db.get_fact(fid)
        assert fact is not None
        assert fact.status == "denied"

    def test_update_fact_status_missing_returns_false(self, db: OrchestroDB) -> None:
        ok = db.update_fact_status("no-such-id", "accepted")
        assert ok is False

    def test_list_facts_by_status_respects_limit(self, db: OrchestroDB) -> None:
        for i in range(10):
            _add_fact(db, f"k{i}", f"v{i}", status="proposed")
        results = db.list_facts_by_status("proposed", limit=4)
        assert len(results) == 4

    def test_status_roundtrip_proposed_then_accepted(self, db: OrchestroDB) -> None:
        fid = _add_fact(db, "roundtrip", "val", status="proposed")
        assert db.list_facts_by_status("proposed")
        db.update_fact_status(fid, "accepted")
        assert not db.list_facts_by_status("proposed")
        accepted = db.list_facts_by_status("accepted")
        assert any(f.id == fid for f in accepted)
