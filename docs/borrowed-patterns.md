# Borrowed Patterns

Patterns identified from the claw-code-parity project (a ~48K LOC Rust rewrite of Claude Code's agent harness) that address gaps in Orchestro's current implementation or roadmap.

Each section describes what the pattern is, why it matters for Orchestro, and how it should be implemented within Orchestro's existing architecture and principles.

## 1. Recovery Recipes and Failure Taxonomy

### What claw does

Claw defines 7 typed `FailureScenario` variants, each mapping to a multi-step `RecoveryRecipe` with max-attempt tracking. When a failure occurs, the system gets one automatic recovery attempt before escalating. Recovery steps are emitted as structured events.

The failure scenarios are typed and categorized: backend timeout, tool crash, permission denied, context overflow, stale branch, build failure, test failure. Each has a distinct recipe with ordered steps.

### Why Orchestro needs this

Orchestro currently has `reflect-retry` as a single-shot mechanism and postmortem recording for failed runs. There is no structured categorization of failures beyond the basic postmortem categories (`timeout`, `tool`, `backend`, `workspace`, `general`), no per-category recovery logic, no escalation path, and no attempt tracking.

When a tool-loop run fails, the system either retries with a generic reflection or gives up. There is no way to say "this is a backend timeout, try a different backend" versus "this is a tool crash, retry with a simpler approach" versus "this is a context overflow, compact and retry."

### How to implement

Add a `recovery.py` module alongside the existing orchestrator.

Define typed failure categories as an enum or string set that extends the existing postmortem categories:

- `backend_timeout` — backend did not respond within expected time
- `backend_unreachable` — backend health check failed during run
- `tool_crash` — tool execution raised an exception
- `tool_output_invalid` — tool returned unparseable output
- `context_overflow` — prompt exceeded backend context window
- `strategy_exhausted` — reflect-retry or tool-loop hit max steps without resolution
- `approval_timeout` — operator did not resolve an approval request in time
- `workspace_conflict` — file was modified externally during a run

Define a `RecoveryRecipe` as an ordered list of recovery steps:

- `retry_same` — retry with same backend and strategy
- `retry_different_backend` — select next backend in fallback chain
- `compact_context` — summarize context and retry
- `simplify_strategy` — fall back from tool-loop to reflect-retry to direct
- `escalate` — pause the run, notify the operator, wait for input
- `abandon` — mark run as failed, record postmortem

Each failure category maps to a recipe. Example:

- `backend_timeout` → `retry_same` (once) → `retry_different_backend` → `escalate`
- `context_overflow` → `compact_context` → `retry_same` → `escalate`
- `tool_crash` → `retry_same` (once) → `simplify_strategy` → `escalate`
- `strategy_exhausted` → `escalate`

Track recovery attempts per run in a `recovery_attempts` column on the `runs` table or in `run_events`. The recovery engine should:

1. Classify the failure using the typed categories.
2. Look up the recipe for that category.
3. Check how many recovery attempts have been made for this run.
4. Execute the next step in the recipe, or escalate if the recipe is exhausted.
5. Emit a structured `recovery_attempted` event with the failure category, step taken, and attempt number.

This should integrate with the existing postmortem system: when escalation happens, the postmortem should include the full recovery trace.

### Database changes

Add columns or a new table:

```sql
ALTER TABLE runs ADD COLUMN failure_category TEXT;
ALTER TABLE runs ADD COLUMN recovery_attempts INTEGER DEFAULT 0;
```

Or use `run_events` with event type `recovery_attempted` and a JSON payload containing the category, step, and attempt number.

### Integration points

- `Orchestro.execute_prepared_run()` — wrap the execution path with failure classification and recovery dispatch
- `_auto_postmortem()` — enrich with failure category and recovery trace
- `decide_auto_backend()` — called by the `retry_different_backend` step

## 2. Plugin System with Hooks

### What claw does

Claw has a full `PluginManager` with install, enable, disable, uninstall lifecycle. Plugins are discovered from a directory, have metadata (name, version, capabilities), and register hooks. The hook system supports `PreToolUse`, `PostToolUse`, and `PostToolUseFailure` events. Hooks can abort execution, modify context, or emit progress events. There is also a `PluginRegistry` for bundled plugins and a health-check system for degraded plugins.

### Why Orchestro needs this

Orchestro has no extensibility mechanism. Adding a new backend requires editing `backend_profiles.py`. Adding a new tool requires editing `tools.py`. Adding a new context provider requires editing the orchestrator. Adding custom postprocessing or validation requires editing the execution path.

This matters because the architecture document already describes future extension points (verifiers, new strategies, knowledge collection ingesters, domain constitutions) that would benefit from a plugin interface rather than direct source modification.

### How to implement

Add a `plugins.py` module. Keep it lightweight — this is Python, not Rust.

Define hook points as string constants:

- `pre_run` — before a run starts execution (can modify context, select strategy)
- `post_run` — after a run completes (can trigger postmortem enrichment, auto-rating)
- `pre_tool` — before a tool call executes (can block, modify args, require approval)
- `post_tool` — after a tool call returns (can transform output, trigger side effects)
- `on_failure` — when a run fails (can attempt recovery, enrich postmortem)
- `on_plan_step` — when a plan step is about to execute (can inject guidance)

A plugin is a Python module in `.orchestro/plugins/` with a `register` function:

```python
def register(hooks):
    hooks.on("pre_tool", my_pre_tool_handler)
    hooks.on("post_run", my_post_run_handler)
```

The `HookRunner` collects registered handlers per hook point and calls them in registration order. Each handler receives a context dict and returns a result that can:

- `continue` — proceed normally
- `abort` — stop execution with a reason
- `modify` — replace the context dict with a modified version

The plugin system should be opt-in. If `.orchestro/plugins/` does not exist or is empty, no plugins load and there is zero overhead.

### What this enables

- Custom verifiers as plugins (Phase 4 of the roadmap)
- Custom context providers (knowledge collection ingesters)
- Custom approval logic (beyond fnmatch patterns)
- Notification hooks (send a message when a long run finishes)
- Metric collection plugins
- Domain-specific postprocessors

### Integration points

- `Orchestro.__init__()` — discover and load plugins
- `Orchestro.execute_prepared_run()` — call `pre_run` and `post_run` hooks
- Tool execution in the tool-loop — call `pre_tool` and `post_tool` hooks
- Failure handling — call `on_failure` hooks

## 3. Policy and Automation Engine

### What claw does

Claw has a declarative `PolicyEngine` with composable conditions (`And`, `Or`, `GreenAt`, `StaleBranch`, `StartupBlocked`) and actions (`MergeToDev`, `MergeForward`, `RecoverOnce`, `Escalate`, `CloseoutLane`). Policies are evaluated against the current system state and trigger automated actions without operator intervention.

### Why Orchestro needs this

Orchestro's approval system is basic fnmatch patterns. The operator must manually approve tool calls, manually rate runs, manually trigger reindexing, and manually manage background jobs. There is no way to express rules like "auto-approve all git read-only commands" or "auto-rate runs that complete successfully with expected output" or "auto-escalate to a stronger backend after two failures."

The policy engine would bridge the gap between Orchestro's current manual-approval model and the autonomous operation needed for background and scheduled work.

### How to implement

Add a `policies.py` module.

Define policies as YAML or JSON in `.orchestro/policies.yaml`:

```yaml
policies:
  - name: auto-approve-readonly
    when:
      tool: bash
      args_match: "git log*|git status*|git diff*|ls *|cat *|rg *"
    action: auto-approve

  - name: escalate-repeated-failures
    when:
      run_status: failed
      failure_count_gte: 3
      same_failure_category: true
    action: escalate-backend

  - name: auto-index-good-runs
    when:
      run_status: completed
      has_rating: true
      rating_gte: 4
    action: queue-embedding

  - name: auto-postmortem-failures
    when:
      run_status: failed
      strategy: tool-loop
    action: record-postmortem

  - name: compact-on-overflow
    when:
      failure_category: context_overflow
    action: compact-and-retry
```

The policy engine evaluates conditions against event payloads and run metadata. Actions map to existing Orchestro functions:

- `auto-approve` → resolve approval request automatically
- `escalate-backend` → rerun with next backend in fallback chain
- `queue-embedding` → call `queue_embeddings()` for the interaction
- `record-postmortem` → call `_auto_postmortem()`
- `compact-and-retry` → summarize context and rerun

Policy evaluation should happen at defined trigger points:

- After a tool call requests approval → evaluate tool-approval policies
- After a run completes → evaluate post-run policies
- After a run fails → evaluate failure policies
- On a timer or idle check → evaluate maintenance policies

### Integration points

- Approval resolution in shell jobs — check policies before prompting operator
- `execute_prepared_run()` — evaluate post-run and failure policies
- The existing `tool_approvals.json` becomes one input to the policy engine rather than the entire approval system

## 4. Session Persistence and Forking

### What claw does

Claw has JSONL-based session persistence with rotation at 256KB, compaction (summarizing old messages to stay within context limits), and forking (branching a session with parent provenance tracking). Sessions can be resumed across process restarts. Compaction replaces old conversation turns with a compressed summary while preserving recent context.

### Why Orchestro needs this

Orchestro tracks individual runs in SQLite but has no concept of a session that spans multiple related runs. Each shell invocation starts fresh. There is no way to:

- Resume a multi-run investigation across shell restarts
- Fork a conversation to try two approaches from the same starting point
- Compact a long session to stay within model context limits
- Track which runs are part of the same logical task

The plan system partially addresses this (plans group related steps), but plans are task-scoped. Sessions would be broader — tracking an entire working session with its context, decisions, and branches.

### How to implement

Add a `sessions` table:

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    parent_session_id TEXT,
    fork_point_run_id TEXT,
    title TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'active',
    summary TEXT,
    context_snapshot TEXT
);
```

Link runs to sessions:

```sql
ALTER TABLE runs ADD COLUMN session_id TEXT REFERENCES sessions(id);
```

Add session management to the shell:

- `/session` — show current session info
- `/session new [title]` — start a new session
- `/session resume [id]` — resume a previous session
- `/session fork` — fork the current session from the current point
- `/session list` — list recent sessions
- `/session compact` — summarize old context in the current session

Session compaction should:

1. Collect all run goals and outputs in the session up to a cutoff point.
2. Send them to the model with a summarization prompt.
3. Store the summary as the session's `context_snapshot`.
4. Inject the snapshot as context for subsequent runs instead of the full history.

Forking should:

1. Create a new session with `parent_session_id` set.
2. Copy the context snapshot up to the fork point.
3. Allow independent continuation from both the original and forked session.

### Integration points

- `Orchestro.start_run()` — attach session_id to new runs
- Context assembly — include session context_snapshot when building run context
- Shell startup — offer to resume the most recent active session

## 5. Model Aliases

### What claw does

Claw maps short aliases to full model identifiers: `opus` → `claude-opus-4-6`, `sonnet` → `claude-sonnet-4-6`, `grok` → `grok-3`. The user types `--model sonnet` and the system resolves it.

### Why Orchestro needs this

Orchestro has backend profiles with names like `vllm-coding`, `ollama-amd`, but the user must know the full backend name. There is no alias layer that maps intent to backend+model combinations.

This is a small quality-of-life improvement that reduces friction for the most common operation: choosing which model to use.

### How to implement

Add an `aliases` section to backend profiles or a separate `.orchestro/aliases.yaml`:

```yaml
aliases:
  fast: {backend: ollama-amd, model: qwen2.5-coder:7b}
  smart: {backend: vllm-coding, model: qwen2.5-coder:32b}
  code: {backend: vllm-coding, model: deepseek-coder-v2}
  reason: {backend: vllm-balanced, model: qwen3-30b-a3b}
  local: {backend: ollama-amd}
  strong: {backend: vllm-balanced}
