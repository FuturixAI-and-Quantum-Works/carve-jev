# Benchmark methodology

This document defines exactly what CARVE's headline accuracy, latency, and
throughput numbers mean. It is the protocol to follow when reproducing or
extending the results.

## 1. Research questions

The evaluation asks:

1. How accurately does a one-token candidate-logit readout answer typed
   decisions?
2. Which prompt, demonstration count, serialization, precision, and serving
   settings give the best development result?
3. What accuracy–latency trade-off does each CARVE family profile provide?
4. How does the frozen CARVE profile compare with externally published systems
   on the same named transfer protocol?
5. What happens to latency, throughput, and failures as concurrency increases?

The evaluation does **not** claim that raw candidate probabilities are
calibrated probabilities of correctness.

## 2. Benchmark and frozen data identity

- Suite: Decision 1.0 `transfer-v9`
- Public benchmark repository:
  `jaredpalmer/kev@7405b72e73e2d24787f3720d162a21c974ff2ad2`
- Full released test inputs: 1,264
- Headline accuracy denominator: 1,046 clean, knowable decisions
- Suite SHA-256:
  `048abea5e12c73c3a622ce5836898c00fa43766e0bf48fb2459e77ee9873497f`
- Few-shot development-pool SHA-256:
  `53872ba045564315cf3c3dd8fb656e76441c6c514b1a7ff985ff0db3955710cf`

The benchmark files are not redistributed in CARVE. The benchmark wrapper
clones the pinned public repository when needed and verifies the hash before
scoring; users remain responsible for reviewing the applicable terms.

## 3. Inclusion and exclusion

The canonical accuracy run keeps records where:

- `_meta.variant == "clean"`, and
- `_meta.source != "unknowable"`.

Permuted, missing-evidence, and other diagnostic variants remain useful for
robustness studies but are excluded from the published 1,046-item accuracy
denominator. The canonical runner aborts on an HTTP failure rather than
silently removing it; a completed canonical summary therefore reports zero
failed records. Custom runners must report failures separately.

## 4. Development and test discipline

Component choices were made on the development split:

- five system-prompt profiles;
- zero, one, or two demonstrations;
- chat, compact, or minimal demonstration serialization;
- BF16 versus official FP8 weights;
- prefill token budget and serving concurrency;
- adaptive per-task demonstration count.

The selected recipe was then evaluated on the test split. However, the test
split was observed in earlier project research, so the current 82.22% result
is **retrospective**, not a fresh blind confirmatory result. New claims should
use a newly held-out suite.

## 5. Deterministic few-shot selection

Demonstrations come only from the development JSONL. For every task family,
candidate examples are ordered by:

```text
SHA256("carve-fewshot-v1:{seed}:{family}:{record_id}:{question_id}")
```

The seed is `20260924`. The first two ranked examples form the frozen FS2 bank.
All `composition_*` sources share the `composition_logic` family; other source
names retain their own family. Labels and `src` metadata are removed from the
target question before it is sent to CARVE. Test labels are never inserted
into demonstrations.

The adaptive profile independently selected the smallest `k` matching each
family's best development correct count: `k=0` for 12 families, `k=1` for 9,
and `k=2` for 4.

## 6. Frozen inference configuration

The headline CARVE-FS2 profile uses:

