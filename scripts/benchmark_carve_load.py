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

from carve.benchmark import demonstrations_for_record, few_shot_bank, load_records, request_payload


def percentile(values: list[float], fraction: float) -> float:
    return sorted(values)[round((len(values) - 1) * fraction)]


def build_payloads(args: argparse.Namespace) -> list[dict[str, Any]]:
    records = load_records(args.suite)
    bank: dict[str, list[dict[str, Any]]] = {}
    if args.few_shot_pool:
        bank, _ = few_shot_bank(
            load_records(args.few_shot_pool),
            reserve=args.few_shot_reserve,
            seed=args.few_shot_seed,
        )
    return [
        request_payload(
            record,
            model=args.model,
            prompt_profile=args.prompt_profile,
            demonstrations=demonstrations_for_record(record, bank=bank, count=args.few_shot_k),
            demonstration_format=args.demonstration_format,
        )
        for record in records
    ]


async def measure(
    endpoint: str,
    payloads: list[dict[str, Any]],
    *,
    count: int,
    concurrency: int,
    seed: int,
    timeout: float,
) -> dict[str, Any]:
    requests = [payloads[index % len(payloads)] for index in range(count)]
    random.Random(seed).shuffle(requests)
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    for payload in requests:
        queue.put_nowait(payload)
    latencies: list[float] = []
    errors: list[str] = []
    usage = {"input_tokens": 0, "output_tokens": 0}
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:

        async def worker() -> None:
            while True:
                try:
                    payload = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                started = time.perf_counter()
                try:
                    response = await client.post(
                        f"{endpoint.rstrip('/')}/v1/systemone", json=payload
                    )
                    response.raise_for_status()
                    result = response.json()
                    if set(result.get("answers", {})) != set(payload["questions"]):
                        raise ValueError("response answer IDs do not match request")
                    latencies.append((time.perf_counter() - started) * 1000)
                    for key in usage:
                        usage[key] += int(result.get("usage", {}).get(key, 0))
                except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
                    errors.append(repr(error))
                finally:
                    queue.task_done()

        started = time.perf_counter()
        await asyncio.gather(*(worker() for _ in range(concurrency)))
        elapsed = time.perf_counter() - started
    return {
        "concurrency": concurrency,
        "requested": count,
        "successful": len(latencies),
        "failed": len(errors),
        "error_rate": len(errors) / count,
        "wall_seconds": elapsed,
        "throughput_requests_per_second": len(latencies) / elapsed,
        "latency_ms": {
            "mean": statistics.fmean(latencies),
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
            "p99": percentile(latencies, 0.99),
            "maximum": max(latencies),
        },
        "usage": usage,
        "sample_errors": errors[:5],
    }


async def run(args: argparse.Namespace) -> dict[str, Any]:
    payloads = build_payloads(args)
    results = [
        await measure(
            args.endpoint,
            payloads,
            count=args.requests,
            concurrency=concurrency,
            seed=args.seed,
            timeout=args.timeout,
        )
        for concurrency in args.concurrency
    ]
    report = {
        "benchmark": "CARVE closed-loop production load sweep",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "suite": args.suite.name,
        "model": args.model,
        "few_shot_k": args.few_shot_k,
        "requests_per_concurrency": args.requests,
        "methodology": (
            "Closed-loop clients with one outstanding request per worker; "
            "HTTP-boundary latency includes queueing."
        ),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure CARVE under closed-loop load")
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
        "--concurrency",
        type=lambda value: [int(item) for item in value.split(",")],
        default=[1, 2, 4, 8, 16, 32],
    )
    parser.add_argument("--requests", type=int, default=512)
    parser.add_argument("--seed", type=int, default=20260924)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.requests < 1 or any(value < 1 for value in args.concurrency):
        parser.error("requests and concurrency values must be positive")
    print(json.dumps(asyncio.run(run(args)), indent=2))


if __name__ == "__main__":
    main()