```

Resolution order:

1. Check if the name is a known alias → resolve to backend+model.
2. Check if the name is a known backend profile → use as-is.
3. Check if the name matches a model name on any reachable backend → auto-select.
4. Fail with a helpful message listing available aliases and backends.

Add `--model` / `-m` flag to `orchestro ask` and the shell's default input that accepts aliases.

### Integration points

- `decide_auto_backend()` — check aliases before keyword heuristics
- CLI argument parsing — resolve aliases early
- Shell `/backends` command — show aliases alongside profiles

## 6. Worker State Machine

### What claw does

Claw's `WorkerStatus` follows a formal lifecycle: `Spawning` → `TrustRequired` → `ReadyForPrompt` → `PromptAccepted` → `Running` → `Finished/Failed`. Transitions are explicit and validated. Events are emitted on every state change. There is trust-gate auto-resolution and prompt-misdelivery detection.

### Why Orchestro needs this

Orchestro's shell jobs track status as simple strings (`pending`, `running`, `paused`, `done`, `failed`, `cancelled`). There is no validation of state transitions — a job could theoretically go from `paused` to `done` without passing through `running`. There is no event emission on state changes, no trust gate concept, and no formal lifecycle.

This matters as background job complexity grows. With recovery recipes, policy-driven automation, and session management, the system needs reliable state tracking to avoid race conditions and invalid transitions.

### How to implement

Add a `job_states.py` module with an explicit state machine.

Define states:

- `pending` — job created, not yet started
- `waiting_approval` — job needs operator approval before proceeding (trust gate)
- `running` — actively executing
- `paused` — operator or policy paused execution
- `waiting_input` — job is blocked on operator input injection
- `recovering` — automatic recovery in progress after a failure
- `completed` — finished successfully
- `failed` — finished with error, recovery exhausted
- `cancelled` — operator cancelled

Define valid transitions:

```
pending → running
pending → waiting_approval
pending → cancelled
waiting_approval → running
waiting_approval → cancelled
running → paused
running → waiting_input
running → completed
running → failed
running → recovering
running → cancelled
paused → running
paused → cancelled
waiting_input → running
waiting_input → cancelled
recovering → running
recovering → failed
recovering → cancelled
```

The state machine should:

1. Validate every transition before allowing it.
2. Emit a `shell_job_event` with type `state_changed` on every transition.
3. Include the previous state, new state, and reason in the event payload.
4. Reject invalid transitions with a clear error.

The `waiting_approval` state replaces the current approval-request polling pattern with a proper state gate. When a tool call needs approval, the job transitions to `waiting_approval`. When the operator resolves the approval, the job transitions back to `running`.

### Integration points

- `OrchestroDB.update_shell_job_status()` — enforce valid transitions
- Shell job management commands — display state with transition history
- Recovery recipes — use the `recovering` state during automatic recovery
- Policy engine — evaluate policies on state transitions

## 7. MCP Client Integration

### What claw does

Claw has a 2,894-line MCP stdio implementation with full JSON-RPC 2.0, tool and resource discovery, lifecycle management, and degraded-startup reporting. MCP servers are configured in the project config, started as child processes, and their tools are bridged into the main tool registry. If an MCP server fails to start, the system continues in degraded mode with a report of what is missing.

### Why Orchestro needs this

MCP client support is already on the roadmap (Phase 8), but the current framing is "MCP wraps existing Orchestro functions" (server mode). What claw demonstrates is the value of MCP *client* mode — consuming tools from external MCP servers.

For Orchestro's local-first philosophy, MCP client support is especially powerful. The operator could run specialized MCP servers on the LAN (database access, file system tools, home automation, calendar integration) and Orchestro would discover and use their tools without any changes to the core tool registry.

### How to implement

Add an `mcp_client.py` module.

Support stdio transport first (consistent with the roadmap). An MCP server is a child process that communicates over stdin/stdout using JSON-RPC 2.0.

Configuration in `.orchestro/mcp_servers.yaml`:

```yaml
servers:
  filesystem:
    command: npx
    args: [-y, "@modelcontextprotocol/server-filesystem", "/home/keith"]
    enabled: true

  sqlite:
    command: npx
    args: [-y, "@modelcontextprotocol/server-sqlite", ".orchestro/orchestro.db"]
    enabled: true

  custom-tools:
    command: python
    args: ["-m", "my_mcp_server"]
    working_directory: /home/keith/projects/my-tools
    enabled: true
