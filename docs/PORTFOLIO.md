# Portfolio and resume notes

Use only claims that remain true for the published repository and deployed environment.

## Resume bullet (English)

> Built and open-sourced EvalForge, an evaluator-neutral evidence and quality-gate layer for AI systems that converts JSON metrics into baseline-aware policies, JSON, JUnit, and SARIF; also shipped a zero-key RAG reference evaluator with dataset fingerprints, a FastAPI/PostgreSQL API, 39 tests (87.68% coverage), Docker Compose, GitHub Actions, and a Streamlit release dashboard.

## Measured follow-up bullet

> Designed a reproducible five-question RAG benchmark that exposed a retrieval-generation trade-off: increasing context from BM25 top-1 to hybrid top-3 improved Recall@K from 90% to 100% while reducing extractive answer token-F1 from 75.92% to 54.85%, demonstrating the need for multi-dimensional release gates.

These numbers describe the committed synthetic demo dataset and deterministic local provider, not a production LLM.

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
