# Trust And Security

Orchestro is a local operator tool with powerful execution surfaces. This guide explains the practical trust model currently implemented in the codebase.

## Table Of Contents

1. [Threat Model](#threat-model)
2. [Tool Approval Model](#tool-approval-model)
3. [Trust Policy Model](#trust-policy-model)
4. [High-Risk Surfaces](#high-risk-surfaces)
5. [Recommended Operator Posture](#recommended-operator-posture)

## Threat Model

Orchestro is optimized for:

- one trusted operator
- one local machine or private environment
- inspectable local state

It is not a hardened multi-tenant platform.

That means:

- treat local tool execution as privileged
- treat API exposure as a trust boundary you own
- assume backends and tools can be powerful enough to modify files and run commands

## Tool Approval Model

Tools are declared with a base approval tier in the tool registry.

Current tiers:

- `auto`
- `confirm`
- `deny`

Implementation:

- tool registry: [`src/orchestro/tools.py`](../src/orchestro/tools.py)
- trust policy: [`src/orchestro/trust.py`](../src/orchestro/trust.py)
- approval-pattern store: [`src/orchestro/approvals.py`](../src/orchestro/approvals.py)

Persistent allow patterns are stored in:

```text
.orchestro/tool_approvals.json
```

Approval requests are also persisted in SQLite for background/shell flows.

## Trust Policy Model

Trust policy is stored in:

```text
.orchestro/trust.json
```

It supports:

- tool-specific overrides
- domain-specific overrides
- session overrides

Resolution order is effectively:

1. base tool tier
2. tool override
3. domain override
4. session override
5. any `deny` wins

## High-Risk Surfaces

Highest-risk tools:

- `bash`
- `edit_file`
- `git_commit`
- MCP-bridged tools from external servers

High-risk API endpoints:

- `POST /ask`
- `POST /ask/stream`
- `POST /tools/run`
- scheduling and approval mutation endpoints

High-risk shell usage:

- autonomous tool-loop runs with permissive approvals
- remembered wildcard approval patterns

## Recommended Operator Posture

- keep the API local unless you have a real isolation story
- keep `bash` and edit-like tools on `confirm` unless you know why to loosen them
- review remembered approval patterns periodically
- prefer sessions and plan workflows for longer tasks so you can inspect the event trail
- inspect `show`, run events, and approval queues when behavior seems surprising

Related docs:

- [API Operations](api-operations.md)
- [Shell Mode](shell.md)
- [MCP](mcp.md)
