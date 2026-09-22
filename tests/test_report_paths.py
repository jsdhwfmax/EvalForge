import json
import os

import pytest
from typer.testing import CliRunner

from evalforge.cli import app


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_gate_never_overwrites_input_with_report(tmp_path, alias):
    candidate = tmp_path / "candidate.json"
    original = '{"quality":0.9}\n'
    candidate.write_text(original)
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"checks": [
        {"id": "quality", "metric": "quality", "op": "gte", "value": 0.8}
    ]}))
    output = candidate
    if alias != "same":
        output = tmp_path / "alias.json"
        if alias == "symlink":
            output.symlink_to(candidate)
        else:
            os.link(candidate, output)
    result = CliRunner().invoke(app, [
        "gate", str(candidate), "--policy", str(policy), "--json", str(output)
    ])
    assert result.exit_code == 2
    assert "Report paths must be distinct" in result.output
    assert candidate.read_text() == original


def test_gate_rejects_report_collision_before_any_write(tmp_path):
    candidate = tmp_path / "candidate.json"
    candidate.write_text('{"quality":0.9}')
    output = tmp_path / "report"
    output.write_text("previous report")
    result = CliRunner().invoke(app, [
        "gate", str(candidate), "--policy", str(tmp_path / "unused.json"),
        "--json", str(output), "--junit", str(output),
    ])
    assert result.exit_code == 2
    assert "Report paths must be distinct" in result.output
    assert output.read_text() == "previous report"


def test_gate_rejects_directory_as_report(tmp_path):
    result = CliRunner().invoke(app, [
        "gate", "unused.json", "--policy", "unused-policy.json", "--json", str(tmp_path)
    ])
    assert result.exit_code == 2
    assert "Report output is a directory" in result.output


def test_gate_rejects_nested_report_paths_before_writing(tmp_path):
    output = tmp_path / "new-report"
    result = CliRunner().invoke(app, [
        "gate", "unused.json", "--policy", "unused-policy.json",
        "--json", str(output), "--junit", str(output / "junit.xml"),
    ])
    assert result.exit_code == 2
    assert "Report paths must be distinct" in result.output
    assert not output.exists()
