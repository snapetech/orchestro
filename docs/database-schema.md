# Database Schema

This is a practical reference for Orchestro’s SQLite persistence layer.

For the raw SQL schema, see [Database Schema SQL](database-schema-sql.md).

## Table Of Contents

1. [Storage Model](#storage-model)
2. [Core Run Tables](#core-run-tables)
3. [Memory And Knowledge Tables](#memory-and-knowledge-tables)
4. [Job And Approval Tables](#job-and-approval-tables)
5. [Plan And Session Tables](#plan-and-session-tables)
6. [Benchmark And Scheduling Tables](#benchmark-and-scheduling-tables)
7. [Collections Tables](#collections-tables)
8. [Embedding Tables](#embedding-tables)

## Storage Model

Orchestro is SQLite-first. The DB file lives under the Orchestro data directory:

- default: `.orchestro/orchestro.db`
- override: `ORCHESTRO_HOME=/path/to/home`

The schema is created and evolved by `OrchestroDB` in [`src/orchestro/db.py`](../src/orchestro/db.py).

## Core Run Tables

### `runs`

Primary execution record.

Stores:

- run identity
- parent/child linkage
- session linkage
- goal, backend, strategy, working directory
- metadata
- status and error fields
- final output and annotations
- token usage
- quality and recovery state

### `run_events`

Append-only event log for each run.

Used for:

- routing decisions
- retries
- tool calls
- reflections
- git snapshots
- completion/failure markers

### `ratings`

Operator ratings attached to runs or events.

### `interactions`

Structured interaction records used for retrieval and preference export.

## Memory And Knowledge Tables

### `facts`

Durable fact records such as accepted operator knowledge.

### `corrections`

Explicit answer repairs:

- context
- wrong answer
- right answer
- optional domain

### `postmortems`

Failure-oriented records used to track lessons and recurring issues.

## Job And Approval Tables

### `shell_jobs`

Background shell job metadata.

### `shell_job_events`

Job lifecycle events.

### `shell_job_inputs`

Deferred operator input injected into a shell job.

### `approval_requests`

Persisted approval queue for tools and long-running shell jobs.

This sits alongside the approval-pattern store in `tool_approvals.json`.

## Plan And Session Tables

### `sessions`

Session records used to group related runs and store compacted context snapshots.

### `plans`

Persisted plans.

### `plan_steps`

Ordered step list for each plan.

### `plan_events`

Plan lifecycle log:

- creation
- replan
- step add/edit/delete
- think notes

## Benchmark And Scheduling Tables

### `benchmark_runs`

Stored benchmark summaries for later comparison and metrics inspection.

### `scheduled_tasks`

Recurring task definitions:

- cron expression
- goal
- backend and strategy
- domain
- enabled state
- autonomous flag

### `tasks`

Subtask/delegation records used by Orchestro’s task packet flow.

## Collections Tables

### `collections`

Collection metadata:

- ID
- name
- source type
- source path or URL
- description
- chunk count
- last ingested timestamp

### `collection_chunks`

Chunked document content associated with a collection.

### `collection_chunks_fts`

FTS index used by collection search.

For collection usage, see [Collections](collections.md).

## Embedding Tables

### `embedding_jobs`

Queue/state for embedding indexing work.

### `interaction_embeddings`

Vector payloads associated with interaction records.

### `correction_embeddings`

Vector payloads associated with correction records.

These tables support the retrieval/indexing path documented in [Testing And Operations](testing-and-operations.md) and the architectural intent in [Architecture](architecture.md).
