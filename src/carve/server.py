from __future__ import annotations

import argparse
import asyncio
import json
import math
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from transformers import AutoTokenizer

PROMPT_PROFILES = {
    "baseline": (
        "Apply the supplied criterion to the supplied evidence. Choose exactly one "
        "listed option. Respond with only its uppercase letter, with no explanation "
        "or reasoning."
    ),
    "semantic": (
        "Choose exactly one option from its meaning, not its letter. Treat letters "
        "only as arbitrary output identifiers. Match the criterion to the evidence, "
        "then respond with only the winning uppercase letter."
    ),
    "evidence": (
        "Choose the one option best supported by the supplied evidence. Do not add "
        "unstated facts. Check negation, exceptions, quantities, and time. If an "
        "insufficient-information or none option exists, use it when warranted. "
        "Respond with only its uppercase letter."
    ),
    "checklist": (
        "Choose exactly one listed option. Silently compare every option against the "
        "criterion and evidence, check negation and constraints, then map the winner "
        "to its letter. Letters are arbitrary identifiers. Output only that uppercase "
        "letter."
    ),
    "strict": (
        "Use only the supplied evidence and apply the criterion literally. Prefer the "
        "exact semantic match; do not infer unstated facts or default to yes. Treat "
        "letters as arbitrary identifiers. Output exactly one uppercase letter."
    ),
}
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
CARVE_RELEASE_DATE = "2026-09-24"
PROBABILITY_LEVEL = "raw"
PROBABILITY_SEMANTICS = (
    "Restricted candidate-token softmax; not a calibrated probability of correctness."
)


