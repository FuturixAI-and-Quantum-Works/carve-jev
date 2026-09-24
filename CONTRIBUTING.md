# Contributing

Thank you for improving CARVE.

1. Open an issue for substantial behavioral or benchmark changes.
2. Create a focused branch and add tests for changed behavior.
3. Run `ruff format --check .`, `ruff check .`, and `pytest`.
4. Document benchmark hardware, data hashes, seeds, and failed requests.
5. Do not commit datasets, prediction JSONL, model weights, secrets, caches, or
   machine-specific paths.

Claims must distinguish measured CARVE results from externally published
numbers. Never describe raw candidate-token probabilities as calibrated
confidence. New benchmark claims require a frozen protocol and machine-readable
summary.

Contributions are licensed under Apache-2.0.
