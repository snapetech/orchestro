# Orchestro Architecture

## Premise

Orchestro is not trying to reproduce frontier-model capability on consumer hardware.

It is trying to make local models materially more useful by combining:

- more test-time compute per query
- verifier-driven retries in domains where correctness can be checked
- persistent memory across facts, interactions, and domain knowledge
- a feedback loop that turns daily use into training data

The target user is a technically capable operator who is comfortable with Python, Git, a terminal workflow, and long-running local services.

## Product Thesis

For a single-user or household deployment, latency is a secondary concern. Quality can be improved by spending more wall-clock time on hard queries and by optimizing for a specific operator's real work rather than broad public benchmarks.

The core flywheel is:

1. Run a local model through an orchestrated strategy rather than a single forward pass.
2. Log the full interaction, including strategy metadata and verifier results.
3. Capture lightweight operator feedback inline.
4. Reuse past reasoning and corrections during future queries.
5. Periodically fine-tune on approved preferences.

Over time, the system becomes better at the operator's recurring tasks even if the base model remains relatively small.

## Design Principles

### Git First

Everything that can be versioned should live in the repo:

- prompt templates
- memory schemas
- ingestion scripts
- evaluation sets
- verifier code
- facts and fact proposals
- training configs

This keeps the system inspectable and debuggable. The intended standard is that meaningful regressions can be tracked with normal software techniques, including `git diff` and `git bisect`.

### SQLite First

The default persistence layer is SQLite, not a service stack.

Goals:

- one local file for core state
- easy inspection with `sqlite3`
- simple backup and replication
- low operational overhead
- easy packaging for a single-user environment

If vector search is needed, the first option is SQLite plus vector support rather than a separate database server.

### Inspectable Memory Over Invisible Automation

The system should make memory visible:

- explicit fact files for durable personal facts
- logged interactions with ratings and edits
- explicit correction records
- discrete knowledge collections with known ingestion sources

The operator should be able to inspect why the system answered the way it did.

### MCP Last, Not First

The memory and orchestration modules are the source of truth.

MCP is added later as an access layer so the same memory can be used by multiple clients. It should wrap existing Python functions instead of defining the architecture.

## System Components

### 1. Model Serving Layer

The serving layer hosts one or more local models behind an API the orchestrator can call.

Likely starting options:

- `llama.cpp` server for portability and broad model support
- `vLLM` when batch throughput matters and hardware supports it
- `ExLlamaV2` or `TabbyAPI` for RTX-oriented high-throughput single-user setups
- `MLX` for Apple Silicon systems

This is a replaceable layer. Orchestro should avoid binding itself to one serving engine.

### 1.1 Backend Abstraction

Orchestro should treat inference providers as backends behind a common interface.

A backend is responsible for taking a prompt, context, and execution options and returning a normalized result.

Initial backend families:

- local model servers such as `llama.cpp`
- local batch-oriented servers such as `vLLM`
- local specialized runtimes such as `ExLlamaV2`
- CLI-driven remote backends invoked as subprocess tools during interactive sessions

Each backend should declare capabilities such as:

- streaming support
- tool support
- context handling
- relative latency
- relative quality tier
- intended use mode, such as interactive or automated

This keeps routing explicit and makes backend churn survivable.

### 2. Orchestrator

The orchestrator is the main application layer. It sits between the user and model servers and is responsible for:

- request routing
- strategy selection
- tool and verifier invocation
- logging
- correction injection
- memory lookups
- response packaging

This should start as a small Python service with clear module boundaries.

### 2.1 Agent Runner

The shell loop and the agent loop should be separate.

The shell is a client for starting, observing, interrupting, and resuming agent runs. The agent runner is the execution engine that performs the work.

Each agent run should have:

- a stable run ID
- a goal
- status such as running, paused, done, or failed
- a trace of messages, tool calls, and state transitions
- backend and strategy metadata
- a working directory reference

This separation enables:

- cancelling or pausing work without killing the shell
- multiple agents running concurrently
- resumable long-running tasks
- cleaner logging and replay

### 2.2 Shell Interface

The primary UX should be a terminal-native shell rather than a chat window.

The intended model is a REPL with AI orchestration features:

- normal shell-style history and editing
- commands prefixed with `/` or `:`
- natural-language queries as the default input mode
- streamed event rendering for active runs
- direct hooks into pager or editor workflows

The shell should feel closer to `ipython` or `psql` than to a terminal-styled web chat.

### 3. Strategy Layer

