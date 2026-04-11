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

### 7.1 MCP as Memory Server (bidirectional)

The roadmap's Phase 8 frames MCP as a wrapper that exposes Orchestro functions to external clients. This is the more important direction: Orchestro becomes the *memory provider* for the entire local AI ecosystem.

Any MCP-compatible client — Claude Code, Claude Desktop, or any agent — could query Orchestro's corrections, facts, postmortems, and domain constitutions as context. Personal operator knowledge ("always use `--dry-run` first for rsync", "this codebase expects snake_case for test functions") accumulated in Orchestro becomes available to every agent, not just Orchestro sessions.

Implement as a FastAPI MCP endpoint layer on top of the existing REST API:

```python
# Expose as MCP resource endpoints
GET /mcp/resources/corrections?domain=coding
GET /mcp/resources/facts
GET /mcp/resources/constitutions/{domain}
GET /mcp/resources/postmortems?limit=5

# Expose as MCP tool endpoints
POST /mcp/tools/search_memory        # lexical search over interactions/corrections
POST /mcp/tools/record_correction    # propose a correction from external agent
POST /mcp/tools/get_context          # assembled context bundle for a domain
```

The MCP server mode and client mode are independent and can coexist. The client consumes external tools; the server publishes Orchestro's memory. Together they make Orchestro the central knowledge node in a local multi-agent setup — the place where corrections accumulate across all tools and sessions.

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

## 11. Agent Autonomy Layer

Patterns 1-10 are discrete features. This section describes the meta-pattern they compose into: a full agent autonomy layer that lets Orchestro operate unattended for extended periods — starting work, making decisions, recovering from failures, coordinating sub-agents, and knowing when to stop and ask for help.

Orchestro's current thesis is *operator leverage* — the human stays in the loop but gets more done. The autonomy layer does not replace that thesis. It extends it: the operator should be able to set direction, walk away, and come back to useful results or a clear escalation, not a silently stalled job.

### 11.1 Autonomous Run Mode

#### What claw does

Claw's `ConversationRuntime::run_turn()` is a fully autonomous execution loop: push input → stream API → process response → for each tool use: run pre-hook → check permissions → execute → run post-hook → push results → loop until done or max iterations. Auto-compaction fires when token count crosses a threshold. No human input is required at any step when permissions are pre-configured.

#### Why Orchestro needs this

Orchestro's tool-loop strategy already approximates this, but it has two hard blocks on autonomy:

1. **Approval gates**: any `bash` call that does not match an fnmatch pattern blocks the entire run until the operator resolves it. For unattended work, this means the agent stalls silently.
2. **No context management**: there is no compaction. A long-running tool-loop run will eventually exceed the backend context window and crash.

#### How to implement

Add an `autonomous` flag to runs (set via `--autonomous` on `orchestro ask` or `/bg --autonomous` in the shell):

```python
class RunRequest:
    autonomous: bool = False
    max_iterations: int = 20
    max_wall_time: int = 3600  # seconds
    escalation_channel: str = "shell"  # or "webhook", "file"
```

When `autonomous=True`:

- The policy engine evaluates tool approvals before prompting. If no policy matches, the default is `escalate` rather than `block`.
- Auto-compaction fires when context usage crosses 75% of the backend's declared context window.
- A wall-clock watchdog enforces `max_wall_time`. On timeout, the run transitions to `failed` with `failure_category=timeout` and the recovery engine takes over.
- Max iterations are enforced per the existing tool-loop limit but with a configurable ceiling.
- Escalation events are emitted through the configured channel rather than blocking on stdin.

This is not "give the agent full access." It is "give the agent pre-approved access via policies, and escalate everything else cleanly."

### 11.2 Trust Resolution and Safety Tiers

#### What claw does

Claw has a three-tier `TrustPolicy`: `AutoTrust` (fully autonomous), `RequireApproval` (escalate to human), `Deny` (hard block). A `TrustResolver` evaluates the working directory against allowlisted and denied root paths. Workers in trusted directories get `trust_auto_resolve=true` and clear trust gates automatically.

Separately, a `PermissionEnforcer` layers workspace-boundary checks on top: even with full trust, writes cannot escape the workspace, and destructive bash commands require explicit permission.

#### Why Orchestro needs this

Orchestro's approval system is flat — every tool call is either pattern-matched or prompted. There is no concept of "this workspace is trusted, auto-approve reads and bounded writes" versus "this workspace is untrusted, prompt for everything." For autonomous operation, the system needs a way to express graduated trust without enumerating every possible tool invocation.

#### How to implement

Add a `trust.py` module.

Define trust tiers for workspaces:

