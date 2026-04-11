#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./scripts/ollama-ephemeral.sh [--port-forward] [-- command ...]

Behavior:
  - scales ollama-amd up to 1 replica
  - waits for the pod to become Ready
  - optionally starts local port-forwarding
  - optionally runs the given command
  - always scales ollama-amd back down to 0 on exit unless ORCHESTRO_KEEP_UP=1

Examples:
  ./scripts/ollama-ephemeral.sh --port-forward
  ./scripts/ollama-ephemeral.sh -- curl http://127.0.0.1:11434/api/tags

Environment overrides:
  ORCHESTRO_OLLAMA_NAMESPACE    default: ollama
  ORCHESTRO_OLLAMA_DEPLOYMENT   default: ollama-amd
  ORCHESTRO_OLLAMA_SERVICE      default: ollama
  ORCHESTRO_OLLAMA_LOCAL_PORT   default: 11434
  ORCHESTRO_OLLAMA_REMOTE_PORT  default: 11434
  ORCHESTRO_OLLAMA_WAIT_TIMEOUT default: 600s
  ORCHESTRO_KEEP_UP             set to 1 to skip cleanup scale-down
EOF
}

PORT_FORWARD=0
if [[ ${1:-} == "-h" || ${1:-} == "--help" ]]; then
  usage
  exit 0
fi

if [[ ${1:-} == "--port-forward" ]]; then
  PORT_FORWARD=1
  shift
fi

if [[ ${1:-} == "--" ]]; then
  shift
fi

NAMESPACE="${ORCHESTRO_OLLAMA_NAMESPACE:-ollama}"
DEPLOYMENT="${ORCHESTRO_OLLAMA_DEPLOYMENT:-ollama-amd}"
SERVICE="${ORCHESTRO_OLLAMA_SERVICE:-ollama}"
LOCAL_PORT="${ORCHESTRO_OLLAMA_LOCAL_PORT:-11434}"
REMOTE_PORT="${ORCHESTRO_OLLAMA_REMOTE_PORT:-11434}"
WAIT_TIMEOUT="${ORCHESTRO_OLLAMA_WAIT_TIMEOUT:-600s}"
KEEP_UP="${ORCHESTRO_KEEP_UP:-0}"

PORT_FORWARD_PID=""

cleanup() {
  local exit_code="$1"
  if [[ -n "$PORT_FORWARD_PID" ]]; then
    kill "$PORT_FORWARD_PID" >/dev/null 2>&1 || true
    wait "$PORT_FORWARD_PID" >/dev/null 2>&1 || true
  fi
  if [[ "$KEEP_UP" != "1" ]]; then
    sudo kubectl -n "$NAMESPACE" scale "deploy/$DEPLOYMENT" --replicas=0 >/dev/null || true
  fi
  exit "$exit_code"
}

trap 'cleanup $?' EXIT
trap 'exit 130' INT TERM

echo "Scaling $DEPLOYMENT up..."
sudo kubectl -n "$NAMESPACE" scale "deploy/$DEPLOYMENT" --replicas=1 >/dev/null

echo "Waiting for pod Ready..."
sudo kubectl -n "$NAMESPACE" wait --for=condition=Ready pod -l "app=ollama,gpu=amd" --timeout="$WAIT_TIMEOUT" >/dev/null

if [[ "$PORT_FORWARD" -eq 1 ]]; then
  echo "Starting port-forward on localhost:$LOCAL_PORT..."
  sudo kubectl -n "$NAMESPACE" port-forward "svc/$SERVICE" "${LOCAL_PORT}:${REMOTE_PORT}" &
  PORT_FORWARD_PID="$!"
  for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:${LOCAL_PORT}/" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  curl -fsS "http://127.0.0.1:${LOCAL_PORT}/" >/dev/null
fi

if [[ $# -gt 0 ]]; then
  "$@"
elif [[ "$PORT_FORWARD" -eq 1 ]]; then
  echo "Port-forward active. Ctrl-C to stop and scale ollama-amd back down."
  wait "$PORT_FORWARD_PID"
else
  echo "$DEPLOYMENT is ready. Exiting will scale it back down."
fi
