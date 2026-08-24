# Changelog

All notable changes are documented here. The project follows semantic versioning while the artifact and policy formats carry independent schema versions.

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
