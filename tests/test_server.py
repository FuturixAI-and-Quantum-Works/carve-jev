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
    if "response_format" in payload:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"city":"Paris"}'}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 5},
            },
        )
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


def tool_request() -> dict[str, object]:
    return {
        "model": "CARVE-27B",
        "state": "What is the weather in Paris?",
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get current weather for a city.",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_docs",
                    "description": "Search product documentation.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                },
            },
        ],
    }


def test_tool_call_selects_then_generates_only_winner_arguments(monkeypatch) -> None:
    seen: list[dict[str, object]] = []

    def capture(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return upstream_response(request)

    with create_test_client(monkeypatch) as client:
        server = client.app.state.carve_server
        asyncio.run(server.client.aclose())
        server.client = httpx.AsyncClient(transport=httpx.MockTransport(capture))
        response = client.post("/v1/tool-calls", json=tool_request())

    assert response.status_code == 200
    payload = response.json()
    assert payload["finish_reason"] == "tool_calls"
    assert payload["selection"]["selected_tool"] == "get_weather"
    assert payload["selection"]["no_tool_probability"] is not None
    assert payload["tool_calls"][0]["function"] == {
        "name": "get_weather",
        "arguments": '{"city":"Paris"}',
    }
    assert payload["tool_calls"][0]["parsed_arguments"] == {"city": "Paris"}
    assert payload["usage"] == {"input_tokens": 30, "output_tokens": 6}
    assert len(seen) == 2
    assert "logprob_token_ids" in seen[0]
    assert seen[1]["response_format"]["type"] == "json_schema"
    argument_payload = json.loads(seen[1]["messages"][-1]["content"])
    assert argument_payload["selected_function"]["name"] == "get_weather"
    assert "search_docs" not in seen[1]["messages"][-1]["content"]


def test_tool_call_can_choose_no_tool_without_argument_generation(monkeypatch) -> None:
    calls = 0

    def choose_last(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        payload = json.loads(request.content)
        candidates = [
            {"token": f"token_id:{token_id}", "logprob": float(index)}
            for index, token_id in enumerate(payload["logprob_token_ids"])
        ]
        return httpx.Response(
            200,
            json={
                "choices": [{"logprobs": {"content": [{"top_logprobs": candidates}]}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 1},
            },
        )

    with create_test_client(monkeypatch) as client:
        server = client.app.state.carve_server
        asyncio.run(server.client.aclose())
        server.client = httpx.AsyncClient(transport=httpx.MockTransport(choose_last))
        response = client.post(
            "/v1/tool-calls",
            json={**tool_request(), "state": "Thanks, that is all."},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["selection"]["selected_tool"] is None
    assert payload["selection"]["no_tool_probability"] > 0.5
    assert payload["tool_calls"] == []
    assert payload["finish_reason"] == "stop"
    assert calls == 1


def test_forced_tool_skips_selection_and_uses_schema(monkeypatch) -> None:
    calls = 0

    def arguments_only(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        payload = json.loads(request.content)
        assert "logprob_token_ids" not in payload
        return upstream_response(request)

    request = tool_request()
    request["tool_choice"] = {
        "type": "function",
        "function": {"name": "get_weather"},
    }
    with create_test_client(monkeypatch) as client:
        server = client.app.state.carve_server
        asyncio.run(server.client.aclose())
        server.client = httpx.AsyncClient(transport=httpx.MockTransport(arguments_only))
        response = client.post("/v1/tool-calls", json=request)

    assert response.status_code == 200
    assert response.json()["selection"]["mode"] == "forced"
    assert response.json()["selection"]["confidence"] == 1.0
    assert calls == 1


def test_tool_call_confidence_gate_skips_arguments(monkeypatch) -> None:
    calls = 0

    def count(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return upstream_response(request)

    with create_test_client(monkeypatch) as client:
        server = client.app.state.carve_server
        asyncio.run(server.client.aclose())
        server.client = httpx.AsyncClient(transport=httpx.MockTransport(count))
        response = client.post(
            "/v1/tool-calls",
            json={**tool_request(), "minimum_confidence": 0.99},
        )

    assert response.status_code == 200
    assert response.json()["finish_reason"] == "low_confidence"
    assert response.json()["tool_calls"] == []
    assert calls == 1


def test_tool_call_rejects_invalid_generated_arguments(monkeypatch) -> None:
    def invalid_arguments(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        if "response_format" not in payload:
            return upstream_response(request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"city":42}'}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 4},
            },
        )

    with create_test_client(monkeypatch) as client:
        server = client.app.state.carve_server
        asyncio.run(server.client.aclose())
        server.client = httpx.AsyncClient(transport=httpx.MockTransport(invalid_arguments))
        response = client.post("/v1/tool-calls", json=tool_request())

    assert response.status_code == 502
    assert "invalid arguments" in response.json()["detail"]


def test_tool_call_validates_schema_and_parallel_mode(monkeypatch) -> None:
    request = tool_request()
    request["parallel_tool_calls"] = True
    with create_test_client(monkeypatch) as client:
        parallel = client.post("/v1/tool-calls", json=request)
        invalid_schema = client.post(
            "/v1/tool-calls",
            json={
                **tool_request(),
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "broken",
                            "parameters": {"type": "string"},
                        },
                    }
                ],
            },
        )
        external_ref = client.post(
            "/v1/tool-calls",
            json={
                **tool_request(),
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "unsafe_schema",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "value": {
                                        "$ref": "https://example.com/schema.json",
                                    }
                                },
                            },
                        },
                    }
                ],
            },
        )

    assert parallel.status_code == 422
    assert "parallel_tool_calls" in parallel.json()["detail"][0]["msg"]
    assert invalid_schema.status_code == 422
    assert "root type object" in invalid_schema.json()["detail"][0]["msg"]
    assert external_ref.status_code == 422
    assert "external $ref" in external_ref.json()["detail"][0]["msg"]


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
