#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${ORCHESTRO_OPENAI_BASE_URL:-http://127.0.0.1:8000/v1}"
MODEL="${ORCHESTRO_OPENAI_MODEL:-Qwen/Qwen3-4B}"

echo "== health =="
curl -sS "${BASE_URL%/v1}/health"
echo
echo "== models =="
curl -sS "$BASE_URL/models"
echo
echo "== orchestro direct =="
ORCHESTRO_OPENAI_BASE_URL="$BASE_URL" \
ORCHESTRO_OPENAI_MODEL="$MODEL" \
PYTHONPATH=src .venv/bin/python -m orchestro.cli ask \
  "Return exactly: vllm smoke ok" \
  --backend openai-compat \
  --domain coding
echo
echo "== orchestro tool-loop =="
ORCHESTRO_OPENAI_BASE_URL="$BASE_URL" \
ORCHESTRO_OPENAI_MODEL="$MODEL" \
PYTHONPATH=src .venv/bin/python -m orchestro.cli ask \
  "Use tool-loop. Determine the current working directory and return only that path." \
  --backend openai-compat \
  --strategy tool-loop \
  --providers instructions,lexical