```

The MCP client lifecycle:

1. On shell startup, read the server config.
2. Start each enabled server as a subprocess.
3. Send `initialize` request, negotiate capabilities.
4. Call `tools/list` to discover available tools.
5. Bridge discovered tools into the tool registry with an `mcp:` prefix.
6. When the agent calls an MCP tool, forward the call via `tools/call` JSON-RPC.
7. On shell exit, send shutdown notifications and terminate child processes.

Degraded startup: if a server fails to start or times out during initialization, log the failure, skip that server, and continue. Report degraded servers in the shell status.

### What this enables

- Consuming tools from the MCP ecosystem without modifying Orchestro
- Running specialized tool servers on different machines on the LAN
- Sharing tools between Orchestro and other MCP-compatible clients
- Gradual tool expansion without bloating the core codebase

### Integration points

- Shell startup/shutdown — start and stop MCP server processes
- `ToolRegistry` — merge MCP-discovered tools alongside built-in tools
- Tool execution in tool-loop — dispatch MCP tool calls through the client
- `/tools` shell command — show MCP tools with their server of origin
- Backend routing — some MCP tools may prefer specific backends

## 8. Command Registry Pattern

### What claw does

Claw has 25+ slash commands in a dedicated `commands` crate with a registry pattern. Each command has metadata (name, aliases, description, category) and a structured handler. Commands are discoverable, categorized, and can be provided by plugins.

### Why Orchestro needs this

Orchestro's `cli.py` is 2,960 lines — the largest file in the project. The shell class has 50+ `do_*` methods mixed with helper methods, argument parsing, output formatting, and state management. Adding a new command means editing this monolith.

Refactoring to a command registry would:

- Make each command self-contained and testable
- Enable plugin-provided commands
- Make help text auto-generated from metadata
- Reduce the cognitive load of working on the shell
- Make it easier to share commands between the CLI and the interactive shell

### How to implement

Add a `commands/` package:

```
src/orchestro/commands/
├── __init__.py          # CommandRegistry, auto-discovery
├── base.py              # Command base class / protocol
├── ask.py               # /ask, default input
├── runs.py              # /runs, /show, /rate
├── plans.py             # /plan, /plan_run, /replan
├── tools.py             # /tools, /tool_run
├── jobs.py              # /bg, /jobs, /fg, /wait, /cancel, /pause, /resume
├── memory.py            # /facts, /corrections, /interactions, /search
├── bench.py             # /bench, /bench_matrix, /benchmark_compare
├── backends.py          # /backends
├── context.py           # /context
├── approvals.py         # /approve, /approval_requests
└── session.py           # /session (new, from pattern 4)
```

Each command module defines one or more command classes:

```python
class RunsCommand:
    name = "runs"
    aliases = ["history"]
    category = "inspection"
    help = "List recent runs with status and ratings."

    def execute(self, shell, args):
        ...
