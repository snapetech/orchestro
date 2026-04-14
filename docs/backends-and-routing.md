# Backends And Routing

This guide describes the backend types Orchestro supports, how `auto` routing works, and how temporary backend failures are handled.

## Table Of Contents

1. [Backend Families](#backend-families)
2. [Configured Default Backends](#configured-default-backends)
3. [Aliases And Model Selection](#aliases-and-model-selection)
4. [Auto Routing](#auto-routing)
5. [Cooldowns And Temporary Unavailability](#cooldowns-and-temporary-unavailability)
6. [Model Discovery](#model-discovery)
7. [Status Surfaces](#status-surfaces)
8. [Configuration Notes](#configuration-notes)

## Backend Families

Orchestro currently supports these categories:

- `MockBackend`: safe fallback for tests and smoke checks
- `OpenAICompatBackend`: local or remote OpenAI-compatible APIs
- `AnthropicBackend`: native Anthropic API integration
- `SubprocessCommandBackend`: custom command-based backend
- `AgentCLIBackend`: installed agent CLIs invoked as subprocesses

## Configured Default Backends

By default, the app registers:

- `mock`
- `openai-compat`
- `subprocess-command`
- `vllm-fast`
- `vllm-balanced`
- `vllm-coding`
- `ollama-amd`
- `claude-code`
- `codex`
- `kilocode`
- `cursor`
- `openai-gpt4o`
- `openai-gpt4o-mini`
- `anthropic-haiku`
- `anthropic-sonnet`
- `anthropic-opus`
- `openrouter`

Not all of these are reachable in every environment. Reachability depends on one of:

- binary present on `PATH`
- API key set
- base URL configured and local health check succeeding
- backend not currently cooled down

## Aliases And Model Selection

Examples of aliases:

- `claude` -> `claude-code`
- `codex` -> `codex`
- `kilo` -> `kilocode`
- `cursor` -> `cursor`
- `fast` -> `vllm-fast`
- `smart` or `balanced` -> `vllm-balanced`
- `code` or `coding` -> `vllm-coding`
- `local` -> `ollama-amd`

Per-run model selection now exists:

- routing can pick a specific model within a backend
- the selected model is attached to run metadata
- backend execution honors that model when the backend supports it

## Auto Routing

When `backend=auto`, Orchestro chooses a backend using:

1. reachable backends
2. alias hints in the goal
3. task signals such as coding or analysis
4. discovered model inventories
5. routing history collected from prior runs

Examples:

- coding-heavy requests can prefer coder-oriented backends or models
- analysis requests can prefer stronger reasoning models
- search/lightweight requests can prefer smaller or faster models

The routing decision is recorded as a `backend_auto_routed` event and is visible in:

- `orchestro show <run-id>`
- `GET /runs/{run_id}`
- `GET /backends`
- `scripts/orchestro_canary.py`

## Cooldowns And Temporary Unavailability

If an auto-routed backend fails with a quota or usage-limit style error, Orchestro can:

1. mark the backend temporarily unavailable
2. parse an `unavailable_until` time when the error message contains one
3. reroute to the next reachable backend
4. skip the unavailable backend until its cooldown expires

This is currently scoped to `auto` routing. If you explicitly request a backend by name, Orchestro does not silently switch providers behind your back.

Related run events:

- `backend_temporarily_unavailable`
- `backend_auto_rerouted`
- `retry_scheduled`

## Model Discovery

Backends can report available models:

- OpenAI-compatible backends: via `/models` where available
- Anthropic backends: configured model
- `cursor-agent`: best-effort model listing
- `kilocode`: best-effort model listing
- some agent CLIs may report no discoverable models even when they work

You can inspect discovered model inventories through:

- `orchestro backends`
- `GET /backends`
- `scripts/orchestro_canary.py --json`

## Status Surfaces

CLI:

- `orchestro backends`
- `orchestro mcp-status`
- `orchestro lsp-status`
- `orchestro plugins`

API:

- `GET /backends`
- `GET /mcp-status`
- `GET /lsp-status`
- `GET /plugins`

These surfaces expose degraded details instead of just “down/up” state.

## Configuration Notes

Useful environment variables are documented in [`.env.example`](../.env.example).

Important current defaults:

- Cursor backend name is `cursor`, but the binary default is `cursor-agent`
- Claude backend name is `claude-code`, but the binary default is `claude`
- Codex uses `codex exec`
- Kilocode uses `kilocode run`

For concrete command and config examples, see [Examples](examples.md). For validation and smoke workflows, see [Testing And Operations](testing-and-operations.md). For MCP/LSP-related setup, see [MCP](mcp.md) and [LSP](lsp.md).
