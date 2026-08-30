# Portfolio and resume notes

Use only claims that remain true for the published repository and deployed environment.

## Resume bullet (English)

> Built and open-sourced EvalForge, a FastAPI/PostgreSQL quality platform for RAG applications that fingerprints datasets, benchmarks retrieval/grounding/security/latency/cost, compares candidates with baselines, and blocks regressions through configurable JSON/JUnit release gates; shipped with 29 automated tests (89% coverage), Docker Compose, GitHub Actions, and a Streamlit dashboard.

## Measured follow-up bullet

> Designed a reproducible five-question RAG benchmark that exposed a retrieval-generation trade-off: increasing context from BM25 top-1 to hybrid top-3 improved Recall@K from 90% to 100% while reducing extractive answer token-F1 from 75.92% to 54.85%, demonstrating the need for multi-dimensional release gates.

These numbers describe the committed synthetic demo dataset and deterministic local provider, not a production LLM.

## 中文项目描述

> 设计并开源 EvalForge——面向 RAG/AI Assistant 的质量与安全发布平台。平台对数据集生成稳定指纹，对比基线与候选版本的召回率、正确性、引用支持、幻觉、延迟、成本及对抗安全结果，并通过可配置阈值输出 JSON/JUnit 报告、自动阻断 CI 回归；配套 FastAPI、PostgreSQL/pgvector、Streamlit、Docker 与 GitHub Actions。

## Interview talking points

- Why golden relevant-document IDs are required to calculate retrieval Recall@K.
- Why citation presence is not citation faithfulness, and why the MVP metric is documented as a proxy.
- How added context can improve recall but harm final-answer quality and cost.
- Why security probes use a synthetic canary instead of real secrets.
- How to evolve synchronous experiment execution into a queue-based worker architecture.
- How deterministic metrics enable CI gates while LLM judges and human review add semantic coverage.
- Why a dataset fingerprint is required before treating two experiment deltas as comparable.
- How JUnit output lets an LLM-specific gate fit standard SDET and CI tooling.
