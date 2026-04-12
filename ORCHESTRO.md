# Orchestro Project Instructions

These instructions load automatically when the working directory is inside this repo.
They supplement the global instructions with project-specific context.

## Project context

This is the Orchestro codebase itself. The primary language is Python 3.12+.
The package lives at `src/orchestro/`. Tests are in `tests/`. Scripts in `scripts/`.
The virtual environment is `.venv/`. Run tests with `.venv/bin/python -m pytest tests/`.

## Conventions

- Use `from __future__ import annotations` at the top of every module.
- Dataclasses use `@dataclass(slots=True)`.
- Database access goes through `OrchestroDB` methods only — never raw SQL in callers.
- New modules need a corresponding `tests/test_<module>.py`.
- New CLI commands need both an argparse entry in `build_parser()` and a `do_<command>` method in `OrchestraShell`.
- Tests must not require a running backend. Use `MockBackend` or `subprocess-command` with a controlled env.

## First-time setup

After cloning, copy the global instructions template to the data directory:

```bash
cp docs/global.md.example .orchestro/global.md
# Edit .orchestro/global.md to reflect your actual preferences.
```

Copy `.env.example` to `.env` and fill in your backend URLs if you have live servers.

## Common operations

- `make test` — run the full test suite
- `make lint` — run ruff and mypy
- `make bench` — run the default benchmark suite against mock backend
- `make bench-agent` — run the agent benchmark suite
- `./scripts/vllm-ephemeral-check.sh fast --smoke` — bring up vllm-fast and run smoke tests
- `./scripts/ollama-ephemeral.sh --port-forward` — bring up ollama-amd with port-forward

## Safety rules for this project

- Do not modify `SCHEMA` in `db.py` without adding the corresponding `_ensure_column` call.
- Do not break the `OrchestroDB` public API — tests and the CLI depend on it directly.
- Do not add new dependencies to `pyproject.toml` without checking if stdlib suffices.
- The mock backend must always remain functional — it is the safety valve for all tests.
