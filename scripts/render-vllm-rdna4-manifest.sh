#!/usr/bin/env bash
set -euo pipefail

PRESET="${1:-balanced}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="$ROOT/deploy/vllm/k8s/vllm-rdna4-template.yaml"

export NAMESPACE="${ORCHESTRO_VLLM_NAMESPACE:-ollama}"
export NODE_NAME="${ORCHESTRO_VLLM_NODE:-kspld0}"
export VLLM_IMAGE="${ORCHESTRO_VLLM_IMAGE:-rocm/vllm-dev:rocm6.4.2_navi_ubuntu24.04_py3.12_pytorch_2.7_vllm_0.9.2}"
export HF_TOKEN="${HUGGING_FACE_HUB_TOKEN:-}"

case "$PRESET" in
  balanced)
    export APP_NAME="vllm-qwen3-8b-fp8"
    export CACHE_PVC="vllm-hf-cache-qwen3-8b-fp8"
    export CACHE_SIZE="${ORCHESTRO_VLLM_CACHE_SIZE:-100Gi}"
    export MODEL_ID="Qwen/Qwen3-8B-FP8"
    export MAX_MODEL_LEN="${ORCHESTRO_VLLM_MAX_MODEL_LEN:-8192}"
    export GPU_MEMORY_UTILIZATION="${ORCHESTRO_VLLM_GPU_MEM_UTIL:-0.92}"
    export EXTRA_ARGS='--enable-reasoning --reasoning-parser deepseek_r1'
    ;;
  fast)
    export APP_NAME="vllm-qwen3-4b"
    export CACHE_PVC="vllm-hf-cache-qwen3-4b"
    export CACHE_SIZE="${ORCHESTRO_VLLM_CACHE_SIZE:-60Gi}"
    export MODEL_ID="Qwen/Qwen3-4B"
    export MAX_MODEL_LEN="${ORCHESTRO_VLLM_MAX_MODEL_LEN:-16384}"
    export GPU_MEMORY_UTILIZATION="${ORCHESTRO_VLLM_GPU_MEM_UTIL:-0.90}"
    export EXTRA_ARGS='--enable-reasoning --reasoning-parser deepseek_r1'
    ;;
  maxq)
    export APP_NAME="vllm-qwen3-4b-coding"
    export CACHE_PVC="vllm-hf-cache-qwen3-4b-coding"
    export CACHE_SIZE="${ORCHESTRO_VLLM_CACHE_SIZE:-60Gi}"
    export MODEL_ID="Qwen/Qwen3-4B"
    export MAX_MODEL_LEN="${ORCHESTRO_VLLM_MAX_MODEL_LEN:-8192}"
    export GPU_MEMORY_UTILIZATION="${ORCHESTRO_VLLM_GPU_MEM_UTIL:-0.92}"
    export EXTRA_ARGS=''
    ;;
  *)
    echo "unknown preset: $PRESET" >&2
    echo "expected one of: balanced, fast, maxq" >&2
    exit 1
    ;;
esac

if ! command -v envsubst >/dev/null 2>&1; then
    echo "envsubst is required" >&2
    exit 1
fi

envsubst < "$TEMPLATE"
