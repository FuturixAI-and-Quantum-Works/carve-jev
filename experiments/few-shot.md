# Few-shot and adaptive-k study

Demonstrations were selected only from Decision 1.0 development data by a
fixed SHA-256 ordering with seed `20260924`. Fifty records across 25 task
families were reserved; every development condition used the same remaining
996 decisions.

## Two-shot selection

- Zero-shot: 77.11% (768/996), 66.6 ms p50
- One-shot: 78.61% (783/996), 79.0 ms p50
- Two-shot: **79.92%** (796/996), 108.8 ms p50

Two-shot was selected before the confirmatory test. In BF16 it scored 81.36%
on test versus 80.11% zero-shot; the 1.24-point gain was not significant
(exact McNemar p=0.208). The selected FP8 two-shot system later scored 82.22%.

## Why shots cost time

Mean prompt lengths were 220.5 tokens zero-shot, 431.6 one-shot, and 586.7
two-shot. The two-shot prompt processes 2.66× as many input tokens. CARVE emits
only one output token, so prefill is the bottleneck.

## Adaptive-k

A development-only policy selected the smallest shot count matching each task
family's best development correct count: k=0 for 12 families, k=1 for 9, and
k=2 for 4. On test it scored 80.88%, versus 82.22% for full two-shot, while
raising concurrency-8 throughput from 23.40 to 27.42 requests/s.

Adaptive-k is an optional speed profile with a measured 1.34-point quality
cost. It must be revalidated for a deployment's task families. Compact and
minimal demonstration serialization were rejected because both reduced
development accuracy to 78.71%.
