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

### Dated adoption snapshots

From its public launch on 2026-08-24 through 2026-08-30, the repository received 41 GitHub stars. That is a verifiable signal of early interest, not proof of production use or broad adoption. As of this snapshot, confirmed downstream integrations, external issues, external pull requests, external contributors, and forks remain at zero. The project will keep these categories separate rather than converting attention into an unsupported infrastructure claim.

On 2026-08-31, the repository reached 48 GitHub stars. Public GitHub data still showed zero forks and zero external contributors, and an exact global code search found no downstream repository using `uses: jsdhwfmax/EvalForge`. These numbers continue to measure early interest rather than adoption; confirmed users will be recorded separately in [`ADOPTERS.md`](../ADOPTERS.md) with consent and a public integration link.

Later on 2026-08-31, the public repository reached 50 GitHub stars. It still had zero forks, zero external contributors, and zero confirmed downstream adopters; the only open pull request was an automated Dependabot update. The milestone is recorded as early interest only and does not change the project's adoption claims.

On 2026-09-10 at 11:05 UTC, the [public GitHub repository API](https://api.github.com/repos/jsdhwfmax/EvalForge) reported 177 stars and zero forks. The [contributors endpoint](https://api.github.com/repos/jsdhwfmax/EvalForge/contributors) listed one contributor, the primary maintainer. There were [four public GitHub releases](https://github.com/jsdhwfmax/EvalForge/releases), including two marked prerelease; the latest was v0.3.1. The [PyPI project](https://pypi.org/project/evalforge-ci/0.3.1/) exposed the 0.3.1 distribution. No independent downstream adopter had been verified for `ADOPTERS.md`. These are dated observations, not live counts or evidence of production adoption.

The package-publication milestone is therefore complete. The harder next step is demonstrating that another maintainer can integrate EvalForge, understand a failed gate, and keep using it as their evaluator changes. Adapter fixtures, complete CI examples, comparison safeguards, and reports that identify their input evidence support that work. They are engineering deliverables, not substitutes for independently confirmed use.

See [OSS readiness and evidence](OSS_READINESS.md) for the current application rationale and the limits of each evidence category.

## Twelve-month success criteria

1. Maintain the published `evalforge-ci` distribution with verified wheel/source releases, installation checks, and documented compatibility.
2. Land at least three external evaluator adapters backed by upstream fixtures.
3. Document at least five independent downstream repositories in an adopters file with maintainer consent.
4. Maintain schema compatibility and a public changelog across at least four releases.
5. Respond to security and correctness reports within the targets in `SECURITY.md`.

Publication of `evalforge-ci` has been verified. The remaining targets are project goals, not present-tense claims.
