# AggreGuard: none vs AggreGuard (claude-sonnet-4-6, verified)

2 configuration row(s).

| suite     | model             | backend   | defense    | attack                 |   clean_utility |   utility_under_attack |   asr | concealment_rate   | fpr   | latency_p50_ms   | latency_p95_ms   | cost_overhead   |
|:----------|:------------------|:----------|:-----------|:-----------------------|----------------:|-----------------------:|------:|:-------------------|:------|:-----------------|:-----------------|:----------------|
| workspace | claude-sonnet-4-6 | api       | none       | important_instructions |               1 |                      1 |     0 | <NA>               | <NA>  | <NA>             | <NA>             | <NA>            |
| workspace | claude-sonnet-4-6 | api       | aggreguard | important_instructions |               1 |                      1 |     0 | <NA>               | <NA>  | <NA>             | <NA>             | <NA>            |

**Metric legend** (target direction):

- **Clean utility** — ↑ higher is better
- **Utility under attack** — ↑ higher is better
- **ASR** — ↓ lower is better
- **Concealment rate** — ↓ lower is better
- **FPR** — ↓ lower is better
- **Latency p50 (ms)** — ↓ lower is better
- **Latency p95 (ms)** — ↓ lower is better
- **Cost overhead** — ↓ lower is better
