# API contract

CARVE implements the TypeSafe System One success-response contract used by
`typesafe-sdk==0.7.1` and `@typesafe-ai/sdk==0.6.0`.

## Endpoints

- `GET /health` — process and configured-backbone health metadata.
- `GET /v1/models` — TypeSafe-compatible model discovery.
- `POST /v1/systemone` — typed Noul, Choice, and Score decisions.
- `POST /v1/systemone/batch` — experimental CARVE bulk extension.
- `POST /v1/tool-calls` — experimental probabilistic tool selection and
  schema-constrained argument generation.

`state` may be a string, object, or array. A request may contain multiple named
questions. Choice criteria may be an object; Score criteria may be a list;
Noul uses true/false options.

Optional few-shot fields:

- `demonstrations`: object mapping each target question ID to a list of labeled
  `{state, question, answer}` examples.
- `demonstration_format`: `chat` (default), `compact`, or `minimal`.
- `prompt_profile`: one of the configured server prompt profiles.

Demonstration answers use the caller's option name, not the internal candidate
letter. CARVE validates the answer, maps it to the corresponding letter, and
constructs the model messages. See the
[concrete two-shot example](../experiments/few-shot.md#concrete-two-shot-example).

Every successful decision response declares:

```json
{
  "probability_level": "raw",
  "probability_semantics": "Restricted candidate-token softmax; not a calibrated probability of correctness.",
  "thinking": false
}
```

Choice and Score answers contain `confidence` for wire compatibility. It is
the largest raw candidate probability, not calibrated confidence. Noul answers
contain only the probability assigned to `true`, as required by the SDK.

Invalid input returns TypeSafe-style HTTP 422 details. Upstream malformed
responses and upstream HTTP failures return 502.

The tool-calling endpoint does not execute functions. See the complete
[CARVE-Tools contract and safety boundary](tool-calling.md).

CARVE accepts bearer headers but performs no authentication. Deploy behind a
gateway that provides TLS, authentication, rate limits, body-size limits, and
request logging appropriate to the data.
