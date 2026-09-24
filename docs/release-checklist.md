# Release checklist

- [ ] Confirm the Qwen checkpoint terms for the intended deployment.
- [ ] Replace provisional citation metadata with final authors and repository URL.
- [ ] Verify third-party links, versions, and notices.
- [ ] Install and test from a clean Python environment.
- [ ] Run `ruff format --check .`, `ruff check .`, and `pytest`.
- [ ] Start the pinned vLLM revision and run the live SDK smoke test.
- [ ] Reproduce one benchmark summary from a verified suite hash.
- [ ] Confirm no secrets, private URLs, user data, datasets, prediction JSONL,
      weights, caches, virtual environments, or machine-specific paths.
- [ ] Keep CARVE's 82.22% separate from Jev's published 87.19%.
- [ ] Describe probabilities as raw candidate-token preferences, not calibrated
      correctness confidence.
- [ ] Describe local speed results with hardware and non-controlled comparison
      caveats.