- `full` — auto-approve all tool calls within workspace boundaries. The agent can read, write, run tests, and commit without asking.
- `standard` — auto-approve reads and bounded writes (files within workspace). Prompt for bash commands that modify state outside the working tree, network access, or destructive operations.
- `readonly` — auto-approve reads only. All writes and bash commands require approval or policy match.
- `untrusted` — prompt for everything. No auto-approvals.

Configuration in `.orchestro/trust.yaml`:

```yaml
workspaces:
  /home/keith/Documents/code/orchestro:
    trust: full

  /home/keith/Documents/code/*:
    trust: standard

  /tmp/*:
    trust: readonly

default: untrusted
```

The trust tier feeds into the policy engine as a condition:

```yaml
policies:
  - name: trusted-workspace-writes
    when:
      trust_tier: full
      tool: [read_file, bash, rg]
    action: auto-approve

  - name: standard-workspace-reads
    when:
      trust_tier: standard
      tool: [read_file, rg]
    action: auto-approve

  - name: standard-workspace-bash-readonly
    when:
      trust_tier: standard
      tool: bash
      args_match: "git log*|git status*|git diff*|ls *|rg *|cat *|head *|tail *"
    action: auto-approve
```

Add a workspace boundary enforcer that prevents path traversal regardless of trust tier. Even `full` trust should not allow writes outside the declared workspace root.

### 11.3 Scheduled and Recurring Autonomous Work

#### What claw does

Claw has a `CronRegistry` with cron-expression scheduling, per-entry enable/disable, run counting, and last-run tracking. Cron entries create tasks from `TaskPacket` structs — structured work orders with objectives, scope, acceptance tests, commit policies, and escalation policies. The tools crate exposes `CronCreate`, `CronDelete`, `CronList` as agent-callable tools.

#### Why Orchestro needs this

Orchestro has no scheduling capability. Every run is initiated by the operator typing a command. For autonomous operation, the system needs to be able to:

- Run a code review every time a branch is pushed
- Re-index embeddings every night
- Run benchmark suites on a schedule
- Execute recurring maintenance tasks without operator initiation

#### How to implement

Add a `scheduler.py` module.

Define a `ScheduledTask` that combines a cron expression with a run template:

```python
@dataclass
class ScheduledTask:
    task_id: str
    name: str
    schedule: str  # cron expression: "0 2 * * *" = 2am daily
    goal: str
    backend: str | None = None
    strategy: str = "tool-loop"
    autonomous: bool = True
    max_wall_time: int = 1800
    enabled: bool = True
    run_count: int = 0
    last_run_at: str | None = None
    last_run_status: str | None = None
```

Persistence in SQLite:

```sql
CREATE TABLE scheduled_tasks (
    task_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    schedule TEXT NOT NULL,
    goal TEXT NOT NULL,
    backend TEXT,
    strategy TEXT NOT NULL DEFAULT 'tool-loop',
    autonomous INTEGER NOT NULL DEFAULT 1,
    max_wall_time INTEGER NOT NULL DEFAULT 1800,
    enabled INTEGER NOT NULL DEFAULT 1,
    run_count INTEGER NOT NULL DEFAULT 0,
    last_run_at TEXT,
    last_run_status TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

The scheduler runs as a background thread in the shell (or as a standalone daemon via `orchestro scheduler`). On each tick (every 60 seconds), it evaluates which tasks are due and starts them as background shell jobs with `autonomous=True`.

Shell commands:

- `/schedule add "0 2 * * *" "reindex embeddings" --strategy direct`
- `/schedule list`
- `/schedule disable <task_id>`
- `/schedule enable <task_id>`
- `/schedule history <task_id>`

CLI commands:

- `orchestro schedule add ...`
- `orchestro schedule list`
- `orchestro scheduler` — run the scheduler daemon

### 11.4 Sub-Agent Coordination

#### What claw does

Claw has a `TaskRegistry` for sub-agent task management (create, assign, track, complete), a `TeamRegistry` for grouping agents into coordinated units, and `TaskPacket` as a validated structured work order format with fields for objective, scope, branch policy, acceptance tests, commit policy, reporting contract, and escalation policy. The tools crate exposes `TaskCreate`, `TaskGet`, `TaskList`, `TaskStop`, `TaskUpdate`, `TaskOutput`, `TeamCreate`, `TeamDelete` as agent-callable tools.

#### Why Orchestro needs this

Orchestro's `delegate` command starts a child run, but there is no structured task format, no team coordination, no acceptance criteria, and no escalation policy. A parent run cannot express "do X, verify it passes these tests, and report back with these specific outputs." It can only say "do X" and hope.

For autonomous operation on complex tasks, the parent agent needs to decompose work, delegate to sub-agents with clear contracts, monitor progress, and handle failures — without operator involvement.

#### How to implement

Add a `tasks.py` module.

Define a `TaskPacket` as the structured work order:

```python
@dataclass
class TaskPacket:
    objective: str
    scope: str | None = None  # files, directories, or domain
    acceptance_tests: list[str] | None = None  # commands that must pass
    commit_policy: str = "squash"  # squash, per-step, none
    escalation_policy: str = "escalate-on-ambiguity"
    max_wall_time: int = 900
    context: dict | None = None  # subset of parent context to pass
    reporting: str = "summary"  # summary, full-trace, structured
