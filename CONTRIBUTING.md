# Contributing

Thanks for helping make RAG quality measurable.

Anyone with a GitHub account can contribute through a fork and pull request. You do not
need write access to this repository. Documentation fixes, bug reports, reproducible
examples, tests, and code improvements are all welcome.

中文：欢迎通过 Fork 提交 PR，无需仓库写权限。小修复和文档改进可以直接提交；较大的功能、指标或兼容性变更请先开 Issue。是否合并由维护者评审决定。

## Choose a contribution

Start with issues labeled [good first issue](https://github.com/jsdhwfmax/EvalForge/issues?q=is%3Aissue%20is%3Aopen%20label%3A%22good%20first%20issue%22)
or [help wanted](https://github.com/jsdhwfmax/EvalForge/issues?q=is%3Aissue%20is%3Aopen%20label%3A%22help%20wanted%22).
These lists may be empty; small documentation or reproducibility fixes are also useful.
Comment on an issue before taking on a larger task so maintainers can help clarify its scope.

Small fixes and documentation improvements can go directly to a PR. Open an issue first
for substantial behavior, architecture, metric, or compatibility changes. Keep each PR
focused on one problem. Follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Your first pull request

1. [Fork EvalForge](https://github.com/jsdhwfmax/EvalForge/fork) into your own GitHub account.
2. Clone **your fork** and add this repository as the upstream remote. Replace
   `YOUR_USERNAME` with your GitHub username:

   ```bash
   git clone https://github.com/YOUR_USERNAME/EvalForge.git
   cd EvalForge
   git remote add upstream https://github.com/jsdhwfmax/EvalForge.git
   git fetch upstream
   git switch -c fix/short-description upstream/main
   ```

3. Make your change and run the relevant checks described below. For a small documentation
   fix, GitHub's Edit button also lets you propose a change through a fork in your browser.
4. Commit and push the feature branch to **your fork**:

   ```bash
   git add path/to/changed-file
   git commit -m "Describe the problem fixed"
   git push -u origin fix/short-description
   ```

5. Open a pull request with base repository `jsdhwfmax/EvalForge`, base branch `main`, and
   your fork's feature branch as the head. Use a draft PR if the change is still in progress.
   Fill in the PR template with the problem, change, and actual validation results.
6. Respond to review feedback by pushing additional commits to the same branch; GitHub
   updates the PR automatically. The maintainer decides whether to merge it.

First-time contributors may see GitHub Actions waiting for maintainer approval. This is
normal: you do not need to add repository secrets, deployment credentials, or a model key.
Maintainers should inspect the proposed changes before approving a workflow run.

Pull requests should explain the user problem, implementation, verification evidence, and any metric-compatibility impact. Changes to a metric definition should update `docs/METRICS.md` and include before/after fixtures.

Changes to the portable artifact or gate policy must also update the matching JSON Schema, `docs/INTEROPERABILITY.md`, and compatibility tests. New evaluator integrations should be backed by a sanitized upstream fixture rather than an invented output shape.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[rag,dashboard,dev]"
make lint
make test
```

CI validates the full suite on Linux, including Bash scripts and symbolic links.
Windows contributors should use WSL2 for the full checks and follow the Linux commands
above. If `make` is unavailable in that environment, use the equivalent checks:

```bash
python -m ruff check .
python -m mypy src/evalforge
python -m pytest --cov=evalforge --cov-report=term-missing --cov-fail-under=85
```

Python 3.12 is a convenient local default; CI checks Python 3.9 and 3.12. Please keep new
code compatible with both. The full test suite uses temporary SQLite databases and
offline or mocked model providers, so it needs no Docker, database server, model key,
or seeded demonstration data. `evalforge seed` is optional when trying the local demo.

For behavior changes, include a regression test and run `make lint` and `make test`.
For documentation-only changes, check the changed links and examples; installing all
dependencies and running application tests is optional. State which checks you ran and
explain any checks you did not run. Keep metrics deterministic or document nondeterminism
and confidence intervals.

## Review and reporting

CI checks lint, typing, tests, package builds, and the container workflow. A passing CI
run supports review; it does not replace maintainer review or guarantee a merge.
`CODEOWNERS` identifies the maintainer to request for review and does not restrict who
can submit a PR.

Never include customer data, real credentials, access keys, or private prompts in issues,
PRs, logs, or fixtures. Use the bug report template for reproducible failures and the
feature request template for proposals. Follow [SECURITY.md](SECURITY.md) for private
vulnerability reporting instead of opening a public issue or PR with exploit details.
