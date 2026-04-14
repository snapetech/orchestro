# Deployment

This guide covers practical deployment shapes for Orchestro beyond “run it once in a shell.”

## Table Of Contents

1. [Supported Deployment Mindset](#supported-deployment-mindset)
2. [Local Persistent Service](#local-persistent-service)
3. [Data Placement](#data-placement)
4. [Backend Dependencies](#backend-dependencies)
5. [Recommended Validation After Deploy](#recommended-validation-after-deploy)

## Supported Deployment Mindset

The codebase is currently best suited to:

- local personal deployment
- a private workstation or homelab box
- an operator who can inspect logs, files, and SQLite state directly

It is not yet documented or hardened as an internet-facing production SaaS deployment.

## Local Persistent Service

The simplest long-running deployment is:

```bash
export ORCHESTRO_HOME=/path/to/orchestro-home
orchestro serve --host 127.0.0.1 --port 8765
```

Concrete examples now live under:

- [`deploy/systemd/orchestro.service`](../deploy/systemd/orchestro.service)
- [`deploy/container/Dockerfile`](../deploy/container/Dockerfile)
- [`deploy/container/README.md`](../deploy/container/README.md)

## Data Placement

Persist:

- the Orchestro home directory
- the project repo if you rely on project-local instructions or constitutions

Important files under `ORCHESTRO_HOME` may include:

- `orchestro.db`
- `global.md`
- `constitutions/`
- `mcp_servers.json`
- `lsp_servers.json`
- `tool_approvals.json`
- `trust.json`
- `plugins/`

## Backend Dependencies

A deployment is only as useful as its configured backends.

Common dependency classes:

- local OpenAI-compatible server
- agent CLIs present on `PATH`
- Anthropic/OpenAI/OpenRouter API credentials
- MCP server subprocess dependencies
- language server binaries

Use these to inspect the deployed environment:

```bash
orchestro backends
orchestro plugins
orchestro mcp-status
orchestro lsp-status
```

## Recommended Validation After Deploy

Minimum checks:

```bash
PYTHONPATH=src pytest -q
PYTHONPATH=src python scripts/orchestro_canary.py --backend mock --json
curl http://127.0.0.1:8765/health
curl http://127.0.0.1:8765/backends
```

If you rely on live backends:

```bash
ORCHESTRO_RUN_LIVE_BACKEND_TESTS=1 PYTHONPATH=src pytest -q tests/test_live_backends.py
```

Related docs:

- [Getting Started](getting-started.md)
- [API Operations](api-operations.md)
- [Testing And Operations](testing-and-operations.md)
- [Troubleshooting](troubleshooting.md)
