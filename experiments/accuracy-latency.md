# Accuracy–latency study

All accuracy values use the same 1,046 clean, knowable Decision 1.0
transfer-v9 test decisions. Serial measurements use concurrency 1; loaded
measurements use concurrency 8 and include endpoint queueing. Hardware was one
RTX PRO 6000 Blackwell Server Edition.

## Serial results

- BF16 zero-shot: 80.11%, 67.5 ms p50
- FP8 zero-shot: 80.50%, 70.3 ms p50
- FP8 one-shot: 80.50%, 71.6 ms p50
- FP8 two-shot: **82.22%**, 72.5 ms p50, 91.0 ms p95
- BF16 two-shot: 81.36%, 109.0 ms p50

The serial Pareto frontier contains BF16 zero-shot, FP8 zero-shot, and FP8
two-shot. The selected FP8 two-shot profile gains 1.72 points over FP8
zero-shot for 2.2 ms additional warm median latency.

## Loaded results

At concurrency 8, FP8 zero-shot delivered 35.87 requests/s at 79.83%
accuracy. FP8 two-shot delivered 23.40 requests/s at 81.93%. A separate
randomized production run measured 21.27 requests/s, and the longer sustained
run measured 20.23 requests/s.

Batching can alter near-tie decisions, so the canonical accuracy claim is the
82.22% serial result. Jev's published transfer accuracy is 87.19%; CARVE
remains lower. Latency comparisons with hosted Jev are not controlled because
hardware, load, and network paths differ.

Machine-readable points are in `artifacts/pareto.json`.