class CandidateServer:
    """Translate typed decisions into restricted next-token scoring requests."""

    def __init__(
        self,
        *,
        upstream: str,
        model: str,
        system_name: str,
        prompt_profile: str,
        tokenizer: str,
        max_concurrency: int,
        max_batch_size: int,
    ) -> None:
        if prompt_profile not in PROMPT_PROFILES:
            raise ValueError(f"unknown prompt profile: {prompt_profile!r}")
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        if max_batch_size < 1:
            raise ValueError("max_batch_size must be positive")
        self.upstream = upstream.rstrip("/")
        self.model = model
        self.system_name = system_name
        self.prompt_profile = prompt_profile
        self.max_batch_size = max_batch_size
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer)
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(600.0))
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.letter_ids = [self._single_token_id(letter) for letter in LETTERS]
        if len(set(self.letter_ids)) != len(self.letter_ids):
            raise ValueError("candidate letter token ids collide")

    def _single_token_id(self, text: str) -> int:
        token_ids = self.tokenizer.encode(text, add_special_tokens=False)
        if len(token_ids) != 1:
            raise ValueError(f"{text!r} is not one token: {token_ids}")
        return int(token_ids[0])

    async def close(self) -> None:
        await self.client.aclose()

    @staticmethod
    def _user_content(payload: dict[str, Any], media: Any) -> str | list[dict[str, Any]]:
        text = json.dumps(payload, ensure_ascii=False)
        if media is None:
            return text
        if not isinstance(media, list):
            raise ValueError("media must be a list of OpenAI image/video content parts")
        content: list[dict[str, Any]] = [{"type": "text", "text": text}]
        for part in media:
            if not isinstance(part, dict) or part.get("type") not in {
                "image_url",
                "video_url",
            }:
                raise ValueError("media supports only image_url and video_url parts")
            content.append(part)
        return content

    @staticmethod
    def _options(question_id: str, question: dict[str, Any]) -> dict[str, Any]:
        kind = question.get("type", "choice")
        criteria = question.get("criteria")
        if kind == "noul":
            return {
                "true": (
                    criteria.get("true", "Yes; the statement is true.")
                    if isinstance(criteria, dict)
                    else "Yes; the statement is true."
                ),
                "false": (
                    criteria.get("false", "No; the statement is false.")
                    if isinstance(criteria, dict)
                    else "No; the statement is false."
                ),
            }
        if isinstance(criteria, list):
            return {str(index): value for index, value in enumerate(criteria)}
        if isinstance(criteria, dict):
            return {
                str(key): str(key) if value is None else value for key, value in criteria.items()
            }
        raise ValueError(f"question {question_id!r} has invalid criteria")

    @classmethod
    def _decision_payload(
        cls, state: Any, question_id: str, question: dict[str, Any]
    ) -> tuple[dict[str, Any], list[str], dict[str, Any]]:
        options = cls._options(question_id, question)
        if not 2 <= len(options) <= len(LETTERS):
            raise ValueError(f"question {question_id!r} has invalid option count")
        names = list(options)
        return (
            {
                "evidence": state,
                "criterion": question.get("instructions", ""),
                "options": [
                    {"letter": LETTERS[index], "description": options[name]}
                    for index, name in enumerate(names)
                ],
            },
            names,
            options,
        )

    @classmethod
    def _demonstration_messages(cls, question_id: str, demonstrations: Any) -> list[dict[str, str]]:
        if demonstrations is None:
            return []
        if not isinstance(demonstrations, list):
            raise ValueError("question demonstrations must be a list")
        messages: list[dict[str, str]] = []
        for index, demonstration in enumerate(demonstrations):
            if not isinstance(demonstration, dict):
                raise ValueError("each demonstration must be an object")
            demo_question = demonstration.get("question")
            if not isinstance(demo_question, dict):
                raise ValueError("each demonstration requires a question object")
            payload, names, _ = cls._decision_payload(
                demonstration.get("state"),
                f"{question_id}.demonstration[{index}]",
                demo_question,
            )
            answer = str(demonstration.get("answer"))
            if answer not in names:
                raise ValueError(f"demonstration answer {answer!r} is not a listed option")
            messages.extend(
                [
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                    {"role": "assistant", "content": LETTERS[names.index(answer)]},
                ]
            )
        return messages

    @classmethod
    def _compact_demonstrations(
        cls,
        question_id: str,
        demonstrations: Any,
        *,
        include_criterion: bool,
    ) -> list[dict[str, Any]]:
        if demonstrations is None:
            return []
        if not isinstance(demonstrations, list):
            raise ValueError("question demonstrations must be a list")
        examples: list[dict[str, Any]] = []
        for index, demonstration in enumerate(demonstrations):
            if not isinstance(demonstration, dict):
                raise ValueError("each demonstration must be an object")
            demo_question = demonstration.get("question")
            if not isinstance(demo_question, dict):
                raise ValueError("each demonstration requires a question object")
            options = cls._options(f"{question_id}.demonstration[{index}]", demo_question)
            answer = str(demonstration.get("answer"))
            if answer not in options:
                raise ValueError(f"demonstration answer {answer!r} is not a listed option")
            example = {
                "evidence": demonstration.get("state"),
                "correct_option": options[answer],
            }
            if include_criterion:
                example["criterion"] = demo_question.get("instructions", "")
            examples.append(example)
        return examples

    async def decide_question(
        self,
        state: Any,
        media: Any,
        prompt_profile: str,
        demonstration_format: str,
        demonstrations: Any,
        question_id: str,
        question: dict[str, Any],
    ) -> tuple[str, dict[str, Any], dict[str, int]]:
        if not isinstance(question, dict):
            raise ValueError(f"question {question_id!r} must be an object")
        kind = question.get("type", "choice")
        if kind not in {"noul", "choice", "score"}:
            raise ValueError(f"question {question_id!r} has unsupported type {kind!r}")
        payload, names, options = self._decision_payload(state, question_id, question)
        demo_messages: list[dict[str, str]] = []
        if demonstration_format == "chat":
            demo_messages = self._demonstration_messages(question_id, demonstrations)
        elif demonstration_format in {"compact", "minimal"}:
            examples = self._compact_demonstrations(
                question_id,
                demonstrations,
                include_criterion=demonstration_format == "compact",
            )
            if examples:
                payload = {"examples": examples, **payload}
        else:
            raise ValueError(f"unknown demonstration format: {demonstration_format!r}")

        token_ids = self.letter_ids[: len(names)]
        request = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": PROMPT_PROFILES[prompt_profile]},
                *demo_messages,
                {"role": "user", "content": self._user_content(payload, media)},
            ],
            "max_tokens": 1,
            "temperature": 0,
            "logprobs": True,
            "top_logprobs": 1,
            "logprob_token_ids": token_ids,
            "return_tokens_as_token_ids": True,
            "chat_template_kwargs": {
                "enable_thinking": False,
                "preserve_thinking": False,
            },
        }
        async with self.semaphore:
            response = await self.client.post(f"{self.upstream}/v1/chat/completions", json=request)
        response.raise_for_status()
        result = response.json()
        candidates = result["choices"][0]["logprobs"]["content"][0]["top_logprobs"]
        by_id = {
            int(candidate["token"].split(":")[1]): float(candidate["logprob"])
            for candidate in candidates
        }
        logits = [by_id[token_id] for token_id in token_ids]
        maximum = max(logits)
        weights = [math.exp(logit - maximum) for logit in logits]
        total = sum(weights)
        probabilities = {name: weight / total for name, weight in zip(names, weights, strict=True)}
        winner = max(probabilities, key=probabilities.get)
        extensions = {
            "probability_level": PROBABILITY_LEVEL,
            "few_shot_count": (
                len(demo_messages) // 2
                if demonstration_format == "chat"
                else len(payload.get("examples", []))
            ),
            "demonstration_format": demonstration_format,
        }
        if kind == "noul":
            answer: dict[str, Any] = {
                "type": "noul",
                "noul": probabilities["true"],
                **extensions,
            }
        elif kind == "choice":
            answer = {
                "type": "choice",
                "choice": winner,
                "probabilities": probabilities,
                "confidence": probabilities[winner],
                **extensions,
            }
        else:
            answer = {
                "type": "score",
                "score": sum(index * probabilities[name] for index, name in enumerate(names)),
                "legend": {name: options[name] for name in names},
                "probabilities": probabilities,
                "confidence": probabilities[winner],
                **extensions,
            }
        raw_usage = result.get("usage")
        if not isinstance(raw_usage, dict):
            raw_usage = {}
        usage = {
            "input_tokens": int(
                raw_usage.get("prompt_tokens", raw_usage.get("input_tokens", 0)) or 0
            ),
            "output_tokens": int(
                raw_usage.get("completion_tokens", raw_usage.get("output_tokens", 0)) or 0
            ),
        }
        return question_id, answer, usage

    async def decide(self, body: dict[str, Any]) -> dict[str, Any]:
        if "state" not in body or not isinstance(body["state"], (str, dict, list)):
            raise ValueError("state must be a string, object, or array")
        if not isinstance(body.get("model"), str) or not body["model"].strip():
            raise ValueError("model must be a non-empty string")
        questions = body.get("questions")
        if not isinstance(questions, dict) or not questions:
            raise ValueError("questions must be a non-empty object")
        prompt_profile = body.get("prompt_profile", self.prompt_profile)
        if prompt_profile not in PROMPT_PROFILES:
            raise ValueError(f"unknown prompt profile: {prompt_profile!r}")
        demonstrations = body.get("demonstrations", {})
        if not isinstance(demonstrations, dict):
            raise ValueError("demonstrations must map question IDs to lists")
        demonstration_format = body.get("demonstration_format", "chat")
        if demonstration_format not in {"chat", "compact", "minimal"}:
            raise ValueError("demonstration_format must be chat, compact, or minimal")
        results = await asyncio.gather(
            *[
                self.decide_question(
                    body["state"],
                    body.get("media"),
                    prompt_profile,
                    demonstration_format,
                    demonstrations.get(question_id),
                    question_id,
                    question,
                )
                for question_id, question in questions.items()
            ]
        )
        return {
            "model": self.system_name,
            "backbone_model": self.model,
            "answers": {question_id: answer for question_id, answer, _ in results},
            "usage": {
                "input_tokens": sum(usage["input_tokens"] for _, _, usage in results),
                "output_tokens": sum(usage["output_tokens"] for _, _, usage in results),
            },
            "method": "CARVE: candidate-aligned readout via vocabulary evidence",
            "probability_level": PROBABILITY_LEVEL,
            "probability_semantics": PROBABILITY_SEMANTICS,
            "thinking": False,
            "prompt_profile": prompt_profile,
            "demonstration_format": demonstration_format,
        }

    async def decide_batch(self, body: dict[str, Any]) -> dict[str, Any]:
        requests = body.get("requests")
        if not isinstance(requests, list) or not requests:
            raise ValueError("requests must be a non-empty array")
        if len(requests) > self.max_batch_size:
            raise ValueError(
                f"batch contains {len(requests)} requests; maximum is {self.max_batch_size}"
            )
        if any(not isinstance(request, dict) for request in requests):
            raise ValueError("every batch request must be an object")
        responses = await asyncio.gather(*(self.decide(request) for request in requests))
        return {
            "object": "systemone.batch",
            "model": self.system_name,
            "probability_level": PROBABILITY_LEVEL,
            "probability_semantics": PROBABILITY_SEMANTICS,
            "batch_size": len(responses),
            "responses": responses,
            "usage": {
                "input_tokens": sum(response["usage"]["input_tokens"] for response in responses),
                "output_tokens": sum(response["usage"]["output_tokens"] for response in responses),
            },
        }


