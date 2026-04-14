# Collections

Collections are a lightweight document-ingestion surface inside Orchestro for storing and searching chunked local text outside the core runs/facts/corrections tables.

## Table Of Contents

1. [What Collections Are For](#what-collections-are-for)
2. [Persistence Model](#persistence-model)
3. [CLI Commands](#cli-commands)
4. [Chunking Behavior](#chunking-behavior)
5. [Search Behavior](#search-behavior)
6. [Practical Usage Pattern](#practical-usage-pattern)

## What Collections Are For

Use collections when you want:

- ad hoc searchable corpora
- imported notes or documents
- bounded document sets separate from durable facts and corrections

Do not confuse them with:

- facts: durable key/value items
- corrections: explicit answer repairs
- interactions: run history and operator feedback

## Persistence Model

Collections are stored in SQLite tables:

- `collections`
- `collection_chunks`
- `collection_chunks_fts`

The DB layer is implemented in [`src/orchestro/db.py`](../src/orchestro/db.py). The ingestion helpers are in [`src/orchestro/collections.py`](../src/orchestro/collections.py).

Collection metadata includes:

- `collection_id`
- `name`
- `description`
- `source_type`
- `source_path`
- `source_url`
- `chunk_count`
- `last_ingested_at`

Search results include:

- `chunk_id`
- `collection_id`
- `collection_name`
- `content`
- `source_ref`
- `sequence`
- `score`

## CLI Commands

- `collections`
- `collection-create`
- `collection-ingest`
- `collection-search`
- `collection-delete`

Typical flow:

```bash
orchestro collection-create docs-local "Local Docs" file --description "Internal markdown docs"
orchestro collection-ingest docs-local ./docs
orchestro collection-search "routing" --collection-id docs-local
```

## Chunking Behavior

Two chunkers currently exist:

- `ParagraphChunker`
- `MarkdownChunker`

Behavior:

- Markdown files use heading-aware chunking by default
- non-Markdown text uses paragraph chunking
- very short chunks may be merged
- overly long paragraphs are truncated

Directory ingestion currently defaults to:

- `.md`
- `.txt`
- `.rst`

## Search Behavior

Collections currently use FTS-based lexical search, not semantic vector search.

That means:

- phrase and token matching matter
- chunk boundaries matter
- this is best for searchable notes/docs, not fuzzy semantic recall

If you need semantic retrieval, use the main retrieval and embedding/indexing paths instead.

## Practical Usage Pattern

Good uses:

- ingesting a project docs folder
- creating a small research corpus
- indexing local notes for fast lookup

Less good uses:

- replacing facts/corrections
- long-lived canonical knowledge without curation
- expecting embedding-style semantic matching from FTS chunks

For concrete commands, see [Examples](examples.md). For memory model context, see [Architecture](architecture.md).
