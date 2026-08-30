# Ecosystem rationale and success measures

## The problem

Open-source maintainers increasingly receive AI-assisted changes while AI applications themselves are released through ordinary software pipelines. Evaluation is fragmented across framework-specific objects, scripts, dashboards, and hosted services. That fragmentation makes it hard to retain comparable evidence, review release policy, or move between evaluation tools.

EvalForge addresses one bounded layer: portable aggregate evidence and deterministic release gates. It can sit after an existing evaluator and before a release. The built-in RAG evaluator is a reference producer and a zero-key path for projects that cannot send private golden datasets to a third party.

## Why this can matter beyond one repository

- **Evaluator independence:** downstream policy consumes a small artifact rather than a framework runtime.
- **Privacy-preserving defaults:** the local demo and gate require no model key, account, or external data transfer.
- **Existing CI standards:** JUnit and SARIF keep evidence usable in current developer workflows.
- **Reviewable governance:** thresholds and allowed regressions live in version control and change through pull requests.
- **Low adoption cost:** flat JSON metrics work before a producer implements the canonical schema.

EvalForge complements richer evaluation frameworks. It should not duplicate their model judges, tracing, dataset generation, or experiment-management features.

## Evidence policy

Project importance must be demonstrated, not declared. Maintainers will report only verifiable public signals:

- unique downstream repositories using the Action or artifact schema;
- package downloads after an official package is published;
- released versions and maintained compatibility windows;
- external issues, pull requests, and contributors;
- documented integrations with evaluation and CI tools;
- security reports and time to remediation.

The project currently begins at zero downstream adoption. A new repository should not describe itself as critical infrastructure until those signals exist.

## Twelve-month success criteria

1. Publish the uniquely named `evalforge-ci` distribution with reproducible releases.
2. Land at least three external evaluator adapters backed by upstream fixtures.
3. Document at least five independent downstream repositories in an adopters file with maintainer consent.
4. Maintain schema compatibility and a public changelog across at least four releases.
5. Respond to security and correctness reports within the targets in `SECURITY.md`.

These are project goals, not present-tense claims.
