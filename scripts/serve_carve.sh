#!/usr/bin/env bash
set -euo pipefail

MODEL="${CARVE_MODEL:-Qwen/Qwen3.8-27B-FP8}"
SERVED_MODEL="${CARVE_SERVED_MODEL:-qwen38-27b}"
SYSTEM_NAME="${CARVE_SYSTEM_NAME:-CARVE-27B}"
TOKENIZER="${CARVE_TOKENIZER:-$MODEL}"
GPU="${CARVE_GPU:-0}"
VLLM_HOST="${CARVE_VLLM_HOST:-127.0.0.1}"
VLLM_PORT="${CARVE_VLLM_PORT:-8000}"
API_HOST="${CARVE_API_HOST:-127.0.0.1}"
API_PORT="${CARVE_API_PORT:-8011}"
MAX_MODEL_LEN="${CARVE_MAX_MODEL_LEN:-8192}"
MAX_NUM_SEQS="${CARVE_MAX_NUM_SEQS:-32}"
MAX_BATCHED_TOKENS="${CARVE_MAX_BATCHED_TOKENS:-8192}"
GPU_MEMORY_UTILIZATION="${CARVE_GPU_MEMORY_UTILIZATION:-0.85}"
MAX_CONCURRENCY="${CARVE_MAX_CONCURRENCY:-32}"
MAX_BATCH_SIZE="${CARVE_MAX_BATCH_SIZE:-256}"
VLLM_BIN="${VLLM_BIN:-vllm}"
PYTHON_BIN="${PYTHON_BIN:-python}"

cleanup() {
  if [[ -n "${VLLM_PID:-}" ]]; then
    kill "$VLLM_PID" 2>/dev/null || true
    wait "$VLLM_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

CUDA_VISIBLE_DEVICES="$GPU" "$VLLM_BIN" serve "$MODEL" \
  --served-model-name "$SERVED_MODEL" \
  --host "$VLLM_HOST" \
  --port "$VLLM_PORT" \
  --max-model-len "$MAX_MODEL_LEN" \
  --max-num-seqs "$MAX_NUM_SEQS" \
  --max-num-batched-tokens "$MAX_BATCHED_TOKENS" \
  --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
  --reasoning-parser qwen3 \
  --default-chat-template-kwargs \
    '{"enable_thinking": false, "preserve_thinking": false}' \
  --enable-prefix-caching \
  --gdn-prefill-backend triton &
VLLM_PID=$!

for _ in $(seq 1 300); do
  if curl --fail --silent "http://${VLLM_HOST}:${VLLM_PORT}/health" >/dev/null; then
    break
  fi
  if ! kill -0 "$VLLM_PID" 2>/dev/null; then
    wait "$VLLM_PID"
  fi
  sleep 1
done

if ! curl --fail --silent "http://${VLLM_HOST}:${VLLM_PORT}/health" >/dev/null; then
  echo "vLLM did not become healthy within 300 seconds" >&2
  exit 1
fi

exec "$PYTHON_BIN" -m carve.server \
  --upstream "http://${VLLM_HOST}:${VLLM_PORT}" \
  --model "$SERVED_MODEL" \
  --system-name "$SYSTEM_NAME" \
  --prompt-profile baseline \
  --tokenizer "$TOKENIZER" \
  --host "$API_HOST" \
  --port "$API_PORT" \
  --max-concurrency "$MAX_CONCURRENCY" \
  --max-batch-size "$MAX_BATCH_SIZE"
