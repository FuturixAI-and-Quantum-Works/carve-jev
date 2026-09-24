from __future__ import annotations

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
