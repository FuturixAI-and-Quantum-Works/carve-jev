from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import httpx

from carve.benchmark import (
    demonstrations_for_record,
    expected_label,
    few_shot_bank,
    load_records,
    prediction_from_answer,
    request_payload,
)


def percentile(values: list[float], fraction: float) -> float:
    return sorted(values)[round((len(values) - 1) * fraction)]


async def run(args: argparse.Namespace) -> dict[str, Any]:
    records = load_records(args.suite, limit=args.limit)
    bank: dict[str, list[dict[str, Any]]] = {}
    pool_hash = None
    if args.few_shot_pool:
        pool = load_records(args.few_shot_pool)
        bank, _ = few_shot_bank(pool, reserve=args.few_shot_reserve, seed=args.few_shot_seed)
        pool_hash = hashlib.sha256(args.few_shot_pool.read_bytes()).hexdigest()
    elif args.few_shot_k:
        raise ValueError("--few-shot-k requires --few-shot-pool")

    semaphore = asyncio.Semaphore(args.concurrency)
    outcomes: list[dict[str, Any]] = []
    limits = httpx.Limits(
        max_connections=args.concurrency,
        max_keepalive_connections=args.concurrency,
    )
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=args.timeout, limits=limits) as client:

        async def score(record: dict[str, Any]) -> None:
            demos = demonstrations_for_record(record, bank=bank, count=args.few_shot_k)
            payload = request_payload(
                record,
                model=args.model,
                prompt_profile=args.prompt_profile,
                demonstrations=demos,
                demonstration_format=args.demonstration_format,
            )
            async with semaphore:
                request_started = time.perf_counter()
                response = await client.post(
                    f"{args.endpoint.rstrip('/')}/v1/systemone",
                    json=payload,
                )
                latency_ms = (time.perf_counter() - request_started) * 1000
            response.raise_for_status()
            result = response.json()
            for question_id, question in record["questions"].items():
                predicted = prediction_from_answer(question, result["answers"][question_id])
                expected = expected_label(question)
                outcomes.append(
                    {
                        "task": question["src"],
                        "correct": predicted == expected,
                        "latency_ms": latency_ms,
                    }
                )

        await asyncio.gather(*(score(record) for record in records))
    elapsed = time.perf_counter() - started

    by_task: dict[str, list[bool]] = defaultdict(list)
    for outcome in outcomes:
        by_task[str(outcome["task"])].append(bool(outcome["correct"]))
    latencies = [float(outcome["latency_ms"]) for outcome in outcomes]
    correct = sum(bool(outcome["correct"]) for outcome in outcomes)
    summary = {
        "benchmark": "Decision 1.0 transfer-v9 clean decisions",
        "suite": args.suite.name,
        "suite_sha256": hashlib.sha256(args.suite.read_bytes()).hexdigest(),
        "model": args.model,
        "prompt_profile": args.prompt_profile,
        "few_shot_k": args.few_shot_k,
        "few_shot_pool_sha256": pool_hash,
        "few_shot_seed": args.few_shot_seed,
        "demonstration_format": args.demonstration_format,
        "concurrency": args.concurrency,
        "scored_decisions": len(outcomes),
        "correct": correct,
        "accuracy": correct / len(outcomes),
        "failed_records": 0,
        "latency_ms_per_decision": {
            "mean": statistics.fmean(latencies),
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
        },
        "wall_seconds": elapsed,
        "throughput_decisions_per_second": len(outcomes) / elapsed,
        "by_task": {
            task: {
                "n": len(values),
                "correct": sum(values),
                "accuracy": sum(values) / len(values),
            }
            for task, values in sorted(by_task.items())
        },
        "probability_note": (
            "CARVE probabilities are raw restricted candidate-token preferences, "
            "not calibrated correctness probabilities."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark CARVE on Decision 1.0 JSONL")
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8011")
    parser.add_argument("--model", default="CARVE-27B")
    parser.add_argument("--prompt-profile", default="baseline")
    parser.add_argument("--few-shot-pool", type=Path)
    parser.add_argument("--few-shot-k", type=int, choices=range(0, 9), default=0)
    parser.add_argument("--few-shot-reserve", type=int, choices=range(0, 9), default=0)
    parser.add_argument("--few-shot-seed", type=int, default=20260924)
    parser.add_argument(
        "--demonstration-format",
        choices=["chat", "compact", "minimal"],
        default="chat",
    )
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.concurrency < 1:
        parser.error("--concurrency must be positive")
    print(json.dumps(asyncio.run(run(args)), indent=2))


if __name__ == "__main__":
    main()
