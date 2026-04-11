# Orchestro Roadmap

## Current Direction

This roadmap merges two compatible frames:

- a local AI flywheel based on logging, feedback, and periodic preference tuning
- a dev-oriented implementation strategy that prioritizes Git, SQLite, CLI workflows, and inspectability

The immediate goal is not to optimize everything at once. The immediate goal is to build the smallest loop that proves daily use will create useful data.

Database stance for the near term:

- use SQLite as the default memory store
- enable WAL mode
- keep all DB access in a thin plain-SQL repository module
- use `sqlite-vec` for semantic retrieval when vector search is added
- do not introduce ChromaDB or another dedicated vector service in early phases
- treat Postgres as a future option only if real workload pain justifies it

Reference:

- [ADR: SQLite First for Memory Storage](/home/keith/Documents/code/orchestro/docs/adr-sqlite-first.md)

Agent-system stance for the near term:

- treat traces, plans, reasoning events, and failures as durable data
- prefer explicit planning over open-ended ReAct loops
- separate plan mode from act mode in the shell
- make evaluation a built-in workflow, not a cleanup task for later

## Phase 1: Foundation

Build the minimum usable path:

- initialize the repo structure
- run a local model server
- create a small Python proxy or orchestrator service
- log every request and response to SQLite
- attach stable IDs to interactions
- add a shell command for rating results
- define the backend interface
- define the agent run schema
- establish the shell loop separate from the agent loop
- define plan mode and act mode boundaries
- log reasoning and tool traces as structured events

Success criteria:

- a request can be sent through the proxy
- the response is logged with metadata
- a rating can be recorded with near-zero friction
- the system can be used for a week without operational drag
- one backend works end to end through the shell
- plan approval and execution feel explicit rather than magical

Hard rule:

If interaction capture and rating are not happening consistently, do not move on to training work.

Implementation rule:

- do not introduce an ORM for the core memory path
- do not hide multi-step execution behind an opaque ReAct loop

## Phase 2: Personal Memory Bootstrap

Add memory sources that immediately improve usefulness:

- a canonical `facts.md`
- a fact proposal flow
- ingestion of past conversation exports
- basic retrieval across prior interactions
- a separate corrections table with high-threshold recall
- a SQLite-native vector index path for semantic search
- stored failure postmortems for similar-task retrieval

Success criteria:

- the system can retrieve prior relevant conversations
- the operator can inspect memory state directly
- corrections can prevent repeated mistakes on similar tasks
- semantic matches can be filtered against normal metadata without cross-database glue code
- prior failures can be retrieved as lessons, not just as transcripts

## Phase 3: Strategy Layer

Add structured inference strategies:

- `Direct`
- `SelfConsistency`
- `CritiqueRevise`
- `Verified`
- `PlanExecute`

Start with simple routing rules based on query shape and keywords.

Success criteria:

- strategies are explicit and measurable
- strategy metadata is logged per interaction
- at least one strategy shows clear quality gains for a recurring task type
- plans are visible, editable, and resumable

Implementation notes:

- add a `think` tool for structured reasoning events in traces
- require explicit reflection before retrying a failed tool call
- run critique passes in fresh calls rather than continuations where feasible

## Phase 3.5: Agentic Shell

Build the interactive shell around the orchestrator:

- terminal-native REPL
- streamed run output
- visible run IDs
- pause, resume, inject, and kill controls
- background run handling
- explicit plan mode and act mode
- visible current plan and execution cursor

Success criteria:

- long-running runs do not block the shell
- the operator can intervene without losing state
- multiple runs can be inspected and resumed cleanly
- the operator can approve strategy at the plan level rather than tool by tool

## Phase 4: Verifiers

Add domain-specific verifiers one at a time.

Expected order:

1. Python syntax or execution verification
2. structured output validation
3. SQL parse or plan validation
4. bookkeeping balance checks

Success criteria:

- failed attempts are hidden from the final user-facing answer
- the model can retry with verifier feedback
- verifier-backed tasks outperform direct generation in practice

In parallel with verifiers, start building domain constitutions as versioned repo assets for self-critique and revision.

## Phase 5: Knowledge Collections

Build domain collections with ingestion scripts and provenance:

- exported prior conversations
- internal notes and docs
- public documentation for recurring problem domains
- domain-specific procedural references
- retrievable past agent trajectories and postmortems

Success criteria:

