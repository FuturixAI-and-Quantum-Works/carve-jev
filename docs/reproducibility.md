# Reproducibility

## Frozen identities

- Qwen checkpoint: `Qwen/Qwen3.8-27B-FP8`
- Qwen revision: `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`
- vLLM revision: `b44895cf932be890235b700b49b0753261cf5b97`
- TypeSafe Python SDK: `0.7.1`
- TypeSafe JavaScript SDK: `0.6.0`
- Few-shot seed: `20260924`
- Transfer-v9 suite SHA-256:
  `048abea5e12c73c3a622ce5836898c00fa43766e0bf48fb2459e77ee9873497f`

## Canonical configuration

Use the baseline prompt, full chat demonstrations, two development-only
examples per task family, FP8 weights, thinking disabled, one output token,
`max_num_seqs=32`, and `max_num_batched_tokens=8192`.

The development bank is selected by sorting SHA-256 ranks over the seed, task
family, record ID, and question ID. Composition tasks share the
`composition_logic` family. Test labels are never inserted into prompts.

## Accuracy reproduction

Obtain Decision 1.0 transfer-v9 under its applicable terms; it is not bundled.

```bash
python scripts/benchmark_carve.py \
  --suite /path/to/transfer-v9/test.jsonl \
  --endpoint http://127.0.0.1:8011 \
  --few-shot-pool /path/to/transfer-v9/development.jsonl \
  --few-shot-k 2 \
  --few-shot-reserve 2 \
  --few-shot-seed 20260924 \
  --demonstration-format chat \
  --concurrency 1 \
  --output artifacts/reproduced-summary.json
```

Verify the suite hash before comparing scores. GPU kernels, driver versions,
vLLM scheduling, and batch shape can move near-tie outcomes.

## Load reproduction

```bash
python scripts/benchmark_carve_load.py \
  --suite /path/to/transfer-v9/test.jsonl \
  --few-shot-pool /path/to/transfer-v9/development.jsonl \
  --concurrency 1,2,4,8,16,32 \
  --requests 512 \
  --output artifacts/reproduced-load-sweep.json
```

Machine-readable files in `artifacts/` are sanitized summaries from the source
workspace. Datasets, generated prediction JSONL, model weights, caches, and
virtual environments are intentionally excluded.

## README comparison figure

The model-comparison figure is generated from committed JSON rather than
hand-edited:

```bash
python scripts/build_readme_assets.py
```

Its inputs, external provenance, and comparability caveat are recorded in
`artifacts/decision1-model-comparison.json`.
