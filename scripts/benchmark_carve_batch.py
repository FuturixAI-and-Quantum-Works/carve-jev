from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from benchmark_carve_load import build_payloads


def percentile(values: list[float], fraction: float) -> float:
    return sorted(values)[round((len(values) - 1) * fraction)]


async def measure(
    endpoint: str,
    payloads: list[dict[str, Any]],
    *,
    count: int,
    batch_size: int,
    seed: int,
    timeout: float,
) -> dict[str, Any]:
    selected = [payloads[index % len(payloads)] for index in range(count)]
    random.Random(seed).shuffle(selected)
    batches = [
        selected[start : start + batch_size] for start in range(0, len(selected), batch_size)
    ]
    latencies: list[float] = []
    successful = 0
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=timeout) as client:
        started = time.perf_counter()
        for batch in batches:
            call_started = time.perf_counter()
            try:
                response = await client.post(
                    f"{endpoint.rstrip('/')}/v1/systemone/batch",
                    json={"requests": batch},
                )
                response.raise_for_status()
                result = response.json()
                if len(result.get("responses", [])) != len(batch):
                    raise ValueError("batch response count does not match request count")
                latencies.append((time.perf_counter() - call_started) * 1000)
                successful += len(batch)
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
                errors.append(repr(error))
        elapsed = time.perf_counter() - started
    return {
        "batch_size": batch_size,
        "batch_calls": len(batches),
        "requested_items": count,
        "successful_items": successful,
        "failed_items": count - successful,
        "wall_seconds": elapsed,
        "throughput_items_per_second": successful / elapsed,
        "batch_latency_ms": {
            "mean": statistics.fmean(latencies),
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
            "p99": percentile(latencies, 0.99),
            "maximum": max(latencies),
        },
        "sample_errors": errors[:5],
    }


async def run(args: argparse.Namespace) -> dict[str, Any]:
    payloads = build_payloads(args)
    results = [
        await measure(
            args.endpoint,
            payloads,
            count=args.requests,
            batch_size=batch_size,
            seed=args.seed,
            timeout=args.timeout,
        )
        for batch_size in args.batch_sizes
    ]
    report = {
        "benchmark": "CARVE batch endpoint sweep",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "suite": args.suite.name,
        "model": args.model,
        "few_shot_k": args.few_shot_k,
        "requests_per_condition": args.requests,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark CARVE's experimental batch API")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8011")
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--model", default="CARVE-27B")
    parser.add_argument("--prompt-profile", default="baseline")
    parser.add_argument("--few-shot-pool", type=Path)
    parser.add_argument("--few-shot-k", type=int, default=2)
    parser.add_argument("--few-shot-reserve", type=int, default=2)
    parser.add_argument("--few-shot-seed", type=int, default=20260924)
    parser.add_argument("--demonstration-format", default="chat")
    parser.add_argument(
        "--batch-sizes",
        type=lambda value: [int(item) for item in value.split(",")],
        default=[1, 4, 8, 16, 32],
    )
    parser.add_argument("--requests", type=int, default=512)
    parser.add_argument("--seed", type=int, default=20260924)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.requests < 1 or any(not 1 <= size <= 256 for size in args.batch_sizes):
        parser.error("requests must be positive; batch sizes must be 1..256")
    print(json.dumps(asyncio.run(run(args)), indent=2))


if __name__ == "__main__":
    main()
