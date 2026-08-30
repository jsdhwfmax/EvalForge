import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_third_party_actions_are_pinned_to_full_commit_shas():
    workflow_files = list((ROOT / ".github" / "workflows").glob("*.yml"))
    workflow_files.append(ROOT / "action.yml")
    uses_pattern = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)

    for path in workflow_files:
        for reference in uses_pattern.findall(path.read_text(encoding="utf-8")):
            assert re.search(r"@[0-9a-f]{40}$", reference), (
                "%s contains an unpinned Action reference: %s" % (path, reference)
            )


def test_pypi_oidc_permission_is_scoped_to_publish_job():
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert workflow.count("id-token: write") == 1
    publish_job = workflow.split("  pypi-publish:", 1)[1]
    assert "id-token: write" in publish_job
    assert "environment:\n      name: pypi" in publish_job
    assert "password:" not in workflow
    assert "PYPI_API_TOKEN" not in workflow


def test_codeql_uses_minimal_write_permission_and_pinned_release():
    workflow = (ROOT / ".github" / "workflows" / "codeql.yml").read_text(encoding="utf-8")

    assert workflow.count("security-events: write") == 1
    assert "contents: write" not in workflow
    assert workflow.count("cdf488f595d80d6e07e03d4674febd5ab45fa938") == 2


def test_dependabot_respects_python_39_tooling_caps():
    config = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")

    assert "dependency-name: mypy\n        update-types: [version-update:semver-major]" in config
    assert "dependency-name: twine\n        update-types: [version-update:semver-major]" in config
