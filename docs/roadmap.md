# Orchestro Roadmap

## Current Direction

This roadmap merges two compatible frames:

- a local AI flywheel based on logging, feedback, and periodic preference tuning
- a dev-oriented implementation strategy that prioritizes Git, SQLite, CLI workflows, and inspectability

The immediate goal is not to optimize everything at once. The immediate goal is to build the smallest loop that proves daily use will create useful data.

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

Success criteria:

- a request can be sent through the proxy
- the response is logged with metadata
- a rating can be recorded with near-zero friction
- the system can be used for a week without operational drag
- one backend works end to end through the shell

Hard rule:

If interaction capture and rating are not happening consistently, do not move on to training work.

## Phase 2: Personal Memory Bootstrap

Add memory sources that immediately improve usefulness:

- a canonical `facts.md`
- a fact proposal flow
- ingestion of past conversation exports
- basic retrieval across prior interactions
- a separate corrections table with high-threshold recall

Success criteria:

- the system can retrieve prior relevant conversations
- the operator can inspect memory state directly
- corrections can prevent repeated mistakes on similar tasks

## Phase 3: Strategy Layer

Add structured inference strategies:

- `Direct`
- `SelfConsistency`
- `CritiqueRevise`
- `Verified`

Start with simple routing rules based on query shape and keywords.

Success criteria:

- strategies are explicit and measurable
- strategy metadata is logged per interaction
- at least one strategy shows clear quality gains for a recurring task type

## Phase 3.5: Agentic Shell

Build the interactive shell around the orchestrator:

- terminal-native REPL
- streamed run output
- visible run IDs
- pause, resume, inject, and kill controls
- background run handling

Success criteria:

- long-running runs do not block the shell
- the operator can intervene without losing state
- multiple runs can be inspected and resumed cleanly

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

## Phase 5: Knowledge Collections

Build domain collections with ingestion scripts and provenance:

- exported prior conversations
- internal notes and docs
- public documentation for recurring problem domains
- domain-specific procedural references

Success criteria:

- each collection has an idempotent ingester
- each ingester tracks source and update behavior
- retrieved context improves outputs without hiding provenance

## Phase 6: Evaluation

Before automated training, create a fixed evaluation set from real interactions.

The eval set should:

- be hand-curated
- cover recurring task categories
- include success and failure cases
- remain stable across training runs

Success criteria:

- the system can compare candidate adapters or strategy changes against a baseline
- promotions are blocked when regressions appear

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

## Phase 8: MCP Wrapper

Once the local memory and orchestration primitives are stable, expose them via MCP so other clients can access the same system.

Implementation rule:

- MCP wraps existing Python functions
- stdio transport first
- no extra service boundary unless clearly needed

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

## Immediate Build Order

The next coding pass should likely produce:

1. a SQLite schema for interactions, ratings, corrections, and facts
2. a small orchestrator entrypoint plus agent run model
3. a backend interface with one working local backend
4. local launch scripts for the selected model server
5. a `rate` CLI command
6. a `review` CLI or TUI for backlog handling
7. an initial shell loop with visible run state

Only after that foundation exists should retrieval, verifiers, and training work begin.
