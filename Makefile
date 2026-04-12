.PHONY: test lint bench bench-agent bench-coding bench-routing bench-live-fast \
        bench-live-smoke shell seed index-embeddings export-prefs clean

PYTHON := .venv/bin/python
PYTEST  := $(PYTHON) -m pytest
RUFF    := .venv/bin/ruff
MYPY    := .venv/bin/mypy

# ---------------------------------------------------------------------------
# Development
# ---------------------------------------------------------------------------

test:
	$(PYTEST) tests/ -q

test-v:
	$(PYTEST) tests/ -v

lint:
	$(RUFF) check src/ tests/
	$(MYPY) src/orchestro/ --ignore-missing-imports --no-strict-optional

format:
	$(RUFF) format src/ tests/

# ---------------------------------------------------------------------------
# Benchmarks (all use mock or subprocess backends — no live server needed)
# ---------------------------------------------------------------------------

bench:
	$(PYTHON) -m orchestro.cli bench --suite benchmarks/default.json

bench-agent:
	$(PYTHON) -m orchestro.cli bench --suite benchmarks/agent.json

bench-coding:
	$(PYTHON) -m orchestro.cli bench --suite benchmarks/coding.json

bench-routing:
	$(PYTHON) -m orchestro.cli bench --suite benchmarks/routing.json

bench-workflows:
	$(PYTHON) -m orchestro.cli bench --suite benchmarks/workflows.json

bench-all: bench bench-agent bench-coding bench-routing bench-workflows

# ---------------------------------------------------------------------------
# Live backend benchmarks (require port-forwarded local servers)
# Use scripts/vllm-ephemeral-check.sh to bring up a backend first.
# ---------------------------------------------------------------------------

bench-live-fast:
	ORCHESTRO_OPENAI_BASE_URL=http://127.0.0.1:8000/v1 \
	ORCHESTRO_OPENAI_MODEL=Qwen/Qwen3-4B \
	$(PYTHON) -m orchestro.cli bench --suite benchmarks/vllm-live.json --backend openai-compat

bench-live-smoke:
	./scripts/vllm-ephemeral-check.sh fast --smoke

# ---------------------------------------------------------------------------
# Shell
# ---------------------------------------------------------------------------

shell:
	$(PYTHON) -m orchestro.cli shell

shell-coding:
	$(PYTHON) -m orchestro.cli shell --domain coding

shell-devops:
	$(PYTHON) -m orchestro.cli shell --domain devops

# ---------------------------------------------------------------------------
# Data pipeline
# ---------------------------------------------------------------------------

# Seed synthetic interactions for training export testing.
# Re-run with COUNT=N to add more: make seed COUNT=500
COUNT ?= 100
seed:
	$(PYTHON) scripts/seed-interactions.py --count $(COUNT)

# Index pending embedding jobs using the hash provider (no server needed).
index-embeddings:
	$(PYTHON) -m orchestro.cli index-embeddings --provider hash --limit 500

# Export preference pairs for DPO/SFT training.
export-prefs:
	$(PYTHON) -m orchestro.cli export-preferences --format dpo --output /tmp/orchestro-prefs.jsonl
	@echo "Exported to /tmp/orchestro-prefs.jsonl"

# Sync accepted facts to facts.md.
facts-sync:
	$(PYTHON) -m orchestro.cli facts-sync

# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------

# Show DB stats.
status:
	@echo "=== Runs ===" && $(PYTHON) -m orchestro.cli runs --limit 5
	@echo "=== Ratings ===" && $(PYTHON) -m orchestro.cli review --limit 5 --no-interactive 2>/dev/null || true
	@echo "=== Backends ===" && $(PYTHON) -m orchestro.cli backends

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -f .orchestro/bench-*.txt