def create_app(
    *,
    upstream: str,
    model: str,
    system_name: str,
    prompt_profile: str,
    tokenizer: str,
    max_concurrency: int,
    max_batch_size: int = 256,
) -> FastAPI:
    server = CandidateServer(
        upstream=upstream,
        model=model,
        system_name=system_name,
        prompt_profile=prompt_profile,
        tokenizer=tokenizer,
        max_concurrency=max_concurrency,
        max_batch_size=max_batch_size,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await server.close()

    app = FastAPI(title=system_name, lifespan=lifespan)
    app.state.carve_server = server

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "model": system_name,
            "backbone_model": model,
            "prompt_profile": prompt_profile,
        }

    def translate_error(error: Exception, *, batch: bool = False) -> HTTPException:
        if isinstance(error, ValueError):
            return HTTPException(
                status_code=422,
                detail=[
                    {
                        "loc": ["body", "requests"] if batch else ["body"],
                        "msg": str(error),
                        "type": "value_error",
                    }
                ],
            )
        if isinstance(error, httpx.HTTPStatusError):
            return HTTPException(status_code=502, detail=error.response.text[:2000])
        return HTTPException(status_code=502, detail=str(error))

    @app.post("/v1/systemone")
    async def systemone(body: dict[str, Any]) -> dict[str, Any]:
        try:
            return await server.decide(body)
        except (ValueError, KeyError, TypeError, httpx.HTTPError) as error:
            raise translate_error(error) from error

    @app.post("/v1/systemone/batch")
    async def systemone_batch(body: dict[str, Any]) -> dict[str, Any]:
        try:
            return await server.decide_batch(body)
        except (ValueError, KeyError, TypeError, httpx.HTTPError) as error:
            raise translate_error(error, batch=True) from error

    @app.get("/v1/models")
    async def models() -> dict[str, list[dict[str, str]]]:
        return {
            "models": [
                {
                    "name": system_name,
                    "description": "CARVE candidate-aligned one-token decision model",
                    "release_date": CARVE_RELEASE_DATE,
                }
            ]
        }

    return app


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serve CARVE decisions from causal-LM candidate logits"
    )
    parser.add_argument("--upstream", default="http://127.0.0.1:8000")
    parser.add_argument("--model", required=True)
    parser.add_argument("--system-name", default="CARVE-27B")
    parser.add_argument("--prompt-profile", choices=sorted(PROMPT_PROFILES), default="baseline")
    parser.add_argument("--tokenizer", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8011)
    parser.add_argument("--max-concurrency", type=int, default=8)
    parser.add_argument("--max-batch-size", type=int, default=256)
    args = parser.parse_args()
    uvicorn.run(
        create_app(
            upstream=args.upstream,
            model=args.model,
            system_name=args.system_name,
            prompt_profile=args.prompt_profile,
            tokenizer=args.tokenizer,
            max_concurrency=args.max_concurrency,
            max_batch_size=args.max_batch_size,
        ),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
