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

CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_events_run_id ON run_events(run_id, sequence_no);
CREATE INDEX IF NOT EXISTS idx_ratings_target ON ratings(target_type, target_id);
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
            conn.execute(
                """
                UPDATE runs
                SET status = 'done', final_output = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (final_output, now, now, run_id),
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