```

Add a `tasks` table:

```sql
CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY,
    parent_run_id TEXT REFERENCES runs(id),
    packet TEXT NOT NULL,  -- JSON TaskPacket
    status TEXT NOT NULL DEFAULT 'created',
    assigned_run_id TEXT REFERENCES runs(id),
    output TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);
```

The agent-callable `spawn_subagent` tool (already in the architecture doc's planned tool list) should create a task from a `TaskPacket`, start a child run with bounded context, and track it:

1. Parent agent calls `spawn_subagent` with a `TaskPacket`.
2. System validates the packet (objective required, acceptance tests parseable).
3. System creates a child run with `parent_run_id` set, context scoped per the packet.
4. Child run executes autonomously using the same recovery, policy, and trust infrastructure.
5. On completion, child run output is stored in the task record.
6. If acceptance tests are specified, they are run and results recorded.
7. Parent agent can poll task status or be notified on completion.
8. If the child fails and recovery is exhausted, the escalation policy determines whether to notify the parent or the operator.

### 11.5 Auto-Compaction and Context Management

#### What claw does

Claw's `ConversationRuntime` calls `maybe_auto_compact()` when cumulative input tokens cross a configurable threshold (default 100,000). Compaction summarizes old conversation turns while preserving recent context. A `SummaryCompressionBudget` controls the output size. The compression system normalizes whitespace, deduplicates lines, and prioritizes content by type (headers > details > bullets > filler).

#### Why Orchestro needs this

Orchestro has no context management for long-running runs. A tool-loop run accumulates full tool outputs in its message history. After enough steps, the context exceeds the backend's window and the run crashes with an opaque error.

For autonomous operation, context overflow is a silent killer. The agent does useful work for 10 steps, then dies on step 11 because the accumulated context is too large. The operator comes back to a failed run with no recovery.

#### How to implement

Add context tracking to the tool-loop execution path in `orchestrator.py`.

Track cumulative token count (estimated) per run. After each tool-loop step:

1. Estimate current context size (character count / 4 as a rough token proxy, or use the backend's tokenizer if available).
2. If context exceeds 75% of the backend's declared context window, trigger compaction.
3. Compaction summarizes all tool outputs older than the last 3 steps into a compressed summary.
4. The summary replaces the individual outputs in the message history.
5. Emit a `context_compacted` event with before/after sizes.

The compaction prompt should be a dedicated internal call (not visible to the user):

```
Summarize the following tool outputs into a concise working summary.
Preserve: key findings, file paths mentioned, errors encountered, decisions made.
Discard: verbose command output, redundant information, intermediate states.
```

For backends that report token usage in their responses, use actual counts instead of estimates.

#### Memory harvest on compaction

Compaction is a natural trigger for memory extraction. When the system summarizes old tool outputs, it already has all the information needed to propose new facts and corrections. Extend the compaction step:

After generating the compressed summary, run a second internal prompt:

```
Review the following conversation history being compacted.
Extract any of the following if present:
- Facts learned (new information about the codebase, project, or operator preferences)
- Corrections made (places where the model was wrong and the operator or a tool corrected it)
- Mistakes to avoid (patterns that led to failures)
Return as JSON: {"facts": [...], "corrections": [...]}
```

Queue the extracted items as `proposed` facts and corrections in the database. The operator reviews and accepts them via the existing `fact-add` and `correction-add` flows. Every long tool-loop session automatically contributes to the knowledge base with zero extra operator effort.

### 11.6 Escalation Channels

#### What claw does

Claw's recovery system has three escalation policies: `AlertHuman`, `LogAndContinue`, `Abort`. The policy engine has `Escalate { reason }` and `Notify { channel }` actions. Lane events provide machine-readable status updates.

#### Why Orchestro needs this

Orchestro's only escalation mechanism is blocking on stdin in the interactive shell. For autonomous and background runs, this means failures are silent until the operator checks. There is no way to notify the operator that a run needs attention without them actively looking.

#### How to implement

Add an `escalation.py` module.

Define escalation channels:

- `shell` — write to the shell's notification area (for interactive sessions)
- `file` — append to `.orchestro/escalations.log` (for daemon mode)
- `webhook` — POST to a configured URL (for external integrations like ntfy, Slack, Discord)
- `command` — run a shell command with the escalation payload as stdin (maximum flexibility)

Configuration in `.orchestro/escalation.yaml`:

```yaml
channels:
  default: shell

  notify:
    type: webhook
    url: https://ntfy.sh/orchestro-alerts
    priority: default

  urgent:
    type: command
    command: notify-send "Orchestro" "$ESCALATION_REASON"

