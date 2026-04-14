# LSP

Orchestro can connect to external language servers and expose diagnostics and symbol/navigation helpers through its tool registry.

## Table Of Contents

1. [What LSP Support Does](#what-lsp-support-does)
2. [Config File](#config-file)
3. [Supported Language Mapping](#supported-language-mapping)
4. [Available LSP Tools](#available-lsp-tools)
5. [Example Configs](#example-configs)
6. [Status And Troubleshooting](#status-and-troubleshooting)

## What LSP Support Does

The LSP client implementation lives in [`src/orchestro/lsp_client.py`](../src/orchestro/lsp_client.py).

When configured, Orchestro can register tools for:

- diagnostics
- definitions
- references
- hover
- document symbols
- workspace symbols

These are supplemental developer tools, not a replacement for an editor.

## Config File

The client looks for:

```text
.orchestro/lsp_servers.json
```

Example shape:

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

Supported fields:

- `name`
- `command`
- `args`
- `languages`
- `root_uri`
- `enabled`

## Supported Language Mapping

Current extension mapping:

- `.py` -> `python`
- `.rs` -> `rust`
- `.ts` -> `typescript`
- `.js` -> `javascript`
- `.go` -> `go`
- `.java` -> `java`
- `.c` / `.h` -> `c`
- `.cpp` / `.hpp` -> `cpp`

If a file extension is not mapped, Orchestro will not know which LSP server to use for it.

## Available LSP Tools

When at least one configured language is active, Orchestro can register:

- `lsp_diagnostics`
- `lsp_definition`
- `lsp_references`
- `lsp_hover`
- `lsp_symbols`
- `lsp_workspace_symbols`

These are added by the main tool registry when an `LSPManager` with supported languages is present.

## Example Configs

### Python

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

### TypeScript

```json
{
  "servers": [
    {
      "name": "typescript-language-server",
      "command": "typescript-language-server",
      "args": ["--stdio"],
      "languages": ["typescript", "javascript"],
      "enabled": true
    }
  ]
}
```

### Rust

```json
{
  "servers": [
    {
      "name": "rust-analyzer",
      "command": "rust-analyzer",
      "languages": ["rust"],
      "enabled": true
    }
  ]
}
```

These examples reflect the config shape Orchestro expects, not a guarantee that the language server is installed on your machine.

## Status And Troubleshooting

Status surfaces:

- `orchestro lsp-status`
- `GET /lsp-status`

They expose:

- configured servers
- active servers
- degraded servers
- `degraded_details`
- supported languages

Common issues:

- server binary not installed
- wrong `--stdio` args
- initialize request failure
- missing file extension mapping

If a server is degraded, use the exposed detail first before guessing.

For config examples, see [Examples](examples.md#example-mcp-and-lsp-config). For tool behavior, see [CLI Reference](cli-reference.md#tools-and-integrations).
