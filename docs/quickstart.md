# Quickstart

## Requirements

- Linux, Python 3.11+, `curl`, and a recent NVIDIA driver
- Enough GPU memory for the selected checkpoint and KV cache
- A vLLM build supporting `logprob_token_ids`

The reported configuration used one 96 GB RTX PRO 6000 Blackwell Server
Edition and vLLM revision
`b44895cf932be890235b700b49b0753261cf5b97` from the compatible
[`razorback16/vllm`](https://github.com/razorback16/vllm) fork.

## Install and start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
# Install a compatible vLLM build into this environment.
cp .env.example .env
set -a; source .env; set +a
bash scripts/serve_carve.sh
```

To run the API separately from an existing vLLM process:

```bash
carve-server \
  --upstream http://127.0.0.1:8000 \
  --model qwen38-27b \
  --tokenizer Qwen/Qwen3.8-27B-FP8
```

Verify:

```bash
curl --fail http://127.0.0.1:8011/health
curl --fail http://127.0.0.1:8011/v1/models
```

## Operating profiles

- Latency-sensitive: concurrency 1.
- Recommended loaded profile: concurrency 8.
- Quality profile: two frozen task-family demonstrations.
- Maximum-throughput profile: zero-shot, with lower measured accuracy.

The launch script starts the model server and API together. Change model,
ports, GPU assignment, limits, and executable paths through `.env`.

The local API has no authentication. Do not bind it to an untrusted network
without a security gateway.
