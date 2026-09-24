# Production performance

The selected FP8 two-shot server was measured on one NVIDIA RTX PRO 6000
Blackwell Server Edition with an 8,192-token context and prefill budget,
32 maximum sequences, prefix caching, thinking disabled, and one output token.

A deterministic 512-request workload was shuffled and sent by closed-loop
clients. HTTP-boundary latency includes queueing.

- Concurrency 1: 13.14 requests/s; 72.2/86.2/123.8 ms p50/p95/p99
- Concurrency 2: 14.84 requests/s; 132.9/148.2/156.4 ms
- Concurrency 4: 19.50 requests/s; 208.0/225.7/234.9 ms
- Concurrency 8: 21.27 requests/s; 380.9/404.2/459.0 ms
- Concurrency 16: 21.74 requests/s; 739.9/784.0/845.2 ms
- Concurrency 32: 22.23 requests/s; 1,451.4/1,529.4/1,541.1 ms

All 3,072 sweep requests succeeded. A separate 2,048-request concurrency-8
run delivered **20.23 requests/s**, 382.3 ms p50, 554.4 ms p95, and zero
failures. The conservative planning number is 20.23 requests/s.

Throughput saturates near concurrency 8; raising concurrency to 32 adds only
4.5% throughput while increasing median latency about 3.8×. Use concurrency 1
for latency-sensitive traffic and 8 for loaded traffic.

The workload and local hardware do not match hosted Jev infrastructure, so
this is not a controlled speed comparison. See `artifacts/load-sweep.json` and
`artifacts/sustained-load.json`.
