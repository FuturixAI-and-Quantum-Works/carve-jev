#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${CARVE_VENV:-$ROOT/.venv}"
PYTHON="${CARVE_BOOTSTRAP_PYTHON:-python3}"
VLLM_SPEC="${CARVE_VLLM_SPEC:-vllm}"

if [[ ! -x "$VENV/bin/python" ]]; then
  "$PYTHON" -m venv "$VENV"
fi

"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install -e "$ROOT"

if [[ "${CARVE_SKIP_VLLM_INSTALL:-0}" != "1" ]] \
  && ! "$VENV/bin/python" -c "import vllm" >/dev/null 2>&1; then
  "$VENV/bin/python" -m pip install "$VLLM_SPEC"
fi

if ! "$VENV/bin/python" -c "import vllm" >/dev/null 2>&1; then
  cat >&2 <<'EOF'
CARVE requires a vLLM build with logprob_token_ids support.
Install it in .venv, or rerun with CARVE_VLLM_SPEC set to a compatible
package/source specification. See docs/quickstart.md for the tested revision.
EOF
  exit 1
fi

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
fi

set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a

export PATH="$VENV/bin:$PATH"
export VLLM_BIN="${CARVE_VLLM_BIN:-${VLLM_BIN:-vllm}}"
export PYTHON_BIN="${CARVE_PYTHON_BIN:-${PYTHON_BIN:-python}}"

cd "$ROOT"
exec bash scripts/serve_carve.sh
