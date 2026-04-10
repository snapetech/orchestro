# ADR: SQLite First for Memory Storage

## Status

Accepted for the current phase of the project.

## Decision

Orchestro should use SQLite as the default persistence layer for core memory and interaction state.

The intended baseline is:

- SQLite
- WAL mode enabled
- plain SQL
- a thin repository module that owns all queries
- SQLite-native vector support when semantic retrieval is needed

The default vector implementation for that path should be `sqlite-vec`.

Postgres remains a future option, not the default starting point.

## Context

Orchestro is currently designed as a local-first system for a single operator or household.

Expected workload characteristics:

- one primary application process
- one primary writer most of the time
- occasional offline scripts or maintenance tasks
- frequent low-latency reads for memory lookup
- active schema iteration during early development

This is SQLite's strongest operating mode. The project benefits more from low operational friction, easy inspection, and fast rewrite cycles than from service-oriented database features.

## Rationale

SQLite is the right default because it preserves useful local-first properties:

- the entire memory state is one local file
- backup and snapshot workflows are trivial
- the database can be inspected directly with standard local tools
- local lookups avoid network and service overhead
- schema changes are cheap during active development

This matters because Orchestro is still in the phase where major parts of the memory model are likely to be rewritten. The project should optimize for easy deletion, restructuring, and recovery rather than for theoretical scale.

Vector search does not change this decision by itself. For the expected scale of early Orchestro memory, SQLite-native vector support is good enough and avoids introducing a second service boundary.

The project should keep structured records and embeddings in the same SQLite storage boundary so similarity search can be joined directly against ratings, domains, strategies, and other metadata in SQL.

This also means early Orchestro should not introduce a separate vector store such as ChromaDB unless real workload pressure justifies that extra persistence system.

## Why Not Postgres Yet

Postgres is a strong option for systems with sustained concurrency, multiple clients, or networked service access. Those are not default requirements here.

Using Postgres now would add cost before it adds proportionate value:

- instance lifecycle management
- auth and connection handling
- more complex backup and restore workflows
- more friction when moving or snapshotting the full memory state

That trade is not justified unless the workload proves it necessary.

## Triggers To Reconsider

Revisit this decision if one or more of the following become normal:

- Orchestro and the memory store need to run on different machines
- multiple agents or services need concurrent writes to the same live store
- external tools need direct networked access to live memory
- query complexity or dataset size makes SQLite the actual bottleneck
- vector scale or write contention makes the local SQLite path operationally awkward

At that point, Postgres may become the right answer. The choice should be driven by measured pain, not anticipated taste.

Revisit the vector-store choice separately only if:

- `sqlite-vec` becomes a measured bottleneck
- vector workload shape no longer fits a single SQLite database cleanly
- a separate vector service solves a demonstrated operational problem instead of creating a second one

## Implementation Notes

- do not use an ORM for the core memory path
- keep storage access behind a narrow repository interface
- prefer explicit migration scripts over heavy migration infrastructure
- keep SQL portable where practical, but do not contort the design for hypothetical future swaps
- keep source rows and embeddings transactionally aligned inside SQLite by default

Portability should come from the repository boundary, not from pretending all databases behave the same under an abstraction layer.

## Consequences

Positive consequences:

- faster local development
- simpler debugging
- easier snapshots, transfer, and rollback
- lower operational overhead

Accepted limitations:

- weaker support for high-concurrency multi-writer workloads
- less natural networked access from other services
- eventual need to migrate if the system grows into a different operating model

Those limitations are acceptable for the current stage of the project.
