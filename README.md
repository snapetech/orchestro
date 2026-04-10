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
```

Current retrieval uses SQLite FTS for lexical search. `sqlite-vec` is the intended next layer for semantic search when the Python package and extension are installed.

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
