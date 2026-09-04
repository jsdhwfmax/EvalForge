# Changelog

All notable changes are documented here. The project follows semantic versioning while the artifact and policy formats carry independent schema versions.

## [0.3.1] - 2026-08-31

### Added

- An explicit promptfoo JSON results-schema-v3 adapter that emits sanitized aggregate evidence and preserves producer provenance.
- Upstream-format synthetic promptfoo fixtures and compatibility tests covering unknown fields, missing provenance, non-finite evidence, inconsistent counts, and the CLI import path.
- CodeQL analysis for Python pull requests, main-branch pushes, and scheduled scans with minimal permissions.
- PyPI Trusted Publishing through GitHub OIDC, with the official publish Action pinned to a reviewed commit.
- Workflow invariants that reject floating third-party Action references and keep the OIDC permission scoped to the publish job.

### Changed

- Build release distributions once, verify them with Twine and SHA-256, then reuse the same workflow artifact for GitHub Release assets and PyPI publication.
- Document the promptfoo metric mapping, source-version boundary, privacy exclusions, and first-release Trusted Publisher checklist.
- Keep Dependabot from proposing mypy 2.x or Twine 7.x while the project maintains Python 3.9 compatibility.
- Include conformance fixtures, examples, workflow definitions, and release metadata in the source distribution so its bundled test suite is self-contained.

## [0.3.0] - 2026-08-31

### Added

- Baseline-versus-candidate comparisons with direction-aware metric verdicts.
- Dataset fingerprints, complete configuration snapshots, and metric-version metadata.
- Stored-experiment release gates in the API and Streamlit dashboard.
- An end-to-end `evalforge check` command that runs the built-in RAG evaluator and emits portable JSON, JUnit, and SARIF evidence.
- A seeded RAG release gate in GitHub Actions.
- An engineering case study and resume-ready project narrative.
- An expanded test suite with an enforced 85% branch-coverage floor.

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
