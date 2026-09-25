# Quickstart

## Requirements

- Linux, Python 3.11+, `git`, `curl`, and a recent NVIDIA driver
- Enough GPU memory for Qwen3.8-27B-FP8 and its KV cache
- At least 45 GiB free disk for a fresh environment plus checkpoint download,
  or an existing local checkpoint
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
space. A preflight check stops before installation when storage is
insufficient. Set `CARVE_MODEL` and `CARVE_TOKENIZER` in `.env` to reuse an
existing local checkpoint, or point `HF_HOME` at a larger filesystem. The
script installs `vllm==0.30.0`, which passed the clean-install test. To try
another published package or source reference, set `CARVE_VLLM_SPEC`; to use a
vLLM already installed in `.venv`, set `CARVE_SKIP_VLLM_INSTALL=1`.

Examples:

```bash
CARVE_VLLM_SPEC=vllm bash scripts/quickstart.sh
CARVE_VLLM_SPEC='vllm==<compatible-version>' bash scripts/quickstart.sh
CARVE_SKIP_VLLM_INSTALL=1 bash scripts/quickstart.sh
```

## Runtime versions and benchmark reproducibility

The 82.22% headline result used historical vLLM source revision
`b44895cf932be890235b700b49b0753261cf5b97`. Its old precompiled wheel is not
assumed to remain downloadable, so the quickstart does not depend on it.

A clean installation with `vllm==0.30.0` completed the full benchmark at
81.26%, 72.6 ms p50, and 91.2 ms p95. Candidate decisions near numerical ties
can move across engine/kernel versions. Use the frozen source revision and
build vLLM from source if reproducing the historical headline exactly; use the
default quickstart when validating current developer usability.

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
- `No space left on device`: provide at least 45 GiB for a fresh setup, use a
  local checkpoint through `CARVE_MODEL`, or move `HF_HOME`. Do not bypass the
  disk guard unless storage has been handled separately.
- `FlashInfer requires GPUs with sm75 or higher` on an SM120 Blackwell GPU:
  leave `VLLM_USE_FLASHINFER_SAMPLER=0` enabled. CARVE sets this safe default
  in `.env.example`; override it only after validating your vLLM/FlashInfer
  combination.
- CUDA out of memory: lower `CARVE_GPU_MEMORY_UTILIZATION`,
  `CARVE_MAX_NUM_SEQS`, or `CARVE_MAX_MODEL_LEN`.
- Model access denied: authenticate with `huggingface-cli login` and accept any
  applicable model terms.
- Port already in use: change `CARVE_VLLM_PORT` or `CARVE_API_PORT` in `.env`.