policies:
  on_failure:
    channel: notify
  on_approval_timeout:
    channel: urgent
  on_recovery_exhausted:
    channel: urgent
  on_task_completed:
    channel: default
```

The escalation system should be used by:

- Recovery recipes — when recovery is exhausted
- Approval system — when an approval request times out in autonomous mode
- Scheduler — when a scheduled task fails
- Sub-agent coordination — when a child task fails and escalation policy says notify parent or operator
- Policy engine — via the `Notify { channel }` action

Each escalation is also persisted as a run event for audit.

### 11.7 Autonomy Budget and Guardrails

#### What claw does

Claw enforces multiple autonomy bounds: `max_iterations` on the conversation loop, sandbox isolation via Linux namespaces, workspace boundary enforcement, permission modes, and the green contract for merge safety. The philosophy is: the agent can do anything within its declared safety envelope, and the envelope is explicit and auditable.

#### Why Orchestro needs this

Autonomous operation without guardrails is dangerous. An agent with `bash` access and no limits could delete files, push broken code, exhaust API credits, or loop forever. The guardrails must be explicit, configurable, and enforced — not implicit in the current "operator is watching" assumption.

#### How to implement

Define an autonomy budget per run or per session:

```python
@dataclass
class AutonomyBudget:
    max_iterations: int = 20          # tool-loop steps
    max_wall_time: int = 3600         # seconds
    max_tool_calls: int = 50          # total tool invocations
    max_bash_calls: int = 10          # bash specifically
    max_file_writes: int = 20         # write operations
    max_child_tasks: int = 5          # sub-agent spawns
    max_retries: int = 3              # recovery attempts
    workspace_boundary: str = "."     # no escaping this
    allow_network: bool = False       # bash commands with network access
    allow_destructive: bool = False   # rm, git push --force, etc.
```

Configuration in `.orchestro/autonomy.yaml`:

```yaml
defaults:
  max_iterations: 20
  max_wall_time: 3600
  max_tool_calls: 50
  allow_network: false
  allow_destructive: false

overrides:
  scheduled:
    max_wall_time: 1800
    max_tool_calls: 30

  high-trust:
    max_iterations: 50
    max_wall_time: 7200
    max_tool_calls: 100
    allow_network: true
```

The budget is checked before every tool call. When any limit is hit, the run transitions to `failed` with `failure_category=budget_exhausted` and the escalation channel is notified. Budget consumption is tracked as run events so the operator can review what the agent spent its budget on.

The workspace boundary enforcer (from pattern 11.2) is a hard guardrail that is not configurable per budget — it always applies. Writes outside the workspace root are always blocked.

### How the autonomy subsystems compose

The full autonomous pipeline for Orchestro:

1. **Scheduler fires** (11.3) → creates a run with `autonomous=True`
2. **Trust tier evaluated** (11.2) → determines auto-approval scope for this workspace
3. **Autonomy budget loaded** (11.7) → sets resource limits for the run
4. **Run executes** (11.1) → tool-loop with policy-driven approvals, no stdin blocking
5. **If tool needs approval** → policy engine (pattern 3) evaluates against trust tier → auto-approve or escalate
6. **If context grows large** → auto-compaction (11.5) summarizes old outputs
7. **If run fails** → failure taxonomy (pattern 1) classifies → recovery recipe fires → retry/escalate
8. **If recovery exhausted** → escalation channel (11.6) notifies operator
9. **If complex task** → parent spawns sub-agents (11.4) with bounded context and acceptance tests
10. **If budget exceeded** → run stops cleanly (11.7) with structured reporting
11. **On completion** → quality contract (pattern 10) assesses confidence → policy engine decides next action

The operator can set this up once, walk away, and come back to:
- Completed work with quality assessments
- Clear escalation messages for things that need human judgment
- Full audit trail of what the agent did, what it spent, and why it stopped

## 12. Prompt Caching Optimization

### What claw does

Claw has a 24K-LOC `prompt_cache.rs` module dedicated to Anthropic prompt cache management. It marks stable portions of the system prompt (instructions, tool definitions, constitutions) with cache control headers so the API can reuse KV-cache across requests. It tracks cache hit/miss rates and adjusts cache breakpoint placement based on observed patterns.

### Why Orchestro needs this

Orchestro calls the Anthropic-compatible API via plain `urllib` with no cache control headers. Every call re-encodes the full system prompt — instructions, constitutions, tool definitions, and retrieved context — even when those portions are identical across turns in a tool-loop run.

For a 6-step tool-loop run with a 2,000-token system prompt, prompt caching reduces input token cost by ~80% on steps 2-6. For Orchestro's target use case of extended local model runs, this directly extends how far the autonomy budget can go on a given token quota.

### How to implement

Add cache control hints to the request payload for OpenAI-compatible backends that support them (Anthropic, some vLLM deployments):

```python
def build_messages_with_cache(request: RunRequest) -> list[dict]:
    system_parts = []

    # Stable: mark for caching
    if request.system_prompt:
        system_parts.append({
            "type": "text",
            "text": request.system_prompt,
            "cache_control": {"type": "ephemeral"}
        })

    # Semi-stable: constitution and instructions (cache if present)
    if request.prompt_context:
        system_parts.append({
            "type": "text",
            "text": request.prompt_context,
            "cache_control": {"type": "ephemeral"}
        })

    return system_parts
