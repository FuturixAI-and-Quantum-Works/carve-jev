from __future__ import annotations

import asyncio
import json

import httpx
import httpx2
from fastapi.testclient import TestClient
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

from carve import server as carve_server


class FakeTokenizer:
    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]:
        assert add_special_tokens is False
        return [ord(text)]


def upstream_response(request: httpx.Request) -> httpx.Response:
    payload = json.loads(request.content)
    candidates = [
        {"token": f"token_id:{token_id}", "logprob": -0.25 - index}
        for index, token_id in enumerate(payload["logprob_token_ids"])
    ]
    return httpx.Response(
        200,
        json={
            "choices": [{"logprobs": {"content": [{"top_logprobs": candidates}]}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 1},
        },
    )


def create_test_client(monkeypatch) -> TestClient:
    monkeypatch.setattr(
        carve_server.AutoTokenizer,
        "from_pretrained",
        lambda _: FakeTokenizer(),
    )
    app = carve_server.create_app(
        upstream="http://upstream.test",
        model="qwen38-27b",
        system_name="CARVE-27B",
        prompt_profile="baseline",
        tokenizer="unused",
        max_concurrency=4,
        max_batch_size=4,
    )
    server = app.state.carve_server
    asyncio.run(server.client.aclose())
    server.client = httpx.AsyncClient(transport=httpx.MockTransport(upstream_response))
    return TestClient(app)


def sdk_transport(client: TestClient) -> httpx2.MockTransport:
    def handle(request: httpx2.Request) -> httpx2.Response:
        response = client.request(
            request.method,
            request.url.path,
            content=request.content,
            headers=dict(request.headers),
        )
        return httpx2.Response(
            response.status_code,
            content=response.content,
            headers=dict(response.headers),
        )

    return httpx2.MockTransport(handle)


def test_health_and_models(monkeypatch) -> None:
    with create_test_client(monkeypatch) as client:
        health = client.get("/health")
        models = client.get("/v1/models")

    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "model": "CARVE-27B",
        "backbone_model": "qwen38-27b",
        "prompt_profile": "baseline",
    }
    assert models.json()["models"][0]["release_date"] == "2026-09-24"


def test_typesafe_sdk_parses_all_answer_types(monkeypatch) -> None:
    with (
        create_test_client(monkeypatch) as api,
        TypeSafeClient(
            api_key="local-test",
            base_url="http://carve.test",
            model="CARVE-27B",
            transport=sdk_transport(api),
        ) as sdk,
    ):
        response = sdk.system_one(
            state={"message": "My card was charged twice."},
            questions={
                "urgent": Noul(
                    instructions="Is this urgent?",
                    criteria={"true": "Time-sensitive", "false": "Can wait"},
                ),
                "department": Choice(
                    instructions={"task": "Choose a team."},
                    criteria={"billing": {"area": "payments"}, "technical": None},
                ),
                "severity": Score(
                    instructions=["Rate the incident."],
                    criteria=["Low", {"level": "Medium"}, ["High", "Immediate"]],
                ),
            },
        )

    assert response.model == "CARVE-27B"
    assert response.usage.input_tokens == 30
    assert response.usage.output_tokens == 3
    assert response.nouls["urgent"].type == "noul"
    assert response.choices["department"].choice == "billing"
    assert response.scores["severity"].legend == {
        0: "Low",
        1: {"level": "Medium"},
        2: ["High", "Immediate"],
    }


def test_raw_probability_metadata_and_noul_shape(monkeypatch) -> None:
    with create_test_client(monkeypatch) as client:
        response = client.post(
            "/v1/systemone",
            json={
                "state": "The service is unavailable.",
                "model": "CARVE-27B",
                "questions": {"outage": {"type": "noul", "instructions": "Is this an outage?"}},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    answer = payload["answers"]["outage"]
    assert "confidence" not in answer
    assert "probabilities" not in answer
    assert answer["probability_level"] == "raw"
    assert payload["probability_level"] == "raw"
    assert payload["probability_semantics"] == carve_server.PROBABILITY_SEMANTICS
    assert payload["usage"] == {"input_tokens": 10, "output_tokens": 1}


def test_batch_preserves_order_and_aggregates_usage(monkeypatch) -> None:
    requests = [
        {
            "state": f"Message {index}",
            "model": "CARVE-27B",
            "questions": {
                "route": {
                    "type": "choice",
                    "instructions": "Choose a route.",
                    "criteria": {f"first-{index}": None, f"second-{index}": None},
                }
            },
        }
        for index in range(3)
    ]
    with create_test_client(monkeypatch) as client:
        response = client.post("/v1/systemone/batch", json={"requests": requests})

    assert response.status_code == 200
    payload = response.json()
    assert payload["object"] == "systemone.batch"
    assert payload["probability_level"] == "raw"
    assert payload["probability_semantics"] == carve_server.PROBABILITY_SEMANTICS
    assert [item["answers"]["route"]["choice"] for item in payload["responses"]] == [
        "first-0",
        "first-1",
        "first-2",
    ]
    assert payload["usage"] == {"input_tokens": 30, "output_tokens": 3}


def test_multimodal_content_is_forwarded(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def capture(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen["content"] = payload["messages"][-1]["content"]
        return upstream_response(request)

    with create_test_client(monkeypatch) as client:
        server = client.app.state.carve_server
        asyncio.run(server.client.aclose())
        server.client = httpx.AsyncClient(transport=httpx.MockTransport(capture))
        response = client.post(
            "/v1/systemone",
            json={
                "state": "Inspect this image.",
                "model": "CARVE-27B",
                "media": [
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,AAAA"},
                    }
                ],
                "questions": {
                    "color": {
                        "type": "choice",
                        "criteria": {"red": None, "blue": None},
                    }
                },
            },
        )

    assert response.status_code == 200
    assert isinstance(seen["content"], list)
    assert seen["content"][1]["type"] == "image_url"


def test_unreachable_upstream_returns_bad_gateway(monkeypatch) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    decision = {
        "state": "The service is unavailable.",
        "model": "CARVE-27B",
        "questions": {"outage": {"type": "noul", "instructions": "Is this an outage?"}},
    }
    with create_test_client(monkeypatch) as client:
        server = client.app.state.carve_server
        asyncio.run(server.client.aclose())
        server.client = httpx.AsyncClient(transport=httpx.MockTransport(refuse))
        single = client.post("/v1/systemone", json=decision)
        batch = client.post("/v1/systemone/batch", json={"requests": [decision]})

    assert single.status_code == 502
    assert single.json()["detail"] == "connection refused"
    assert batch.status_code == 502


def test_validation_errors(monkeypatch) -> None:
    with create_test_client(monkeypatch) as client:
        missing_state = client.post(
            "/v1/systemone",
            json={
                "model": "CARVE-27B",
                "questions": {"route": {"criteria": {"a": None, "b": None}}},
            },
        )
        empty_batch = client.post("/v1/systemone/batch", json={"requests": []})

    assert missing_state.status_code == 422
    assert missing_state.json()["detail"][0]["loc"] == ["body"]
    assert empty_batch.status_code == 422
    assert empty_batch.json()["detail"][0]["loc"] == ["body", "requests"]
