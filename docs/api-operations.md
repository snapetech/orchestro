# API Operations

This guide is about running the Orchestro API as a local service, not just calling one endpoint by hand.

## Table Of Contents

1. [Service Model](#service-model)
2. [Run It Locally](#run-it-locally)
3. [State And Data Paths](#state-and-data-paths)
4. [Operational Risks](#operational-risks)
5. [Recommended Local Usage Pattern](#recommended-local-usage-pattern)
6. [Monitoring And Health](#monitoring-and-health)

## Service Model

The API is a FastAPI app defined in [`src/orchestro/api.py`](../src/orchestro/api.py).

It is local-first. It exposes:

- read/write endpoints over the SQLite-backed state
- run execution
- tool execution
- plan/session management
- benchmark and scheduling surfaces

This is convenient, but it means you should treat the API as a trusted local operator service unless you intentionally harden and isolate it yourself.

## Run It Locally

```bash
orchestro serve --host 127.0.0.1 --port 8765
```

Recommended default:

- bind to `127.0.0.1`
- keep it private
- use it behind your own local reverse proxy only if you know why

## State And Data Paths

The API uses the same Orchestro data root as the CLI.

Default:

```text
.orchestro/
```

Override:

```bash
export ORCHESTRO_HOME=/path/to/orchestro-home
```

This affects:

- SQLite DB path
- plugin directory
- global instructions
- LSP config
- MCP config
- approvals state

## Operational Risks

High-risk endpoints for exposure beyond your own machine:

- `POST /ask`
- `POST /ask/stream`
- `POST /tools/run`
- scheduling endpoints
- approval resolution endpoints

Why:

- they can trigger backend calls
- they can mutate state
- tool-running surfaces may execute shell commands if the tool and approval path allow it

Practical advice:

- do not expose the API publicly by default
- do not assume the API is multi-tenant safe
- do not grant remote users unfettered access to tool-running endpoints

## Recommended Local Usage Pattern

For daily use:

1. keep the service bound locally
2. verify with `/health` and `/backends`
3. run the canary periodically
4. use the CLI for heavy operator workflows
5. use the API for dashboards, wrappers, and lightweight automation

## Monitoring And Health

Minimum checks:

- `GET /health`
- `GET /backends`
- `GET /plugins`
- `GET /mcp-status`
- `GET /lsp-status`

Those tell you much more than a simple process-up signal.

For acceptance verification, see [Testing And Operations](testing-and-operations.md). For endpoint coverage, see [API Reference](api-reference.md).
