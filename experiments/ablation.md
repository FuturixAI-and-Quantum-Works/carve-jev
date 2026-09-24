# Component ablation

This staged ablation selected the prompt, demonstration count and format,
weight precision, and vLLM prefill budget. Tuning used Decision 1.0
transfer-v9 development data; the test split was used only after selection.

## Findings

- Prompt profiles on 1,046 development decisions: baseline **77.82%**,
  evidence 76.77%, strict 74.86%, semantic 74.47%, checklist 73.23%.
- Demonstrations on a shared 996-decision denominator: zero-shot 77.11%,
  one-shot 78.61%, two-shot **79.92%**. Two-shot versus zero-shot had 60
  fixes, 32 breaks, and exact McNemar p=0.00461.
- Serialization: chat **79.92%**, compact 78.71%, minimal 78.71%.
- Precision with two-shot chat: BF16 and FP8 both **79.92%** on development;
  FP8 reduced serial p50 from 108.8 ms to 73.6 ms.
- Prefill budget at concurrency 16: 8,192 tokens delivered 24.92 requests/s;
  16,384 tokens delivered 17.50 requests/s.

The selected configuration is baseline prompt, two full chat demonstrations,
official FP8 weights, thinking disabled, one output token,
`max_num_seqs=32`, and `max_num_batched_tokens=8192`.

On test, FP8 scored 82.22% versus BF16 two-shot at 81.36%. This is an observed
quantization-boundary effect, not evidence that FP8 generally improves model
reasoning. See `artifacts/ablation.json`.