```

Track cache hit/miss in run_events when the backend reports them:

```python
# OpenAI-compatible backends return usage.cache_read_input_tokens
if "cache_read_input_tokens" in usage:
    append_event(run_id, "cache_stats", {
        "cache_read_tokens": usage["cache_read_input_tokens"],
        "cache_write_tokens": usage.get("cache_creation_input_tokens", 0)
    })
```

### Integration points

- `OpenAICompatBackend.run()` — build requests with cache headers
- Token tracking (pattern 14) — report cache savings separately
- Auto-compaction (11.5) — identify the stable vs. dynamic boundary for cache placement

---

## 13. Static Bash Command Analysis

### What claw does

Claw has 18 validation submodules in `bash_validation.rs` that perform static analysis on bash commands before execution. Each module targets a category of destructive or dangerous operations:

- `rm_rf_detector` — detects `rm -rf`, `rm -r`, recursive deletion patterns
- `force_push_detector` — detects `git push --force`, `git push -f`
- `reset_hard_detector` — detects `git reset --hard`, `git checkout .`, `git restore .`
- `drop_table_detector` — detects SQL `DROP TABLE`, `DROP DATABASE`, `TRUNCATE`
- `network_exfil_detector` — detects `curl` and `wget` posting to external URLs
- `cred_file_detector` — detects reads of `.env`, `~/.ssh/`, `~/.aws/credentials`
- ... and 12 more

These run before any approval check. If a command matches a destructive pattern, it is either blocked or automatically escalated regardless of trust tier or approval patterns.

### Why Orchestro needs this

Orchestro's approval system is purely syntactic pattern matching via fnmatch. `bash *` auto-approves everything. `bash git*` auto-approves all git commands including `git push --force`. There is no layer that says "this command is structurally dangerous, regardless of patterns."

The trust tier (pattern 11.2) adds an `allow_destructive: false` guardrail, but "destructive" is not defined anywhere. Without static analysis, the system cannot distinguish `git log` from `git reset --hard` — both are `git` commands.

### How to implement

Add a `bash_analysis.py` module with detection functions for each category:

```python
import re
import shlex

DESTRUCTIVE_PATTERNS = [
    # Recursive deletion
    (re.compile(r'\brm\b.*-[^\s]*r', re.IGNORECASE), "recursive_delete"),
    # Force push
    (re.compile(r'\bgit\b.*push\b.*(-f\b|--force\b)'), "force_push"),
    # Hard reset
    (re.compile(r'\bgit\b.*(reset\b.*--hard|checkout\s+\.|restore\s+\.)'), "hard_reset"),
    # Drop table
    (re.compile(r'\b(DROP\s+(TABLE|DATABASE)|TRUNCATE\s+TABLE)\b', re.IGNORECASE), "sql_drop"),
    # Credential files
    (re.compile(r'(\.env|\.aws/credentials|\.ssh/id_|/etc/shadow)'), "credential_access"),
    # Pipe to shell (curl | bash, wget | sh)
    (re.compile(r'(curl|wget)\b.*\|\s*(ba)?sh\b'), "remote_exec"),
    # Fork bomb
    (re.compile(r':\(\)\{.*\}'), "fork_bomb"),
]

def analyze_bash_command(command: str) -> list[dict]:
    """
    Returns list of findings: [{"category": str, "severity": "block"|"warn", "match": str}]
    """
    findings = []
    for pattern, category in DESTRUCTIVE_PATTERNS:
        if pattern.search(command):
            findings.append({
                "category": category,
                "severity": "block" if category in ALWAYS_BLOCK else "warn",
                "match": pattern.search(command).group(0)
            })
    return findings