- each collection has an idempotent ingester
- each ingester tracks source and update behavior
- retrieved context improves outputs without hiding provenance
- trace retrieval can surface prior successful or failed procedures for similar tasks

## Phase 6: Evaluation

Before automated training, create a fixed evaluation set from real interactions.

The eval set should:

- be hand-curated
- cover recurring task categories
- include success and failure cases
- remain stable across training runs
- include multi-step agent tasks, not only single-turn prompts

Success criteria:

- the system can compare candidate adapters or strategy changes against a baseline
- promotions are blocked when regressions appear
- a `bench` workflow exists for prompt, strategy, retrieval, and backend changes

## Phase 7: Preference Training

Only begin once there is enough high-quality interaction data.

Entry condition:

- roughly 500 rated interactions, or enough to represent the main recurring task mix

Training loop:

1. export approved preferences and edits
2. format a preference dataset
3. run adapter training
4. evaluate against the held-out set
5. promote only if the candidate wins
6. keep rollbackable prior adapters

Success criteria:

- the system improves on personal tasks without obvious collapse in general behavior
- rollback is straightforward
- training is periodic, not continuous chaos

Longer term, the same dataset should be reused to improve orchestration components beyond the base model:

- routing
- planning
- critique
- retrieval
- confidence calibration

## Phase 8: MCP Wrapper

Once the local memory and orchestration primitives are stable, expose them via MCP so other clients can access the same system.

Implementation rule:

- MCP wraps existing Python functions
- stdio transport first
- no extra service boundary unless clearly needed
- preserve the distinction between tools, resources, and prompts
- use MCP sampling only where model-in-the-loop server decisions are clearly useful

Success criteria:

- hosted or external clients can use the same memory and tools
- local and external usage share one source of truth

## Phase 9: Additional Backends

Once the local path is solid, add more backends through the shared interface.

Potential backend types:

- stronger local runtimes
- interactive CLI-driven backends
- domain-specific specialists

Success criteria:

- backend routing is explicit and logged
- context handoff is consistent across backends
- the shell supports operator-driven escalation between backend tiers

## Open Questions

The next implementation pass should answer:

- what hardware is available for inference
- which serving engine best fits that hardware
- which task domain should get the first verifier
- what the SQLite schema should look like in v1
- what rating flow creates the highest real capture rate
- what the shell event model should look like
- which backend should be the first non-local target, if any
- what the first embedding pipeline should look like using `sqlite-vec`
- what the run trace schema should look like for plans, reasoning events, and postmortems
- what the first domain constitution should be
- what should be in the initial benchmark suite

The following are explicitly not immediate questions and should be revisited only after real usage data exists:

- whether SQLite has hit a concrete concurrency limit
- whether the memory store needs to be shared live across multiple machines
- whether external services need direct networked DB access
- whether vector search scale is large enough to justify a different backend
- whether a move to Postgres solves a measured bottleneck rather than a theoretical one
- whether a dedicated vector database solves a measured bottleneck rather than adding a second persistence system

## Immediate Build Order

The next coding pass should likely produce:

1. a SQLite schema for interactions, ratings, corrections, and facts
2. a small orchestrator entrypoint plus agent run model
3. a backend interface with one working local backend
4. local launch scripts for the selected model server
5. a `rate` CLI command
6. a `review` CLI or TUI for backlog handling
7. an initial shell loop with visible run state
8. a visible plan representation with execution cursor
9. a first benchmark command over a small fixed task set

The first retrieval implementation after this should:

1. add embedding tables or virtual tables inside the existing SQLite database
2. keep source rows and embeddings transactionally aligned
3. query semantic matches with SQL joins against ratings, domains, and run metadata
4. support retrieval of prior trajectories, corrections, and failure lessons

Only after that foundation exists should retrieval, verifiers, and training work begin.

## Future Option: Postgres Migration

Postgres remains a valid later move, but only in response to an observed limit.

Triggers that would justify serious evaluation:

- multi-process or multi-agent concurrent writes become routine
- Orchestro and the memory store need to live on different machines
- other tools or services need direct network access to live memory
- query complexity or dataset size starts making SQLite the bottleneck

If that happens, the migration path should be:

1. keep the existing repository interface stable
2. port the repository implementation with plain SQL
3. migrate data with explicit scripts
4. compare behavior and performance on real workloads before switching defaults

Until then, prioritize the local-first properties that make iteration cheap:

- one-file backups and snapshots
- easy inspection with local tools
- low-latency lookups without a service hop
- fast schema rewrites during active development
