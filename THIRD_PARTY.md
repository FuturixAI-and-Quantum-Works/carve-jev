# Third-party software, models, and data

CARVE source code is Apache-2.0. That license does not relicense external
models, datasets, services, or packages.

## Runtime dependencies

- [Qwen3.8-27B-FP8](https://huggingface.co/Qwen/Qwen3.8-27B-FP8) supplies the
  Apache-2.0 backbone weights. Weights are not distributed here; review the
  model card and license before use.
- [vLLM](https://github.com/vllm-project/vllm) supplies inference serving.
  Reported experiments used revision
  `b44895cf932be890235b700b49b0753261cf5b97` from a
  [compatible fork](https://github.com/razorback16/vllm). vLLM is Apache-2.0.
- FastAPI, HTTPX, Transformers, Uvicorn, and development dependencies retain
  the licenses published by their respective maintainers.

## Protocol and evaluation

- [TypeSafe AI](https://typesafe.ai/) defines the System One API shape.
  CARVE was tested with
  [typesafe-sdk](https://pypi.org/project/typesafe-sdk/) 0.7.1 and
  [@typesafe-ai/sdk](https://www.npmjs.com/package/@typesafe-ai/sdk) 0.6.0.
  The SDKs are optional clients, not server runtime dependencies.
- [Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev) is a
  hosted external comparison. Jev code or weights are not included.
- [Decision 1.0 / Semantic Router](https://huggingface.co/llm-semantic-router/Decision-1.0-Lux-9B/blob/main/EVALUATION.md)
  provides the benchmark protocol and published comparison. Dataset rows are
  not included.
- [JevBench](https://github.com/fstandhartinger/jevbench) is related external
  evaluation work and is not included.

## Related work and inspiration

The following projects are references, not copied code or dependencies:

- [AnyJev](https://github.com/nokia-applied-research/AnyJev)
- [Laya](https://github.com/NandhaKishorM/laya)
- [Kev](https://github.com/jaredpalmer/kev)

Names and trademarks belong to their owners. CARVE is not affiliated with or
endorsed by these projects or organizations.
