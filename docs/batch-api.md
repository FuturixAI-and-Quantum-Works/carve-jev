# Experimental batch API

`POST /v1/systemone/batch` accepts ordinary CARVE request objects:

```json
{
  "requests": [
    {
      "model": "CARVE-27B",
      "state": "My card was charged twice.",
      "questions": {
        "route": {
          "type": "choice",
          "instructions": "Choose a team.",
          "criteria": {"billing": null, "technical": null}
        }
      }
    }
  ]
}
```

The response preserves request order, aggregates token usage, and declares
`probability_level: "raw"` plus the raw probability semantics. Validation or
upstream failure currently fails the whole batch. The default maximum is 256
items and is configurable with `--max-batch-size`.

This endpoint is not part of the official TypeSafe SDK contract. On the
measured two-shot FP8 workload, batch sizes 1/4/8/16/32 delivered
13.30/18.54/20.30/20.97/21.50 items/s. All 2,560 logical requests succeeded.
Larger batches increased completion latency and did not beat a properly
concurrent individual-request client. Start with batch size 8.

See `artifacts/batch-size-sweep.json` and reproduce with:

```bash
python scripts/benchmark_carve_batch.py \
  --suite /path/to/transfer-v9/test.jsonl \
  --few-shot-pool /path/to/transfer-v9/development.jsonl \
  --output artifacts/my-batch-sweep.json
```
