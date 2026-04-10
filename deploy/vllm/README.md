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

- Model: `Qwen/Qwen3-8B-AWQ`
- Why: best quality/speed tradeoff that still leaves room for KV cache on 16 GB
- Use for: general chat, agentic routing, tool use, coding assist, planning
- vLLM args:
  - `--enable-reasoning`
  - `--reasoning-parser deepseek_r1`
  - `--max-model-len 16384`
  - `--gpu-memory-utilization 0.9`

### 2. Fast model

- Model: `Qwen/Qwen3-4B`
- Why: much faster and safer on limited VRAM, good for routing, cheap retries, and tool loops
- Use for: fast shell work, classification, planning drafts, lightweight coding
- vLLM args:
  - `--enable-reasoning`
  - `--reasoning-parser deepseek_r1`
  - `--max-model-len 16384`
  - `--gpu-memory-utilization 0.9`

### 3. Quality-max, still plausible on 16 GB

- Model: `Qwen/Qwen3-14B-AWQ`
- Why: strongest dense Qwen3 target that is still realistic on consumer VRAM when quantized
- Use for: harder coding and reasoning queries where latency is acceptable
- Caveat: this is the first thing to cut if ROCm or AWQ behavior is unstable on the node
- vLLM args:
  - `--enable-reasoning`
  - `--reasoning-parser deepseek_r1`
  - `--max-model-len 8192`
  - `--gpu-memory-utilization 0.92`

## Models to skip on 16 GB

- `Qwen/Qwen3-30B-A3B-Instruct-2507`
- `Qwen3-Coder-480B-A35B-Instruct`

Even though the MoE variants have low active parameters, their total weight footprint is wrong for a 16 GB single-card deployment.

## Why not Qwen3-Coder first?

The current official Qwen3-Coder launch leads with the very large 480B-A35B model, and explicitly says smaller sizes are still on the way. For a 16 GB local deployment, the dense Qwen3 line is the practical target right now.

## Cluster shape

The manifest in `k8s/vllm-rdna4-template.yaml` mirrors the current AMD Ollama deployment pattern:

- `nodeSelector: kubernetes.io/hostname=kspld0`
- `amd.com/gpu: 1`
- privileged container
- `/dev/kfd` and `/dev/dri` mounted from host
- PVC-backed Hugging Face cache

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

Then export:

```bash
export ORCHESTRO_OPENAI_BASE_URL=http://127.0.0.1:8000/v1
export ORCHESTRO_OPENAI_MODEL=Qwen/Qwen3-8B-AWQ
export ORCHESTRO_EMBED_BASE_URL=http://127.0.0.1:8000/v1
```

If you still want Ollama for embeddings, keep `ORCHESTRO_EMBED_BASE_URL` pointed at Ollama and use vLLM only for chat.
