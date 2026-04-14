# Testing And Operations

This guide covers how to validate an Orchestro install and how the project now approaches acceptance and live verification.

## Table Of Contents

1. [Test Layers](#test-layers)
2. [Common Commands](#common-commands)
3. [Acceptance Coverage](#acceptance-coverage)
4. [Live Backend Verification](#live-backend-verification)
5. [Canary Workflow](#canary-workflow)
6. [Benchmarks](#benchmarks)
7. [Data And Export Paths](#data-and-export-paths)

## Test Layers

The repo now has several layers of validation:

- unit and integration tests under `tests/`
- acceptance workflow tests:
  - `tests/test_api_acceptance.py`
  - `tests/test_cli_acceptance.py`
- opt-in live smoke tests:
  - `tests/test_live_backends.py`
- a runnable canary:
  - `scripts/orchestro_canary.py`

The acceptance layer exists to cover real persisted workflows, not just isolated functions.

## Common Commands

Full suite:

```bash
PYTHONPATH=src pytest -q
```

Targeted acceptance tests:

```bash
PYTHONPATH=src pytest -q tests/test_api_acceptance.py tests/test_cli_acceptance.py
```

Lint:

```bash
make lint
```

Benchmarks:

```bash
make bench
make bench-agent
make bench-coding
make bench-routing
make bench-workflows
```

## Acceptance Coverage

### API acceptance

Covers:

- `/ask`
- `/runs`
- `/runs/{id}`
- run summary and note updates
- `/tools/run`
- session creation and compaction
- plan create, step add, step edit, step delete, and replan

### CLI acceptance

Covers:

- `ask`
- `runs`
- `run-summary`
- `run-note`
- `session-new`
- `session-compact`
- `plan-create`
- `plan-step-add`
- `plan-run`
- `plan-show`

For the concrete commands, see [Examples](examples.md).

## Live Backend Verification

Live backend smoke tests are opt-in because they depend on external binaries, auth state, and quota state.

Enable them with:

```bash
ORCHESTRO_RUN_LIVE_BACKEND_TESTS=1 PYTHONPATH=src pytest -q tests/test_live_backends.py
```

Optional backend subset:

```bash
ORCHESTRO_RUN_LIVE_BACKEND_TESTS=1 \
ORCHESTRO_LIVE_BACKENDS=codex,kilocode \
PYTHONPATH=src \
pytest -q tests/test_live_backends.py
```

Behavior:

- skip if the backend binary is unavailable
- skip if the backend reports a usage-limit or quota-style failure
- fail on real wrapper or execution errors

## Canary Workflow

The canary is for local operator confidence, not CI exhaustiveness.

Basic:

```bash
PYTHONPATH=src python scripts/orchestro_canary.py --backend mock --goal "Reply with canary ok."
```

What it checks:

- backend statuses before the run
- one tool invocation
- one persisted run
- event stream for routing and retries
- cooldown registry

Useful flags:

- `--backend auto`
- `--home <path>`
- `--inject-limit <backend>`
- `--json`

Using a fresh `--home` path is the cleanest way to inspect routing without prior DB history skewing the decision.

## Benchmarks

Benchmark suites currently live in `benchmarks/`:

- `default.json`
- `agent.json`
- `coding.json`
- `routing.json`
- `workflows.json`
- `vllm-live.json`

The Makefile wraps the common ones:

- `make bench`
- `make bench-agent`
- `make bench-coding`
- `make bench-routing`
- `make bench-workflows`

`vllm-live.json` is intended for live local model services and pairs with the helper scripts under `scripts/`.

## Data And Export Paths

Useful operational commands:

- `orchestro index-embeddings`
- `orchestro queue-embeddings`
- `orchestro facts-sync`
- `orchestro export-preferences`
- `orchestro export-stats`

Supporting scripts:

- [`scripts/seed-interactions.py`](../scripts/seed-interactions.py)
- [`scripts/reindex-ollama-embeddings.sh`](../scripts/reindex-ollama-embeddings.sh)
- [`scripts/vllm-smoke.sh`](../scripts/vllm-smoke.sh)
- [`scripts/vllm-ephemeral-check.sh`](../scripts/vllm-ephemeral-check.sh)

For setup and backend env vars, also see [Getting Started](getting-started.md) and [Backends And Routing](backends-and-routing.md).
