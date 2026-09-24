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

## Concrete two-shot example

Suppose the options are ordered as `billing`, then `technical`. CARVE maps
those names to candidate letters `A` and `B`. A request supplies demonstrations
under the target question ID:

```json
{
  "model": "CARVE-27B",
  "state": "The app crashes whenever I upload a receipt.",
  "demonstration_format": "chat",
  "demonstrations": {
    "route": [
      {
        "state": "I was charged twice for one order.",
        "question": {
          "type": "choice",
          "instructions": "Choose the support team.",
          "criteria": {
            "billing": "Payment issue",
            "technical": "Product failure"
          }
        },
        "answer": "billing"
      },
      {
        "state": "The dashboard stays blank after login.",
        "question": {
          "type": "choice",
          "instructions": "Choose the support team.",
          "criteria": {
            "billing": "Payment issue",
            "technical": "Product failure"
          }
        },
        "answer": "technical"
      }
    ]
  },
  "questions": {
    "route": {
      "type": "choice",
      "instructions": "Choose the support team.",
      "criteria": {
        "billing": "Payment issue",
        "technical": "Product failure"
      }
    }
  }
}
```

For this question, the actual chat sequence sent to Qwen is equivalent to:

```text
SYSTEM
Apply the supplied criterion to the supplied evidence. Choose exactly one
listed option. Respond with only its uppercase letter, with no explanation or
reasoning.

USER (demonstration 1)
{"evidence":"I was charged twice for one order.","criterion":"Choose the support team.","options":[{"letter":"A","description":"Payment issue"},{"letter":"B","description":"Product failure"}]}
ASSISTANT
A

USER (demonstration 2)
{"evidence":"The dashboard stays blank after login.","criterion":"Choose the support team.","options":[{"letter":"A","description":"Payment issue"},{"letter":"B","description":"Product failure"}]}
ASSISTANT
B

USER (target)
{"evidence":"The app crashes whenever I upload a receipt.","criterion":"Choose the support team.","options":[{"letter":"A","description":"Payment issue"},{"letter":"B","description":"Product failure"}]}
```

CARVE does not ask Qwen to generate an explanation. It requests one output
token and exact log probabilities for `A` and `B`, applies a restricted
softmax, then maps the winning letter back to `billing` or `technical`.

## Why shots cost time

Mean prompt lengths were 220.5 tokens zero-shot, 431.6 one-shot, and 586.7
two-shot. The two-shot prompt processes 2.66× as many input tokens. CARVE emits
only one output token, so prefill is the bottleneck.

## Prefix-cache experiment

Prefix caching was already enabled, but the hybrid cache resolved to a
784-token physical block while the median two-shot prompt was only 522 tokens.
Most requests therefore could not reuse one complete default block.

We tested `--prefix-match-unit 16`, including a run with dense Mamba
checkpoints. It reduced, rather than improved, performance:

- Default selected server: 72.5 ms serial p50 and 23.40 requests/s at
  concurrency 8
- Fine-grained matching: 113.4 ms serial p50 and 16.70 requests/s
- Fine-grained loaded latency: 416.0 ms p50 and 760.2 ms p95

The measured hit rate was only 2.05%, and scheduler/checkpoint overhead
outweighed reuse. Fine-grained prefix matching was rejected and the default
server configuration restored.

## Adaptive-k

A development-only policy selected the smallest shot count matching each task
family's best development correct count: k=0 for 12 families, k=1 for 9, and
k=2 for 4. On test it scored 80.88%, versus 82.22% for full two-shot, while
raising concurrency-8 throughput from 23.40 to 27.42 requests/s.

Adaptive-k is an optional speed profile with a measured 1.34-point quality
cost. It must be revalidated for a deployment's task families. Compact and
minimal demonstration serialization were rejected because both reduced
development accuracy to 78.71%.

There was no measured free removal of few-shot prefill cost. A future no-loss
approach would require a shorter learned prompt or engine support for cheaply
pinning and restoring recurrent state at the demonstration boundary.
