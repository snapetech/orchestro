# Shell Mode

The interactive shell is Orchestro’s terminal-first operator UI. It is not just a wrapper around `ask`; it carries session state, default backend/strategy/domain, background jobs, plan workflows, approvals, and review commands.

It is also the fallback and power-user surface while the richer full-screen TUI is built out. See [TUI Vision](tui.md).

## Table Of Contents

1. [Starting The Shell](#starting-the-shell)
2. [Mental Model](#mental-model)
3. [Important Slash Commands](#important-slash-commands)
4. [Modes Sessions And Plans](#modes-sessions-and-plans)
5. [Tools And Approvals](#tools-and-approvals)
6. [Background Jobs](#background-jobs)
7. [Operator Tips](#operator-tips)

## Starting The Shell

```bash
orchestro shell --backend auto
```

Optional defaults:

- `--backend`
- `--model`
- `--strategy`
- `--domain`
- `--providers`

The prompt looks like:

```text
orchestro[act:<cwd>]>
```

Or, with a session:

```text
orchestro[act:<cwd>:s=<session-prefix>]>
```

## Mental Model

The shell keeps local operator state:

- current working directory
- default backend
- default strategy
- default domain
- current mode
- current session
- current plan
- autonomous toggle

Free text runs a goal. Slash commands mutate or inspect shell state.

## Important Slash Commands

Core:

- `/help`
- `/backend`
- `/strategy`
- `/domain`
- `/context`
- `/autonomous`
- `/pwd`
- `/cd`
- `/ls`
- `/backends`

Runs and review:

- `/last`
- `/runs`
- `/show`
- `/events`
- `/rate`
- `/rate_event`
- `/note`
- `/summary`
- `/changes`

Tools:

- `/tools`
- `/tool`
- `/plugins`
- `/mcp_status`
- `/lsp_status`
- `/approvals`
- `/approvals_review`
- `/trust`
- `/trust_set`

Knowledge:

- `/facts`
- `/facts_sync`
- `/corrections`
- `/interactions`
- `/search`
- `/collection_ingest`
- `/collection_search`

Benchmarks and ops:

- `/bench`
- `/bench_local`
- `/bench_matrix`
- `/benchmark_runs`
- `/benchmark_compare`
- `/benchmark_metrics`

## Modes Sessions And Plans

Modes:

- `act`
- `plan`

Useful commands:

- `/mode <plan|act>`
- `/session ...`
- `/plan ...`
- `/plans`
- `/plan_show`
- `/plan_add`
- `/plan_edit`
- `/plan_drop`
- `/replan`
- `/plan_run`
- `/plan_bg`

The shell is the richest operator surface for plans because it can drive plan execution and background jobs in one place.

## Tools And Approvals

Tool approval is interactive by default for `confirm` tools.

What matters:

- approval prompts can be remembered by pattern
- approvals can be reviewed later
- `autonomous` changes how some execution paths handle approval gating

Related commands:

- `/tool <name> <arg>`
- `/approvals`
- `/approvals_review`
- `/approval_requests`
- `/approve`

For the tool model itself, see [CLI Reference](cli-reference.md#tools-and-integrations).

## Background Jobs

Important commands:

- `/bg`
- `/jobs`
- `/job_show`
- `/wait`
- `/watch`
- `/fg`
- `/inject`
- `/cancel`
- `/pause`
- `/resume`

These are useful when a run is long-lived, approval-gated, or needs operator input later.

## Operator Tips

- Use `/help` often. The shell has more surface area than the plain CLI.
- Use sessions if you want related work compacted and resumable.
- Use plan mode for longer engineering tasks you want to persist step-by-step.
- Use `/show` and `/events` to debug routing, retries, approvals, and tool behavior.
- Use the shell for daily-driver use, and the plain CLI/API for scripting.

For setup, see [Getting Started](getting-started.md). For examples, see [Examples](examples.md). For backend behavior, see [Backends And Routing](backends-and-routing.md).
