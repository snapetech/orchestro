# Benchmarks

Orchestro has a benchmark system for evaluating strategies, backends, routing behavior, recovery behavior, and workflow-like tasks.

## Table Of Contents

1. [What The Benchmark System Does](#what-the-benchmark-system-does)
2. [Suite Files](#suite-files)
3. [Suite Schema](#suite-schema)
4. [Stored Benchmark Runs](#stored-benchmark-runs)
5. [CLI And API Surfaces](#cli-and-api-surfaces)
6. [Current Suite Inventory](#current-suite-inventory)

## What The Benchmark System Does

The implementation lives in [`src/orchestro/bench.py`](../src/orchestro/bench.py).

It can:

- load a suite JSON file
- execute each case through Orchestro
- validate output, status, events, failure categories, and recovery attempts
- store a benchmark summary in SQLite
- compare a run against a previous baseline

This is not just prompt matching. Some cases explicitly assert lifecycle behavior such as approvals, retries, compaction, routing, and recovery.

## Suite Files

Suite files are JSON with a top-level `suite` name and `cases` array.

Minimal example:

```json
{
  "suite": "default",
  "cases": [
    {
      "id": "mock-basic",
      "goal": "describe a simple mock benchmark response",
      "match": "contains",
      "expected": "Mock backend response"
    }
  ]
}
```

## Suite Schema

Supported case fields include:

- `id`
- `goal`
- `match`
- `expected`
- `domain`
- `backend`
- `strategy`
- `providers`
- `env`
- `prompt_context`
- `expected_status`
- `expected_backend`
- `expected_events`
- `expected_failure_category`
- `min_recovery_attempts`
- `approval_pattern`
- `operator_note`
- `operator_note_after_approval`

This schema is derived from `BenchmarkCase` in [`src/orchestro/bench.py`](../src/orchestro/bench.py).

## Stored Benchmark Runs

Benchmark run summaries are stored in SQLite and exposed through:

- `benchmark-runs`
- `benchmark-compare`
- `benchmark-metrics`
- `GET /benchmark-runs`
- `GET /benchmark-runs/{id}`
- `GET /benchmark-runs/{id}/baseline`
- `GET /benchmark-runs/compare`

Stored summaries include:

- suite metadata
- backend and strategy used
- pass/fail counts and pass rate
- detailed per-case results
- aggregate metrics such as token usage, wall time, tool calls, recovery attempts, and quality distribution

## CLI And API Surfaces

CLI:

- `orchestro bench`
- `orchestro bench-local`
- `orchestro bench-matrix`
- `orchestro benchmark-runs`
- `orchestro benchmark-compare`
- `orchestro benchmark-metrics`

API:

- `POST /bench/run`
- `POST /bench/matrix`
- `GET /benchmark-runs`
- `GET /benchmark-runs/{benchmark_run_id}`
- `GET /benchmark-runs/{benchmark_run_id}/baseline`
- `GET /benchmark-runs/compare`

## Current Suite Inventory

The repo currently ships:

- `benchmarks/default.json`
- `benchmarks/agent.json`
- `benchmarks/coding.json`
- `benchmarks/routing.json`
- `benchmarks/workflows.json`
- `benchmarks/vllm-live.json`

Rough intent:

- `default`: simple baseline sanity cases
- `agent`: tool-loop, retry, approval, and failure/recovery behavior
- `coding`: coding-oriented and git/tool lifecycle cases
- `routing`: auto-routing expectations
- `workflows`: higher-level multi-step operator flows
- `vllm-live`: live local model smoke/evaluation cases

For operational commands around these suites, see [Testing And Operations](testing-and-operations.md#benchmarks). For daily-driver validation, see [Examples](examples.md#canary-and-live-smoke-examples).