A `Strategy` is a reusable inference pattern selected per query.

Initial strategy set:

- `Direct`
- `SelfConsistency`
- `CritiqueRevise`
- `Verified`
- `Debate`

A router chooses among strategies using simple rules first and only becomes learned later if the data supports it.

### 4. Verifier Layer

Verifiers are domain-specific correctness checks that allow retries before the user sees an answer.

Examples:

- Python parsing or execution
- type checks
- SQL parse checks
- bookkeeping balance checks
- structured output validation

Verifier-driven inference is a core differentiation point. Each new verifier should create a durable quality gain for its domain.

### 4.1 Tool Layer

Agent-visible tools should be first-class product concepts rather than ad hoc prompt additions.

The likely initial tool set includes:

- `bash`
- `read_file`
- `edit_file`
- `run_tests`
- `git_status`
- `git_diff`
- `git_commit`
- memory lookup tools
- correction and fact proposal tools
- `spawn_subagent`

Tool calls should be structured, logged, and individually reviewable.

File editing should be diff-oriented rather than full-file replacement wherever possible.

### 5. Memory Layers

#### Layer 1: Facts

Durable personal or project facts should live in a human-readable repo file such as `facts.md`.

Model writes do not go directly into the canonical facts file. Instead, the model can propose additions that are accepted or rejected by the operator.

#### Layer 2: Episodic Memory

This stores interaction history and related metadata, including:

- query
- response
- strategy used
- verifier results
- rating
- edits
- tool calls
- timestamps
- model and adapter versions

This layer supports retrieval over prior work and analysis of orchestration quality.

#### Layer 3: Knowledge Collections

These are curated domain corpora ingested from specific sources such as documentation, regulations, prior conversations, or exported notes.

Each collection should have:

- a dedicated ingestion script
- stable source tracking
- chunking suited to the corpus
- clear provenance

### 6. Corrections Memory

Corrections are important enough to treat separately.

Each correction stores:

- wrong answer
- right answer
- context
- severity
- retrieval key or embedding

Before normal generation, the system should check for similar prior corrections and inject them as hard guidance when confidence is high.

### 7. Feedback and Training Loop

The system should convert daily use into a dataset for preference optimization.

The ideal flow is:

1. Interaction is logged automatically.
2. Operator rates it inline or later.
3. Edited answers become strong preference data.
4. Weekly or periodic training jobs build adapters from approved examples.
5. New adapters are evaluated against a fixed held-out set before promotion.

Training comes after the logging loop is proven to work in real usage.

### 7.1 Fine-Grained Review

The system should support rating not only whole responses but also intermediate tool calls and decision points.

This matters because many agent failures are local mistakes:

- the wrong tool call
- the wrong file edit
- the wrong backend choice
- the wrong strategy selection

Capturing these step-level judgments should improve future orchestration quality more efficiently than response-only ratings.

## Interface Assumptions

For the initial operator, the primary interface should be terminal-friendly.

This suggests:

- a CLI or TUI review flow
- inline rating commands
- plain files for durable facts
- visible UUIDs or IDs for rating and inspection

A web UI may be useful later, but it should not be the initial dependency.

The interrupt model should explicitly support:

- pause after the current operation
- inject operator guidance into a paused or running task
- terminate a run cleanly

## Backend Routing

Backend choice should be explicit and inspectable.

The first router should be rule-based, not learned.

Expected heuristics:

- automated or scheduled work routes to local backends
- simple or high-volume tasks route to local backends
- harder interactive tasks can escalate to higher-capability backends
- backend decisions should be logged as part of the run trace

The shell should also support explicit escalation so the operator can rerun a task on a stronger backend without reconstructing context manually.

## Context Handoff

Because different backends have different context models, Orchestro should normalize its internal run state and translate to backend-specific invocation formats at the boundary.

This translation layer should handle:

- prompt packaging
- memory injection
- tool availability
- streaming normalization
- output parsing

This is operational plumbing, but it is core infrastructure rather than a temporary shim.

## Multi-Machine Outlook

If multiple machines are available on the LAN, Orchestro should eventually support heterogeneous routing rather than tensor-level model sharding.

Examples:

- a fast small classifier on one machine
- a coding model on another
- a general reasoner on a third

This resembles a home-scale mixture of experts while remaining operationally simple.

## Non-Goals for Early Versions

- reproducing hosted frontier-model generality
- complex distributed infrastructure
- opaque autonomous memory mutation
- heavy multi-service deployment requirements
- training before logging discipline exists
