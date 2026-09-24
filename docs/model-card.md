# CARVE-27B model card

## Model

CARVE-27B is an Apache-2.0 open-source Jev-style decision readout over
`Qwen/Qwen3.8-27B-FP8`. It presents evidence, a criterion, and up to 26 options
to the backbone with thinking disabled, requests one token, obtains candidate
letter logits from vLLM, and applies a softmax restricted to those letters.

CARVE packages inference logic and an API. This repository does not distribute
model weights.

## Intended use

- Routing, classification, and ordinal scoring with explicit options
- Local evaluation of typed System One workflows
- Research on candidate-token readouts and low-decode-latency decisions

Human review and application-specific validation are required for
high-impact, safety-critical, financial, medical, legal, or access-control
decisions.

## Output interpretation

Outputs are typed Noul, Choice, or Score answers. Reported probabilities and
the wire-compatible `confidence` field are raw restricted candidate-token
preferences. They are **not calibrated probabilities of correctness**.
Thresholds must be validated and calibrated independently on representative
deployment data.

## Evaluation

The selected FP8 two-shot configuration scored 860/1,046 (**82.22%**) on the
clean, knowable Decision 1.0 transfer-v9 test decisions. Jev's published score
is **87.19%**; CARVE does not match it. This is a retrospective result because
the test split was observed during earlier research, not a fresh blind
evaluation.

Warm serial latency was 72.5 ms p50 and 91.0 ms p95. A sustained
concurrency-8 run delivered 20.23 requests/s. These measurements used one
NVIDIA RTX PRO 6000 Blackwell Server Edition and are not controlled
comparisons with hosted systems.

## Limitations

- Accuracy varies substantially by task family.
- Two-shot quality depends on labeled development examples.
- The candidate representation is limited to 26 uppercase-letter tokens.
- Prompt wording, candidate order, quantization, and batch shape can change
  results, particularly for near ties.
- Missing evidence does not reliably produce low raw candidate probability.
- Only a synthetic image smoke test supports the multimodal path.
- No fairness, toxicity, privacy, robustness, or domain-specific safety audit
  has been completed.

## Provenance

- Backbone revision:
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`
- vLLM revision:
  `b44895cf932be890235b700b49b0753261cf5b97`
- Benchmark suite SHA-256:
  `048abea5e12c73c3a622ce5836898c00fa43766e0bf48fb2459e77ee9873497f`
- Few-shot seed: `20260924`

See `docs/reproducibility.md` and `THIRD_PARTY.md` for data, software, and
license boundaries.
