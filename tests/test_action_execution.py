"""Run the composite Action shell with real inputs and isolated report destinations."""

import json
import os
import shlex
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPORT_KEYS = ("EVALFORGE_JSON", "EVALFORGE_JUNIT", "EVALFORGE_SARIF", "EVALFORGE_MARKDOWN")


def action_environment(tmp_path):
    candidate = tmp_path / "candidate with spaces.json"
    baseline = tmp_path / "baseline.json"
    policy = tmp_path / "policy.json"
    candidate.write_text(json.dumps({"quality": 0.9}))
    baseline.write_text(json.dumps({"quality": 0.8}))
    policy.write_text(json.dumps({"version": 1, "checks": [{
        "id": "quality", "metric": "quality", "op": "delta_gte", "value": -0.05,
    }]}))
    summary = tmp_path / "job-summary"
    output = tmp_path / "job-output"
    summary.touch()
    output.touch()
    executable = tmp_path / "evalforge"
    executable.write_text(
        "#!/bin/bash\nexec %s -m evalforge.cli \"$@\"\n" % shlex.quote(sys.executable)
    )
    executable.chmod(0o755)
    return {
        **os.environ,
        "PATH": os.pathsep.join((
            str(tmp_path), str(Path(sys.executable).parent), os.environ["PATH"],
        )),
        "EVALFORGE_CANDIDATE": str(candidate), "EVALFORGE_BASELINE": str(baseline),
        "EVALFORGE_POLICY": str(policy), "EVALFORGE_JSON": str(tmp_path / "report.json"),
        "EVALFORGE_JUNIT": str(tmp_path / "report.xml"),
        "EVALFORGE_SARIF": str(tmp_path / "report.sarif"),
        "EVALFORGE_MARKDOWN": str(tmp_path / "reports with spaces" / "summary.md"),
        "EVALFORGE_JOB_SUMMARY": "true", "GITHUB_OUTPUT": str(output),
        "GITHUB_STEP_SUMMARY": str(summary),
    }


def run_action(tmp_path, env):
    script = textwrap.dedent((ROOT / "action.yml").read_text().rsplit("run: |", 1)[1])
    return subprocess.run(
        ["bash", "-eo", "pipefail", "-c", script], env=env, cwd=tmp_path,
        capture_output=True, text=True,
    )


@pytest.mark.parametrize("second_result", ["invalid", "blocked"])
def test_real_action_replaces_or_removes_all_reports_after_a_previous_pass(tmp_path, second_result):
    env = action_environment(tmp_path)
    first = run_action(tmp_path, env)
    assert first.returncode == 0, first.stderr
    assert json.loads(Path(env["EVALFORGE_JSON"]).read_text())["passed"]
    assert all(Path(env[key]).is_file() for key in REPORT_KEYS)
    Path(env["GITHUB_STEP_SUMMARY"]).write_text("")
    Path(env["GITHUB_OUTPUT"]).write_text("")
    candidate = Path(env["EVALFORGE_CANDIDATE"])
    candidate.write_text("{broken" if second_result == "invalid" else '{"quality":0.1}')

    result = run_action(tmp_path, env)
    expected = 2 if second_result == "invalid" else 1
    assert result.returncode == expected, result.stderr
    assert Path(env["GITHUB_OUTPUT"]).read_text() == "exit-code=%s\n" % expected
    if second_result == "invalid":
        assert all(not Path(env[key]).exists() for key in REPORT_KEYS)
        assert Path(env["GITHUB_STEP_SUMMARY"]).read_text() == ""
    else:
        assert all(Path(env[key]).is_file() for key in REPORT_KEYS)
        assert not json.loads(Path(env["EVALFORGE_JSON"]).read_text())["passed"]
        assert "EvalForge gate: FAIL" in Path(env["GITHUB_STEP_SUMMARY"]).read_text()


