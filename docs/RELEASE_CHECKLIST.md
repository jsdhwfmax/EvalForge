# Release checklist

EvalForge releases should leave public, reproducible evidence that the tagged source is usable.

1. Confirm the changelog, package version, `evalforge.__version__`, README Action tag, and `CITATION.cff` agree.
2. Run `make lint`, `make test`, `make gate-demo`, and `make release-check` from a clean checkout.
3. Install the built wheel in a fresh environment and run the committed quality-gate example.
4. Confirm main-branch CI, CodeQL, and all dependency update checks are green.
5. Before the first PyPI release, create a protected GitHub environment named `pypi` and configure a PyPI pending Trusted Publisher with owner `jsdhwfmax`, repository `EvalForge`, workflow `release.yml`, and environment `pypi`. Do not create an API token.
6. Confirm `https://pypi.org/pypi/evalforge-ci/json` still returns 404 before registering the pending publisher. Stop if another owner has claimed the distribution name.
7. Create a signed or GitHub-verified tag and publish release notes that state compatibility and known limitations.
8. Verify the release workflow attached the wheel, source distribution, and `SHA256SUMS` file and completed the `pypi-publish` job through OIDC.
9. Verify the exact release from an unauthenticated environment with `python -m pip install --no-cache-dir 'evalforge-ci==<version>'`, then run `evalforge --help` and the committed gate example.
10. Record only verifiable adoption, compatibility, and security evidence; never infer production use from stars alone.

The release CI must also parse the generated JSON, JUnit, and SARIF reports and install the built wheel in a fresh environment before a tag is published. The release workflow builds distributions once, stores them as a short-lived workflow artifact, and sends those same verified files to GitHub Releases and PyPI.

PyPI publication uses Trusted Publishing. Only the `pypi-publish` job receives `id-token: write`; no PyPI password or API token belongs in repository secrets. Do not claim that `evalforge-ci` is available from PyPI until the project page and published files are publicly verifiable.
