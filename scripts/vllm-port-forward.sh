#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${ORCHESTRO_VLLM_NAMESPACE:-ollama}"
SERVICE="${ORCHESTRO_VLLM_SERVICE:-vllm-qwen3-8b-awq}"
LOCAL_PORT="${ORCHESTRO_VLLM_LOCAL_PORT:-8000}"
REMOTE_PORT="${ORCHESTRO_VLLM_REMOTE_PORT:-8000}"

exec sudo kubectl -n "$NAMESPACE" port-forward "svc/$SERVICE" "${LOCAL_PORT}:${REMOTE_PORT}"
