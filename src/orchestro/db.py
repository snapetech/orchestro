from __future__ import annotations

import hashlib
import importlib
import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_EMBED_MODEL = "debug-hash-256"

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

CREATE TABLE IF NOT EXISTS embedding_jobs (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    model_name TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    indexed_at TEXT,
    error_message TEXT,
    UNIQUE(source_type, source_id, model_name)
);

CREATE TABLE IF NOT EXISTS shell_jobs (
    id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
    goal TEXT NOT NULL,
    backend_name TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    domain TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS interaction_embeddings (
    source_id TEXT PRIMARY KEY REFERENCES interactions(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    embedding BLOB NOT NULL,
    indexed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS correction_embeddings (
    source_id TEXT PRIMARY KEY REFERENCES corrections(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    embedding BLOB NOT NULL,
    indexed_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS interaction_fts USING fts5(
    source_id UNINDEXED,
    query_text,
    response_text,
    domain
);

CREATE VIRTUAL TABLE IF NOT EXISTS correction_fts USING fts5(
    source_id UNINDEXED,
    context,
    wrong_answer,
    right_answer,
    domain
);

CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_events_run_id ON run_events(run_id, sequence_no);
CREATE INDEX IF NOT EXISTS idx_ratings_target ON ratings(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_interactions_created_at ON interactions(created_at);
CREATE INDEX IF NOT EXISTS idx_facts_key ON facts(fact_key, updated_at);
CREATE INDEX IF NOT EXISTS idx_corrections_domain ON corrections(domain, created_at);
CREATE INDEX IF NOT EXISTS idx_embedding_jobs_source ON embedding_jobs(source_type, status, updated_at);
CREATE INDEX IF NOT EXISTS idx_interaction_embeddings_model ON interaction_embeddings(model_name, indexed_at);
CREATE INDEX IF NOT EXISTS idx_correction_embeddings_model ON correction_embeddings(model_name, indexed_at);
CREATE INDEX IF NOT EXISTS idx_shell_jobs_updated_at ON shell_jobs(updated_at);
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


@dataclass(slots=True)
class EmbeddingJobRecord:
    id: str
    source_type: str
    source_id: str
    model_name: str
    content_hash: str
    status: str
    created_at: str
    updated_at: str
    indexed_at: str | None
    error_message: str | None


@dataclass(slots=True)
class SearchHit:
    source_type: str
    source_id: str
    title: str
    snippet: str
    domain: str | None
    score: float


@dataclass(slots=True)
class ShellJobRecord:
    id: str
    run_id: str | None
    goal: str
    backend_name: str
    strategy_name: str
    domain: str | None
    status: str
    created_at: str
    updated_at: str
    error_message: str | None


def content_hash(*parts: str | None) -> str:
    joined = "\n".join(part or "" for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def fts_match_query(text: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9_]+", text.lower())
    if not tokens:
        return '""'
    return " OR ".join(f'"{token}"' for token in tokens)


class OrchestroDB:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._sqlite_vec = self._import_sqlite_vec()
        self._initialize()

    @contextmanager
    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        self._load_optional_extensions(conn)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def _import_sqlite_vec(self) -> Any | None:
        try:
            return importlib.import_module("sqlite_vec")
        except ModuleNotFoundError:
            return None

    def _load_optional_extensions(self, conn: sqlite3.Connection) -> None:
        if self._sqlite_vec is None:
            return
        enable = getattr(conn, "enable_load_extension", None)
        if enable is None:
            return
        enable(True)
        try:
            self._sqlite_vec.load(conn)
        finally:
            enable(False)

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
            conn.execute("DELETE FROM interaction_fts WHERE source_id = ?", (run_id,))
            conn.execute(
                """
                INSERT INTO interaction_fts (source_id, query_text, response_text, domain)
                VALUES (?, ?, ?, ?)
                """,
                (
                    run_id,
                    run["goal"],
                    final_output,
                    metadata.get("domain"),
                ),
            )
            self._upsert_embedding_job(
                conn,
                source_type="interaction",
                source_id=run_id,
                model_name=DEFAULT_EMBED_MODEL,
                new_content_hash=content_hash(run["goal"], final_output, metadata.get("domain")),
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

    def create_shell_job(
        self,
        *,
        job_id: str,
        goal: str,
        backend_name: str,
        strategy_name: str,
        domain: str | None,
    ) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO shell_jobs (
                    id, goal, backend_name, strategy_name, domain,
                    status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'running', ?, ?)
                """,
                (job_id, goal, backend_name, strategy_name, domain, now, now),
            )

    def attach_shell_job_run(self, *, job_id: str, run_id: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE shell_jobs
                SET run_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (run_id, utc_now(), job_id),
            )

    def update_shell_job(
        self,
        *,
        job_id: str,
        status: str,
        error_message: str | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE shell_jobs
                SET status = ?, error_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, error_message, utc_now(), job_id),
            )

    def get_shell_job(self, job_id: str) -> ShellJobRecord | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM shell_jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_shell_job(row)

    def list_shell_jobs(self, limit: int = 20) -> list[ShellJobRecord]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM shell_jobs
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_shell_job(row) for row in rows]

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
            conn.execute("DELETE FROM correction_fts WHERE source_id = ?", (correction_id,))
            conn.execute(
                """
                INSERT INTO correction_fts (source_id, context, wrong_answer, right_answer, domain)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    correction_id,
                    context,
                    wrong_answer,
                    right_answer,
                    domain,
                ),
            )
            self._upsert_embedding_job(
                conn,
                source_type="correction",
                source_id=correction_id,
                model_name=DEFAULT_EMBED_MODEL,
                new_content_hash=content_hash(context, wrong_answer, right_answer, domain, severity),
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

    def list_embedding_jobs(
        self,
        limit: int = 50,
        source_type: str | None = None,
        status: str | None = None,
    ) -> list[EmbeddingJobRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if source_type:
            clauses.append("source_type = ?")
            params.append(source_type)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM embedding_jobs
                {where}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._row_to_embedding_job(row) for row in rows]

    def search(
        self,
        *,
        query: str,
        kind: str = "all",
        limit: int = 10,
        domain: str | None = None,
    ) -> list[SearchHit]:
        hits: list[SearchHit] = []
        match_query = fts_match_query(query)
        with self.connect() as conn:
            if kind in {"all", "interactions"}:
                params: list[Any] = [match_query]
                domain_clause = ""
                order_prefix = ""
                if domain:
                    domain_clause = "AND (i.domain = ? OR i.domain IS NULL)"
                    order_prefix = "CASE WHEN i.domain = ? THEN 0 WHEN i.domain IS NULL THEN 1 ELSE 2 END, "
                    params.extend([domain, domain])
                params.append(limit)
                rows = conn.execute(
                    f"""
                    SELECT
                        i.id,
                        i.query_text,
                        substr(i.response_text, 1, 240) AS snippet,
                        i.domain,
                        bm25(interaction_fts) AS score
                    FROM interaction_fts
                    JOIN interactions i ON i.id = interaction_fts.source_id
                    WHERE interaction_fts MATCH ?
                    {domain_clause}
                    ORDER BY {order_prefix} score
                    LIMIT ?
                    """,
                    params,
                ).fetchall()
                for row in rows:
                    hits.append(
                        SearchHit(
                            source_type="interaction",
                            source_id=row["id"],
                            title=row["query_text"],
                            snippet=row["snippet"],
                            domain=row["domain"],
                            score=float(row["score"]),
                        )
                    )
            if kind in {"all", "corrections"}:
                params = [match_query]
                domain_clause = ""
                order_prefix = ""
                if domain:
                    domain_clause = "AND (c.domain = ? OR c.domain IS NULL)"
                    order_prefix = "CASE WHEN c.domain = ? THEN 0 WHEN c.domain IS NULL THEN 1 ELSE 2 END, "
                    params.extend([domain, domain])
                params.append(limit)
                rows = conn.execute(
                    f"""
                    SELECT
                        c.id,
                        c.context,
                        substr(c.right_answer, 1, 240) AS snippet,
                        c.domain,
                        bm25(correction_fts) AS score
                    FROM correction_fts
                    JOIN corrections c ON c.id = correction_fts.source_id
                    WHERE correction_fts MATCH ?
                    {domain_clause}
                    ORDER BY {order_prefix} score
                    LIMIT ?
                    """,
                    params,
                ).fetchall()
                for row in rows:
                    hits.append(
                        SearchHit(
                            source_type="correction",
                            source_id=row["id"],
                            title=row["context"],
                            snippet=row["snippet"],
                            domain=row["domain"],
                            score=float(row["score"]),
                        )
                    )
        return sorted(hits, key=lambda hit: hit.score)[:limit]

    def vector_status(self) -> dict[str, Any]:
        status: dict[str, Any] = {
            "sqlite_version": sqlite3.sqlite_version,
            "sqlite_vec_python_installed": self._sqlite_vec is not None,
            "vec_version": None,
            "enabled": False,
        }
        try:
            with self.connect() as conn:
                row = conn.execute("SELECT vec_version() AS version").fetchone()
        except Exception as exc:
            status["error"] = str(exc)
            return status
        status["enabled"] = True
        status["vec_version"] = row["version"]
        return status

    def get_pending_embedding_jobs(
        self,
        *,
        limit: int = 50,
        source_type: str | None = None,
        model_name: str | None = None,
    ) -> list[EmbeddingJobRecord]:
        clauses = ["status = 'pending'"]
        params: list[Any] = []
        if source_type:
            clauses.append("source_type = ?")
            params.append(source_type)
        if model_name:
            clauses.append("model_name = ?")
            params.append(model_name)
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM embedding_jobs
                WHERE {' AND '.join(clauses)}
                ORDER BY updated_at ASC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._row_to_embedding_job(row) for row in rows]

    def mark_embedding_job_status(
        self,
        *,
        source_type: str,
        source_id: str,
        model_name: str,
        status: str,
        error_message: str | None = None,
    ) -> None:
        now = utc_now()
        indexed_at = now if status == "indexed" else None
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE embedding_jobs
                SET status = ?, updated_at = ?, indexed_at = COALESCE(?, indexed_at), error_message = ?
                WHERE source_type = ? AND source_id = ? AND model_name = ?
                """,
                (status, now, indexed_at, error_message, source_type, source_id, model_name),
            )

    def get_embedding_source_text(self, *, source_type: str, source_id: str) -> str:
        with self.connect() as conn:
            if source_type == "interaction":
                row = conn.execute(
                    """
                    SELECT query_text, response_text, domain
                    FROM interactions
                    WHERE id = ?
                    """,
                    (source_id,),
                ).fetchone()
                if row is None:
                    raise ValueError(f"interaction source not found: {source_id}")
                return "\n".join(
                    part for part in [row["domain"], row["query_text"], row["response_text"]] if part
                )
            if source_type == "correction":
                row = conn.execute(
                    """
                    SELECT domain, severity, context, wrong_answer, right_answer
                    FROM corrections
                    WHERE id = ?
                    """,
                    (source_id,),
                ).fetchone()
                if row is None:
                    raise ValueError(f"correction source not found: {source_id}")
                return "\n".join(
                    part
                    for part in [
                        row["domain"],
                        row["severity"],
                        row["context"],
                        row["wrong_answer"],
                        row["right_answer"],
                    ]
                    if part
                )
        raise ValueError(f"unsupported source type: {source_type}")

    def upsert_embedding_vector(
        self,
        *,
        source_type: str,
        source_id: str,
        model_name: str,
        dimensions: int,
        embedding_blob: bytes,
    ) -> None:
        table = self._embedding_table_for(source_type)
        with self.connect() as conn:
            conn.execute(
                f"""
                INSERT INTO {table} (source_id, model_name, dimensions, embedding, indexed_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    model_name = excluded.model_name,
                    dimensions = excluded.dimensions,
                    embedding = excluded.embedding,
                    indexed_at = excluded.indexed_at
                """,
                (source_id, model_name, dimensions, embedding_blob, utc_now()),
            )

    def semantic_search(
        self,
        *,
        query_embedding: bytes,
        model_name: str,
        kind: str = "all",
        limit: int = 10,
        domain: str | None = None,
    ) -> list[SearchHit]:
        status = self.vector_status()
        if not status["enabled"]:
            raise RuntimeError("sqlite-vec is not enabled in the current Python environment")
        hits: list[SearchHit] = []
        with self.connect() as conn:
            if kind in {"all", "interactions"}:
                params: list[Any] = [query_embedding, model_name]
                domain_clause = ""
                order_prefix = ""
                if domain:
                    domain_clause = "AND (i.domain = ? OR i.domain IS NULL)"
                    order_prefix = "CASE WHEN i.domain = ? THEN 0 WHEN i.domain IS NULL THEN 1 ELSE 2 END, "
                    params.extend([domain, domain])
                params.append(limit)
                rows = conn.execute(
                    f"""
                    SELECT
                        i.id,
                        i.query_text,
                        substr(i.response_text, 1, 240) AS snippet,
                        i.domain,
                        vec_distance_cosine(ie.embedding, ?) AS distance
                    FROM interaction_embeddings ie
                    JOIN interactions i ON i.id = ie.source_id
                    WHERE ie.model_name = ?
                    {domain_clause}
                    ORDER BY {order_prefix} distance ASC
                    LIMIT ?
                    """,
                    params,
                ).fetchall()
                for row in rows:
                    hits.append(
                        SearchHit(
                            source_type="interaction",
                            source_id=row["id"],
                            title=row["query_text"],
                            snippet=row["snippet"],
                            domain=row["domain"],
                            score=float(row["distance"]),
                        )
                    )
            if kind in {"all", "corrections"}:
                params = [query_embedding, model_name]
                domain_clause = ""
                order_prefix = ""
                if domain:
                    domain_clause = "AND (c.domain = ? OR c.domain IS NULL)"
                    order_prefix = "CASE WHEN c.domain = ? THEN 0 WHEN c.domain IS NULL THEN 1 ELSE 2 END, "
                    params.extend([domain, domain])
                params.append(limit)
                rows = conn.execute(
                    f"""
                    SELECT
                        c.id,
                        c.context,
                        substr(c.right_answer, 1, 240) AS snippet,
                        c.domain,
                        vec_distance_cosine(ce.embedding, ?) AS distance
                    FROM correction_embeddings ce
                    JOIN corrections c ON c.id = ce.source_id
                    WHERE ce.model_name = ?
                    {domain_clause}
                    ORDER BY {order_prefix} distance ASC
                    LIMIT ?
                    """,
                    params,
                ).fetchall()
                for row in rows:
                    hits.append(
                        SearchHit(
                            source_type="correction",
                            source_id=row["id"],
                            title=row["context"],
                            snippet=row["snippet"],
                            domain=row["domain"],
                            score=float(row["distance"]),
                        )
                    )
        return sorted(hits, key=lambda hit: hit.score)[:limit]

    def queue_embedding_jobs_for_model(
        self,
        *,
        model_name: str,
        source_type: str | None = None,
    ) -> int:
        queued = 0
        with self.connect() as conn:
            if source_type in {None, "interaction"}:
                rows = conn.execute(
                    """
                    SELECT id, query_text, response_text, domain
                    FROM interactions
                    """
                ).fetchall()
                for row in rows:
                    self._upsert_embedding_job(
                        conn,
                        source_type="interaction",
                        source_id=row["id"],
                        model_name=model_name,
                        new_content_hash=content_hash(
                            row["query_text"],
                            row["response_text"],
                            row["domain"],
                        ),
                    )
                    queued += 1
            if source_type in {None, "correction"}:
                rows = conn.execute(
                    """
                    SELECT id, domain, severity, context, wrong_answer, right_answer
                    FROM corrections
                    """
                ).fetchall()
                for row in rows:
                    self._upsert_embedding_job(
                        conn,
                        source_type="correction",
                        source_id=row["id"],
                        model_name=model_name,
                        new_content_hash=content_hash(
                            row["context"],
                            row["wrong_answer"],
                            row["right_answer"],
                            row["domain"],
                            row["severity"],
                        ),
                    )
                    queued += 1
        return queued

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

    def _row_to_embedding_job(self, row: sqlite3.Row) -> EmbeddingJobRecord:
        return EmbeddingJobRecord(
            id=row["id"],
            source_type=row["source_type"],
            source_id=row["source_id"],
            model_name=row["model_name"],
            content_hash=row["content_hash"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            indexed_at=row["indexed_at"],
            error_message=row["error_message"],
        )

    def _row_to_shell_job(self, row: sqlite3.Row) -> ShellJobRecord:
        return ShellJobRecord(
            id=row["id"],
            run_id=row["run_id"],
            goal=row["goal"],
            backend_name=row["backend_name"],
            strategy_name=row["strategy_name"],
            domain=row["domain"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            error_message=row["error_message"],
        )

    def _upsert_embedding_job(
        self,
        conn: sqlite3.Connection,
        *,
        source_type: str,
        source_id: str,
        model_name: str,
        new_content_hash: str,
    ) -> None:
        now = utc_now()
        row = conn.execute(
            """
            SELECT id, content_hash
            FROM embedding_jobs
            WHERE source_type = ? AND source_id = ? AND model_name = ?
            """,
            (source_type, source_id, model_name),
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO embedding_jobs (
                    id, source_type, source_id, model_name, content_hash,
                    status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    f"{source_type}:{source_id}:{model_name}",
                    source_type,
                    source_id,
                    model_name,
                    new_content_hash,
                    now,
                    now,
                ),
            )
            return
        if row["content_hash"] != new_content_hash:
            conn.execute(
                """
                UPDATE embedding_jobs
                SET content_hash = ?, status = 'pending', updated_at = ?, indexed_at = NULL, error_message = NULL
                WHERE id = ?
                """,
                (new_content_hash, now, row["id"]),
            )

    def _embedding_table_for(self, source_type: str) -> str:
        if source_type == "interaction":
            return "interaction_embeddings"
        if source_type == "correction":
            return "correction_embeddings"
        raise ValueError(f"unsupported source type: {source_type}")