```

The `CommandRegistry` discovers commands from the package and from plugins, resolves aliases, and dispatches. The shell's `default()` and `do_*` methods become thin wrappers that delegate to the registry.

### Migration path

This is a refactor, not a rewrite. Migrate one command group at a time:

1. Create the registry infrastructure and base class.
2. Move one simple command group (e.g., `/backends`) to validate the pattern.
3. Migrate remaining groups incrementally.
4. Keep the shell class as the REPL host but with most logic delegated.

### Integration points

- Shell initialization — register built-in and plugin commands
- Plugin system — plugins can register commands through hooks
- Help system — auto-generate help from command metadata
- Tab completion — derive completions from the registry

## 9. LSP Integration

### What claw does

Claw has a 746-line LSP client registry providing symbols, references, diagnostics, definition, and hover lookups. LSP servers are managed as child processes with a registry tracking server capabilities per language.

### Why Orchestro needs this

Orchestro's coding tools are limited to `rg` (ripgrep), `read_file`, and `bash`. There is no code intelligence — no way to jump to a definition, find all references to a symbol, get hover documentation, or check diagnostics without running the full build.

For Orchestro's intended use as a coding assistant on local hardware, LSP integration would dramatically improve the quality of code-related runs by giving the model structured code intelligence instead of relying on text search.

### How to implement

Add an `lsp_client.py` module.

LSP servers are long-running child processes that communicate over stdio using JSON-RPC (same transport as MCP, different protocol).

Configuration in `.orchestro/lsp_servers.yaml`:

```yaml
servers:
  python:
    command: pyright-langserver
    args: [--stdio]
    languages: [python]
    root_uri: /home/keith/Documents/code

  rust:
    command: rust-analyzer
    args: []
    languages: [rust]
    root_uri: /home/keith/Documents/code

  typescript:
    command: typescript-language-server
    args: [--stdio]
    languages: [typescript, javascript]
