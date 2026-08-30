# EvalForge case study

## Problem

A RAG demo can return plausible answers while hiding several independent failures: retrieval misses the source, the answer is wrong, a citation does not support its claim, latency or cost regresses, or an adversarial prompt leaks restricted data. A single “looks good” check cannot support a release decision.

EvalForge treats RAG quality as a software-testing problem. A version is evaluated against a stable golden dataset, compared with a baseline, and accepted only when explicit quality and security gates pass.

## Design goals

- Reproduce a result without requiring a paid model or API key.
- Preserve test-level evidence instead of storing only an aggregate score.
- Separate retrieval quality from generation quality.
- Make thresholds executable in local development and CI.
- Keep provider keys out of persisted configuration.
- Document proxy metrics honestly instead of presenting them as semantic truth.

## Architecture decisions

| Decision | Reason | Trade-off |
|---|---|---|
| FastAPI modular monolith | Small operational surface with clear service boundaries | Long model runs should later move to workers |
| SQLite locally, PostgreSQL/pgvector in production | Zero-key onboarding plus a realistic deployment path | SQLite does not exercise native ANN search |
| Deterministic local provider | Reproducible demos and CI without external cost | It is not a production-quality judge |
| Stable dataset fingerprint | Prevent invalid comparisons across changed corpora | Fingerprint records identity, not data lineage history |
| JSON + JUnit + SARIF reports | Human-readable evidence and standard CI/security ingestion | Current reports are experiment-level, not trend analytics |

## Test strategy

The suite covers metric edge cases, three retrieval modes, provider guardrails, duplicate imports, API validation, persistence, experiment execution, baseline/candidate comparison, quality-gate pass/fail behavior, dataset fingerprints, artifact schemas, and JSON/JUnit/SARIF output. GitHub Actions runs the suite on Python 3.9 and 3.12, builds the package and Docker image, and executes both portable-policy and seeded RAG release gates.

## Measured result

On the committed five-question synthetic benchmark:

| Result | BM25 top-1 | Hybrid top-3 |
|---|---:|---:|
| Retrieval Recall@K | 90.00% | 100.00% |
| Answer token-F1 | 75.92% | 54.85% |
| Citation support | 100.00% | 100.00% |
| Security probes passed | 4 / 4 | 4 / 4 |

The candidate retrieved both sources required by the multi-hop question, but the additional context caused the extractive answer to include irrelevant sentences. EvalForge therefore exposed a release trade-off that a retrieval-only benchmark would have missed: recall improved by 10 percentage points while answer F1 regressed by 21.07 points.

## What I would build next

1. Add calibrated LLM-as-judge and human-review queues for semantic entailment.
2. Run experiments in durable workers with cancellation and bounded concurrency.
3. Add dataset/version lineage, confidence intervals, and statistical significance.
4. Execute native pgvector HNSW retrieval for larger corpora.
5. Add tenant authentication and role-based access before hosting private datasets.

## Interview summary

> I built EvalForge to turn RAG evaluation into an executable release process. It fingerprints the dataset, runs retrieval and adversarial tests, stores test-level evidence, compares a candidate with its baseline, and emits portable JSON/JUnit/SARIF quality-gate evidence that can fail CI. The demo benchmark caught a real multi-metric trade-off: higher Recall@K produced lower answer correctness because added context increased irrelevant output.
