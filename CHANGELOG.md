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
- An expanded 39-test suite with 87.68% measured line coverage.

## [0.2.1] - 2026-08-30

### Fixed

- Reject non-finite metric values and policy thresholds before they can enter JSON, JUnit, or SARIF evidence.
- Fail baseline-delta checks when candidate and baseline units or metric directions do not match.
- Reject duplicate policy check IDs so report identifiers remain unambiguous.
- Isolate SQLite databases per pytest session so concurrent test runs cannot corrupt each other.

### Changed

- Update maintained GitHub Actions and development dependency ranges after successful Dependabot CI runs; pin Actions to full commit SHAs.
- Cancel superseded CI runs on the same ref.
- Build and attach checked Python distributions plus SHA-256 checksums when a GitHub Release is published.
- Mark the installed Python package as typed for PEP 561-aware consumers.

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
