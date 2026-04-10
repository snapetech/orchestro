# Orchestro

Orchestro is a local-first orchestration harness for personal AI systems that improve through use.

The initial focus is:

- test-time compute scaling for small local models
- logging and review of interactions
- weekly preference tuning on user-approved outputs
- routing work across models running on a home LAN

## Phase 1 Status

The first implementation slice is in place:

- SQLite-backed run, event, and rating storage
- SQLite-backed interactions, facts, and corrections storage
- FTS-backed search over interactions and corrections
- embedding job tracking inside the same SQLite database
- a backend interface
- a working `mock` backend
- an OpenAI-compatible backend stub for local model servers
- a terminal shell and CLI commands for `ask`, `runs`, `show`, `rate`, and `review`
- a minimal FastAPI service for `/health`, `/backends`, `/runs`, and `/ask`

## Quickstart

Create a virtual environment, install the package, and use the shell:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
orchestro shell
```

Run the API server:

```bash
orchestro serve
curl http://127.0.0.1:8765/health
```

If Ollama is running in Kubernetes, bridge it locally first:

```bash
./scripts/ollama-port-forward.sh
```

Run one query directly:

```bash
orchestro ask "draft a short plan for Orchestro" --backend mock
```

List or inspect recent runs:

```bash
orchestro runs
orchestro show <run-id>
```

Rate a run:

```bash
orchestro rate run <run-id> good --note "useful first pass"
```

Inspect the memory tables:

```bash
orchestro interactions --limit 20
orchestro fact-add employer Lakeside --source manual
orchestro facts
orchestro correction-add --context "payroll calc" --wrong "EI is manual" --right "EI follows payroll tables" --domain payroll
orchestro corrections
```

Search and vector readiness:

```bash
orchestro search payroll --kind all
orchestro index-status
orchestro vector-status
orchestro index-embeddings --provider hash
orchestro semantic-search payroll --provider hash
```

Current retrieval works in two layers:

- SQLite FTS for lexical search
- `sqlite-vec` for semantic search once embeddings are indexed

The default verification path uses a deterministic local hash embedder so the indexing pipeline can run without an external model service.

For real embeddings, point Orchestro at an OpenAI-compatible embeddings endpoint:

```bash
export ORCHESTRO_EMBED_BASE_URL=http://127.0.0.1:11434/v1
export ORCHESTRO_EMBED_MODEL=nomic-embed-text
export ORCHESTRO_RETRIEVAL_PROVIDER=openai-compat
orchestro queue-embeddings --model-name nomic-embed-text
orchestro index-embeddings --provider openai-compat
orchestro semantic-search payroll --provider openai-compat
```

For live chat against Ollama's OpenAI-compatible API:

```bash
export ORCHESTRO_OPENAI_BASE_URL=http://127.0.0.1:11434/v1
export ORCHESTRO_OPENAI_MODEL=qwen2.5-coder:7b
orchestro ask "What payroll correction should I remember?" --backend openai-compat --domain payroll
```

By default, local state is stored in `.orchestro/orchestro.db` at the repo root. Set `ORCHESTRO_HOME` to override that path.

## Planning

Initial product and implementation planning lives in:

- `docs/architecture.md`
- `docs/roadmap.md`

## License

This project uses dual licensing:

- `AGPL-3.0-or-later` for open source use
- commercial licensing is available for organizations that want to use, embed, or distribute Orchestro outside AGPL terms

See [LICENSE](LICENSE), [LICENSES/AGPL-3.0.txt](LICENSES/AGPL-3.0.txt), and [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md).