```

Expose LSP capabilities as tools:

- `lsp_diagnostics(file)` — get errors and warnings for a file
- `lsp_definition(file, line, col)` — jump to definition
- `lsp_references(file, line, col)` — find all references
- `lsp_hover(file, line, col)` — get type info and docs
- `lsp_symbols(file)` — list symbols in a file
- `lsp_workspace_symbols(query)` — search symbols across the project

LSP servers should be started lazily — only when a tool call targets a language that has a configured server.

### Integration points

- `ToolRegistry` — register LSP tools alongside built-in tools
- Context assembly — optionally include diagnostics for files being edited
- Recovery recipes — use diagnostics to classify build failures
- Shell `/tools` command — show available LSP capabilities

## 10. Quality Contract

### What claw does

Claw has a `GreenContract` with 4 levels of "greenness" (targeted → merge-ready) that represents confidence in code quality. The policy engine uses these levels to make automated decisions about merging, escalation, and lane management.

### Why Orchestro needs this

Orchestro has no structured way to express confidence in run outputs. A run either succeeds or fails. There is no gradient between "the model produced something" and "this output has been verified and is ready to use."

A quality contract would let the system and the operator communicate about output reliability, drive automatic review routing, and enable the policy engine to make better decisions.

### How to implement

Define quality levels for run outputs:

- `unverified` — model produced output, no checks applied
- `self-checked` — model reviewed its own output (critique pass)
- `tool-verified` — a verifier or test confirmed correctness
- `operator-reviewed` — operator rated the output positively
- `operator-edited` — operator corrected the output (highest signal)

Add a `quality_level` column to the `runs` table:

```sql
ALTER TABLE runs ADD COLUMN quality_level TEXT DEFAULT 'unverified';
```

Quality level should be updated automatically:

- After a `CritiqueRevise` strategy completes → `self-checked`
- After a verifier passes → `tool-verified`
- After an operator rates ≥ 4 → `operator-reviewed`
- After an operator provides an edit → `operator-edited`

The policy engine can use quality levels:

```yaml
policies:
  - name: skip-review-for-verified
    when:
      quality_level: tool-verified
      strategy: Verified
    action: auto-approve-output

  - name: require-review-for-unverified
    when:
      quality_level: unverified
      affects_files: true
    action: require-operator-review
