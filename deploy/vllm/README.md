# vLLM on AMD RDNA4

This directory stages a practical vLLM deployment path for the existing AMD GPU node in the cluster.

Current assumptions:

- GPU class: Radeon RX 9070 XT 16 GB
- Cluster node: `kspld0`
- Kubernetes GPU resource: `amd.com/gpu`
- Device mounts required: `/dev/kfd` and `/dev/dri`
- Orchestro will talk to vLLM through the existing OpenAI-compatible backend

## Model Picks for RX 9070 XT 16 GB

These are the models worth trying first on a 16 GB RDNA4 card.

### 1. Default balanced model

- Model: `Qwen/Qwen3-8B-FP8`
- Why: best current quality/speed tradeoff on 16 GB while staying compatible with vLLM on the AMD ROCm image we tested
- Use for: general chat, agentic routing, tool use, coding assist, planning
- Status: good deployment target, but the fully validated live Orchestro path in this repo is currently `Qwen/Qwen3-4B`
- vLLM args:
  - `--enable-reasoning`
  - `--reasoning-parser deepseek_r1`
  - `--max-model-len 16384`
  - `--gpu-memory-utilization 0.9`

### 2. Fast model

- Model: `Qwen/Qwen3-4B`
- Why: much faster and safer on limited VRAM, good for routing, cheap retries, and tool loops
- Use for: fast shell work, classification, planning drafts, lightweight coding
- Status: fully validated end to end with Orchestro on the cluster-backed vLLM endpoint
- vLLM args:
  - `--enable-reasoning`
  - `--reasoning-parser deepseek_r1`
  - `--max-model-len 16384`
  - `--gpu-memory-utilization 0.9`

### 3. Quality-max, still plausible on 16 GB

- Model: `Qwen/Qwen2.5-Coder-7B-Instruct`
- Why: still one of the strongest small open coding models and a better coding-specific fallback than forcing a larger Qwen3 model onto 16 GB
- Use for: code editing, code review, and coding-focused agent loops
- Caveat: this is not the newest Qwen line, but it is still a strong practical coding target for this VRAM class
- vLLM args:
  - `--max-model-len 8192`
  - `--max-model-len 8192`
  - `--gpu-memory-utilization 0.92`

## Models to skip on 16 GB

- `Qwen/Qwen3-30B-A3B-Instruct-2507`
- `Qwen3-Coder-480B-A35B-Instruct`
- `Qwen/Qwen3-14B-AWQ` on the current ROCm vLLM image

The MoE variants are simply the wrong size for a single 16 GB card. On top of that, the AMD ROCm vLLM image we tested crashes on AWQ with `awq_dequantize` missing, so AWQ should be treated as unsupported here unless the image changes.

## Cluster shape

The manifest in `k8s/vllm-rdna4-template.yaml` mirrors the current AMD Ollama deployment pattern:

- `nodeSelector: kubernetes.io/hostname=kspld0`
- `amd.com/gpu: 1`
- privileged container
- `/dev/kfd` and `/dev/dri` mounted from host
- PVC-backed Hugging Face cache

The template also uses a long `startupProbe`, because first boot on RDNA4 can spend multiple minutes downloading weights, compiling kernels, and capturing graphs before the API socket is available.

The default preset uses AMD's published Radeon/Navi vLLM image family. You can still override it with `ORCHESTRO_VLLM_IMAGE`.

## Render a manifest

Use one of the presets:

```bash
./scripts/render-vllm-rdna4-manifest.sh balanced > /tmp/vllm-balanced.yaml
./scripts/render-vllm-rdna4-manifest.sh fast > /tmp/vllm-fast.yaml
./scripts/render-vllm-rdna4-manifest.sh maxq > /tmp/vllm-maxq.yaml
```

Then apply it:

```bash
sudo kubectl apply -f /tmp/vllm-balanced.yaml
```

## Point Orchestro at vLLM

Once the service is up, port-forward it locally:

```bash
./scripts/vllm-port-forward.sh
```

By default, that helper now targets the currently validated service name `vllm-qwen3-4b`. Override `ORCHESTRO_VLLM_SERVICE` if you want to point at `vllm-qwen3-8b-fp8` or another deployment.

Then export:

```bash
export ORCHESTRO_OPENAI_BASE_URL=http://127.0.0.1:8000/v1
export ORCHESTRO_OPENAI_MODEL=Qwen/Qwen3-4B
export ORCHESTRO_EMBED_BASE_URL=http://127.0.0.1:8000/v1
```

If you still want Ollama for embeddings, keep `ORCHESTRO_EMBED_BASE_URL` pointed at Ollama and use vLLM only for chat.

## Smoke test the live endpoint

Once port-forwarding is active, run:

```bash
./scripts/vllm-smoke.sh
PYTHONPATH=src .venv/bin/python -m orchestro.cli bench --suite benchmarks/vllm-live.json --backend openai-compat --strategy direct
```
