# Changelog

All notable changes to EvalForge are documented here.

## 0.2.0 - 2026-08-30

- Added baseline-versus-candidate comparisons with direction-aware metric verdicts.
- Added configurable release quality gates in the API, CLI, and dashboard.
- Added reproducibility metadata: dataset fingerprints, configuration snapshots, and metric versions.
- Added CI-ready JSON and JUnit reports through `evalforge check`.
- Made the seeded release gate part of GitHub Actions.
- Expanded the suite to 29 tests with 89% measured line coverage.
- Added an engineering case study and resume-ready project narrative.

## 0.1.0 - 2026-08-24

- Added the FastAPI evaluation service, Streamlit dashboard, and SQL experiment store.
- Added BM25, vector, and hybrid retrieval with deterministic local generation.
- Added quality, grounding, latency, cost, and adversarial security metrics.
- Added Docker, PostgreSQL/pgvector support, and GitHub Actions.
