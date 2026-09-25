# CARVE-Tools: decision-native tool calling

CARVE-Tools is an experimental tool-calling extension for the CARVE Jev-like
model family. The existing System One endpoint performs two internal jobs:

1. CARVE selects one function, or no function, from next-token candidate
   logits.
2. Only the winning function's JSON Schema is sent to a constrained generation
   request for arguments.

The server returns an OpenAI-shaped `tool_calls` array but never executes a
tool. Existing `/v1/systemone` behavior and TypeSafe SDK compatibility are
unchanged.

## Why split selection from arguments?

Tool choice is a closed decision over known candidates, which matches CARVE's
one-token readout. Arguments are open-ended values and require generation.
Keeping these phases separate provides a probability distribution over tool
selection while avoiding every losing tool schema in the argument prompt.

The selection probability does **not** measure argument correctness. Arguments
are structurally validated against JSON Schema, but they can still be
semantically wrong. Authorization, confirmation, side-effect policy, and tool
execution remain caller responsibilities.

## Endpoint

`POST /v1/systemone`

With CARVE running, execute the reusable live check:

```bash
python scripts/smoke_tool_calling.py
```

`tools` may be supplied alone or alongside ordinary `questions`; the same
response then contains both typed `answers` and `tool_calls`.

```json
{
  "model": "CARVE-27B",
  "state": "What is the weather in Paris?",
  "tool_choice": "auto",
  "minimum_confidence": 0.6,
  "parallel_tool_calls": false,
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
            "units": {"type": "string", "enum": ["celsius", "fahrenheit"]}
          },
          "required": ["city"],
          "additionalProperties": false
        }
      }
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
          "additionalProperties": false
        }
      }
    }
  ]
}
```

Example response:

```json
{
  "model": "CARVE-27B",
  "answers": {},
  "tool_selection": {
    "mode": "auto",
    "selected_tool": "get_weather",
    "confidence": 0.91,
    "tool_probabilities": {
      "get_weather": 0.91,
      "search_docs": 0.03
    },
    "no_tool_probability": 0.06,
    "probability_level": "raw"
  },
  "tool_calls": [
    {
      "id": "call_...",
      "type": "function",
      "function": {
        "name": "get_weather",
        "arguments": "{\"city\":\"Paris\",\"units\":\"celsius\"}"
      },
      "parsed_arguments": {
        "city": "Paris",
        "units": "celsius"
      }
    }
  ],
  "finish_reason": "tool_calls"
}
```

## Tool-choice modes

- `auto` (default): scores every function plus an internal no-tool candidate.
  Supports up to 25 functions.
- `required`: scores functions without a no-tool candidate. Supports up to 26.
- `none`: returns no call without contacting the model.
- `{"type":"function","function":{"name":"..."}}`: forces one function and
  skips selection.

CARVE v1 emits at most one function call. Set `parallel_tool_calls` to `false`
or omit it.

## Confidence gate

Set `minimum_confidence` from `0` to `1`. When the selected function is below
the threshold, CARVE returns no call and `finish_reason: "low_confidence"`.
The confidence is a raw restricted softmax, not a calibrated probability of
correctness. Choose a threshold from labelled tool-routing traces rather than
guessing one.

## Argument generation

`max_argument_tokens` defaults to 256 and accepts values from 1 to 2048. CARVE
uses vLLM's JSON Schema response format, parses the generated object, and
validates it again with JSON Schema before returning it. Invalid schemas and
external `$ref` URLs are rejected during request validation. Schema features
unsupported by the configured vLLM backend, or invalid generated arguments,
produce HTTP 502 rather than an executable call.

## Safety boundary

The endpoint plans a call; it does not run one. Before execution, applications
should independently enforce:

- a trusted server-side registry rather than user-supplied tool definitions;
- tool allowlists and user permissions;
- confirmation for destructive, expensive, irreversible, or external actions;
- semantic validation of IDs, paths, URLs, and amounts;
- timeouts, retries, idempotency, and audit logs;
- a fallback when selection confidence is low.

Jev has previously been used as a tool selector in external agent harnesses.
CARVE-Tools packages that decision/generation split as an open server contract;
it should not be described as the first use of a Jev-like model anywhere in
tool routing.
