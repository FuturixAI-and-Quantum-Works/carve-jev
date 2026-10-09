# Changelog

All notable changes follow Keep a Changelog conventions.

## [Unreleased]

### Changed

- Redesigned the README banner and benchmark figures in the FuturixAI brand
  (DM Sans, ink/blue/lime palette, light sky background).

### Added

- CARVE logo, mark, dark-mode logo, and social preview (`assets/`).
- `scripts/brand.py` and `scripts/brand_glyphs.py` with brand tokens and
  outlined wordmarks; `scripts/build_readme_assets.py` now generates every asset.

## [0.1.0] - 2026-09-24

### Added

- CARVE candidate-token decision server and `carve-server` entrypoint.
- TypeSafe-compatible health, model discovery, and System One endpoints.
- Experimental batch and multimodal request paths.
- Raw probability-level and probability-semantics metadata.
- GPU-free mocked tests and CARVE-only benchmark/load scripts.
- Sanitized benchmark summaries, model card, and release documentation.