```

Integrate with the tool execution path. Before any bash call:

1. Run `analyze_bash_command()`.
2. If any `block`-severity findings: reject the call and emit a `tool_blocked` event with the findings.
3. If any `warn`-severity findings: auto-elevate to `confirm` tier regardless of existing approval patterns.
4. If `allow_destructive=False` in the autonomy budget and any finding is present: block.

The analysis runs in milliseconds and requires no external dependencies.

### Integration points

- `ToolRegistry.run()` — pre-execution gate for bash tool
- Trust resolution (11.2) — `allow_destructive` flag maps to block-on-findings
- Autonomy budget (11.7) — budget enforcement calls the analyzer
- Policy engine (pattern 3) — policies can reference `finding_category` as a condition

---

## 14. Token and Cost Tracking per Step

### What claw does

Claw's telemetry crate records `input_tokens`, `output_tokens`, and estimated cost for every model call in the session trace. The `AssistantEvent::Usage` variant captures per-turn token counts. Session-level aggregates are available for the `/cost` slash command.

### Why Orchestro needs this

Orchestro logs events but does not track token counts or cost per run or per step. The rating system rates runs as `good`/`bad`/`edit`/`skip` but has no cost dimension. A cheap bad run and an expensive bad run look identical in the data — but they have different implications for the fine-tuning pipeline and for backend routing decisions.

Token tracking also directly powers three other patterns in this document: auto-compaction (11.5) needs a token count to know when to fire; benchmark comparison benefits from cost-per-case metrics; and data-driven routing (pattern 16) can factor cost efficiency alongside success rate.

### How to implement

Parse token usage from backend responses and record it in run_events:

```python
# In OpenAICompatBackend.run()
usage = response.get("usage", {})
if usage:
    append_event(run_id, "token_usage", {
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
        "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
        "cache_write_tokens": usage.get("cache_creation_input_tokens", 0),
        "step": step_number  # for tool-loop runs
    })
```

Add a `total_tokens` column to the `runs` table for fast querying:

```sql
ALTER TABLE runs ADD COLUMN total_input_tokens INTEGER DEFAULT 0;
ALTER TABLE runs ADD COLUMN total_output_tokens INTEGER DEFAULT 0;
```

Add CLI output:

```
orchestro runs --show-tokens     # include token counts in run listing
orchestro show <run-id>          # include token breakdown in run detail
orchestro bench --show-cost      # cost column in benchmark results
```

In the shell, add `/cost` to show session-level token totals, consistent with Claude Code's `/cost` slash command.

### Integration points

- `OpenAICompatBackend.run()` — extract and emit usage
- `OrchestroDB.complete_run()` — aggregate token counts from step events
- Auto-compaction (11.5) — use actual token counts when available, estimate otherwise
- Benchmark system — report cost per case and per suite
- Rating system — weight negative ratings by token cost in training data export
- Data-driven routing (pattern 16) — cost efficiency as a routing signal

---

## 15. Model-Callable Tool Discovery (ToolSearch)

### What claw does

Claw exposes a `ToolSearch` tool that the model can call during a run. The model passes a query string and receives a list of matching tool specs (name, description, parameters). This enables the model to discover available tools dynamically rather than relying solely on the tool list injected at the start of the conversation.

### Why Orchestro needs this

Orchestro's tool registry is static. The model is primed with all tool definitions at the start of every run. As the tool list grows — especially with MCP-bridged tools (pattern 7) and plugin-provided tools (pattern 2) — the full tool list becomes too large to include in every prompt.

`ToolSearch` solves this elegantly: inject a minimal core set of tools plus `ToolSearch` itself, and let the model retrieve specialized tools by query when it needs them. This keeps the base prompt small and scales to arbitrarily large tool registries.

### How to implement

Add `tool_search` as a built-in tool in `ToolRegistry`:

```python
ToolDefinition(
    name="tool_search",
    description="Search available tools by name or capability. Returns matching tool specs. Use when you need a tool that isn't in your current tool list.",
    approval="auto",
    runner=tool_registry.search
)
```

Implement the search in `ToolRegistry`:

```python
def search(self, query: str, limit: int = 5) -> ToolResult:
    query_lower = query.lower()
    matches = []
    for tool in self._all_tools.values():
        score = 0
        if query_lower in tool.name.lower():
            score += 10
        if query_lower in tool.description.lower():
            score += 5
        for keyword in query_lower.split():
            if keyword in tool.description.lower():
                score += 1
        if score > 0:
            matches.append((score, tool))
    matches.sort(key=lambda x: x[0], reverse=True)
    result = [{"name": t.name, "description": t.description, "approval": t.approval}
              for _, t in matches[:limit]]
    return ToolResult(ok=True, output=json.dumps(result, indent=2), metadata={})