@pytest.mark.parametrize("status,report_flags", [
    (0, ["--json", "--junit", "--sarif", "--markdown"]),
    (1, ["--json", "--junit", "--sarif", "--markdown"]),
    (2, []),
    (1, []),
    (1, ["--json"]),
])
def test_action_keeps_status_and_never_publishes_stale_or_partial_reports(
    tmp_path, status, report_flags
):
    env = action_environment(tmp_path)
    mock = tmp_path / "evalforge"
    cases = "|".join(report_flags) or "--never"
    mock.write_text(
        '#!/bin/bash\nwhile [[ "$#" -gt 0 ]]; do\n'
        '  case "$1" in\n    %s) shift; echo "CURRENT GATE" > "$1";;\n' % cases
        + '  esac\n  shift\ndone\nexit %s\n' % status
    )
    mock.chmod(0o755)
    for key in REPORT_KEYS:
        path = Path(env[key])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("OLD PASS REPORT\n")

    result = run_action(tmp_path, env)
    assert result.returncode == status, result.stderr
    assert Path(env["GITHUB_OUTPUT"]).read_text() == "exit-code=%s\n" % status
    complete = len(report_flags) == 4
    assert ("CURRENT GATE" in Path(env["GITHUB_STEP_SUMMARY"]).read_text()) == complete
    for key in REPORT_KEYS:
        path = Path(env[key])
        assert path.exists() == complete
        if complete:
            assert path.read_text() == "CURRENT GATE\n"


@pytest.mark.parametrize("input_key", [
    "EVALFORGE_CANDIDATE", "EVALFORGE_BASELINE", "EVALFORGE_POLICY",
])
@pytest.mark.parametrize("alias", ["direct", "symlink", "hardlink"])
def test_action_rejects_input_output_aliases_before_clearing_any_files(tmp_path, input_key, alias):
    env = action_environment(tmp_path)
    source = Path(env[input_key])
    original = source.read_bytes()
    destination = tmp_path / "output-alias.json"
    if alias == "direct":
        destination = source
    elif alias == "symlink":
        destination.symlink_to(source)
    else:
        os.link(source, destination)
    env["EVALFORGE_SARIF"] = str(destination)
    old_report = Path(env["EVALFORGE_JSON"])
    old_report.write_text("KEEP UNTIL ALL PATHS ARE VALID")

    result = run_action(tmp_path, env)
    assert result.returncode == 2, result.stderr
    assert "overlaps a protected input" in result.stderr
    assert source.read_bytes() == original
    assert destination.read_bytes() == original
    assert old_report.read_text() == "KEEP UNTIL ALL PATHS ARE VALID"
    assert Path(env["GITHUB_OUTPUT"]).read_text() == "exit-code=2\n"


@pytest.mark.parametrize("collision", ["directory", "duplicate", "nested"])
def test_action_rejects_invalid_report_layout_before_cleanup(tmp_path, collision):
    env = action_environment(tmp_path)
    old_report = Path(env["EVALFORGE_JSON"])
    old_report.write_text("KEEP OLD FILE")
    if collision == "directory":
        env["EVALFORGE_MARKDOWN"] = str(tmp_path)
    elif collision == "duplicate":
        env["EVALFORGE_MARKDOWN"] = env["EVALFORGE_JSON"]
    else:
        env["EVALFORGE_JUNIT"] = str(tmp_path / "new-path")
        env["EVALFORGE_MARKDOWN"] = str(tmp_path / "new-path" / "summary.md")

    result = run_action(tmp_path, env)
    assert result.returncode == 2, result.stderr
    assert old_report.read_text() == "KEEP OLD FILE"
    assert Path(env["EVALFORGE_CANDIDATE"]).exists()


def test_action_can_disable_job_summary_without_losing_reports(tmp_path):
    env = action_environment(tmp_path)
    env["EVALFORGE_JOB_SUMMARY"] = "false"
    result = run_action(tmp_path, env)
    assert result.returncode == 0, result.stderr
    assert all(Path(env[key]).is_file() for key in REPORT_KEYS)
    assert Path(env["GITHUB_STEP_SUMMARY"]).read_text() == ""
