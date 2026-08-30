import re
from pathlib import Path

from evalforge import __version__

ROOT = Path(__file__).resolve().parents[1]


def _required_match(path, pattern):
    match = re.search(pattern, path.read_text(encoding="utf-8"), flags=re.MULTILINE | re.DOTALL)
    assert match is not None, "Missing release metadata in %s" % path
    return match.group(1)


def test_release_versions_and_dates_agree():
    project_version = _required_match(
        ROOT / "pyproject.toml", r"^\[project\]\s+.*?^version = \"([^\"]+)\""
    )
    citation_version = _required_match(ROOT / "CITATION.cff", r"^version:\s*([^\s]+)$")
    action_version = _required_match(
        ROOT / "README.md", r"uses:\s+jsdhwfmax/EvalForge@v([0-9]+\.[0-9]+\.[0-9]+)"
    )
    changelog_date = _required_match(
        ROOT / "CHANGELOG.md", r"^## \[%s\] - ([0-9]{4}-[0-9]{2}-[0-9]{2})$" % __version__
    )
    citation_date = _required_match(
        ROOT / "CITATION.cff", r"^date-released:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})$"
    )

    assert {project_version, citation_version, action_version, __version__} == {__version__}
    assert citation_date == changelog_date
