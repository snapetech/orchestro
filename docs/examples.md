# Examples

This doc collects concrete examples that are useful enough to copy into a real local setup.

## Table Of Contents

1. [CLI Examples](#cli-examples)
2. [API Examples](#api-examples)
3. [Example MCP And LSP Config](#example-mcp-and-lsp-config)
4. [Example Plugin](#example-plugin)
5. [Canary And Live Smoke Examples](#canary-and-live-smoke-examples)

## CLI Examples

### Basic ask

```bash
orchestro ask "Summarize the current repo status" --backend auto
```

### Force mock backend

```bash
orchestro ask "Say hello" --backend mock
```

### Use a model alias

```bash
orchestro ask "Review this code path for risks" --model smart
orchestro ask "Fix the failing test" --model code
```

### Review recent runs

```bash
orchestro runs --limit 10
orchestro show <run-id>
orchestro run-summary <run-id> "Good output, but too verbose."
orchestro run-note <run-id> "Retry with verified strategy next time."
orchestro rate run <run-id> good --note "Accepted"
```

### Session workflow

```bash
orchestro session-new "Daily Driver"
orchestro ask "Inspect the repo for flaky tests" --backend auto
orchestro session-compact <session-id> --limit 20
orchestro session-show <session-id>
```

### Plan workflow

```bash
orchestro plan-create "Add coverage for routing edge cases" --backend mock
orchestro plan-show <plan-id>
orchestro plan-step-add <plan-id> 5 "Run the focused tests" "Verify the new routing path."
orchestro plan-run <plan-id>
```

### Tool workflow

```bash
orchestro tools
orchestro tool-run pwd
orchestro tool-run read_file README.md
orchestro tool-run git_status
```

## API Examples

### Health and backends

```bash
curl http://127.0.0.1:8765/health
curl http://127.0.0.1:8765/backends
```

### Run a request

```bash
curl -X POST http://127.0.0.1:8765/ask \
  -H 'content-type: application/json' \
  -d '{
    "goal": "Summarize the repo",
    "backend": "mock",
    "cwd": "."
  }'
```

### Stream a request

```bash
curl -N -X POST http://127.0.0.1:8765/ask/stream \
  -H 'content-type: application/json' \
  -d '{
    "goal": "Stream this response",
    "backend": "mock"
  }'
```

### Run a tool

```bash
curl -X POST http://127.0.0.1:8765/tools/run \
  -H 'content-type: application/json' \
  -d '{
    "tool_name": "pwd",
    "cwd": "."
  }'
```

### Create a session and compact it

```bash
curl -X POST http://127.0.0.1:8765/sessions \
  -H 'content-type: application/json' \
  -d '{"title":"Daily Session"}'

curl -X POST "http://127.0.0.1:8765/sessions/<session-id>/compact?limit=20"
```

### Create a plan

```bash
curl -X POST http://127.0.0.1:8765/plans \
  -H 'content-type: application/json' \
  -d '{
    "goal": "Draft a verification plan",
    "backend": "mock",
    "cwd": "."
  }'
```

## Example MCP And LSP Config

These files live under `ORCHESTRO_HOME`, which defaults to `.orchestro/`.

### `.orchestro/mcp_servers.json`

```json
{
  "servers": [
    {
      "name": "demo-mcp",
      "command": "python",
      "args": ["-m", "some_mcp_server"],
      "working_directory": ".",
      "enabled": true,
      "env": {
        "EXAMPLE_FLAG": "1"
      }
    }
  ]
}
```

### `.orchestro/lsp_servers.json`

```json
{
  "servers": [
    {
      "name": "pyright",
      "command": "pyright-langserver",
      "args": ["--stdio"],
      "languages": ["python"],
      "enabled": true
    }
  ]
}
```

After creating them:

```bash
orchestro mcp-status
orchestro lsp-status
```

## Example Plugin

Plugins are Python files under `.orchestro/plugins/`.

### `.orchestro/plugins/example_plugin.py`

```python
from __future__ import annotations

from orchestro.plugins import CONTINUE, HookResult, PluginMetadata

METADATA = PluginMetadata(
    name="example-plugin",
    version="0.1.0",
    description="Logs and lightly annotates run context.",
)


def _pre_run(context: dict) -> HookResult:
    context["plugin_example_seen"] = True
    return CONTINUE


def register(hooks) -> None:
    hooks.on("pre_run", _pre_run, plugin_name="example-plugin")
```

Then inspect it with:

```bash
orchestro plugins
curl http://127.0.0.1:8765/plugins
```

## Canary And Live Smoke Examples

### Basic canary

```bash
PYTHONPATH=src python scripts/orchestro_canary.py \
  --backend mock \
  --goal "Reply with canary ok." \
  --json
```

### Auto-routing canary

```bash
PYTHONPATH=src python scripts/orchestro_canary.py \
  --backend auto \
  --goal "Review this repo for backend issues" \
  --json
```

### Inject a temporary usage-limit failure

```bash
PYTHONPATH=src python scripts/orchestro_canary.py \
  --backend auto \
  --goal "use claude to inspect the repo" \
  --inject-limit claude-code \
  --json
```

### Live backend smoke tests

```bash
ORCHESTRO_RUN_LIVE_BACKEND_TESTS=1 \
PYTHONPATH=src \
pytest -q tests/test_live_backends.py
```

You can limit which backends are checked:

```bash
ORCHESTRO_RUN_LIVE_BACKEND_TESTS=1 \
ORCHESTRO_LIVE_BACKENDS=codex,kilocode \
PYTHONPATH=src \
pytest -q tests/test_live_backends.py
```

For why these flows exist and how they fit the test strategy, see [Testing And Operations](testing-and-operations.md). For the underlying feature docs, also see [MCP](mcp.md), [LSP](lsp.md), [Plugins](plugins.md), [Collections](collections.md), and [Benchmarks](benchmarks.md).
