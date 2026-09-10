# Portfolio and resume notes

Use only claims that remain true for the exact published version being discussed. Link to its source, release files, and successful checks; do not describe a local change as a published feature or a deployment blueprint as a running service.

## Resume bullet (English)

> Built and open-sourced EvalForge, an evaluator-neutral evidence and quality-gate layer for AI systems that converts JSON metrics into baseline-aware policies and JSON, JUnit, and SARIF reports. Published the `evalforge-ci` Python package and reusable GitHub Action, with a zero-key RAG reference evaluator, dataset fingerprints, a FastAPI API, PostgreSQL support, and a Streamlit comparison dashboard.

Verification: [published releases](https://github.com/jsdhwfmax/EvalForge/releases), [PyPI](https://pypi.org/project/evalforge-ci/), [test suite](../tests), and [CI workflow](../.github/workflows/ci.yml). Test counts and coverage belong to a specific commit and run; cite that result when needed instead of carrying an outdated number in a resume bullet.

## Measured follow-up bullet

> Designed a reproducible five-question RAG benchmark that exposed a retrieval-generation trade-off: increasing context from BM25 top-1 to hybrid top-3 improved Recall@K from 90% to 100% while reducing extractive answer token-F1 from 75.92% to 54.85%, demonstrating the need for multi-dimensional release gates.

These numbers describe the committed synthetic demo dataset and deterministic local provider, not a production LLM.

## Evidence and scope

- The [benchmark methodology](BENCHMARK.md) explains the five-question demonstration and its limitations.
- The [artifact and policy specification](INTEROPERABILITY.md) defines the supported interchange and gate behavior.
- [OSS readiness](OSS_READINESS.md) separates delivered engineering work, verified public activity, and adoption evidence that remains missing.
- The project is early. Stars measure interest; do not claim production users, independent adopters, broad ecosystem adoption, or maintainer time saved without a public source that establishes the claim.

## 中文项目描述

> 设计并开源 EvalForge——面向 AI 系统的评测证据互操作与质量门禁平台，可把任意 JSON 指标转换为可审查的基线策略、JUnit 与 SARIF，并自动阻断 CI 回归；同时提供数据集指纹、无需模型密钥的 RAG 参考评测器、FastAPI、PostgreSQL/pgvector、Streamlit、Docker 与 GitHub Actions。

## Interview talking points

- Why golden relevant-document IDs are required to calculate retrieval Recall@K.
- Why citation presence is not citation faithfulness, and why the MVP metric is documented as a proxy.
- How added context can improve recall but harm final-answer quality and cost.
- Why security probes use a synthetic canary instead of real secrets.
- How to evolve synchronous experiment execution into a queue-based worker architecture.
- How deterministic metrics enable CI gates while LLM judges and human review add semantic coverage.
- Why a dataset fingerprint is required before treating two experiment deltas as comparable.
- How JUnit output lets an LLM-specific gate fit standard SDET and CI tooling.
- Why evaluator-neutral artifacts let maintainers change measurement tools without rewriting release policy.
- Why a matching metric name and unit alone cannot establish that two evaluations used the same dataset and metric implementation.
- How to preserve aggregate release evidence while excluding raw prompts, responses, and private test data from evaluator imports.
