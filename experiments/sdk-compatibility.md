# TypeSafe SDK compatibility

Compatibility was checked on 2026-09-24 against `typesafe-sdk==0.7.1` and
`@typesafe-ai/sdk==0.6.0`.

Supported behavior includes `POST /v1/systemone`, `GET /v1/models`, string and
structured state, multiple questions, Noul/Choice/Score types, structured
instructions and criteria, score legends, aggregate token usage, and
TypeSafe-style 422 validation.

The Python SDK is exercised in-process against a mocked vLLM upstream by
`tests/test_server.py`. The official client performs strict parsing for all
three answer types and model discovery. Both official SDKs also passed live
endpoint smoke tests in the source study.

CARVE adds `probability_level="raw"` and `probability_semantics` fields.
Official clients safely ignore these extensions. Direct clients should retain
them and must not interpret the wire-compatible `confidence` field as
calibrated correctness probability.

The API accepts SDK bearer headers but does not authenticate them. Production
authentication and rate limiting belong at a gateway.
