# MCP

Orchestro uses MCP in two directions:

- as an MCP client that can connect to external MCP servers and bridge their tools into Orchestro
- as an MCP server that exposes Orchestro memory and correction surfaces to other clients

## Table Of Contents

1. [Client Mode](#client-mode)
2. [Server Mode](#server-mode)
3. [Client Config](#client-config)
4. [Bridged Tool Behavior](#bridged-tool-behavior)
5. [Status And Troubleshooting](#status-and-troubleshooting)
6. [Current Server Tools And Resources](#current-server-tools-and-resources)

## Client Mode

The client implementation is in [`src/orchestro/mcp_client.py`](../src/orchestro/mcp_client.py).

It:

- loads MCP server configs from `mcp_servers.json`
- starts enabled servers as subprocesses
- performs `initialize`
- lists server tools
- bridges those tools into Orchestro as `mcp:<server>:<tool>`

Bridged tools are inserted into the main tool registry with `confirm` approval.

## Server Mode

The built-in MCP server is in [`src/orchestro/mcp_server.py`](../src/orchestro/mcp_server.py).

Run it with:

```bash
orchestro mcp-serve
```

Or via the script entrypoint:

```bash
orchestro-mcp
```

## Client Config

The client looks for:

```text
.orchestro/mcp_servers.json
```

Example:

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

Each server config supports:

- `name`
- `command`
- `args`
- `working_directory`
- `enabled`
- `env`

## Bridged Tool Behavior

Bridged tools are named:

```text
mcp:<server-name>:<tool-name>
```

They:

- appear in the Orchestro tool registry
- require approval
- accept JSON arguments when possible
- fall back to a raw `"input"` wrapper when the argument is not JSON

This behavior is implemented by `_make_mcp_runner(...)` in [`src/orchestro/mcp_client.py`](../src/orchestro/mcp_client.py).

## Status And Troubleshooting

Status surfaces:

- `orchestro mcp-status`
- `GET /mcp-status`

These expose:

- connected servers
- degraded servers
- `degraded_details`
- bridged tool counts

Common failure modes:

- command not found
- initialize timeout or protocol mismatch
- tool listing failure
- server stderr-only failures during startup

If a server is degraded, inspect `degraded_details` first. That is the point of truth the code now exposes.

## Current Server Tools And Resources

The built-in Orchestro MCP server currently exposes tools:

- `search_memory`
- `get_facts`
- `get_corrections`
- `record_correction`
- `get_postmortems`

And resources:

- `orchestro://facts`
- `orchestro://corrections`
- `orchestro://postmortems`

That surface is intentionally narrow and memory-oriented. It is not a full remote-control API for Orchestro.

For examples, see [Examples](examples.md#example-mcp-and-lsp-config). For plugin interactions, see [Plugins](plugins.md).
