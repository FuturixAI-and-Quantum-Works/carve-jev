# Changelog

All notable changes follow Keep a Changelog conventions.

## [Unreleased]

### Added

- Experimental `POST /v1/tool-calls` CARVE-Tools endpoint.
- One-token probabilistic function selection with auto, required, none, and
  forced modes.
- No-tool and configurable low-confidence gates.
- JSON Schema-constrained argument generation and post-generation validation.
- OpenAI-shaped tool calls plus parsed arguments without server-side execution.

## [0.1.0] - 2026-09-24

### Added

- CARVE candidate-token decision server and `carve-server` entrypoint.
- TypeSafe-compatible health, model discovery, and System One endpoints.
- Experimental batch and multimodal request paths.
- Raw probability-level and probability-semantics metadata.
- GPU-free mocked tests and CARVE-only benchmark/load scripts.
- Sanitized benchmark summaries, model card, and release documentation.
