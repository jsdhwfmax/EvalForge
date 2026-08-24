# Portfolio and resume notes

Use only claims that remain true for the published repository and deployed environment.

## Resume bullet (English)

> Built and open-sourced EvalForge, a FastAPI/PostgreSQL evaluation platform for RAG applications that benchmarks retrieval recall, answer correctness, citation support, hallucination, latency, token cost, and adversarial security across versioned configurations; shipped with 23 automated tests (87% coverage), Docker Compose, CI, and a Streamlit dashboard.

## Measured follow-up bullet

> Designed a reproducible five-question RAG benchmark that exposed a retrieval-generation trade-off: increasing context from BM25 top-1 to hybrid top-3 improved Recall@K from 90% to 100% while reducing extractive answer token-F1 from 75.92% to 54.85%, demonstrating the need for multi-dimensional release gates.

These numbers describe the committed synthetic demo dataset and deterministic local provider, not a production LLM.

## 中文项目描述

> 设计并开源 EvalForge——面向 RAG/AI Assistant 的质量与安全评估平台。平台支持版本化检索/模型配置对比，记录召回率、答案正确性、引用支持度、幻觉、延迟、Token 成本与对抗安全结果，并提供 FastAPI、PostgreSQL/pgvector、Streamlit Dashboard、Docker 与 GitHub Actions。

## Interview talking points

- Why golden relevant-document IDs are required to calculate retrieval Recall@K.
- Why citation presence is not citation faithfulness, and why the MVP metric is documented as a proxy.
- How added context can improve recall but harm final-answer quality and cost.
- Why security probes use a synthetic canary instead of real secrets.
- How to evolve synchronous experiment execution into a queue-based worker architecture.
- How deterministic metrics enable CI gates while LLM judges and human review add semantic coverage.