```

The tool is always included in the base tool list sent to the model. When the model calls `tool_search("file editing")`, the result includes `edit_file`, `write_file`, etc. The model can then call those tools in subsequent steps.

### Integration points

- `ToolRegistry` — add `tool_search` as a built-in with `auto` approval
- Tool-loop execution — `tool_search` results inform which tools are available next step
- MCP client (pattern 7) — MCP tools are searchable by `mcp:` prefix query
- Plugin system (pattern 2) — plugin tools are discoverable via search

---

## 16. Data-Driven Backend Routing

### What claw does

Claw's backend routing is based on goal and strategy heuristics defined at compile time. There is no runtime learning.

### Why Orchestro needs this

Orchestro's routing is already heuristic-based (`decide_auto_backend()`). But Orchestro has something claw does not: a persistent rating history across hundreds of runs. This is the data needed to make routing empirically better over time.

The routing flywheel:
1. Route request to backend X using heuristics
2. Operator rates the run
3. Rating is stored with backend, strategy, and domain metadata
4. Routing weights are updated from rating aggregates
5. Next similar request is routed more accurately

This closes a feedback loop that the existing rating system leaves open.

### How to implement

Add a `routing_stats` view to the database:

```sql
CREATE VIEW routing_stats AS
SELECT
    r.backend_name,
    r.strategy_name,
    r.metadata ->> '$.domain' AS domain,
    COUNT(*) AS run_count,
    AVG(CASE rt.rating WHEN 'good' THEN 1.0 WHEN 'bad' THEN 0.0 ELSE 0.5 END) AS success_rate,
    AVG(r.total_input_tokens + r.total_output_tokens) AS avg_tokens
FROM runs r
LEFT JOIN ratings rt ON rt.target_id = r.id AND rt.target_type = 'run'
WHERE r.status = 'completed'
GROUP BY r.backend_name, r.strategy_name, domain
HAVING run_count >= 5;  -- minimum sample size
```

Modify `decide_auto_backend()` to query this view when sufficient data exists:

```python
def decide_auto_backend(goal: str, strategy: str, domain: str | None, db: OrchestroDB) -> str:
    # Try empirical routing first (requires >= 5 rated runs)
    stats = db.get_routing_stats(strategy=strategy, domain=domain, min_runs=5)
    if stats:
        best = max(stats, key=lambda s: s.success_rate)
        if best.success_rate > 0.7 and is_reachable(best.backend_name):
            return best.backend_name

    # Fall back to heuristic routing
    return _heuristic_routing(goal, strategy, domain)
```

Add a CLI command to inspect routing stats:

```
orchestro routing-stats           # show per-backend success rates by domain
orchestro routing-stats --domain coding
```

The stats update automatically as runs complete and operators rate them. No separate training step is required.

### Integration points

- `decide_auto_backend()` — query stats before heuristics
- Token tracking (pattern 14) — cost efficiency as secondary routing signal
- Rating system — ratings are the signal; this just closes the loop
- Benchmark system — benchmark runs can be excluded from routing stats (separate flag)

---

## 17. Correction-Aware Tool Approval

### What claw does

Claw's permission system is static — permission modes and workspace boundaries are fixed at run time. The correction system and the permission system do not interact.

### Why Orchestro needs this

Orchestro has both a correction retrieval system and a tool approval system, but they are independent. When a correction fires during retrieval ("we lost data using this approach last time"), the approval system does not know. The operator who added that correction presumably wants extra caution in similar situations — but the system does not enforce it.

This is the most direct use of Orchestro's memory to improve Orchestro's safety. The knowledge accumulated from past mistakes should actively influence how cautiously future similar operations are treated.

### How to implement

Add a correction-based approval elevation step in the tool execution path.

When a tool call is about to execute, check whether any high-scoring correction was retrieved for the current run that mentions the tool being called:

```python
def should_elevate_approval(tool_name: str, tool_args: str, retrieval_bundle: RetrievalBundle) -> tuple[bool, str]:
    """
    Returns (should_elevate, reason) if a retrieved correction suggests extra caution.
    """
    if not retrieval_bundle:
        return False, ""

    for hit in retrieval_bundle.selected_hits:
        if hit.source_type == "correction" and hit.score > 0.85:
            correction = db.get_correction(hit.source_id)
            # Check if the correction mentions the tool or key args
            combined = f"{correction.context} {correction.wrong_answer}"
            if tool_name in combined or _args_overlap(tool_args, combined):
                return True, f"Relevant correction: {correction.context[:100]}"

    return False, ""
