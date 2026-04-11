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
    summary TEXT,
    operator_note TEXT,
    git_snapshot_start_json TEXT,
    git_snapshot_end_json TEXT,
    git_change_summary_json TEXT,
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

CREATE TABLE IF NOT EXISTS postmortems (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE REFERENCES runs(id) ON DELETE CASCADE,
    domain TEXT,
    category TEXT NOT NULL,
    summary TEXT NOT NULL,
    error_message TEXT NOT NULL,
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
    error_message TEXT,
    cancel_requested_at TEXT,
    cancel_reason TEXT,
    control_state TEXT NOT NULL DEFAULT 'running',
    control_reason TEXT
);

CREATE TABLE IF NOT EXISTS shell_job_events (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES shell_jobs(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    sequence_no INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(job_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS approval_requests (
    id TEXT PRIMARY KEY,
    job_id TEXT REFERENCES shell_jobs(id) ON DELETE CASCADE,
    run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    argument TEXT NOT NULL,
    pattern TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    resolution_note TEXT
);

CREATE TABLE IF NOT EXISTS shell_job_inputs (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES shell_jobs(id) ON DELETE CASCADE,
    run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
    input_text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    consumed_at TEXT
);

CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,
    backend_name TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    working_directory TEXT NOT NULL,
    domain TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    current_step_no INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plan_steps (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL,
    title TEXT NOT NULL,
    details TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(plan_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS plan_events (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    sequence_no INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(plan_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS benchmark_runs (
    id TEXT PRIMARY KEY,
    suite_name TEXT NOT NULL,
    backend_name TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    summary_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    parent_session_id TEXT REFERENCES sessions(id),
    fork_point_run_id TEXT REFERENCES runs(id),
    title TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    summary TEXT,
    context_snapshot TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
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

CREATE VIRTUAL TABLE IF NOT EXISTS postmortem_fts USING fts5(
    source_id UNINDEXED,
    summary,
    error_message,
    domain,
    category
);

CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_events_run_id ON run_events(run_id, sequence_no);
CREATE INDEX IF NOT EXISTS idx_ratings_target ON ratings(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_interactions_created_at ON interactions(created_at);
CREATE INDEX IF NOT EXISTS idx_facts_key ON facts(fact_key, updated_at);
CREATE INDEX IF NOT EXISTS idx_corrections_domain ON corrections(domain, created_at);
CREATE INDEX IF NOT EXISTS idx_postmortems_domain ON postmortems(domain, created_at);
CREATE INDEX IF NOT EXISTS idx_embedding_jobs_source ON embedding_jobs(source_type, status, updated_at);
CREATE INDEX IF NOT EXISTS idx_interaction_embeddings_model ON interaction_embeddings(model_name, indexed_at);
CREATE INDEX IF NOT EXISTS idx_correction_embeddings_model ON correction_embeddings(model_name, indexed_at);
CREATE INDEX IF NOT EXISTS idx_shell_jobs_updated_at ON shell_jobs(updated_at);
CREATE INDEX IF NOT EXISTS idx_shell_job_events_job_id ON shell_job_events(job_id, sequence_no);
CREATE INDEX IF NOT EXISTS idx_approval_requests_status ON approval_requests(status, created_at);
CREATE INDEX IF NOT EXISTS idx_shell_job_inputs_job_id ON shell_job_inputs(job_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_plans_updated_at ON plans(updated_at);
CREATE INDEX IF NOT EXISTS idx_plan_steps_plan_id ON plan_steps(plan_id, sequence_no);
CREATE INDEX IF NOT EXISTS idx_plan_events_plan_id ON plan_events(plan_id, sequence_no);
CREATE INDEX IF NOT EXISTS idx_benchmark_runs_created_at ON benchmark_runs(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at);
"""


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat()


@dataclass(slots=True)
class RunRecord:
    id: str
    session_id: str | None
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
    summary: str | None
    operator_note: str | None
    git_snapshot_start: dict[str, Any] | None
    git_snapshot_end: dict[str, Any] | None
    git_change_summary: dict[str, Any] | None
    metadata: dict[str, Any]


@dataclass(slots=True)
class SessionRecord:
    id: str
    parent_session_id: str | None
    fork_point_run_id: str | None
    title: str | None
    status: str
    summary: str | None
    context_snapshot: str | None
    created_at: str
    updated_at: str


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
class PostmortemRecord:
    id: str
    run_id: str
    domain: str | None
    category: str
    summary: str
    error_message: str
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
    cancel_requested_at: str | None
    cancel_reason: str | None
    control_state: str
    control_reason: str | None


@dataclass(slots=True)
class ShellJobEventRecord:
    id: str
    job_id: str
    event_type: str
    sequence_no: int
    created_at: str
    payload: dict[str, Any]


@dataclass(slots=True)
class ApprovalRequestRecord:
    id: str
    job_id: str | None
    run_id: str | None
    tool_name: str
    argument: str
    pattern: str
    status: str
    created_at: str
    resolved_at: str | None
    resolution_note: str | None


@dataclass(slots=True)
class ShellJobInputRecord:
    id: str
    job_id: str
    run_id: str | None
    input_text: str
    status: str
    created_at: str
    consumed_at: str | None


@dataclass(slots=True)
class PlanRecord:
    id: str
    goal: str
    backend_name: str
    strategy_name: str
    working_directory: str
    domain: str | None
    status: str
    current_step_no: int
    created_at: str
    updated_at: str


@dataclass(slots=True)
class PlanStepRecord:
    id: str
    plan_id: str
    sequence_no: int
    title: str
    details: str | None
    status: str
    created_at: str
    updated_at: str


@dataclass(slots=True)
class PlanEventRecord:
    id: str
    plan_id: str
    event_type: str
    sequence_no: int
    created_at: str
    payload: dict[str, Any]


@dataclass(slots=True)
class BenchmarkRunRecord:
    id: str
    suite_name: str
    backend_name: str
    strategy_name: str
    created_at: str
    summary: dict[str, Any]


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
            self._ensure_column(conn, "shell_jobs", "cancel_requested_at", "TEXT")
            self._ensure_column(conn, "shell_jobs", "cancel_reason", "TEXT")
            self._ensure_column(conn, "shell_jobs", "control_state", "TEXT NOT NULL DEFAULT 'running'")
            self._ensure_column(conn, "shell_jobs", "control_reason", "TEXT")
            self._ensure_column(conn, "runs", "summary", "TEXT")
            self._ensure_column(conn, "runs", "operator_note", "TEXT")
            self._ensure_column(conn, "runs", "session_id", "TEXT REFERENCES sessions(id)")
            self._ensure_column(conn, "runs", "git_snapshot_start_json", "TEXT")
            self._ensure_column(conn, "runs", "git_snapshot_end_json", "TEXT")
            self._ensure_column(conn, "runs", "git_change_summary_json", "TEXT")

    def _ensure_column(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_def: str,
    ) -> None:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing = {row["name"] for row in rows}
        if column_name in existing:
            return
        try:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" in str(exc).lower():
                return
            raise

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

    def create_session(
        self,
        *,
        session_id: str,
        title: str | None,
        parent_session_id: str | None = None,
        fork_point_run_id: str | None = None,
        status: str = "active",
        summary: str | None = None,
        context_snapshot: str | None = None,
    ) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    id, parent_session_id, fork_point_run_id, title, status, summary, context_snapshot, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, parent_session_id, fork_point_run_id, title, status, summary, context_snapshot, now, now),
            )

    def get_session(self, session_id: str) -> SessionRecord | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    def list_sessions(self, limit: int = 20, *, status: str | None = None) -> list[SessionRecord]:
        params: list[object] = []
        where = ""
        if status:
            where = "WHERE status = ?"
            params.append(status)
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM sessions
                {where}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._row_to_session(row) for row in rows]

    def update_session(
        self,
        *,
        session_id: str,
        title: str | None = None,
        status: str | None = None,
        summary: str | None = None,
        context_snapshot: str | None = None,
    ) -> bool:
        now = utc_now()
        clauses = ["updated_at = ?"]
        params: list[object] = [now]
        if title is not None:
            clauses.append("title = ?")
            params.append(title)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if summary is not None:
            clauses.append("summary = ?")
            params.append(summary)
        if context_snapshot is not None:
            clauses.append("context_snapshot = ?")
            params.append(context_snapshot)
        params.append(session_id)
        with self.connect() as conn:
            row = conn.execute(
                f"UPDATE sessions SET {', '.join(clauses)} WHERE id = ?",
                params,
            )
        return row.rowcount > 0

    def list_session_runs(self, session_id: str, limit: int = 200) -> list[RunRecord]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM runs
                WHERE session_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [self._row_to_run(row) for row in rows]

    def create_run(
        self,
        *,
        run_id: str,
        goal: str,
        backend_name: str,
        strategy_name: str,
        working_directory: str,
        parent_run_id: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    id, parent_run_id, session_id, goal, status, backend_name, strategy_name,
                    working_directory, created_at, updated_at, metadata_json
                )
                VALUES (?, ?, ?, ?, 'running', ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    parent_run_id,
                    session_id,
                    goal,
                    backend_name,
                    strategy_name,
                    working_directory,
                    now,
                    now,
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )
            if session_id:
                conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))

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
            conn.execute("BEGIN IMMEDIATE")
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

    def append_shell_job_event(
        self,
        *,
        job_id: str,
        event_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> int:
        now = utc_now()
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT COALESCE(MAX(sequence_no), 0) + 1 AS next_no FROM shell_job_events WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            sequence_no = int(row["next_no"])
            conn.execute(
                """
                INSERT INTO shell_job_events (id, job_id, event_type, sequence_no, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    job_id,
                    event_type,
                    sequence_no,
                    now,
                    json.dumps(payload, sort_keys=True),
                ),
            )
            conn.execute(
                "UPDATE shell_jobs SET updated_at = ? WHERE id = ?",
                (now, job_id),
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

    def cancel_run(self, *, run_id: str, error_message: str | None = None) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE runs
                SET status = 'canceled', error_message = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (error_message, now, now, run_id),
            )


    def update_run_summary(self, *, run_id: str, summary: str | None) -> bool:
        now = utc_now()
        with self.connect() as conn:
            row = conn.execute(
                """
                UPDATE runs
                SET summary = ?, updated_at = ?
                WHERE id = ?
                """,
                (summary, now, run_id),
            )
        return row.rowcount > 0

    def update_run_operator_note(self, *, run_id: str, note: str | None) -> bool:
        now = utc_now()
        with self.connect() as conn:
            row = conn.execute(
                """
                UPDATE runs
                SET operator_note = ?, updated_at = ?
                WHERE id = ?
                """,
                (note, now, run_id),
            )
        return row.rowcount > 0

    def update_run_git_snapshot(self, *, run_id: str, phase: str, snapshot: dict[str, Any] | None, summary: dict[str, Any] | None = None) -> bool:
        now = utc_now()
        column = "git_snapshot_start_json" if phase == "start" else "git_snapshot_end_json"
        with self.connect() as conn:
            row = conn.execute(
                f"""
                UPDATE runs
                SET {column} = ?,
                    git_change_summary_json = COALESCE(?, git_change_summary_json),
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(snapshot, sort_keys=True) if snapshot is not None else None,
                    json.dumps(summary, sort_keys=True) if summary is not None else None,
                    now,
                    run_id,
                ),
            )
        return row.rowcount > 0

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
                    status, control_state, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'running', 'running', ?, ?)
                """,
                (job_id, goal, backend_name, strategy_name, domain, now, now),
            )
        self.append_shell_job_event(
            job_id=job_id,
            event_id=f"{job_id}-created",
            event_type="job_created",
            payload={
                "goal": goal,
                "backend": backend_name,
                "strategy": strategy_name,
                "domain": domain,
            },
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
        self.append_shell_job_event(
            job_id=job_id,
            event_id=f"{job_id}-run-{run_id}",
            event_type="run_attached",
            payload={"run_id": run_id},
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

    def request_shell_job_pause(self, *, job_id: str, reason: str | None = None) -> bool:
        now = utc_now()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT status, control_state FROM shell_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                return False
            if row["status"] in {"done", "failed", "canceled"}:
                return False
            if row["control_state"] == "paused":
                return False
            conn.execute(
                """
                UPDATE shell_jobs
                SET control_state = 'paused',
                    control_reason = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (reason, now, job_id),
            )
        self.append_shell_job_event(
            job_id=job_id,
            event_id=f"{job_id}-pause-{now}",
            event_type="pause_requested",
            payload={"reason": reason},
        )
        return True

    def request_shell_job_resume(self, *, job_id: str, reason: str | None = None) -> bool:
        now = utc_now()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT status, control_state FROM shell_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                return False
            if row["status"] in {"done", "failed", "canceled"}:
                return False
            if row["control_state"] == "running":
                return False
            conn.execute(
                """
                UPDATE shell_jobs
                SET control_state = 'running',
                    control_reason = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (reason, now, job_id),
            )
        self.append_shell_job_event(
            job_id=job_id,
            event_id=f"{job_id}-resume-{now}",
            event_type="resume_requested",
            payload={"reason": reason},
        )
        return True

    def get_shell_job_control_state(self, job_id: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT control_state FROM shell_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return str(row["control_state"])

    def request_shell_job_cancel(self, *, job_id: str, reason: str | None = None) -> bool:
        now = utc_now()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT status FROM shell_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                return False
            if row["status"] in {"done", "failed", "canceled"}:
                return False
            conn.execute(
                """
                UPDATE shell_jobs
                SET status = 'cancel_requested',
                    cancel_requested_at = COALESCE(cancel_requested_at, ?),
                    cancel_reason = COALESCE(?, cancel_reason),
                    updated_at = ?
                WHERE id = ?
                """,
                (now, reason, now, job_id),
            )
        self.append_shell_job_event(
            job_id=job_id,
            event_id=f"{job_id}-cancel-{now}",
            event_type="cancel_requested",
            payload={"reason": reason},
        )
        return True

    def is_shell_job_cancel_requested(self, job_id: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM shell_jobs
                WHERE id = ? AND status = 'cancel_requested'
                """,
                (job_id,),
            ).fetchone()
        return row is not None

    def get_shell_job(self, job_id: str) -> ShellJobRecord | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM shell_jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_shell_job(row)

    def list_shell_job_events(self, job_id: str) -> list[ShellJobEventRecord]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, job_id, event_type, sequence_no, created_at, payload_json
                FROM shell_job_events
                WHERE job_id = ?
                ORDER BY sequence_no ASC
                """,
                (job_id,),
            ).fetchall()
        return [self._row_to_shell_job_event(row) for row in rows]

    def get_shell_job_by_run_id(self, run_id: str) -> ShellJobRecord | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM shell_jobs WHERE run_id = ? ORDER BY updated_at DESC LIMIT 1",
                (run_id,),
            ).fetchone()
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

    def create_approval_request(
        self,
        *,
        request_id: str,
        job_id: str | None,
        run_id: str | None,
        tool_name: str,
        argument: str,
        pattern: str,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO approval_requests (
                    id, job_id, run_id, tool_name, argument, pattern, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (request_id, job_id, run_id, tool_name, argument, pattern, utc_now()),
            )

    def get_pending_approval_request(
        self,
        *,
        job_id: str,
        run_id: str,
        tool_name: str,
        argument: str,
    ) -> ApprovalRequestRecord | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM approval_requests
                WHERE job_id = ? AND run_id = ? AND tool_name = ? AND argument = ? AND status = 'pending'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (job_id, run_id, tool_name, argument),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_approval_request(row)

    def list_approval_requests(self, *, status: str | None = None, limit: int = 50) -> list[ApprovalRequestRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM approval_requests
                {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._row_to_approval_request(row) for row in rows]

    def get_approval_request(self, request_id: str) -> ApprovalRequestRecord | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM approval_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_approval_request(row)

    def resolve_approval_request(
        self,
        *,
        request_id: str,
        status: str,
        resolution_note: str | None = None,
    ) -> bool:
        if status not in {"approved", "denied"}:
            raise ValueError("approval status must be 'approved' or 'denied'")
        now = utc_now()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE approval_requests
                SET status = ?, resolved_at = ?, resolution_note = ?
                WHERE id = ? AND status = 'pending'
                """,
                (status, now, resolution_note, request_id),
            )
        return cursor.rowcount > 0

    def enqueue_shell_job_input(
        self,
        *,
        input_id: str,
        job_id: str,
        run_id: str | None,
        input_text: str,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO shell_job_inputs (id, job_id, run_id, input_text, status, created_at)
                VALUES (?, ?, ?, ?, 'pending', ?)
                """,
                (input_id, job_id, run_id, input_text, utc_now()),
            )

    def consume_pending_shell_job_inputs(self, *, job_id: str) -> list[ShellJobInputRecord]:
        now = utc_now()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM shell_job_inputs
                WHERE job_id = ? AND status = 'pending'
                ORDER BY created_at ASC
                """,
                (job_id,),
            ).fetchall()
            if not rows:
                return []
            conn.execute(
                """
                UPDATE shell_job_inputs
                SET status = 'consumed',
                    consumed_at = ?
                WHERE job_id = ? AND status = 'pending'
                """,
                (now, job_id),
            )
        return [
            ShellJobInputRecord(
                id=row["id"],
                job_id=row["job_id"],
                run_id=row["run_id"],
                input_text=row["input_text"],
                status="consumed",
                created_at=row["created_at"],
                consumed_at=now,
            )
            for row in rows
        ]

    def list_shell_job_inputs(
        self,
        *,
        job_id: str,
        status: str | None = None,
        limit: int = 50,
    ) -> list[ShellJobInputRecord]:
        clauses = ["job_id = ?"]
        params: list[Any] = [job_id]
        if status:
            clauses.append("status = ?")
            params.append(status)
        params.append(limit)
        where = f"WHERE {' AND '.join(clauses)}"
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM shell_job_inputs
                {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._row_to_shell_job_input(row) for row in rows]

    def create_plan(
        self,
        *,
        plan_id: str,
        goal: str,
        backend_name: str,
        strategy_name: str,
        working_directory: str,
        domain: str | None,
        steps: list[tuple[str, str | None]],
    ) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO plans (
                    id, goal, backend_name, strategy_name, working_directory,
                    domain, status, current_step_no, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'draft', 1, ?, ?)
                """,
                (plan_id, goal, backend_name, strategy_name, working_directory, domain, now, now),
            )
            for sequence_no, (title, details) in enumerate(steps, start=1):
                conn.execute(
                    """
                    INSERT INTO plan_steps (
                        id, plan_id, sequence_no, title, details, status, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (f"{plan_id}:{sequence_no}", plan_id, sequence_no, title, details, now, now),
                )

    def list_plans(self, limit: int = 20) -> list[PlanRecord]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM plans
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_plan(row) for row in rows]

    def get_plan(self, plan_id: str) -> PlanRecord | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_plan(row)

    def list_plan_steps(self, plan_id: str) -> list[PlanStepRecord]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM plan_steps
                WHERE plan_id = ?
                ORDER BY sequence_no ASC
                """,
                (plan_id,),
            ).fetchall()
        return [self._row_to_plan_step(row) for row in rows]

    def append_plan_event(
        self,
        *,
        plan_id: str,
        event_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> int:
        now = utc_now()
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT COALESCE(MAX(sequence_no), 0) + 1 AS next_no FROM plan_events WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()
            sequence_no = int(row["next_no"])
            conn.execute(
                """
                INSERT INTO plan_events (id, plan_id, event_type, sequence_no, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    plan_id,
                    event_type,
                    sequence_no,
                    now,
                    json.dumps(payload, sort_keys=True),
                ),
            )
            conn.execute(
                "UPDATE plans SET updated_at = ? WHERE id = ?",
                (now, plan_id),
            )
        return sequence_no

    def list_plan_events(self, plan_id: str) -> list[PlanEventRecord]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, plan_id, event_type, sequence_no, created_at, payload_json
                FROM plan_events
                WHERE plan_id = ?
                ORDER BY sequence_no ASC
                """,
                (plan_id,),
            ).fetchall()
        return [self._row_to_plan_event(row) for row in rows]

    def get_current_plan_step(self, plan_id: str) -> PlanStepRecord | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT ps.*
                FROM plan_steps ps
                JOIN plans p ON p.id = ps.plan_id
                WHERE p.id = ? AND ps.sequence_no = p.current_step_no
                """,
                (plan_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_plan_step(row)

    def update_plan_status(self, *, plan_id: str, status: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE plans
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, utc_now(), plan_id),
            )

    def update_plan_step_status(self, *, plan_id: str, sequence_no: int, status: str) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE plan_steps
                SET status = ?, updated_at = ?
                WHERE plan_id = ? AND sequence_no = ?
                """,
                (status, now, plan_id, sequence_no),
            )
            conn.execute(
                "UPDATE plans SET updated_at = ? WHERE id = ?",
                (now, plan_id),
            )

    def insert_plan_step(
        self,
        *,
        plan_id: str,
        after_sequence_no: int,
        title: str,
        details: str | None,
    ) -> int:
        now = utc_now()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, sequence_no
                FROM plan_steps
                WHERE plan_id = ? AND sequence_no > ?
                ORDER BY sequence_no DESC
                """,
                (plan_id, after_sequence_no),
            ).fetchall()
            for row in rows:
                conn.execute(
                    """
                    UPDATE plan_steps
                    SET sequence_no = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (int(row["sequence_no"]) + 1, now, row["id"]),
                )
            new_sequence_no = after_sequence_no + 1
            conn.execute(
                """
                INSERT INTO plan_steps (
                    id, plan_id, sequence_no, title, details, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (f"{plan_id}:{new_sequence_no}:{now}", plan_id, new_sequence_no, title, details, now, now),
            )
            conn.execute("UPDATE plans SET updated_at = ? WHERE id = ?", (now, plan_id))
        return new_sequence_no

    def update_plan_step(
        self,
        *,
        plan_id: str,
        sequence_no: int,
        title: str,
        details: str | None,
    ) -> bool:
        now = utc_now()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE plan_steps
                SET title = ?, details = ?, updated_at = ?
                WHERE plan_id = ? AND sequence_no = ?
                """,
                (title, details, now, plan_id, sequence_no),
            )
            conn.execute("UPDATE plans SET updated_at = ? WHERE id = ?", (now, plan_id))
        return cursor.rowcount > 0

    def delete_plan_step(self, *, plan_id: str, sequence_no: int) -> bool:
        now = utc_now()
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT 1 FROM plan_steps WHERE plan_id = ? AND sequence_no = ?",
                (plan_id, sequence_no),
            ).fetchone()
            if existing is None:
                return False
            conn.execute(
                "DELETE FROM plan_steps WHERE plan_id = ? AND sequence_no = ?",
                (plan_id, sequence_no),
            )
            rows = conn.execute(
                """
                SELECT id, sequence_no
                FROM plan_steps
                WHERE plan_id = ? AND sequence_no > ?
                ORDER BY sequence_no ASC
                """,
                (plan_id, sequence_no),
            ).fetchall()
            for row in rows:
                conn.execute(
                    """
                    UPDATE plan_steps
                    SET sequence_no = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (int(row["sequence_no"]) - 1, now, row["id"]),
                )
            plan = conn.execute("SELECT current_step_no FROM plans WHERE id = ?", (plan_id,)).fetchone()
            current_step_no = int(plan["current_step_no"]) if plan is not None else 1
            new_current = current_step_no
            if current_step_no > sequence_no:
                new_current = current_step_no - 1
            elif current_step_no == sequence_no:
                replacement = conn.execute(
                    "SELECT MIN(sequence_no) AS seq FROM plan_steps WHERE plan_id = ? AND sequence_no >= ?",
                    (plan_id, sequence_no),
                ).fetchone()
                if replacement and replacement["seq"] is not None:
                    new_current = int(replacement["seq"])
                else:
                    replacement = conn.execute(
                        "SELECT MAX(sequence_no) AS seq FROM plan_steps WHERE plan_id = ?",
                        (plan_id,),
                    ).fetchone()
                    new_current = int(replacement["seq"]) if replacement and replacement["seq"] is not None else 1
            conn.execute(
                "UPDATE plans SET current_step_no = ?, updated_at = ? WHERE id = ?",
                (new_current, now, plan_id),
            )
        return True

    def replace_plan_steps_from(
        self,
        *,
        plan_id: str,
        start_sequence_no: int,
        steps: list[tuple[str, str | None]],
    ) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                DELETE FROM plan_steps
                WHERE plan_id = ? AND sequence_no >= ?
                """,
                (plan_id, start_sequence_no),
            )
            for offset, (title, details) in enumerate(steps, start=0):
                sequence_no = start_sequence_no + offset
                conn.execute(
                    """
                    INSERT INTO plan_steps (
                        id, plan_id, sequence_no, title, details, status, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (f"{plan_id}:{sequence_no}", plan_id, sequence_no, title, details, now, now),
                )
            conn.execute(
                """
                UPDATE plans
                SET current_step_no = ?, status = 'draft', updated_at = ?
                WHERE id = ?
                """,
                (start_sequence_no, now, plan_id),
            )

    def advance_plan(self, plan_id: str) -> int | None:
        now = utc_now()
        with self.connect() as conn:
            plan = conn.execute(
                "SELECT current_step_no FROM plans WHERE id = ?",
                (plan_id,),
            ).fetchone()
            if plan is None:
                return None
            current_step_no = int(plan["current_step_no"])
            next_step = conn.execute(
                """
                SELECT sequence_no
                FROM plan_steps
                WHERE plan_id = ? AND sequence_no > ?
                ORDER BY sequence_no ASC
                LIMIT 1
                """,
                (plan_id, current_step_no),
            ).fetchone()
            if next_step is None:
                conn.execute(
                    """
                    UPDATE plans
                    SET status = 'done', updated_at = ?
                    WHERE id = ?
                    """,
                    (now, plan_id),
                )
                return None
            next_no = int(next_step["sequence_no"])
            conn.execute(
                """
                UPDATE plans
                SET current_step_no = ?, status = 'in_progress', updated_at = ?
                WHERE id = ?
                """,
                (next_no, now, plan_id),
            )
        return next_no

    def add_benchmark_run(
        self,
        *,
        benchmark_run_id: str,
        suite_name: str,
        backend_name: str,
        strategy_name: str,
        summary: dict[str, Any],
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO benchmark_runs (
                    id, suite_name, backend_name, strategy_name, created_at, summary_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    benchmark_run_id,
                    suite_name,
                    backend_name,
                    strategy_name,
                    utc_now(),
                    json.dumps(summary, sort_keys=True),
                ),
            )

    def list_benchmark_runs(self, limit: int = 20) -> list[BenchmarkRunRecord]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM benchmark_runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_benchmark_run(row) for row in rows]

    def get_benchmark_run(self, benchmark_run_id: str) -> BenchmarkRunRecord | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM benchmark_runs WHERE id = ?",
                (benchmark_run_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_benchmark_run(row)

    def find_previous_benchmark_run(
        self,
        *,
        suite_name: str,
        backend_name: str,
        strategy_name: str,
        created_before: str,
    ) -> BenchmarkRunRecord | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM benchmark_runs
                WHERE suite_name = ? AND backend_name = ? AND strategy_name = ? AND created_at < ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (suite_name, backend_name, strategy_name, created_before),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_benchmark_run(row)

    def list_runs(
        self,
        limit: int = 20,
        *,
        query: str | None = None,
        backend_name: str | None = None,
        status: str | None = None,
        session_id: str | None = None,
    ) -> list[RunRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if query:
            clauses.append("(goal LIKE ? OR COALESCE(final_output, '') LIKE ? OR COALESCE(error_message, '') LIKE ?)")
            like = f"%{query}%"
            params.extend([like, like, like])
        if backend_name:
            clauses.append("backend_name = ?")
            params.append(backend_name)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM runs
                {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [self._row_to_run(row) for row in rows]

    def list_child_runs(self, parent_run_id: str, limit: int = 50) -> list[RunRecord]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM runs
                WHERE parent_run_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (parent_run_id, limit),
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

    def add_postmortem(
        self,
        *,
        postmortem_id: str,
        run_id: str,
        summary: str,
        error_message: str,
        category: str,
        domain: str | None = None,
    ) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO postmortems (
                    id, run_id, domain, category, summary, error_message, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (postmortem_id, run_id, domain, category, summary, error_message, now),
            )
            conn.execute("DELETE FROM postmortem_fts WHERE source_id = ?", (run_id,))
            conn.execute(
                """
                INSERT INTO postmortem_fts (source_id, summary, error_message, domain, category)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, summary, error_message, domain, category),
            )

    def list_postmortems(
        self,
        limit: int = 50,
        domain: str | None = None,
        query: str | None = None,
    ) -> list[PostmortemRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if domain:
            clauses.append("domain = ?")
            params.append(domain)
        if query:
            clauses.append("(summary LIKE ? OR error_message LIKE ? OR category LIKE ?)")
            needle = f"%{query}%"
            params.extend([needle, needle, needle])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM postmortems
                {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._row_to_postmortem(row) for row in rows]

    def search_postmortems(
        self,
        *,
        query: str,
        limit: int = 10,
        domain: str | None = None,
    ) -> list[SearchHit]:
        match_query = fts_match_query(query)
        params: list[Any] = [match_query]
        domain_clause = ""
        order_prefix = ""
        if domain:
            domain_clause = "AND (p.domain = ? OR p.domain IS NULL)"
            order_prefix = "CASE WHEN p.domain = ? THEN 0 WHEN p.domain IS NULL THEN 1 ELSE 2 END, "
            params.extend([domain, domain])
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    p.id,
                    p.summary,
                    substr(p.error_message, 1, 240) AS snippet,
                    p.domain,
                    bm25(postmortem_fts) AS score
                FROM postmortem_fts
                JOIN postmortems p ON p.run_id = postmortem_fts.source_id
                WHERE postmortem_fts MATCH ?
                {domain_clause}
                ORDER BY {order_prefix} score
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [
            SearchHit(
                source_type="postmortem",
                source_id=row["id"],
                title=row["summary"],
                snippet=row["snippet"],
                domain=row["domain"],
                score=float(row["score"]),
            )
            for row in rows
        ]

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

    def _row_to_session(self, row: sqlite3.Row) -> SessionRecord:
        return SessionRecord(
            id=row["id"],
            parent_session_id=row["parent_session_id"],
            fork_point_run_id=row["fork_point_run_id"],
            title=row["title"],
            status=row["status"],
            summary=row["summary"],
            context_snapshot=row["context_snapshot"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_run(self, row: sqlite3.Row) -> RunRecord:
        return RunRecord(
            id=row["id"],
            session_id=row["session_id"],
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
            summary=row["summary"],
            operator_note=row["operator_note"],
            git_snapshot_start=json.loads(row["git_snapshot_start_json"]) if row["git_snapshot_start_json"] else None,
            git_snapshot_end=json.loads(row["git_snapshot_end_json"]) if row["git_snapshot_end_json"] else None,
            git_change_summary=json.loads(row["git_change_summary_json"]) if row["git_change_summary_json"] else None,
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

    def _row_to_postmortem(self, row: sqlite3.Row) -> PostmortemRecord:
        return PostmortemRecord(
            id=row["id"],
            run_id=row["run_id"],
            domain=row["domain"],
            category=row["category"],
            summary=row["summary"],
            error_message=row["error_message"],
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
            cancel_requested_at=row["cancel_requested_at"],
            cancel_reason=row["cancel_reason"],
            control_state=row["control_state"],
            control_reason=row["control_reason"],
        )

    def _row_to_shell_job_event(self, row: sqlite3.Row) -> ShellJobEventRecord:
        return ShellJobEventRecord(
            id=row["id"],
            job_id=row["job_id"],
            event_type=row["event_type"],
            sequence_no=row["sequence_no"],
            created_at=row["created_at"],
            payload=json.loads(row["payload_json"]),
        )

    def _row_to_approval_request(self, row: sqlite3.Row) -> ApprovalRequestRecord:
        return ApprovalRequestRecord(
            id=row["id"],
            job_id=row["job_id"],
            run_id=row["run_id"],
            tool_name=row["tool_name"],
            argument=row["argument"],
            pattern=row["pattern"],
            status=row["status"],
            created_at=row["created_at"],
            resolved_at=row["resolved_at"],
            resolution_note=row["resolution_note"],
        )

    def _row_to_shell_job_input(self, row: sqlite3.Row) -> ShellJobInputRecord:
        return ShellJobInputRecord(
            id=row["id"],
            job_id=row["job_id"],
            run_id=row["run_id"],
            input_text=row["input_text"],
            status=row["status"],
            created_at=row["created_at"],
            consumed_at=row["consumed_at"],
        )

    def _row_to_plan(self, row: sqlite3.Row) -> PlanRecord:
        return PlanRecord(
            id=row["id"],
            goal=row["goal"],
            backend_name=row["backend_name"],
            strategy_name=row["strategy_name"],
            working_directory=row["working_directory"],
            domain=row["domain"],
            status=row["status"],
            current_step_no=int(row["current_step_no"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_plan_step(self, row: sqlite3.Row) -> PlanStepRecord:
        return PlanStepRecord(
            id=row["id"],
            plan_id=row["plan_id"],
            sequence_no=int(row["sequence_no"]),
            title=row["title"],
            details=row["details"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_plan_event(self, row: sqlite3.Row) -> PlanEventRecord:
        return PlanEventRecord(
            id=row["id"],
            plan_id=row["plan_id"],
            event_type=row["event_type"],
            sequence_no=int(row["sequence_no"]),
            created_at=row["created_at"],
            payload=json.loads(row["payload_json"]),
        )

    def _row_to_benchmark_run(self, row: sqlite3.Row) -> BenchmarkRunRecord:
        return BenchmarkRunRecord(
            id=row["id"],
            suite_name=row["suite_name"],
            backend_name=row["backend_name"],
            strategy_name=row["strategy_name"],
            created_at=row["created_at"],
            summary=json.loads(row["summary_json"]),
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
