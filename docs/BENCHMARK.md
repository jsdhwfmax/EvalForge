# Reproducible demo benchmark

Measured on 2026-08-24 with Python 3.9.6, SQLite, the committed six-document demo corpus, five golden questions, and the deterministic local extractive provider. Each configuration was executed once after seeding a fresh database.

| Metric | BM25 · top 1 | Hybrid · top 3 |
|---|---:|---:|
| Retrieval Recall@K | 90.00% | 100.00% |
| Answer correctness (token F1) | 75.92% | 54.85% |
| Citation support | 100.00% | 100.00% |
| Hallucination proxy | 0.00% | 0.00% |
| Mean latency | 0.26 ms | 0.34 ms |
| Security pass rate (4 probes) | 100.00% | 100.00% |
| Input / output tokens (estimated) | 310 / 98 | 597 / 175 |
| Configured model cost | $0.00 | $0.00 |

The top-3 configuration retrieved every labeled relevant document, including both documents needed by the multi-hop deletion question. Its extractive answer F1 fell because additional context produced longer answers with irrelevant sentences. This is a useful demo of the trade-off EvalForge is designed to expose; it is not evidence that hybrid retrieval is generally worse.

Sub-millisecond local latency and zero cost describe only the offline provider. They must not be used as estimates for a hosted LLM.

## Reproduce

```bash
rm -f evalforge.db
evalforge seed
evalforge run baseline_top1 --name "Measured baseline"
evalforge run hybrid_top3 --name "Measured candidate"
```

Metric definitions and limitations are documented in [METRICS.md](METRICS.md).
