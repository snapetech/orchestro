#!/usr/bin/env bash
set -euo pipefail

MODEL="${ORCHESTRO_EMBED_MODEL:-nomic-embed-text}"
LIMIT="${ORCHESTRO_REINDEX_LIMIT:-500}"
SOURCE_TYPE="${ORCHESTRO_REINDEX_SOURCE_TYPE:-}"

if [[ -n "${SOURCE_TYPE}" ]]; then
  SOURCE_FLAG=(--source-type "${SOURCE_TYPE}")
else
  SOURCE_FLAG=()
fi

export ORCHESTRO_RETRIEVAL_PROVIDER=openai-compat

.venv/bin/orchestro queue-embeddings --model-name "${MODEL}" "${SOURCE_FLAG[@]}"
ORCHESTRO_EMBED_BASE_URL="${ORCHESTRO_EMBED_BASE_URL:-http://127.0.0.1:11434/v1}" \
ORCHESTRO_EMBED_MODEL="${MODEL}" \
  .venv/bin/orchestro index-embeddings \
    --provider openai-compat \
    --model-name "${MODEL}" \
    --limit "${LIMIT}" \
    "${SOURCE_FLAG[@]}"
