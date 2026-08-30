# Release checklist

EvalForge releases should leave public, reproducible evidence that the tagged source is usable.

1. Confirm the changelog, package version, `evalforge.__version__`, README Action tag, and `CITATION.cff` agree.
2. Run `make lint`, `make test`, `make gate-demo`, and `make release-check` from a clean checkout.
3. Install the built wheel in a fresh environment and run the committed quality-gate example.
4. Confirm main-branch CI and all dependency update checks are green.
5. Create a signed or GitHub-verified tag and publish release notes that state compatibility and known limitations.
6. Verify the release workflow attached the wheel, source distribution, and `SHA256SUMS` file.
7. Record only verifiable adoption, compatibility, and security evidence; never infer production use from stars alone.

The release CI must also parse the generated JSON, JUnit, and SARIF reports and install the built wheel in a fresh environment before a tag is published.

PyPI publication is a separate step. Do not claim that `evalforge-ci` is available from PyPI until the project page and published files are publicly verifiable.