```

When elevation triggers, the tool call is moved to `confirm` tier regardless of current patterns. The approval request includes the correction reason so the operator understands why they are being asked.

This is additive — it does not override trust tiers or autonomy budget decisions. It is an additional signal that says "we have specific past evidence to be cautious here."

### Integration points

- Tool execution in `orchestrator.py` — check elevation before approval tier lookup
- Retrieval builder — pass corrections-only hits to the elevation check (score > 0.85)
- Approval request creation — include correction reason in the request payload
- Policy engine (pattern 3) — policies can reference `correction_elevated: true` as a condition

---

## Implementation Priority

Recommended build order based on impact, effort, and dependency chain:

| Order | Pattern | Reason |
|-------|---------|--------|
| 1 | Recovery recipes (1) | Directly improves existing failure handling with minimal new infrastructure |
| 2 | Model aliases (5) | Small effort, immediate daily-use improvement |
| 3 | Token and cost tracking (14) | Low effort; unlocks auto-compaction triggers, benchmark cost metrics, and rating weight |
| 4 | Static bash analysis (13) | Low effort, high safety payoff; no dependencies |
| 5 | Worker state machine (6) | Foundational for recovery, policies, autonomy, and session management |
| 6 | Trust resolution (11.2) | Required before any autonomous operation can be safe |
| 7 | Autonomy budget (11.7) | Hard guardrails that must exist before enabling unattended runs |
| 8 | Autonomous run mode (11.1) | Core capability: runs that don't block on stdin |
| 9 | Escalation channels (11.6) | Required for autonomous runs to communicate failures |
| 10 | Auto-compaction with memory harvest (11.5) | Required for autonomous runs to survive long execution; harvest extracts memory as a side effect |
| 11 | Prompt caching (12) | Low-hanging token savings; add alongside compaction while touching the request path |
| 12 | Policy engine (3) | Builds on trust + budget; enables declarative automation |
| 13 | Correction-aware approval (17) | Small addition once correction retrieval and approval system are both active |
| 14 | Plugin system (2) | Enables extensibility for everything that follows |
| 15 | Session persistence (4) | Improves multi-run workflows; builds on run tracking |
| 16 | Scheduled tasks (11.3) | Requires autonomous mode, trust, budget, and escalation |
| 17 | Sub-agent coordination (11.4) | Requires autonomous mode, trust, budget, and task tracking |
| 18 | Data-driven routing (16) | Requires sufficient rated run history (50+ runs); add after rating flywheel is established |
| 19 | ToolSearch (15) | Most valuable once tool registry has grown via MCP and plugins |
| 20 | Command registry (8) | Refactor that unblocks plugin-provided commands |
| 21 | Quality contract (10) | Most useful after verifiers exist (Phase 4 of roadmap) |
| 22 | MCP client (7) | High value but high effort; depends on stable tool registry |
| 23 | MCP memory server (7.1) | Build after MCP client proves the JSON-RPC transport layer |
| 24 | LSP integration (9) | High effort, best tackled after MCP client proves the pattern |

The first 11 items form the **autonomy foundation** — the minimum viable set for unattended operation. Items 12-18 build the **autonomous intelligence** layer on that foundation. Items 19-24 are infrastructure improvements that benefit from but do not require autonomy.

## Relationship to Existing Roadmap

These patterns map onto the existing roadmap phases:

- **Phase 3 (Strategy Layer)**: Recovery recipes (1), quality contract (10), auto-compaction with memory harvest (11.5), prompt caching (12)
- **Phase 3.5 (Agentic Shell)**: Worker state machine (6), session persistence (4), command registry (8), escalation channels (11.6), token and cost tracking (14)
- **Phase 4 (Verifiers)**: Plugin system (2) — verifiers as plugins; quality contract (10) — tracks verification results
- **Phase 8 (MCP)**: MCP client integration (7), MCP memory server (7.1)
- **Phase 9 (Additional Backends)**: Model aliases (5), data-driven routing (16), policy engine for backend routing (3)
- **New: Autonomy Phase** (between 3.5 and 4): Trust resolution (11.2), static bash analysis (13), autonomy budget (11.7), autonomous run mode (11.1), scheduled tasks (11.3), sub-agent coordination (11.4), correction-aware approval (17)

The autonomy layer is not currently represented in the roadmap. It sits naturally between Phase 3.5 (Agentic Shell) and Phase 4 (Verifiers) — the shell must support background jobs and operator controls before autonomy makes sense, and verifiers become much more valuable once the agent can run them without human initiation.

Patterns 12-17 (prompt caching, bash analysis, token tracking, ToolSearch, data-driven routing, correction-aware approval) are cross-cutting additions that do not map cleanly to a single roadmap phase. They are best introduced incrementally alongside the phases they enhance rather than as a dedicated phase.

The patterns do not replace roadmap phases. They add implementation specificity to phases that were described at a goals level, fill gaps between phases that were not previously addressed (recovery, plugins, policies, sessions), and introduce a new autonomy phase and several cross-cutting improvements that the roadmap did not originally envision.
