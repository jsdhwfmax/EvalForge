# OSS readiness and evidence

EvalForge is an early MIT-licensed project for turning evaluator output into reviewable CI release decisions. Its application case rests on a concrete interoperability problem and inspectable maintenance work. Broad adoption has not been established.

## Official program alignment

Checked on 2026-09-10:

- [Codex for Open Source](https://learn.chatgpt.com/community/codex-for-oss) invites core maintainers and widely used public projects to apply. A project outside those categories may still explain its ecosystem importance. The page publishes no minimum star count.
- The [program terms](https://learn.chatgpt.com/docs/codex-for-oss-terms) require a valid ChatGPT account and accurate information about the applicant, repositories, and maintenance role. Review may consider usage, ecosystem importance, active maintenance, permissions, and program capacity; affiliation or control may need verification.
- Selection and benefits are discretionary. API credits and Codex Security may require additional review, and repository access must be authorized.

This is an evidence map, not a claim of acceptance or a replacement for the current application form and terms.

## Public evidence snapshot

The following public endpoints were checked on **2026-09-10 at 11:05 UTC**. They are live sources; their values can change after this dated snapshot.

| Category | Verified observation | Source and limit |
|---|---|---|
| Public source and license | `jsdhwfmax/EvalForge`, MIT | [Repository](https://github.com/jsdhwfmax/EvalForge) and [license](../LICENSE) |
| Maintenance responsibility | One named primary maintainer | [MAINTAINERS.md](../MAINTAINERS.md); program reviewers may separately verify repository permissions |
| Interest | 177 GitHub stars | [Repository API](https://api.github.com/repos/jsdhwfmax/EvalForge); interest does not establish use |
| Forks | 0 | Same repository endpoint; no adoption claim follows from this count |
| Contributors | GitHub's endpoint listed only `jsdhwfmax` | [Contributors API](https://api.github.com/repos/jsdhwfmax/EvalForge/contributors); this does not capture every kind of community contribution |
| Released source | Four GitHub releases, two marked prerelease; latest v0.3.1 | [Releases](https://github.com/jsdhwfmax/EvalForge/releases) |
| Python distribution | `evalforge-ci` 0.3.1 available on PyPI | [Exact package version](https://pypi.org/project/evalforge-ci/0.3.1/); this observation is package availability, not a new installation test |
| Independent adoption | None verified for the adopters record | [ADOPTERS.md](../ADOPTERS.md); absence from this record does not prove nobody uses the package |
| Quality evidence | Test code and CI/release workflows are public | [Tests](../tests), [CI](../.github/workflows/ci.yml), [release workflow](../.github/workflows/release.yml); a workflow definition alone does not prove a run passed |

The v0.4.0 upgrade is separate from this pre-upgrade snapshot. Any claim that v0.4.0 is published, installed successfully, or passing CI must cite its actual release and verification results after they exist.

## Why the project can matter

An evaluator answers how a system scored. A release gate must also answer which evidence was compared, what policy was enforced, and why a release passed or failed. EvalForge keeps that boundary small: aggregate artifacts, explicit policies, and reports consumed by existing CI tools. It can be used without running an EvalForge service or sending a private golden dataset to one.

The strongest demonstration is a complete, reproducible integration: import a supported evaluator's sanitized output, compare it with the intended baseline, fail a policy for a known regression, and retain reports that explain the decision. [Interoperability](INTEROPERABILITY.md) documents the supported formats and semantic boundaries. Adapters complement existing evaluators; they do not establish that an evaluator's metric is scientifically valid.

For baseline checks, unit agreement alone is insufficient. Dataset identity, producer identity, and metric-implementation version are useful comparison constraints when the producer supplies them. These safeguards must have explicit behavior for missing or incompatible evidence and retain a documented path for simple flat summaries.

## Maintenance work the program could support

- Review schema, adapter, and policy changes against compatibility fixtures.
- Triage reproducible issues and turn regressions into tests.
- Review input parsing, report rendering, dependency changes, and the release supply chain.
- Maintain versioned adapter mappings and executable CI examples.
- Prepare release notes and verify distributions before publishing.

The maintainer remains responsible for review and release decisions. Sanitized fixtures and public source are sufficient for this maintenance work; private user datasets are not needed in application materials.

## What remains to demonstrate

1. A public integration in an independently maintained repository, linked and listed with that maintainer's consent.
2. Feedback showing whether another maintainer can install the package, understand a failed check, and maintain its policy.
3. Sustained compatibility across evaluator versions and several maintenance releases.
4. Measured outcomes, such as a documented regression caught or maintenance time saved, with the method and source attached.

These are evidence gaps and project goals. They cannot be filled by stars, synthetic users, a new README claim, or a local demonstration labeled as production use. For the application, describe the present engineering contribution and these limits together.
