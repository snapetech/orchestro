# ADR: Agent Loop and Control Patterns

## Status

Accepted as the current design direction for Orchestro's agent layer.

## Decision

Orchestro should treat agent reasoning, control flow, and failure history as first-class data.

The current design direction is:

- separate planning from acting
- prefer structured plans over pure ReAct loops
- log explicit reasoning and tool decisions as trace data
- make tool failure recovery reflective rather than blind retry
- keep domain constitutions and evaluation tasks as versioned repo assets
- retrieve prior traces and failure postmortems, not only documents
- keep subagents tightly scoped with bounded context

## Context

The project is already building three important foundations:

- persistent run and job traces
- retrieval over prior interactions and corrections
- a controllable shell with background jobs and subprocess control

The next quality gains will not come from adding more raw model calls alone. They will come from better orchestration patterns:

- how the agent plans before acting
- how it records and reuses procedural history
- how it reflects on failures
- how it decides when to escalate, retry, or stop

These patterns are more important than prompt polish because they directly shape inspectability, recovery, and long-term improvement.

## Adopted Patterns

### Plan / Act Split

Orchestro should explicitly distinguish:

- `plan` mode: read-only reasoning, context gathering, and plan creation
- `act` mode: tool execution against an approved or current plan

This is the preferred replacement for unstructured step-by-step agent loops. Plans should be visible, editable, and resumable from the shell.

### Structured Planning Over ReAct

The default agent shape should be:

1. build or update a structured plan
2. execute one step at a time
3. re-plan when observations invalidate the plan

Pure `thought -> action -> observation` loops are acceptable only for very small tasks. Multi-step work should be plan-driven.

### Think Events

Orchestro should support a structured no-op reasoning primitive analogous to a `think` tool.

Reasoning should be logged as explicit trace events instead of being mixed into user-facing prose. This makes it possible to:

- inspect reasoning separately from tool use
- rate reasoning and actions independently
- retrieve past reasoning traces later

### Reflective Tool Error Recovery

When a tool call fails, Orchestro should not default to immediate retry.

The next attempt should be preceded by an explicit reflective step that records:

- what failed
- the probable cause
- what will change before retrying

This reduces repeated identical failures and creates useful training data for future runs.

### Failure Postmortems as Memory

Layer 2 memory should include short postmortems for failed or corrected runs, not only successful outputs.

These postmortems should be retrievable as first-class memory alongside interactions and corrections. This is the mechanism by which the agent can avoid repeating procedural mistakes.

### Agent Trace Retrieval

Retrieval should expand beyond document lookup and answer lookup. Orchestro should retrieve prior agent trajectories when a new task resembles earlier work.

The useful unit is often:

- plan
- tool sequence
- result
- failure mode or correction

This is more valuable for agentic work than document-only RAG.

### Domain Constitutions

Orchestro should support versioned domain constitutions: explicit checklists for what a good answer or action must satisfy in a domain.

Examples:

- bookkeeping: balances, account validity, tax implications
- coding: error handling, tests, style consistency
- document drafting: tone, required facts, omissions to avoid

These constitutions should be reusable by critique and verification strategies.

### Bounded Subagents

Subagents should be spawned with minimal, explicit context.

The parent agent should specify:

- task
- allowed tools
- bounded context package
- expected return format

The default should not be "inherit everything." This keeps worker context clean and reduces cross-task pollution.

### Prompt Caching as Architecture

Stable prompt layers should be separated from volatile query layers.

The intended prompt layout is:

- fixed system and identity layer
- stable project or personal context
- retrieved task-specific context
- current user goal

This structure supports prompt caching on hosted backends and keeps the same prompt architecture useful on local backends.

### Evaluation Harness as Core Infrastructure

Orchestro should treat benchmarking as a product feature, not an optional afterthought.

The project should grow toward a `bench` command with:

- fixed task sets drawn from real work
- known-good outcomes or judgments
- scores tracked over time
- comparisons across prompt, router, and strategy changes

Without this, orchestration changes will drift without clear evidence of improvement.

## Patterns Worth Studying or Lifting

The following concrete patterns align with the decision above and should inform implementation:

- Anthropic-style `think` tool behavior for structured reasoning events
- explicit reflection prompts after tool failures
- plan-mode vs act-mode shell workflow
- Aider-style diff or search/replace editing protocols
- context providers that are explicit and selectable
- project-level instruction files such as `ORCHESTRO.md`
- actor / critic separation for critique-revise strategies

These should be lifted selectively where they strengthen Orchestro's core loop rather than turning it into a kitchen-sink framework.

## Near-Term Implementation Implications

Near-term implementation work should trend toward:

- a plan object and plan cursor in run state
- plan and think events in the trace schema
- failure-postmortem storage and retrieval
- strategy hooks for critique, constitution checks, and reflective retries
- explicit context-provider selection in the shell
- project-level instruction file loading
- a benchmark harness with stable fixtures

## Rationale

These patterns are accepted because they improve the properties Orchestro is supposed to optimize for:

- inspectability
- controllability
- personal adaptation over time
- recoverability after failure
- measurable improvement instead of anecdotal prompt tweaking

They also fit the repo-first, SQLite-first design already in place. Reasoning traces, plan state, postmortems, and benchmark results all belong in the same inspectable local system boundary.

## Consequences

Positive consequences:

- more debuggable agent runs
- better long-term reuse of past procedural knowledge
- safer multi-step execution
- clearer control semantics in the shell
- better basis for later training and router improvements

Accepted costs:

- more schema and trace complexity
- more design work around plan state and strategy boundaries
- more need for benchmark maintenance

Those costs are acceptable because the alternative is a less inspectable agent that forgets its own failures and is difficult to improve systematically.
