# Troubleshooting

This is the central failure cookbook for common Orchestro issues.

## Table Of Contents

1. [Quick Triage](#quick-triage)
2. [Backend Problems](#backend-problems)
3. [MCP Problems](#mcp-problems)
4. [LSP Problems](#lsp-problems)
5. [Run And Plan Problems](#run-and-plan-problems)
6. [Approval And Tool Problems](#approval-and-tool-problems)
7. [Collections And Indexing Problems](#collections-and-indexing-problems)
8. [Benchmark Problems](#benchmark-problems)

## Quick Triage

Run these first:

```bash
orchestro backends
orchestro plugins
orchestro mcp-status
orchestro lsp-status
PYTHONPATH=src python scripts/orchestro_canary.py --backend mock --json
```

If the issue is broad, also run:

```bash
PYTHONPATH=src pytest -q
```

## Backend Problems

### `unknown backend`

Check:

- `orchestro backends`
- `GET /backends`

Fix:

- use a configured backend name or alias
- confirm the alias exists if you expected one

### Quota or usage limit failures

Check:

- run events for `backend_temporarily_unavailable`
- `orchestro backends` for cooldown state

Fix:

- wait for the reported cooldown/reset window
- use `auto` so Orchestro can reroute
- avoid forcing the exhausted backend until reset

### Backend timed out

Fix:

- reduce context size
- try a faster backend
- use a simpler strategy

## MCP Problems

### `no MCP servers configured`

Check:

- `.orchestro/mcp_servers.json`

### MCP server degraded

Check:

- `orchestro mcp-status`
- `GET /mcp-status`

Fix:

- inspect `degraded_details`
- verify the server command exists
- verify args and working directory

## LSP Problems

### `no LSP servers configured`

Check:

- `.orchestro/lsp_servers.json`

### `no LSP server available for <lang>`

Fix:

- confirm the file extension is mapped
- confirm the config lists that language
- check `orchestro lsp-status`

## Run And Plan Problems

### `run not found`

Usually means:

- wrong run ID
- different `ORCHESTRO_HOME`

### `plan not found` or `session not found`

Check:

- `orchestro plans`
- `orchestro sessions`

### Plan step failed

Check:

- `orchestro show <run-id>`
- run events
- plan events

## Approval And Tool Problems

### `tool requires approval`

Fix:

- run interactively and approve
- inspect `tool-approvals`
- inspect pending requests with `approval-requests`

### Tool fails repeatedly

Check:

- tool approval tier
- trust policy
- actual command arguments

## Collections And Indexing Problems

### `collection not found`

Check:

- `orchestro collections`

### Collection search has weak results

Remember:

- collections use lexical FTS search
- they are not semantic vector search

### Indexing failed

Check:

- embedding provider config
- backend availability

## Benchmark Problems

### `benchmark run not found`

Usually means:

- wrong benchmark run ID
- wrong DB / `ORCHESTRO_HOME`

### Live benchmark failures

Check:

- backend base URL
- auth state
- helper scripts under `scripts/`

Related docs:

- [Benchmarks](benchmarks.md)
- [Deployment](deployment.md)
- [API Operations](api-operations.md)
