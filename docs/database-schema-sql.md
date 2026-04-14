# Database Schema SQL

This is the current raw schema reference from [`src/orchestro/db.py`](../src/orchestro/db.py).

```sql
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
    failure_category TEXT,
    recovery_attempts INTEGER NOT NULL DEFAULT 0,
    summary TEXT,
    operator_note TEXT,
    git_snapshot_start_json TEXT,
    git_snapshot_end_json TEXT,
    git_change_summary_json TEXT,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    quality_level TEXT DEFAULT 'unverified',
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

CREATE TABLE IF NOT EXISTS scheduled_tasks (
    task_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    schedule TEXT NOT NULL,
    goal TEXT NOT NULL,
    backend TEXT,
    strategy TEXT NOT NULL DEFAULT 'direct',
    domain TEXT,
    autonomous INTEGER NOT NULL DEFAULT 1,
    max_wall_time INTEGER NOT NULL DEFAULT 1800,
    enabled INTEGER NOT NULL DEFAULT 1,
    run_count INTEGER NOT NULL DEFAULT 0,
    last_run_at TEXT,
    last_run_status TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_enabled ON scheduled_tasks(enabled);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    parent_run_id TEXT REFERENCES runs(id),
    objective TEXT NOT NULL,
    packet_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'created',
    assigned_run_id TEXT REFERENCES runs(id),
    output TEXT,
    acceptance_result TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_parent_run_id ON tasks(parent_run_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status, created_at);

CREATE TABLE IF NOT EXISTS collections (
    collection_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    source_type TEXT NOT NULL,
    source_path TEXT,
    source_url TEXT,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    last_ingested_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS collection_chunks (
    chunk_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES collections(collection_id),
    content TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    source_ref TEXT NOT NULL DEFAULT '',
    sequence INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_collection_chunks_collection ON collection_chunks(collection_id);

CREATE VIRTUAL TABLE IF NOT EXISTS collection_chunks_fts USING fts5(content, source_ref, content=collection_chunks, content_rowid=rowid);
```

For the practical explanation, see [Database Schema](database-schema.md).
