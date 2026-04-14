# API Reference

Orchestro exposes a FastAPI service for status, runs, tools, plans, sessions, knowledge records, scheduled tasks, and benchmark metadata.

Run it with:

```bash
orchestro serve --host 127.0.0.1 --port 8765
```

## Table Of Contents

1. [Status And Discovery](#status-and-discovery)
2. [Runs](#runs)
3. [Sessions And Plans](#sessions-and-plans)
4. [Tools And Search](#tools-and-search)
5. [Knowledge And Memory](#knowledge-and-memory)
6. [Operations And Scheduling](#operations-and-scheduling)
7. [Examples](#examples)

## Status And Discovery

- `GET /health`
- `GET /backends`
- `GET /plugins`
- `GET /mcp-status`
- `GET /lsp-status`
- `GET /instructions`
- `GET /constitutions`
- `GET /aliases`

Use these first when wiring a UI or debugging a local install.

`/backends` includes:

- reachability
- cooldown state
- unavailable-until timestamps
- discovered models
- backend capability metadata

See [Backends And Routing](backends-and-routing.md).

## Runs

- `POST /ask`
- `POST /ask/stream`
- `GET /runs`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/events`
- `PUT /runs/{run_id}/summary`
- `PUT /runs/{run_id}/note`
- `GET /runs/{run_id}/changes`

`POST /ask` payload:

```json
{
  "goal": "Summarize the repo",
  "backend": "auto",
  "model_alias": null,
  "strategy": "direct",
  "cwd": ".",
  "domain": null,
  "providers": null,
  "autonomous": false
}
```

`POST /ask/stream` returns server-sent events with token chunks and a final done event.

## Sessions And Plans

### Sessions

- `GET /sessions`
- `GET /sessions/{session_id}`
- `POST /sessions`
- `POST /sessions/{session_id}/compact`

### Plans

- `GET /plans`
- `GET /plans/{plan_id}`
- `POST /plans`
- `POST /plans/{plan_id}/replan`
- `POST /plans/{plan_id}/steps`
- `PUT /plans/{plan_id}/steps/{sequence_no}`
- `DELETE /plans/{plan_id}/steps/{sequence_no}`

These are persisted objects backed by SQLite, not transient in-memory state.

## Tools And Search

- `GET /tools`
- `POST /tools/run`
- `GET /search`
- `POST /semantic-search`
- `GET /interactions`

`POST /tools/run` is useful for integration tests and lightweight UIs. It enforces the same approval semantics as the CLI/API layer.

## Knowledge And Memory

- `GET /facts`
- `POST /facts`
- `GET /corrections`
- `POST /corrections`
- `GET /postmortems`

These records feed retrieval and training export paths. See [Architecture](architecture.md) and [Testing And Operations](testing-and-operations.md#data-and-export-paths).

## Operations And Scheduling

- `GET /vector-status`
- `GET /index-jobs`
- `POST /index-jobs/run`
- `POST /index-jobs/queue`
- `GET /routing-stats`
- `GET /scheduled-tasks`
- `POST /scheduled-tasks`
- `POST /scheduled-tasks/{task_id}/toggle`
- `DELETE /scheduled-tasks/{task_id}`
- `GET /shell-jobs`
- `GET /shell-jobs/{job_id}`
- `POST /shell-jobs/{job_id}/inject`
- `GET /benchmark-runs`
- `GET /benchmark-runs/compare`
- `GET /benchmark-runs/{benchmark_run_id}`
- `GET /benchmark-runs/{benchmark_run_id}/baseline`
- `POST /bench/run`
- `POST /bench/matrix`
- `POST /export-preferences`

## Examples

Backends:

```bash
curl http://127.0.0.1:8765/backends
```

Run:

```bash
curl -X POST http://127.0.0.1:8765/ask \
  -H 'content-type: application/json' \
  -d '{"goal":"Say hello","backend":"mock"}'
```

Session:

```bash
curl -X POST http://127.0.0.1:8765/sessions \
  -H 'content-type: application/json' \
  -d '{"title":"Daily Session"}'
```

Tool:

```bash
curl -X POST http://127.0.0.1:8765/tools/run \
  -H 'content-type: application/json' \
  -d '{"tool_name":"pwd","cwd":"."}'
```

More concrete request flows are in [Examples](examples.md#api-examples). For service-running guidance and trust boundaries, see [API Operations](api-operations.md).
