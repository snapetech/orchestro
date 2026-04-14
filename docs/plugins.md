# Plugins

Orchestro plugins are local Python files that register hook handlers into the run and tool lifecycle.

## Table Of Contents

1. [What A Plugin Is](#what-a-plugin-is)
2. [Where Plugins Live](#where-plugins-live)
3. [Plugin File Shape](#plugin-file-shape)
4. [Available Hooks](#available-hooks)
5. [Error Handling](#error-handling)
6. [Example Plugin](#example-plugin)
7. [Operational Notes](#operational-notes)

## What A Plugin Is

A plugin is a Python file loaded from the Orchestro data directory. It can:

- register hook handlers
- inspect or annotate lifecycle context
- abort or modify a flow through hook return values

The current implementation lives in [`src/orchestro/plugins.py`](../src/orchestro/plugins.py).

## Where Plugins Live

By default, plugins live under:

```text
.orchestro/plugins/
```

If `ORCHESTRO_HOME` is set, the plugin directory becomes:

```text
$ORCHESTRO_HOME/plugins/
```

Each plugin is a `.py` file. Files starting with `_` are ignored.

## Plugin File Shape

Expected pieces:

- optional `METADATA`
- optional `register(hooks)` function

`METADATA` should be a `PluginMetadata` instance. `register(hooks)` receives the shared `HookRunner`.

## Available Hooks

Defined hooks:

- `pre_run`
- `post_run`
- `pre_tool`
- `post_tool`
- `on_failure`
- `on_plan_step`

Handlers can return:

- `CONTINUE`
- `HookResult("abort", ...)`
- `HookResult("modify", data={...})`

`modify` updates the shared context dict passed through the hook runner.

## Error Handling

Plugin errors do not currently crash the whole app by default. They are captured into:

- `PluginManager.load_errors`
- `HookRunner.last_errors`

You can inspect them with:

- `orchestro plugins`
- `GET /plugins`

This means you should treat plugin code as production code anyway. Silent behavior changes are worse than obvious failures.

## Example Plugin

```python
from __future__ import annotations

from orchestro.plugins import CONTINUE, HookResult, PluginMetadata

METADATA = PluginMetadata(
    name="safety-tag",
    version="0.1.0",
    description="Annotates run context with a local tag.",
)


def _pre_run(context: dict) -> HookResult:
    context["local_tag"] = "daily-driver"
    return CONTINUE


def _on_failure(context: dict) -> HookResult:
    context["plugin_failure_seen"] = True
    return CONTINUE


def register(hooks) -> None:
    hooks.on("pre_run", _pre_run, plugin_name="safety-tag")
    hooks.on("on_failure", _on_failure, plugin_name="safety-tag")
```

Place that in `.orchestro/plugins/safety_tag.py`, then run:

```bash
orchestro plugins
curl http://127.0.0.1:8765/plugins
```

## Operational Notes

- Keep plugin side effects explicit and local.
- Avoid long-running network work in hooks unless you want that latency in the core run path.
- Prefer annotation and validation over hidden mutation.
- If a plugin changes operator-visible behavior, add a note in [Examples](examples.md) or the relevant feature doc.

For related integration surfaces, see [MCP](mcp.md), [Shell Mode](shell.md), and [API Reference](api-reference.md).
