# Changelog

All notable changes are documented here. The project follows semantic versioning while the artifact and policy formats carry independent schema versions.

## [0.3.0] - 2026-08-30

### Added

- Baseline-versus-candidate comparisons with direction-aware metric verdicts.
- Dataset fingerprints, complete configuration snapshots, and metric-version metadata.
- Stored-experiment release gates in the API and Streamlit dashboard.
- An end-to-end `evalforge check` command that runs the built-in RAG evaluator and emits portable JSON, JUnit, and SARIF evidence.
- A seeded RAG release gate in GitHub Actions.
- An engineering case study and resume-ready project narrative.
- An expanded 35-test suite with 87.35% measured line coverage.

## [0.2.0] - 2026-08-24

### Added

- Evaluator-neutral evaluation artifact schema 1.0.
- Policy schema 1 with absolute and baseline-delta checks.
- JSON, JUnit XML, and SARIF 2.1.0 gate reports.
- CI-safe gate exit codes and a reusable GitHub composite Action.
- Public governance, maintainer responsibilities, and ecosystem success measures.

### Changed

- The unique Python distribution name is now `evalforge-ci`; the import package and CLI remain `evalforge`.
- `evalforge run` can write a portable artifact with `--output`.

## [0.1.0] - 2026-08-24

- Initial RAG quality and security evaluation MVP.
