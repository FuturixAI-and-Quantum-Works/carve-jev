#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a live CARVE-Tools smoke test")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8011")
    parser.add_argument("--model", default="CARVE-27B")
    args = parser.parse_args()

    response = httpx.post(
        f"{args.endpoint.rstrip('/')}/v1/tool-calls",
        json={
            "model": args.model,
            "state": "What is the weather in Paris in Celsius?",
            "tool_choice": "auto",
            "parallel_tool_calls": False,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get current weather for a city.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "city": {"type": "string"},
                                "units": {
                                    "type": "string",
                                    "enum": ["celsius", "fahrenheit"],
                                },
                            },
                            "required": ["city", "units"],
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
        },
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    if payload["selection"]["selected_tool"] != "get_weather":
        raise RuntimeError(f"unexpected selection: {payload['selection']}")
    if not payload["tool_calls"]:
        raise RuntimeError(f"no tool call returned: {payload}")
    arguments = payload["tool_calls"][0]["parsed_arguments"]
    if arguments.get("city") != "Paris" or arguments.get("units") != "celsius":
        raise RuntimeError(f"unexpected arguments: {arguments}")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
