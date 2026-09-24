# References

CARVE builds on public models, serving infrastructure, typed-decision
interfaces, and evaluation protocols. No code from the related research
projects listed below is copied into CARVE.

## Backbone and serving

1. Qwen Team. [Qwen3.8-27B-FP8 model card](https://huggingface.co/Qwen/Qwen3.8-27B-FP8).
   Apache-2.0 model weights used for the reported CARVE configuration.
2. Kwon et al. [Efficient Memory Management for Large Language Model Serving
   with PagedAttention](https://arxiv.org/abs/2309.06180). SOSP 2023.
3. [vLLM project](https://github.com/vllm-project/vllm). CARVE requires
   candidate-token log-probability support; the exact tested revision is
   recorded in `docs/reproducibility.md`.

## Typed decision systems and evaluations

4. TypeSafe AI. [Introducing System One Models &
   Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev).
5. [TypeSafe SDK documentation](https://docs.typesafe.ai/). CARVE implements
   the tested System One request and response contract.
6. vLLM Semantic Router. [Decision 1.0 evaluation
   report](https://huggingface.co/llm-semantic-router/Decision-1.0-Lux-9B/blob/main/EVALUATION.md).
7. Standhartinger et al. [JevBench](https://github.com/fstandhartinger/jevbench).
8. Palmer. [Kev](https://github.com/jaredpalmer/kev).
9. ConvAI Innovations. [Laya](https://github.com/NandhaKishorM/laya).

## Related readout and calibration work

10. Nokia Applied Research et al.
    [AnyJev](https://github.com/nokia-applied-research/AnyJev). Related
    candidate-logit readout, option-order debiasing, post-hoc calibration, and
    closed-form decision-head research.
11. Guo et al. [On Calibration of Modern Neural
    Networks](https://arxiv.org/abs/1706.04599). ICML 2017.
12. Brier. [Verification of Forecasts Expressed in Terms of
    Probability](https://doi.org/10.1175/1520-0493(1950)078%3C0001:VOFEIT%3E2.0.CO;2).
    Monthly Weather Review, 1950.

## Naming and independence

CARVE is an independent research implementation. It is not affiliated with or
endorsed by Qwen, Alibaba Cloud, vLLM, TypeSafe AI, Jev, Semantic Router,
JevBench, AnyJev, Laya, or Kev.