```

The benchmark system can report quality level distributions across runs.

### Integration points

- `Orchestro.execute_prepared_run()` — set initial quality level based on strategy
- Verifier execution — upgrade quality level on pass
- Rating flow — upgrade quality level on positive rating
- Policy engine — evaluate quality-level conditions
- Benchmark comparison — include quality level metrics

## Implementation Priority

Recommended build order based on impact, effort, and dependency chain:

| Order | Pattern | Reason |
|-------|---------|--------|
| 1 | Recovery recipes | Directly improves existing failure handling with minimal new infrastructure |
| 2 | Model aliases | Small effort, immediate daily-use improvement |
| 3 | Worker state machine | Foundational for recovery recipes, policies, and session management |
| 4 | Plugin system | Enables extensibility for everything that follows |
| 5 | Policy engine | Builds on recovery recipes and state machine; enables autonomous operation |
| 6 | Session persistence | Improves multi-run workflows; builds on run tracking infrastructure |
| 7 | Command registry | Refactor that unblocks plugin-provided commands and reduces cli.py complexity |
| 8 | MCP client | High value but high effort; depends on stable tool registry |
| 9 | Quality contract | Most useful after verifiers exist (Phase 4 of roadmap) |
| 10 | LSP integration | High effort, best tackled after MCP client proves the child-process tool pattern |

## Relationship to Existing Roadmap

These patterns map onto the existing roadmap phases:

- **Phase 3 (Strategy Layer)**: Recovery recipes, quality contract
- **Phase 3.5 (Agentic Shell)**: Worker state machine, session persistence, command registry
- **Phase 4 (Verifiers)**: Plugin system (verifiers as plugins), quality contract
- **Phase 8 (MCP)**: MCP client integration
- **Phase 9 (Additional Backends)**: Model aliases, policy engine for backend routing

The patterns do not replace roadmap phases. They add implementation specificity to phases that were described at a goals level and fill gaps between phases that were not previously addressed (recovery, plugins, policies, sessions).
