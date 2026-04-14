# CLI Reference

The CLI is the main operator surface for Orchestro. This doc groups the commands by job rather than listing them in one flat dump.

Source of truth is still:

```bash
orchestro --help
orchestro <command> --help
```

## Table Of Contents

1. [Core Commands](#core-commands)
2. [Run And Review Commands](#run-and-review-commands)
3. [Sessions And Plans](#sessions-and-plans)
4. [Tools And Integrations](#tools-and-integrations)
5. [Knowledge And Search](#knowledge-and-search)
6. [Benchmarks And Exports](#benchmarks-and-exports)
7. [Scheduling And Operations](#scheduling-and-operations)
8. [Notes](#notes)

## Core Commands

### Ask And Shell

- `ask`: run one goal through Orchestro
- `shell`: launch the interactive shell
- `tui`: launch the full-screen TUI operator surface
- `backends`: show configured backend profiles, reachability, cooldowns, and discovered models

Common options:

- `--backend auto|<name>`
- `--model <alias>`
- `--strategy direct|tool-loop|reflect-retry|reflect-retry-once|self-consistency|critique-revise|verified`
- `--domain <label>`
- `--cwd <path>`
- `--providers <comma-separated context providers>`
- `--autonomous`

See [Backends And Routing](backends-and-routing.md) for how `auto` behaves.

## Run And Review Commands

- `runs`: list recent runs
- `show`: show one run with events and status
- `changes`: show git changes for a run working tree
- `run-summary`: attach or update a run summary
- `run-note`: attach or update an operator note
- `rate`: rate a run or event
- `rate-event`: rate one event by index
- `children`: inspect child runs
- `review`: operator review workflow
- `review-stats`: review/ratings stats

Typical flow:

1. `orchestro ask "..."`
2. `orchestro runs --limit 5`
3. `orchestro show <run-id>`
4. `orchestro run-summary <run-id> "..."`
5. `orchestro rate run <run-id> good --note "..."`

## Sessions And Plans

### Sessions

- `sessions`
- `session-new`
- `session-show`
- `session-resume`
- `session-fork`
- `session-compact`

### Plans

- `plans`
- `plan-show`
- `plan-create`
- `plan-run`
- `plan-step-add`
- `plan-step-edit`
- `plan-step-drop`
- `plan-step-replan`

These commands operate on persisted, SQLite-backed session and plan records. For API equivalents, see [API Reference](api-reference.md). For examples, see [Examples](examples.md).

## Tools And Integrations

- `tools`: list available Orchestro tools
- `tool-run`: run a tool manually
- `plugins`: show loaded plugins, load errors, and hook errors
- `mcp-status`: show MCP server status and degraded details
- `lsp-status`: show LSP server status and degraded details
- `tool-approvals`: inspect tool approval state
- `approval-requests`
- `approval-resolve`
- `mcp-serve`: run Orchestro’s own MCP server

Tool approval model:

- some tools are `auto`
- some require explicit approval
- MCP-bridged tools are registered with `confirm`

For MCP and LSP config paths, see [Examples](examples.md#example-mcp-and-lsp-config), [MCP](mcp.md), and [LSP](lsp.md).

## Knowledge And Search

- `facts`
- `fact-add`
- `facts-sync`
- `corrections`
- `correction-add`
- `interactions`
- `search`
- `semantic-search`
- `postmortems`
- `escalations`
- `collections`
- `collection-create`
- `collection-ingest`
- `collection-search`
- `collection-delete`
- `instructions-show`
- `constitutions-show`

These surfaces feed the retrieval and memory system discussed in [Architecture](architecture.md). Collections have their own guide in [Collections](collections.md).

## Benchmarks And Exports

- `bench`
- `bench-local`
- `bench-matrix`
- `benchmark-runs`
- `benchmark-compare`
- `benchmark-metrics`
- `export-preferences`
- `export-stats`

Benchmark suites currently live under `benchmarks/`:

- `default.json`
- `agent.json`
- `coding.json`
- `routing.json`
- `workflows.json`
- `vllm-live.json`

See [Benchmarks](benchmarks.md) and [Testing And Operations](testing-and-operations.md#benchmarks).

## Scheduling And Operations

- `schedule-add`
- `schedule-list`
- `schedule-toggle`
- `schedule-delete`
- `vector-status`
- `index-status`
- `index-embeddings`
- `queue-embeddings`
- `routing-stats`
- `shell-jobs`
- `shell-job-show`
- `shell-job-inject`
- `tasks`
- `delegate`

These are the commands most likely to benefit from concrete examples, so see [Examples](examples.md#examples-by-workflow).

## Notes

- `cli.py` is large and integration-heavy. Treat `--help` output as the freshest command contract.
- Shell mode includes additional slash commands that overlap with CLI commands.
- The TUI is an optional extra powered by Textual. See [TUI Vision](tui.md) and [TUI Implementation Plan](tui-plan.md).
- If a backend is temporarily unavailable due to quota or usage limits, `auto` can reroute away from it and track a cooldown window. That behavior is documented in [Backends And Routing](backends-and-routing.md#cooldowns-and-temporary-unavailability).
- The interactive shell has its own higher-level operator flow. See [Shell Mode](shell.md).
