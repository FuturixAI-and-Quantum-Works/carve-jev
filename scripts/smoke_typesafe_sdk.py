from __future__ import annotations

import argparse
import json

from typesafe_sdk import Choice, Noul, Score, TypeSafeClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify CARVE with the TypeSafe Python SDK")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8011")
    parser.add_argument("--model", default="CARVE-27B")
    parser.add_argument("--api-key", default="local")
    args = parser.parse_args()
    with TypeSafeClient(
        api_key=args.api_key,
        base_url=args.endpoint,
        model=args.model,
        timeout=60.0,
    ) as client:
        models = client.models.list()
        response = client.system_one(
            state={"message": "My card was charged twice and I need help."},
            questions={
                "urgent": Noul(instructions="Is this request urgent?"),
                "department": Choice(
                    instructions="Which team should handle this?",
                    criteria={"billing": None, "technical": None, "sales": None},
                ),
                "severity": Score(
                    instructions="Rate the severity.",
                    criteria=["low", "medium", "high"],
                ),
            },
        )
    print(
        json.dumps(
            {
                "models": [model.name for model in models.models],
                "response_model": response.model,
                "answer_types": {name: answer.type for name, answer in response.answers.items()},
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                "status": "compatible",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