- checkpoint: `Qwen/Qwen3.8-27B-FP8`;
- checkpoint revision:
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`;
- baseline system prompt;
- two full chat demonstrations from the frozen bank;
- thinking and preserved thinking disabled;
- one output token;
- temperature `0`;
- exact candidate token IDs requested through `logprob_token_ids`;
- restricted softmax over candidate letters only;
- `max_num_seqs=32`;
- `max_num_batched_tokens=8192`;
- prefix caching enabled;
- one RTX PRO 6000 Blackwell Server Edition.

The model sees the state, criterion, and option descriptions. Option names are
mapped to uppercase candidate letters. It does not generate a JSON answer.

## 7. Decision scoring

For candidate logits \(z_1,\ldots,z_K\), CARVE reports:

```text
p_i = exp(z_i - max(z)) / sum_j exp(z_j - max(z))
```

The scoring rules are:

- **Choice:** exact match between the selected option name and gold label.
- **Noul:** predict `true` when the returned true probability is at least 0.5;
  otherwise predict `false`.
- **Score:** select the option with largest restricted probability and compare
  its label with gold.

Headline accuracy is micro-accuracy:

```text
accuracy = number of correct decisions / number of scored decisions
```

CARVE-FS2 produced 860 correct decisions out of 1,046:

```text
860 / 1046 = 0.8221797323 = 82.22%
```

The raw probabilities are preference distributions among supplied options.
They are not used as calibrated correctness probabilities.

## 8. Latency and throughput

### Serial latency

Concurrency is fixed at one. Timing starts immediately before acquiring the
client semaphore and ends after the HTTP response returns, so it includes
client queueing, CARVE request construction already completed by that point,
upstream serving, response transfer, and parsing. It excludes model download,
server startup, and cold compilation.

Headline latency comes from a warm server. The benchmark script does not
perform hidden warm-up automatically; a reproduction must warm the model and
record that procedure before collecting comparable numbers.

### Loaded latency

Closed-loop clients submit another request after the preceding request
completes. Reported endpoint latency includes queueing. The load sweep uses 512
requests at each concurrency in `1, 2, 4, 8, 16, 32`. The sustained run uses
2,048 shuffled requests at concurrency 8.

### Throughput

```text
throughput = successful HTTP requests / wall-clock seconds
```

Failures are counted independently. Throughput is not inferred from median
latency. CARVE's conservative sustained value is 20.23 requests/s at
concurrency 8 with zero failures.

## 9. External comparison

Jev, Kev, Lux, Nox, Decider, Qwen3.5, Sol, Laya, Eos, and Kai values are
externally published in the
[Decision 1.0 evaluation](https://huggingface.co/llm-semantic-router/Decision-1.0-Lux-9B/blob/main/EVALUATION.md).
CARVE was run locally. The chart is a comparison on the same named benchmark
and denominator; it is not evidence of identical infrastructure.

Jev's published aggregate is 87.19%. The cited source does not provide the
per-task Jev values required for CARVE's family-by-task chart, so no such
values are estimated or reconstructed.

## 10. Statistical comparisons

When two local systems produce predictions for identical decisions, the
project reports:

- errors fixed by the candidate;
- baseline-correct decisions broken by the candidate;
- exact two-sided McNemar p-value.

The few-shot development comparison fixed 60 zero-shot errors, broke 32
zero-shot correct decisions, and produced `p=0.00461`. Statistical
significance does not establish deployment significance, calibration, or
out-of-domain robustness.

## 11. Reproduction

Start the service:

```bash
bash scripts/quickstart.sh
```

Run the complete canonical accuracy benchmark:

```bash
bash scripts/run_full_benchmark.sh
```

The wrapper freezes the prompt, demonstration count, seed, serialization,
concurrency, and output path. For custom experiments, call
`scripts/benchmark_carve.py` directly.

## 12. Artifacts and audit trail

- `artifacts/benchmark-summary.json`: headline result and frozen configuration
- `artifacts/carve-family.json`: family accuracy/latency/throughput profiles
- `artifacts/carve-family-by-task.json`: per-task family comparison
- `artifacts/pareto.json`: accuracy–latency points
- `artifacts/ablation.json`: component-selection results
- `artifacts/load-sweep.json`: concurrency sweep
- `artifacts/sustained-load.json`: 2,048-request sustained run
- `experiments/`: human-readable AIM, method, result, and conclusion reports

Per-example prediction files are intentionally omitted from the public
repository. This limits independent paired-error auditing; rerunning with the
original suite regenerates local outcomes.

## 13. Threats to validity

- The test split is no longer blind.
- Development selection may overfit task-family wording.
- Near-tie decisions can change with batch shape and floating-point reduction
  order.
- External hosted-system latency is not comparable with local GPU latency.
- The public benchmark may not represent a deployment's domains, class
  prevalence, costs, or abstention needs.
- The multimodal path has a smoke test but no representative accuracy
  benchmark.
- Raw softmax probabilities remain uncalibrated.
