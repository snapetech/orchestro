# Getting Started

This guide gets Orchestro running from a clean clone and points you to the docs you will need next.

## Table Of Contents

1. [Prerequisites](#prerequisites)
2. [Install](#install)
3. [Initialize Local State](#initialize-local-state)
4. [Choose Backends](#choose-backends)
5. [Run Basic Checks](#run-basic-checks)
6. [First Commands](#first-commands)
7. [Next Docs](#next-docs)

## Prerequisites

- Python 3.12+
- Git
- A Unix-like shell
- Optional live backends:
  - local OpenAI-compatible server
  - Anthropic API key
  - installed agent CLIs such as `claude`, `codex`, `kilocode`, `cursor-agent`

## Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

If you prefer the repo-local venv conventions already used by the project:

```bash
.venv/bin/python -m pytest -q
```

## Initialize Local State

Orchestro stores its runtime state under `.orchestro/` by default. Override with `ORCHESTRO_HOME` if you want a separate data root.

Create the two baseline files:

```bash
cp docs/global.md.example .orchestro/global.md
cp .env.example .env
```

What these are for:

- `.orchestro/global.md`: your local operator instructions
- `.env`: backend URLs, API keys, and optional agent CLI overrides

For backend-specific details, see [Backends And Routing](backends-and-routing.md).

## Choose Backends

Safe default:

- Use `mock` or `auto`
- Keep `.env` mostly unchanged

If you want live routing:

- configure local OpenAI-compatible servers in `.env`
- or install one or more agent CLIs
- or set API keys for Anthropic/OpenAI/OpenRouter-compatible backends

Useful checks:

```bash
orchestro backends
curl http://127.0.0.1:8765/backends
```

## Run Basic Checks

Full test suite:

```bash
PYTHONPATH=src pytest -q
```

Daily-driver canary:

```bash
PYTHONPATH=src python scripts/orchestro_canary.py --backend mock --goal "Reply with canary ok." --json
```

Optional live backend smoke:

```bash
ORCHESTRO_RUN_LIVE_BACKEND_TESTS=1 PYTHONPATH=src pytest -q tests/test_live_backends.py
```

More operational checks are in [Testing And Operations](testing-and-operations.md).

## First Commands

Run one request:

```bash
orchestro ask "Summarize the repo" --backend auto
```

Inspect recent runs:

```bash
orchestro runs --limit 5
orchestro show <run-id>
```

Start the shell:

```bash
orchestro shell --backend auto
```

Start the TUI:

```bash
pip install -e .[tui]
orchestro tui --backend auto
```

Start the API:

```bash
orchestro serve --host 127.0.0.1 --port 8765
```

For concrete command examples, see [Examples](examples.md). For a grouped command index, see [CLI Reference](cli-reference.md).

## Next Docs

- Want command coverage: [CLI Reference](cli-reference.md)
- Want shell-specific usage: [Shell Mode](shell.md)
- Want the full-screen operator direction: [TUI Vision](tui.md) and [TUI Implementation Plan](tui-plan.md)
- Want HTTP usage: [API Reference](api-reference.md)
- Want to run the API persistently and safely: [API Operations](api-operations.md)
- Want backend setup and routing behavior: [Backends And Routing](backends-and-routing.md)
- Want examples you can copy: [Examples](examples.md)
- Want operations and test flows: [Testing And Operations](testing-and-operations.md)
