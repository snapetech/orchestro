from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    parent_run_id TEXT REFERENCES runs(id),
    goal TEXT NOT NULL,
    status TEXT NOT NULL,
    backend_name TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    working_directory TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    error_message TEXT,
    final_output TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS run_events (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    sequence_no INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(run_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS ratings (
    id TEXT PRIMARY KEY,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    rating TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interactions (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE REFERENCES runs(id) ON DELETE CASCADE,
    query_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    backend_name TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    domain TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS facts (
    id TEXT PRIMARY KEY,
    fact_key TEXT NOT NULL,
    fact_value TEXT NOT NULL,
    source TEXT,
    status TEXT NOT NULL DEFAULT 'accepted',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS corrections (
    id TEXT PRIMARY KEY,
    source_run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
    domain TEXT,
    severity TEXT NOT NULL DEFAULT 'normal',
    context TEXT NOT NULL,
    wrong_answer TEXT NOT NULL,
    right_answer TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_events_run_id ON run_events(run_id, sequence_no);
CREATE INDEX IF NOT EXISTS idx_ratings_target ON ratings(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_interactions_created_at ON interactions(created_at);
CREATE INDEX IF NOT EXISTS idx_facts_key ON facts(fact_key, updated_at);
CREATE INDEX IF NOT EXISTS idx_corrections_domain ON corrections(domain, created_at);
"""


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat()


@dataclass(slots=True)
class RunRecord:
    id: str
    goal: str
    status: str
    backend_name: str
    strategy_name: str
    working_directory: str
    created_at: str
    updated_at: str
    completed_at: str | None
    error_message: str | None
    final_output: str | None
    metadata: dict[str, Any]


@dataclass(slots=True)
class InteractionRecord:
    id: str
    run_id: str
    query_text: str
    response_text: str
    backend_name: str
    strategy_name: str
    domain: str | None
    created_at: str
    rating: str | None


@dataclass(slots=True)
class FactRecord:
    id: str
    fact_key: str
    fact_value: str
    source: str | None
    status: str
    created_at: str
    updated_at: str


@dataclass(slots=True)
class CorrectionRecord:
    id: str
    source_run_id: str | None
    domain: str | None
    severity: str
    context: str
    wrong_answer: str
    right_answer: str
    created_at: str


class OrchestroDB:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def create_run(
        self,
        *,
        run_id: str,
        goal: str,
        backend_name: str,
        strategy_name: str,
        working_directory: str,
        parent_run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    id, parent_run_id, goal, status, backend_name, strategy_name,
                    working_directory, created_at, updated_at, metadata_json
                )
                VALUES (?, ?, ?, 'running', ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    parent_run_id,
                    goal,
                    backend_name,
                    strategy_name,
                    working_directory,
                    now,
                    now,
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )

    def append_event(
        self,
        *,
        run_id: str,
        event_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> int:
        now = utc_now()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(sequence_no), 0) + 1 AS next_no FROM run_events WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            sequence_no = int(row["next_no"])
            conn.execute(
                """
                INSERT INTO run_events (id, run_id, event_type, sequence_no, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    run_id,
                    event_type,
                    sequence_no,
                    now,
                    json.dumps(payload, sort_keys=True),
                ),
            )
            conn.execute(
                "UPDATE runs SET updated_at = ? WHERE id = ?",
                (now, run_id),
            )
        return sequence_no

    def complete_run(self, *, run_id: str, final_output: str) -> None:
        now = utc_now()
        with self.connect() as conn:
            run = conn.execute(
                """
                SELECT id, goal, backend_name, strategy_name, created_at, metadata_json
                FROM runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
            if run is None:
                raise ValueError(f"run not found: {run_id}")
            metadata = json.loads(run["metadata_json"])
            conn.execute(
                """
                UPDATE runs
                SET status = 'done', final_output = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (final_output, now, now, run_id),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO interactions (
                    id, run_id, query_text, response_text, backend_name,
                    strategy_name, domain, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    run_id,
                    run["goal"],
                    final_output,
                    run["backend_name"],
                    run["strategy_name"],
                    metadata.get("domain"),
                    run["created_at"],
                ),
            )

    def fail_run(self, *, run_id: str, error_message: str) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE runs
                SET status = 'failed', error_message = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (error_message, now, now, run_id),
            )

    def add_rating(
        self,
        *,
        rating_id: str,
        target_type: str,
        target_id: str,
        rating: str,
        note: str | None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO ratings (id, target_type, target_id, rating, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (rating_id, target_type, target_id, rating, note, utc_now()),
            )

    def list_runs(self, limit: int = 20) -> list[RunRecord]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_run(row) for row in rows]

    def get_run(self, run_id: str) -> RunRecord | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_run(row)

    def list_events(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, event_type, sequence_no, created_at, payload_json
                FROM run_events
                WHERE run_id = ?
                ORDER BY sequence_no ASC
                """,
                (run_id,),
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            events.append(
                {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "sequence_no": row["sequence_no"],
                    "created_at": row["created_at"],
                    "payload": json.loads(row["payload_json"]),
                }
            )
        return events

    def list_unrated_runs(self, limit: int = 20) -> list[RunRecord]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT r.*
                FROM runs r
                LEFT JOIN ratings t
                    ON t.target_type = 'run' AND t.target_id = r.id
                WHERE t.id IS NULL
                ORDER BY r.created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_run(row) for row in rows]

    def list_interactions(self, limit: int = 20, query: str | None = None) -> list[InteractionRecord]:
        params: list[Any] = []
        where = ""
        if query:
            where = """
            WHERE i.query_text LIKE ? OR i.response_text LIKE ? OR COALESCE(i.domain, '') LIKE ?
            """
            needle = f"%{query}%"
            params.extend([needle, needle, needle])
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    i.*,
                    (
                        SELECT r.rating
                        FROM ratings r
                        WHERE r.target_type = 'run' AND r.target_id = i.run_id
                        ORDER BY r.created_at DESC
                        LIMIT 1
                    ) AS rating
                FROM interactions i
                {where}
                ORDER BY i.created_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._row_to_interaction(row) for row in rows]

    def add_fact(
        self,
        *,
        fact_id: str,
        fact_key: str,
        fact_value: str,
        source: str | None,
        status: str = "accepted",
    ) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO facts (id, fact_key, fact_value, source, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (fact_id, fact_key, fact_value, source, status, now, now),
            )

    def list_facts(self, limit: int = 50, key: str | None = None) -> list[FactRecord]:
        params: list[Any] = []
        where = ""
        if key:
            where = "WHERE fact_key LIKE ?"
            params.append(f"%{key}%")
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM facts
                {where}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._row_to_fact(row) for row in rows]

    def add_correction(
        self,
        *,
        correction_id: str,
        context: str,
        wrong_answer: str,
        right_answer: str,
        domain: str | None,
        severity: str,
        source_run_id: str | None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO corrections (
                    id, source_run_id, domain, severity, context,
                    wrong_answer, right_answer, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    correction_id,
                    source_run_id,
                    domain,
                    severity,
                    context,
                    wrong_answer,
                    right_answer,
                    utc_now(),
                ),
            )

    def list_corrections(
        self,
        limit: int = 50,
        domain: str | None = None,
        query: str | None = None,
    ) -> list[CorrectionRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if domain:
            clauses.append("domain = ?")
            params.append(domain)
        if query:
            clauses.append("(context LIKE ? OR wrong_answer LIKE ? OR right_answer LIKE ?)")
            needle = f"%{query}%"
            params.extend([needle, needle, needle])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM corrections
                {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._row_to_correction(row) for row in rows]

    def _row_to_run(self, row: sqlite3.Row) -> RunRecord:
        return RunRecord(
            id=row["id"],
            goal=row["goal"],
            status=row["status"],
            backend_name=row["backend_name"],
            strategy_name=row["strategy_name"],
            working_directory=row["working_directory"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
            error_message=row["error_message"],
            final_output=row["final_output"],
            metadata=json.loads(row["metadata_json"]),
        )

    def _row_to_interaction(self, row: sqlite3.Row) -> InteractionRecord:
        return InteractionRecord(
            id=row["id"],
            run_id=row["run_id"],
            query_text=row["query_text"],
            response_text=row["response_text"],
            backend_name=row["backend_name"],
            strategy_name=row["strategy_name"],
            domain=row["domain"],
            created_at=row["created_at"],
            rating=row["rating"],
        )

    def _row_to_fact(self, row: sqlite3.Row) -> FactRecord:
        return FactRecord(
            id=row["id"],
            fact_key=row["fact_key"],
            fact_value=row["fact_value"],
            source=row["source"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_correction(self, row: sqlite3.Row) -> CorrectionRecord:
        return CorrectionRecord(
            id=row["id"],
            source_run_id=row["source_run_id"],
            domain=row["domain"],
            severity=row["severity"],
            context=row["context"],
            wrong_answer=row["wrong_answer"],
            right_answer=row["right_answer"],
            created_at=row["created_at"],
        )
