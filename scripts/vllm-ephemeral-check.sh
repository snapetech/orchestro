#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./scripts/vllm-ephemeral-check.sh <fast|balanced|maxq> [--smoke] [--bench]

Behavior:
  - scales the chosen vLLM deployment up to 1 replica
  - waits for the pod to become Ready
  - optionally port-forwards and runs smoke/benchmark checks
  - always scales the deployment back down to 0 on exit unless ORCHESTRO_KEEP_UP=1

Environment overrides:
  ORCHESTRO_VLLM_NAMESPACE    default: ollama
  ORCHESTRO_VLLM_LOCAL_PORT   default: 8000
  ORCHESTRO_VLLM_WAIT_TIMEOUT default: 900s
  ORCHESTRO_KEEP_UP           set to 1 to skip cleanup scale-down
EOF
}

if [[ $# -lt 1 ]]; then
  usage >&2
  exit 1
fi

PRESET="$1"
shift

RUN_SMOKE=0
RUN_BENCH=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --smoke)
      RUN_SMOKE=1
      ;;
    --bench)
      RUN_BENCH=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

NAMESPACE="${ORCHESTRO_VLLM_NAMESPACE:-ollama}"
LOCAL_PORT="${ORCHESTRO_VLLM_LOCAL_PORT:-8000}"
WAIT_TIMEOUT="${ORCHESTRO_VLLM_WAIT_TIMEOUT:-900s}"
KEEP_UP="${ORCHESTRO_KEEP_UP:-0}"

case "$PRESET" in
  fast)
    SERVICE="vllm-qwen3-4b"
    MODEL="Qwen/Qwen3-4B"
    SUITE_NAME="vllm-live-fast"
    ;;
  balanced)
    SERVICE="vllm-qwen3-8b-fp8"
    MODEL="Qwen/Qwen3-8B-FP8"
    SUITE_NAME="vllm-live-balanced"
    ;;
  maxq)
    SERVICE="vllm-qwen3-4b-coding"
    MODEL="Qwen/Qwen3-4B"
    SUITE_NAME="vllm-live-coding"
    ;;
  *)
    echo "unknown preset: $PRESET" >&2
    usage >&2
    exit 1
    ;;
esac

PORT_FORWARD_PID=""
TMP_SUITE=""

cleanup() {
  local exit_code="$1"
  if [[ -n "$PORT_FORWARD_PID" ]]; then
    kill "$PORT_FORWARD_PID" >/dev/null 2>&1 || true
    wait "$PORT_FORWARD_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$TMP_SUITE" && -f "$TMP_SUITE" ]]; then
    rm -f "$TMP_SUITE"
  fi
  if [[ "$KEEP_UP" != "1" ]]; then
    sudo kubectl -n "$NAMESPACE" scale "deploy/$SERVICE" --replicas=0 >/dev/null || true
  fi
  exit "$exit_code"
}

trap 'cleanup $?' EXIT
trap 'exit 130' INT TERM

echo "Scaling $SERVICE up..."
sudo kubectl -n "$NAMESPACE" scale "deploy/$SERVICE" --replicas=1 >/dev/null

echo "Waiting for pod Ready..."
sudo kubectl -n "$NAMESPACE" wait --for=condition=Ready pod -l "app=$SERVICE" --timeout="$WAIT_TIMEOUT" >/dev/null

if [[ "$RUN_SMOKE" -eq 0 && "$RUN_BENCH" -eq 0 ]]; then
  echo "$SERVICE is ready."
  echo "Set ORCHESTRO_KEEP_UP=1 if you want this helper to leave the deployment running."
  exit 0
fi

echo "Starting port-forward on localhost:$LOCAL_PORT..."
ORCHESTRO_VLLM_SERVICE="$SERVICE" ORCHESTRO_VLLM_LOCAL_PORT="$LOCAL_PORT" \
  "$(dirname "$0")/vllm-port-forward.sh" >/tmp/orchestro-vllm-port-forward.log 2>&1 &
PORT_FORWARD_PID="$!"

for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${LOCAL_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS "http://127.0.0.1:${LOCAL_PORT}/health" >/dev/null

if [[ "$RUN_SMOKE" -eq 1 ]]; then
  echo "Running smoke checks..."
  ORCHESTRO_OPENAI_BASE_URL="http://127.0.0.1:${LOCAL_PORT}/v1" \
  ORCHESTRO_OPENAI_MODEL="$MODEL" \
    "$(dirname "$0")/vllm-smoke.sh"
fi

if [[ "$RUN_BENCH" -eq 1 ]]; then
  echo "Running benchmark suite..."
  TMP_SUITE="$(mktemp /tmp/orchestro-vllm-live-XXXX.json)"
  sed \
    -e "s/8000/${LOCAL_PORT}/g" \
    -e "s|Qwen/Qwen3-4B|${MODEL}|g" \
    -e "s|\"suite\": \"vllm-live\"|\"suite\": \"${SUITE_NAME}\"|" \
    benchmarks/vllm-live.json > "$TMP_SUITE"
  ORCHESTRO_OPENAI_BASE_URL="http://127.0.0.1:${LOCAL_PORT}/v1" \
  ORCHESTRO_OPENAI_MODEL="$MODEL" \
  PYTHONPATH=src .venv/bin/python -m orchestro.cli bench \
    --suite "$TMP_SUITE" \
    --backend openai-compat \
    --strategy direct
fi
