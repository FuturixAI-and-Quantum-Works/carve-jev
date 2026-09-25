from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
from pathlib import Path

import httpx
import pytest

from carve.benchmark import (
    demonstrations_for_record,
    expected_label,
    few_shot_bank,
    request_payload,
    task_family,
)


def record(record_id: str, task: str, label: str) -> dict:
    return {
        "_meta": {"id": record_id, "variant": "clean", "source": "fixture"},
        "state": f"state-{record_id}",
        "questions": {
            "route": {
                "type": "choice",
                "instructions": "Choose.",
                "criteria": {"a": None, "b": None},
                "label": label,
                "src": task,
            }
        },
    }


def test_few_shot_selection_is_deterministic() -> None:
    records = [record(str(index), "routing", "a") for index in range(5)]
    first, first_ids = few_shot_bank(records, reserve=2, seed=20260924)
    second, second_ids = few_shot_bank(records, reserve=2, seed=20260924)

    assert first == second
    assert first_ids == second_ids
    assert len(first["routing"]) == 2


def test_payload_removes_labels_and_adds_demonstrations() -> None:
    target = record("target", "composition_final_negation", "b")
    pool = [record(str(index), "composition_held_negation", "a") for index in range(3)]
    bank, _ = few_shot_bank(pool, reserve=2, seed=20260924)
    demonstrations = demonstrations_for_record(target, bank=bank, count=2)
    payload = request_payload(
        target,
        model="CARVE-27B",
        prompt_profile="baseline",
        demonstrations=demonstrations,
    )

    assert task_family("composition_final_negation") == "composition_logic"
    assert expected_label(target["questions"]["route"]) == "b"
    assert "label" not in payload["questions"]["route"]
    assert "src" not in payload["questions"]["route"]
    assert len(payload["demonstrations"]["route"]) == 2


@pytest.mark.asyncio
async def test_serial_latency_excludes_semaphore_queue_wait(monkeypatch, tmp_path) -> None:
    script_path = Path(__file__).parents[1] / "scripts" / "benchmark_carve.py"
    spec = importlib.util.spec_from_file_location("benchmark_carve_script", script_path)
    assert spec is not None and spec.loader is not None
    benchmark_carve = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark_carve)

    suite = tmp_path / "test.jsonl"
    suite.write_text(
        "\n".join(json.dumps(record(str(index), "routing", "a")) for index in range(3)),
        encoding="utf-8",
    )

    async def respond(_: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.05)
        return httpx.Response(
            200,
            json={
                "answers": {
                    "route": {
                        "type": "choice",
                        "choice": "a",
                        "probabilities": {"a": 0.9, "b": 0.1},
                    }
                }
            },
        )

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        benchmark_carve.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(respond),
            **kwargs,
        ),
    )
    args = argparse.Namespace(
        suite=suite,
        endpoint="http://carve.test",
        model="CARVE-27B",
        prompt_profile="baseline",
        few_shot_pool=None,
        few_shot_k=0,
        few_shot_reserve=0,
        few_shot_seed=20260924,
        demonstration_format="chat",
        concurrency=1,
        timeout=1.0,
        limit=None,
        output=tmp_path / "summary.json",
    )

    summary = await benchmark_carve.run(args)

    assert summary["correct"] == 3
    assert 40 <= summary["latency_ms_per_decision"]["p50"] < 90
