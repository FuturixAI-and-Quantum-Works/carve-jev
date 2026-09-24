#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

ENDPOINT="${CARVE_ENDPOINT:-http://127.0.0.1:8011}"
MODEL="${CARVE_SYSTEM_NAME:-CARVE-27B}"
OUTPUT="${CARVE_BENCHMARK_OUTPUT:-$ROOT/artifacts/reproduced-summary.json}"
PYTHON="${CARVE_PYTHON_BIN:-$ROOT/.venv/bin/python}"
KEV_REPOSITORY="${CARVE_BENCHMARK_REPOSITORY:-https://github.com/jaredpalmer/kev.git}"
KEV_REVISION="${CARVE_BENCHMARK_REVISION:-7405b72e73e2d24787f3720d162a21c974ff2ad2}"
KEV_CHECKOUT="${CARVE_BENCHMARK_CHECKOUT:-$ROOT/.cache/kev}"
EXPECTED_SUITE_SHA256="048abea5e12c73c3a622ce5836898c00fa43766e0bf48fb2459e77ee9873497f"

if [[ ! -x "$PYTHON" ]]; then
  echo "Python environment not found at $PYTHON; run scripts/quickstart.sh first." >&2
  exit 1
fi

if [[ -n "${CARVE_TEST_SUITE:-}" || -n "${CARVE_DEV_SUITE:-}" ]]; then
  TEST_SUITE="${CARVE_TEST_SUITE:?Set both CARVE_TEST_SUITE and CARVE_DEV_SUITE}"
  DEV_SUITE="${CARVE_DEV_SUITE:?Set both CARVE_TEST_SUITE and CARVE_DEV_SUITE}"
else
  if [[ ! -d "$KEV_CHECKOUT/.git" ]]; then
    mkdir -p "$(dirname "$KEV_CHECKOUT")"
    git clone "$KEV_REPOSITORY" "$KEV_CHECKOUT"
    git -C "$KEV_CHECKOUT" checkout --detach "$KEV_REVISION"
  fi
  CURRENT_REVISION="$(git -C "$KEV_CHECKOUT" rev-parse HEAD)"
  if [[ "$CURRENT_REVISION" != "$KEV_REVISION" ]]; then
    echo "Benchmark checkout is $CURRENT_REVISION; expected $KEV_REVISION." >&2
    echo "Remove $KEV_CHECKOUT or set CARVE_TEST_SUITE and CARVE_DEV_SUITE." >&2
    exit 1
  fi
  TEST_SUITE="$KEV_CHECKOUT/evals/v9/transfer-v9/test.jsonl"
  DEV_SUITE="$KEV_CHECKOUT/evals/v9/transfer-v9/development.jsonl"
fi

ACTUAL_SUITE_SHA256="$(
  "$PYTHON" -c \
    'import hashlib, pathlib, sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' \
    "$TEST_SUITE"
)"
if [[ "$ACTUAL_SUITE_SHA256" != "$EXPECTED_SUITE_SHA256" ]]; then
  echo "Test suite SHA-256 mismatch: $ACTUAL_SUITE_SHA256" >&2
  echo "Expected: $EXPECTED_SUITE_SHA256" >&2
  exit 1
fi

COMMAND=(
  "$PYTHON" "$ROOT/scripts/benchmark_carve.py"
  --suite "$TEST_SUITE"
  --endpoint "$ENDPOINT"
  --model "$MODEL"
  --prompt-profile baseline
  --few-shot-pool "$DEV_SUITE"
  --few-shot-k 2
  --few-shot-reserve 2
  --few-shot-seed 20260924
  --demonstration-format chat
  --concurrency 1
  --output "$OUTPUT"
)

if [[ "${CARVE_BENCHMARK_DRY_RUN:-0}" == "1" ]]; then
  printf "Benchmark command:"
  printf " %q" "${COMMAND[@]}"
  printf "\n"
  exit 0
fi

"${COMMAND[@]}"

echo "Benchmark summary written to $OUTPUT"
