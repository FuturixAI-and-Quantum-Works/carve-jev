# Quickstart

## Requirements

- Linux, Python 3.11+, `git`, `curl`, and a recent NVIDIA driver
- Enough GPU memory for Qwen3.8-27B-FP8 and its KV cache
- A vLLM build supporting `logprob_token_ids`
- Hugging Face access to `Qwen/Qwen3.8-27B-FP8`

The reported configuration used one 96 GB RTX PRO 6000 Blackwell Server
Edition and vLLM revision
`b44895cf932be890235b700b49b0753261cf5b97` after candidate-token log-probability
support had landed upstream. Earlier development used the compatible
[`razorback16/vllm`](https://github.com/razorback16/vllm) fork.

## Fast path: install and start everything

This creates `.venv`, installs CARVE and vLLM when needed, creates `.env`, then
starts both the vLLM model server and the CARVE API:

```bash
git clone https://github.com/rudransh2004/carve-jev.git && cd carve-jev && bash scripts/quickstart.sh
```

The first run downloads the model and can take significant time and disk
space. The script installs the current `vllm` package by default. To supply a
specific package or source reference, set `CARVE_VLLM_SPEC`; to use a vLLM
already installed in `.venv`, set `CARVE_SKIP_VLLM_INSTALL=1`.

Examples:

```bash
CARVE_VLLM_SPEC='vllm==<compatible-version>' bash scripts/quickstart.sh
CARVE_SKIP_VLLM_INSTALL=1 bash scripts/quickstart.sh
```

## Reproduce the tested environment

For exact comparisons, use the frozen vLLM source and compiled-wheel revisions:

```bash
python -m venv .venv
source .venv/bin/activate
git clone https://github.com/vllm-project/vllm.git .vendor/vllm
git -C .vendor/vllm checkout b44895cf932be890235b700b49b0753261cf5b97
VLLM_USE_PRECOMPILED=1 \
VLLM_PRECOMPILED_WHEEL_COMMIT=9bbf7418e85020dc76da9f60cdfe6c4e912ec048 \
  python -m pip install -e .vendor/vllm
python -m pip install -e .
cp .env.example .env
set -a; source .env; set +a
VLLM_BIN=.venv/bin/vllm PYTHON_BIN=.venv/bin/python bash scripts/serve_carve.sh
```

The pinned precompiled wheel is an installation aid; the CARVE-facing Python
source revision is the vLLM revision listed above.

## Use an existing vLLM server

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

## Run the full benchmark

With the server running, execute the canonical FP8 two-shot benchmark:

```bash
bash scripts/run_full_benchmark.sh
```

The wrapper clones the pinned public Kev benchmark checkout into `.cache/kev`
when necessary, verifies the test-suite SHA-256, evaluates all 1,046 canonical
decisions, and writes `artifacts/reproduced-summary.json`. To use existing
files, set both `CARVE_TEST_SUITE` and `CARVE_DEV_SUITE`. Override the result
path with `CARVE_BENCHMARK_OUTPUT`. See
[`benchmark-methodology.md`](benchmark-methodology.md) before comparing the
result with published numbers.

## Operating profiles

- Latency-sensitive: concurrency 1.
- Recommended loaded profile: concurrency 8.
- Quality profile: two frozen task-family demonstrations.
- Maximum-throughput profile: zero-shot, with lower measured accuracy.

The launch script starts the model server and API together. Change model,
ports, GPU assignment, limits, and executable paths through `.env`.

The local API has no authentication. Do not bind it to an untrusted network
without a security gateway.

## Troubleshooting

- `logprob_token_ids` rejected: the installed vLLM is too old or incompatible;
  use the tested revision above.
- CUDA out of memory: lower `CARVE_GPU_MEMORY_UTILIZATION`,
  `CARVE_MAX_NUM_SEQS`, or `CARVE_MAX_MODEL_LEN`.
- Model access denied: authenticate with `huggingface-cli login` and accept any
  applicable model terms.
- Port already in use: change `CARVE_VLLM_PORT` or `CARVE_API_PORT` in `.env`.
