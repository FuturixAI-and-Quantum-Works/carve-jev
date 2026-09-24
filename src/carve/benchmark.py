"""CARVE-only helpers for Decision 1.0 transfer evaluation."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_records(
    path: Path,
    *,
    include_diagnostics: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        metadata = record["_meta"]
        if not include_diagnostics and (
            metadata["variant"] != "clean" or metadata["source"] == "unknowable"
        ):
            continue
        records.append(record)
        if limit is not None and len(records) >= limit:
            break
    return records


def normalized_question(question: dict[str, Any]) -> dict[str, Any]:
    normalized = {key: value for key, value in question.items() if key not in {"label", "src"}}
    criteria = normalized.get("criteria")
    if isinstance(criteria, dict):
        normalized["criteria"] = {
            str(key): str(key) if description is None else description
            for key, description in criteria.items()
        }
    return normalized


def expected_label(question: dict[str, Any]) -> str:
    if question["type"] == "noul":
        return "true" if bool(question["label"]) else "false"
    return str(question["label"])


def task_family(task: str) -> str:
    return "composition_logic" if task.startswith("composition_") else task


def few_shot_bank(
    records: list[dict[str, Any]],
    *,
    reserve: int,
    seed: int,
) -> tuple[dict[str, list[dict[str, Any]]], set[str]]:
    candidates: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for record in records:
        record_id = str(record["_meta"]["id"])
        for question_id, question in record["questions"].items():
            family = task_family(str(question["src"]))
            rank = hashlib.sha256(
                f"carve-fewshot-v1:{seed}:{family}:{record_id}:{question_id}".encode()
            ).hexdigest()
            candidates[family].append(
                (
                    rank,
                    {
                        "record_id": record_id,
                        "state": record["state"],
                        "question": normalized_question(question),
                        "answer": expected_label(question),
                    },
                )
            )
    bank: dict[str, list[dict[str, Any]]] = {}
    reserved_ids: set[str] = set()
    for family, ranked in sorted(candidates.items()):
        selected = [item for _, item in sorted(ranked)[:reserve]]
        if len(selected) < reserve:
            raise ValueError(f"task {family!r} has only {len(selected)} demonstration records")
        bank[family] = selected
        reserved_ids.update(item["record_id"] for item in selected)
    return bank, reserved_ids


def demonstrations_for_record(
    record: dict[str, Any],
    *,
    bank: dict[str, list[dict[str, Any]]],
    count: int,
) -> dict[str, list[dict[str, Any]]]:
    demonstrations: dict[str, list[dict[str, Any]]] = {}
    for question_id, question in record["questions"].items():
        available = bank.get(task_family(str(question["src"])), [])
        if len(available) < count:
            raise ValueError(f"task for {question_id!r} has fewer than {count} demonstrations")
        if count:
            demonstrations[question_id] = [
                {
                    "state": item["state"],
                    "question": item["question"],
                    "answer": item["answer"],
                }
                for item in available[:count]
            ]
    return demonstrations


def request_payload(
    record: dict[str, Any],
    *,
    model: str,
    prompt_profile: str,
    demonstrations: dict[str, list[dict[str, Any]]] | None = None,
    demonstration_format: str = "chat",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "state": record["state"],
        "questions": {
            question_id: normalized_question(question)
            for question_id, question in record["questions"].items()
        },
        "prompt_profile": prompt_profile,
    }
    if demonstrations:
        payload["demonstrations"] = demonstrations
        payload["demonstration_format"] = demonstration_format
    return payload


def prediction_from_answer(question: dict[str, Any], answer: dict[str, Any]) -> str:
    if question["type"] == "noul":
        return "true" if float(answer["noul"]) >= 0.5 else "false"
    if question["type"] == "choice":
        return str(answer["choice"])
    probabilities = answer["probabilities"]
    return str(max(probabilities, key=probabilities.get))
