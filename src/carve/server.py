from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import jsonschema
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
NO_TOOL_NAME = "__carve_no_tool__"
MAX_TOOL_SCHEMA_BYTES = 65_536
TOOL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
TOOL_SELECTION_INSTRUCTIONS = (
    "Select the single function that should handle the supplied state. Choose the "
    "no-tool option when no function is relevant. Judge only from function purpose; "
    "argument generation happens separately."
)
TOOL_ARGUMENT_PROMPT = (
    "Generate arguments for the selected function from the supplied state. Follow "
    "the JSON schema exactly. Return only the JSON object, with no explanation or "
    "reasoning. Do not invent values that are absent from the state."
)


class ToolArgumentError(RuntimeError):
    """Raised when upstream argument generation violates the selected schema."""


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

    @staticmethod
    def _normalize_tools(raw_tools: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_tools, list) or not raw_tools:
            raise ValueError("tools must be a non-empty array")

        def has_external_ref(value: Any) -> bool:
            if isinstance(value, dict):
                reference = value.get("$ref")
                if reference is not None and (
                    not isinstance(reference, str) or not reference.startswith("#")
                ):
                    return True
                return any(has_external_ref(item) for item in value.values())
            if isinstance(value, list):
                return any(has_external_ref(item) for item in value)
            return False

        tools: list[dict[str, Any]] = []
        names: set[str] = set()
        for index, raw_tool in enumerate(raw_tools):
            if not isinstance(raw_tool, dict) or raw_tool.get("type") != "function":
                raise ValueError(f"tools[{index}] must be a function tool")
            function = raw_tool.get("function")
            if not isinstance(function, dict):
                raise ValueError(f"tools[{index}].function must be an object")
            name = function.get("name")
            if not isinstance(name, str) or not TOOL_NAME_PATTERN.fullmatch(name):
                raise ValueError(
                    f"tools[{index}].function.name must match {TOOL_NAME_PATTERN.pattern}"
                )
            if name == NO_TOOL_NAME:
                raise ValueError(f"tool name {NO_TOOL_NAME!r} is reserved")
            if name in names:
                raise ValueError(f"duplicate tool name: {name!r}")
            names.add(name)
            description = function.get("description", "")
            if not isinstance(description, str):
                raise ValueError(f"tools[{index}].function.description must be a string")
            if len(description) > 4096:
                raise ValueError(f"tools[{index}].function.description exceeds 4096 characters")
            parameters = function.get(
                "parameters",
                {"type": "object", "properties": {}, "additionalProperties": False},
            )
            if not isinstance(parameters, dict):
                raise ValueError(f"tools[{index}].function.parameters must be an object")
            if parameters.get("type") != "object":
                raise ValueError(f"tools[{index}] parameter schema must have root type object")
            if len(json.dumps(parameters, ensure_ascii=False).encode()) > MAX_TOOL_SCHEMA_BYTES:
                raise ValueError(
                    f"tools[{index}].function.parameters exceeds {MAX_TOOL_SCHEMA_BYTES} bytes"
                )
            if has_external_ref(parameters):
                raise ValueError(f"tools[{index}].function.parameters has an external $ref")
            try:
                jsonschema.Draft202012Validator.check_schema(parameters)
            except jsonschema.SchemaError as error:
                raise ValueError(
                    f"tools[{index}].function.parameters is not valid JSON Schema: {error.message}"
                ) from error
            tools.append(
                {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                }
            )
        return tools

    @staticmethod
    def _tool_choice(raw_choice: Any, names: set[str]) -> tuple[str, str | None]:
        if raw_choice is None:
            return "auto", None
        if isinstance(raw_choice, str):
            if raw_choice not in {"auto", "required", "none"}:
                raise ValueError("tool_choice must be auto, required, none, or a function object")
            return raw_choice, None
        if not isinstance(raw_choice, dict) or raw_choice.get("type") != "function":
            raise ValueError("tool_choice function selection must have type 'function'")
        function = raw_choice.get("function")
        if not isinstance(function, dict) or not isinstance(function.get("name"), str):
            raise ValueError("tool_choice.function.name must be a string")
        name = function["name"]
        if name not in names:
            raise ValueError(f"tool_choice references unknown tool {name!r}")
        return "forced", name

    @staticmethod
    def _usage(result: dict[str, Any]) -> dict[str, int]:
        raw_usage = result.get("usage")
        if not isinstance(raw_usage, dict):
            raw_usage = {}
        return {
            "input_tokens": int(
                raw_usage.get("prompt_tokens", raw_usage.get("input_tokens", 0)) or 0
            ),
            "output_tokens": int(
                raw_usage.get("completion_tokens", raw_usage.get("output_tokens", 0)) or 0
            ),
        }

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
        return question_id, answer, self._usage(result)

    async def decide(self, body: dict[str, Any]) -> dict[str, Any]:
        if "state" not in body or not isinstance(body["state"], (str, dict, list)):
            raise ValueError("state must be a string, object, or array")
        if not isinstance(body.get("model"), str) or not body["model"].strip():
            raise ValueError("model must be a non-empty string")
        has_tools = "tools" in body
        questions = body.get("questions", {})
        if not isinstance(questions, dict) or (not questions and not has_tools):
            raise ValueError("questions must be a non-empty object when tools are not supplied")
        prompt_profile = body.get("prompt_profile", self.prompt_profile)
        if prompt_profile not in PROMPT_PROFILES:
            raise ValueError(f"unknown prompt profile: {prompt_profile!r}")
        demonstrations = body.get("demonstrations", {})
        if not isinstance(demonstrations, dict):
            raise ValueError("demonstrations must map question IDs to lists")
        demonstration_format = body.get("demonstration_format", "chat")
        if demonstration_format not in {"chat", "compact", "minimal"}:
            raise ValueError("demonstration_format must be chat, compact, or minimal")
        question_results = asyncio.gather(
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
        tool_result: dict[str, Any] | None = None
        if has_tools:
            results, tool_result = await asyncio.gather(question_results, self.tool_call(body))
        else:
            results = await question_results
        response = {
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
        if tool_result is not None:
            response["tool_selection"] = tool_result["selection"]
            response["tool_calls"] = tool_result["tool_calls"]
            response["finish_reason"] = tool_result["finish_reason"]
            response["tool_method"] = tool_result["method"]
            response["usage"] = {
                "input_tokens": (
                    response["usage"]["input_tokens"] + tool_result["usage"]["input_tokens"]
                ),
                "output_tokens": (
                    response["usage"]["output_tokens"] + tool_result["usage"]["output_tokens"]
                ),
            }
        return response

    async def generate_tool_arguments(
        self,
        *,
        state: Any,
        media: Any,
        tool: dict[str, Any],
        max_tokens: int,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        payload = {
            "state": state,
            "selected_function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        }
        request = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": TOOL_ARGUMENT_PROMPT},
                {"role": "user", "content": self._user_content(payload, media)},
            ],
            "max_tokens": max_tokens,
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "carve_tool_arguments",
                    "schema": tool["parameters"],
                    "strict": True,
                },
            },
            "chat_template_kwargs": {
                "enable_thinking": False,
                "preserve_thinking": False,
            },
        }
        async with self.semaphore:
            response = await self.client.post(f"{self.upstream}/v1/chat/completions", json=request)
        response.raise_for_status()
        result = response.json()
        try:
            content = result["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("message content is not a string")
            arguments = json.loads(content)
            if not isinstance(arguments, dict):
                raise TypeError("arguments are not a JSON object")
            jsonschema.Draft202012Validator(tool["parameters"]).validate(arguments)
        except (
            KeyError,
            IndexError,
            TypeError,
            json.JSONDecodeError,
            jsonschema.ValidationError,
        ) as error:
            raise ToolArgumentError(
                f"upstream returned invalid arguments for tool {tool['name']!r}: {error}"
            ) from error
        return arguments, self._usage(result)

    async def tool_call(self, body: dict[str, Any]) -> dict[str, Any]:
        if "state" not in body or not isinstance(body["state"], (str, dict, list)):
            raise ValueError("state must be a string, object, or array")
        if not isinstance(body.get("model"), str) or not body["model"].strip():
            raise ValueError("model must be a non-empty string")
        if body.get("parallel_tool_calls", False) is not False:
            raise ValueError("parallel_tool_calls is not supported; pass false")
        max_argument_tokens = body.get("max_argument_tokens", 256)
        if (
            isinstance(max_argument_tokens, bool)
            or not isinstance(max_argument_tokens, int)
            or not 1 <= max_argument_tokens <= 2048
        ):
            raise ValueError("max_argument_tokens must be an integer from 1 to 2048")
        minimum_confidence = body.get("minimum_confidence", 0.0)
        if (
            isinstance(minimum_confidence, bool)
            or not isinstance(minimum_confidence, (int, float))
            or not 0 <= minimum_confidence <= 1
        ):
            raise ValueError("minimum_confidence must be a number from 0 to 1")
        prompt_profile = body.get("prompt_profile", self.prompt_profile)
        if prompt_profile not in PROMPT_PROFILES:
            raise ValueError(f"unknown prompt profile: {prompt_profile!r}")

        tools = self._normalize_tools(body.get("tools"))
        by_name = {tool["name"]: tool for tool in tools}
        choice_mode, forced_name = self._tool_choice(body.get("tool_choice"), set(by_name))
        maximum_tools = len(LETTERS) - 1 if choice_mode == "auto" else len(LETTERS)
        if len(tools) > maximum_tools:
            raise ValueError(f"tool_choice={choice_mode} supports at most {maximum_tools} tools")

        usage = {"input_tokens": 0, "output_tokens": 0}
        selected_name: str | None
        confidence: float
        tool_probabilities: dict[str, float]
        no_tool_probability: float | None
        if choice_mode == "none":
            selected_name = None
            confidence = 1.0
            tool_probabilities = {name: 0.0 for name in by_name}
            no_tool_probability = 1.0
        elif choice_mode == "forced":
            selected_name = forced_name
            confidence = 1.0
            tool_probabilities = {name: 1.0 if name == selected_name else 0.0 for name in by_name}
            no_tool_probability = None
        elif choice_mode == "required" and len(tools) == 1:
            selected_name = tools[0]["name"]
            confidence = 1.0
            tool_probabilities = {selected_name: 1.0}
            no_tool_probability = None
        else:
            criteria = {
                tool["name"]: (
                    f"{tool['name']}: {tool['description']}"
                    if tool["description"]
                    else f"Call {tool['name']}"
                )
                for tool in tools
            }
            if choice_mode == "auto":
                criteria[NO_TOOL_NAME] = "No available function should be called."
            _, answer, usage = await self.decide_question(
                body["state"],
                body.get("media"),
                prompt_profile,
                "chat",
                None,
                "tool",
                {
                    "type": "choice",
                    "instructions": TOOL_SELECTION_INSTRUCTIONS,
                    "criteria": criteria,
                },
            )
            winner = answer["choice"]
            probabilities = answer["probabilities"]
            selected_name = None if winner == NO_TOOL_NAME else winner
            confidence = float(answer["confidence"])
            tool_probabilities = {name: float(probabilities[name]) for name in by_name}
            no_tool_probability = (
                float(probabilities[NO_TOOL_NAME]) if choice_mode == "auto" else None
            )

        selection = {
            "mode": choice_mode,
            "selected_tool": selected_name,
            "confidence": confidence,
            "tool_probabilities": tool_probabilities,
            "no_tool_probability": no_tool_probability,
            "probability_level": PROBABILITY_LEVEL,
        }
        tool_calls: list[dict[str, Any]] = []
        if selected_name is None:
            finish_reason = "stop"
        elif confidence < float(minimum_confidence):
            finish_reason = "low_confidence"
        else:
            arguments, argument_usage = await self.generate_tool_arguments(
                state=body["state"],
                media=body.get("media"),
                tool=by_name[selected_name],
                max_tokens=max_argument_tokens,
            )
            usage = {
                "input_tokens": usage["input_tokens"] + argument_usage["input_tokens"],
                "output_tokens": usage["output_tokens"] + argument_usage["output_tokens"],
            }
            tool_calls.append(
                {
                    "id": f"call_{uuid.uuid4().hex}",
                    "type": "function",
                    "function": {
                        "name": selected_name,
                        "arguments": json.dumps(
                            arguments,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    },
                    "parsed_arguments": arguments,
                }
            )
            finish_reason = "tool_calls"

        return {
            "selection": selection,
            "tool_calls": tool_calls,
            "finish_reason": finish_reason,
            "usage": usage,
            "method": (
                "CARVE-Tools: candidate-logit selection plus schema-constrained argument generation"
            ),
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
        except (
            ValueError,
            KeyError,
            TypeError,
            ToolArgumentError,
            httpx.HTTPStatusError,
        ) as error:
            raise translate_error(error) from error

    @app.post("/v1/systemone/batch")
    async def systemone_batch(body: dict[str, Any]) -> dict[str, Any]:
        try:
            return await server.decide_batch(body)
        except (
            ValueError,
            KeyError,
            TypeError,
            ToolArgumentError,
            httpx.HTTPStatusError,
        ) as error:
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
