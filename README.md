# Orchestro

Local-first orchestration for personal AI workflows.

Orchestro is a Python application that sits above model backends and agent CLIs and adds routing, persistence, memory retrieval, sessions, plans, tools, ratings, corrections, benchmark runs, scheduled tasks, MCP bridging, LSP integration, and exportable feedback data.

It is designed for an operator who wants a terminal-first daily-driver, not just a thin wrapper around one model endpoint.

Current state in this checkout:

- Full `pytest` suite is green.
- The project has acceptance-style API and CLI workflow coverage.
- Live backend smoke tests exist for opt-in verification of external agent CLIs.
- A canary script exists for day-to-day environment checks and auto-routing/cooldown inspection.

## Table Of Contents

1. [What Orchestro Does](#what-orchestro-does)
2. [Quick Start](#quick-start)
3. [Documentation Index](#documentation-index)
4. [Project Surface](#project-surface)
5. [Repo Layout](#repo-layout)
6. [Documentation Gaps](#documentation-gaps)

## What Orchestro Does

Orchestro combines several layers:

- Backend abstraction: local OpenAI-compatible servers, Anthropic, subprocess backends, and agent CLIs such as `claude`, `codex`, `kilocode`, and `cursor-agent`.
- Routing: `auto` backend selection, model-aware routing, and cooldown-based skipping of temporarily unavailable backends.
- Execution strategies: `direct`, `tool-loop`, `reflect-retry`, `reflect-retry-once`, `self-consistency`, `critique-revise`, and `verified`.
- Persistent memory: runs, ratings, interactions, facts, corrections, postmortems, plans, sessions, scheduled tasks, and collections in SQLite.
- Tooling: shell commands, file reads, git inspection, tests, memory search, fact/correction proposals, and optional bridged MCP tools.
- Operator surfaces: CLI, shell mode, a full-screen TUI path, FastAPI service, benchmark runner, and a daily-driver canary script.
- Developer support: acceptance tests, live smoke tests, benchmark suites, and export paths for preference/training data.

For architecture and design intent, see [Architecture](docs/architecture.md), [ADR: SQLite First](docs/adr-sqlite-first.md), and [Roadmap](docs/roadmap.md).

## Quick Start

### 1. Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

### 2. Seed local config

```bash
cp docs/global.md.example .orchestro/global.md
cp .env.example .env
```

Edit `.env` only if you want live non-mock backends. The test-safe default is still the mock backend.

### 3. Sanity-check the install

```bash
PYTHONPATH=src pytest -q
PYTHONPATH=src python scripts/orchestro_canary.py --backend mock --goal "Reply with canary ok." --json
```

### 4. Start using it

CLI:

```bash
orchestro ask "Summarize the repo" --backend auto
orchestro tui --backend auto
orchestro backends
orchestro runs --limit 5
```

API:

```bash
orchestro serve --host 127.0.0.1 --port 8765
curl http://127.0.0.1:8765/health
curl http://127.0.0.1:8765/backends
```

For a fuller setup flow, see [Getting Started](docs/getting-started.md).

## Documentation Index

### Core Guides

- [Getting Started](docs/getting-started.md)
- [CLI Reference](docs/cli-reference.md)
- [Shell Mode](docs/shell.md)
- [TUI Vision](docs/tui.md)
- [TUI Implementation Plan](docs/tui-plan.md)
- [API Reference](docs/api-reference.md)
- [API Operations](docs/api-operations.md)
- [Deployment](docs/deployment.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Backends And Routing](docs/backends-and-routing.md)
- [MCP](docs/mcp.md)
- [LSP](docs/lsp.md)
- [Plugins](docs/plugins.md)
- [Collections](docs/collections.md)
- [Benchmarks](docs/benchmarks.md)
- [Database Schema](docs/database-schema.md)
- [Database Schema SQL](docs/database-schema-sql.md)
- [Instructions And Constitutions](docs/instructions-and-constitutions.md)
- [Trust And Security](docs/trust-and-security.md)
- [Examples](docs/examples.md)
- [Testing And Operations](docs/testing-and-operations.md)

### Existing Design Docs

- [Architecture](docs/architecture.md)
- [ADR: SQLite First](docs/adr-sqlite-first.md)
- [ADR: Agent Loop Patterns](docs/adr-agent-loop-patterns.md)
- [Borrowed Patterns](docs/borrowed-patterns.md)
- [Roadmap](docs/roadmap.md)
- [Global Instructions Template](docs/global.md.example)

### Project Maintenance

- [Documentation Gaps](docs/documentation-gaps.md)

## Project Surface

### Main User Interfaces

- CLI entrypoint: `orchestro`
- MCP server entrypoint: `orchestro-mcp`
- FastAPI service in [`src/orchestro/api.py`](src/orchestro/api.py)
- Interactive shell in [`src/orchestro/cli.py`](src/orchestro/cli.py)

### High-Value CLI Areas

- Asking and shell work: `ask`, `shell`, `backends`
- Run management: `runs`, `show`, `changes`, `run-summary`, `run-note`, `rate`, `rate-event`
- Sessions and plans: `sessions`, `session-*`, `plans`, `plan-*`
- Tools and integrations: `tools`, `tool-run`, `plugins`, `mcp-status`, `lsp-status`
- Memory and knowledge: `facts`, `corrections`, `interactions`, `search`, `semantic-search`, `collections`
- Benchmarks and exports: `bench*`, `benchmark-*`, `export-preferences`, `export-stats`
- Scheduling and operations: `schedule-*`, `approval-*`, `vector-status`, `index-*`, `queue-embeddings`

See [CLI Reference](docs/cli-reference.md) for the grouped command index.

### High-Value API Areas

- Health and status: `/health`, `/backends`, `/plugins`, `/mcp-status`, `/lsp-status`
- Runs: `/ask`, `/ask/stream`, `/runs`, `/runs/{run_id}`, `/runs/{run_id}/events`
- Sessions and plans: `/sessions`, `/sessions/{id}`, `/plans`, `/plans/{id}`
- Tools and memory: `/tools`, `/tools/run`, `/facts`, `/corrections`, `/search`, `/semantic-search`
- Operations: `/scheduled-tasks`, `/routing-stats`, `/index-jobs`, `/benchmark-runs`

See [API Reference](docs/api-reference.md) and [Examples](docs/examples.md).

## Repo Layout

```text
src/orchestro/        Application code
tests/                Unit, integration, acceptance, and live smoke tests
docs/                 Human docs, ADRs, architecture notes
benchmarks/           Benchmark suites
scripts/              Operational helpers and canaries
.orchestro/           Default local data directory
```

Key files:

- [`src/orchestro/orchestrator.py`](src/orchestro/orchestrator.py): run lifecycle, routing, retries, tool execution, persistence glue
- [`src/orchestro/cli.py`](src/orchestro/cli.py): terminal UI and command entrypoints
- [`src/orchestro/api.py`](src/orchestro/api.py): FastAPI service
- [`src/orchestro/db.py`](src/orchestro/db.py): SQLite persistence layer
- [`src/orchestro/backend_profiles.py`](src/orchestro/backend_profiles.py): backend registry, aliases, auto routing, cooldowns
- [`scripts/orchestro_canary.py`](scripts/orchestro_canary.py): daily-driver canary

## Documentation Gaps

The major documentation gaps from the previous passes are now closed. Ongoing maintenance risks are tracked in [docs/documentation-gaps.md](docs/documentation-gaps.md).

If you are changing behavior, update the relevant focused doc rather than growing this README again.
