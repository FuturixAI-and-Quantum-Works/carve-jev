# Reproducibility

This page is the command-oriented reproduction guide. See
[`benchmark-methodology.md`](benchmark-methodology.md) for data inclusion,
split discipline, scoring formulas, timing boundaries, external-comparison
rules, statistics, and threats to validity.

## Frozen identities

- Qwen checkpoint: `Qwen/Qwen3.8-27B-FP8`
- Qwen revision: `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`
- vLLM revision: `b44895cf932be890235b700b49b0753261cf5b97`
- TypeSafe Python SDK: `0.7.1`
- TypeSafe JavaScript SDK: `0.6.0`
- Few-shot seed: `20260924`
- Kev benchmark checkout:
  `7405b72e73e2d24787f3720d162a21c974ff2ad2`
- Transfer-v9 suite SHA-256:
  `048abea5e12c73c3a622ce5836898c00fa43766e0bf48fb2459e77ee9873497f`

These identities describe the historical 82.22% headline run. The developer
quickstart pins the currently available and clean-tested `vllm==0.30.0`;
engine and kernel changes can move near-tie decisions.

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
bash scripts/run_full_benchmark.sh
```

The wrapper fetches the pinned public Kev checkout and verifies the suite hash
before running. GPU kernels, driver versions, vLLM scheduling, and batch shape
can move near-tie outcomes. The
[fresh-install validation record](../artifacts/fresh-install-validation.json)
captures the current-runtime compatibility result; exact headline
reproduction requires the frozen vLLM source revision above.

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

## README figures and brand assets

The banner, logos, social preview, model-comparison figure, and CARVE-family
figure are generated rather than hand-edited. The two charts read committed JSON:

```bash
python scripts/build_readme_assets.py
```

Their inputs, external provenance, and comparability caveats are recorded in
`artifacts/decision1-model-comparison.json` and
`artifacts/carve-family-by-task.json`.
