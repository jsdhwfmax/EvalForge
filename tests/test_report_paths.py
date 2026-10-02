import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from evalforge.cli import app

ROOT = Path(__file__).resolve().parents[1]
IMPORT_CASES = [
    ("promptfoo", "promptfoo/results-v3.json", []),
    (
        "ragas", "ragas/evaluation-result-records.json",
        ["--producer-version", "0.2.12", "--metric", "faithfulness"],
    ),
    (
        "deepeval", "deepeval/evaluation-result-4.2.2.json",
        ["--producer-version", "4.2.2"],
    ),
]


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


@pytest.mark.parametrize("adapter,fixture,options", IMPORT_CASES)
@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
@pytest.mark.parametrize("valid_source", [True, False])
def test_import_preserves_source_and_checks_alias_before_reading(
    tmp_path, adapter, fixture, options, alias, valid_source,
):
    source = tmp_path / "source.json"
    original = (
        (ROOT / "tests" / "fixtures" / fixture).read_bytes()
        if valid_source else b"This is not a valid evaluator export.\n"
    )
    source.write_bytes(original)
    output = source
    if alias != "same":
        output = tmp_path / "output.json"
        if alias == "symlink":
            output.symlink_to(source)
        else:
            os.link(source, output)

    result = CliRunner().invoke(app, [
        "import", adapter, str(source), "--output", str(output), *options,
    ])

    assert result.exit_code == 2
    assert "Report paths must be distinct" in result.output
    assert source.read_bytes() == original
    assert output.read_bytes() == original


@pytest.mark.parametrize("adapter,fixture,options", IMPORT_CASES)
def test_import_to_distinct_output_preserves_source(tmp_path, adapter, fixture, options):
    source = tmp_path / "source.json"
    original = (ROOT / "tests" / "fixtures" / fixture).read_bytes()
    source.write_bytes(original)
    output = tmp_path / "artifacts" / "imported.json"

    result = CliRunner().invoke(app, [
        "import", adapter, str(source), "--output", str(output), *options,
    ])

    assert result.exit_code == 0, result.output
    assert source.read_bytes() == original
    assert json.loads(output.read_text())["producer"]["name"] == adapter


@pytest.mark.parametrize("invalid_input", ["candidate", "baseline", "policy"])
@pytest.mark.parametrize("failure", ["invalid_json", "missing_file"])
def test_invalid_gate_rerun_removes_previous_reports(tmp_path, invalid_input, failure):
    inputs = {name: tmp_path / (name + ".json") for name in ("candidate", "baseline", "policy")}
    inputs["candidate"].write_text('{"quality":0.9}')
    inputs["baseline"].write_text('{"quality":0.8}')
    inputs["policy"].write_text(json.dumps({"checks": [
        {"id": "quality", "metric": "quality", "op": "gte", "value": 0.8},
    ]}))
    reports = {format_: tmp_path / ("report." + format_) for format_ in (
        "json", "junit", "sarif", "markdown",
    )}
    unselected = tmp_path / "other-report.json"
    unselected.write_text("an unrelated report")
    args = [
        "gate", str(inputs["candidate"]), "--baseline", str(inputs["baseline"]),
        "--policy", str(inputs["policy"]),
    ]
    for format_, path in reports.items():
        args.extend(["--" + format_, str(path)])
    first = CliRunner().invoke(app, args)
    assert first.exit_code == 0, first.output
    assert json.loads(reports["json"].read_text())["passed"] is True
    assert all(path.is_file() for path in reports.values())

    if failure == "invalid_json":
        inputs[invalid_input].write_text("invalid JSON")
    else:
        inputs[invalid_input].unlink()
    second = CliRunner().invoke(app, args)

    assert second.exit_code == 2, second.output
    assert not any(path.exists() for path in reports.values())
    assert unselected.read_text() == "an unrelated report"


def test_gate_path_conflict_preserves_inputs_and_other_existing_reports(tmp_path):
    candidate = tmp_path / "candidate.json"
    candidate.write_text('{"quality":0.9}')
    previous = tmp_path / "report.json"
    previous.write_text("previous report")

    result = CliRunner().invoke(app, [
        "gate", str(candidate), "--policy", "unused-policy.json",
        "--json", str(previous), "--junit", str(candidate),
    ])

    assert result.exit_code == 2
    assert "Report paths must be distinct" in result.output
    assert candidate.read_text() == '{"quality":0.9}'
    assert previous.read_text() == "previous report"
