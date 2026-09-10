"""Exercise the actual composite Action shell, including a stale-summary failure."""

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("status,write_summary", [(0, True), (1, True), (2, False), (1, False)])
def test_action_keeps_status_and_never_appends_old_summary(tmp_path, status, write_summary):
    mock = tmp_path / "evalforge"
    mock.write_text(
        '#!/bin/bash\n'
        'while [[ "$#" -gt 0 ]]; do\n'
        '  if [[ "$1" == "--markdown" ]]; then\n'
        '    shift\n'
        + ('    echo "CURRENT GATE" > "$1"\n' if write_summary else '    :\n')
        + '  fi\n  shift\ndone\nexit %s\n' % status
    )
    mock.chmod(0o755)
    markdown = tmp_path / "old summary.md"
    markdown.write_text("OLD PASS SUMMARY\n")
    summary = tmp_path / "job-summary"
    summary.touch()
    output = tmp_path / "job-output"
    script = textwrap.dedent((ROOT / "action.yml").read_text().rsplit("run: |", 1)[1])
    env = {
        **os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
        "EVALFORGE_CANDIDATE": "candidate with spaces.json", "EVALFORGE_BASELINE": "",
        "EVALFORGE_POLICY": "policy.json", "EVALFORGE_JSON": "report.json",
        "EVALFORGE_JUNIT": "report.xml", "EVALFORGE_SARIF": "report.sarif",
        "EVALFORGE_MARKDOWN": str(markdown), "EVALFORGE_JOB_SUMMARY": "true",
        "GITHUB_OUTPUT": str(output), "GITHUB_STEP_SUMMARY": str(summary),
    }
    result = subprocess.run(["bash", "-eo", "pipefail", "-c", script], env=env, cwd=tmp_path)
    assert result.returncode == status
    assert output.read_text() == "exit-code=%s\n" % status
    assert "OLD PASS SUMMARY" not in summary.read_text()
    assert ("CURRENT GATE" in summary.read_text()) == write_summary
