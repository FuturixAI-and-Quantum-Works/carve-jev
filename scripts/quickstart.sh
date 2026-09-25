#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
fi

set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a

VENV="${CARVE_VENV:-$ROOT/.venv}"
PYTHON="${CARVE_BOOTSTRAP_PYTHON:-python3}"
DEFAULT_VLLM_SPEC="vllm==0.30.0"
VLLM_SPEC="${CARVE_VLLM_SPEC:-$DEFAULT_VLLM_SPEC}"
MODEL="${CARVE_MODEL:-Qwen/Qwen3.8-27B-FP8}"

if [[ "${CARVE_SKIP_DISK_CHECK:-0}" != "1" ]]; then
  require_space() {
    local path="$1"
    local required_gib="$2"
    local purpose="$3"
    local available_kib
    local available_gib
    local required_kib

    available_kib="$(df -Pk "$path" | awk 'NR == 2 {print $4}')"
    available_gib="$((available_kib / 1024 / 1024))"
    required_kib="$((required_gib * 1024 * 1024))"
    if (( available_kib < required_kib )); then
      cat >&2 <<EOF
Insufficient free disk for ${purpose}: ${available_gib} GiB available,
${required_gib} GiB required on the filesystem containing ${path}.
Free disk, use an existing local checkpoint, move CARVE_VENV/HF_HOME to larger
filesystems, or deliberately bypass this guard with CARVE_SKIP_DISK_CHECK=1.
EOF
      exit 1
    fi
  }

  VENV_PARENT="$(dirname "$VENV")"
  if [[ -d "$MODEL" ]]; then
    if [[ -x "$VENV/bin/python" ]]; then
      ENV_GIB="${CARVE_MIN_ENV_FREE_GIB:-5}"
    else
      ENV_GIB="${CARVE_MIN_ENV_FREE_GIB:-12}"
    fi
    require_space "$VENV_PARENT" "$ENV_GIB" "the Python environment"
  else
    CACHE_ROOT="${HF_HOME:-${HF_HUB_CACHE:-$HOME/.cache/huggingface}}"
    mkdir -p "$CACHE_ROOT"
    VENV_DEVICE="$(df -P "$VENV_PARENT" | awk 'NR == 2 {print $1}')"
    CACHE_DEVICE="$(df -P "$CACHE_ROOT" | awk 'NR == 2 {print $1}')"
    if [[ "$VENV_DEVICE" == "$CACHE_DEVICE" ]]; then
      require_space \
        "$VENV_PARENT" "${CARVE_MIN_FREE_GIB:-45}" \
        "the environment and checkpoint"
    else
      if [[ -x "$VENV/bin/python" ]]; then
        ENV_GIB="${CARVE_MIN_ENV_FREE_GIB:-5}"
      else
        ENV_GIB="${CARVE_MIN_ENV_FREE_GIB:-12}"
      fi
      require_space "$VENV_PARENT" "$ENV_GIB" "the Python environment"
      require_space \
        "$CACHE_ROOT" "${CARVE_MIN_MODEL_FREE_GIB:-35}" \
        "the checkpoint cache"
    fi
  fi
fi

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

export PATH="$VENV/bin:$PATH"
export VLLM_BIN="${CARVE_VLLM_BIN:-${VLLM_BIN:-vllm}}"
export PYTHON_BIN="${CARVE_PYTHON_BIN:-${PYTHON_BIN:-python}}"

cd "$ROOT"
exec bash scripts/serve_carve.sh
