import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from evalforge.cli import app

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("adapter,fixture,options", [
    ("promptfoo", "promptfoo/results-v3.json", []),
    ("ragas", "ragas/evaluation-result-records.json", [
        "--producer-version", "0.2.12", "--metric", "faithfulness"
    ]),
    ("deepeval", "deepeval/evaluation-result-4.2.2.json", ["--producer-version", "4.2.2"]),
])
def test_import_cli_retains_explicit_identity_and_rejects_blank_metric_version(
    tmp_path, adapter, fixture, options
):
    output = tmp_path / "artifact.json"
    args = ["import", adapter, str(ROOT / "tests/fixtures" / fixture), *options,
            "--output", str(output), "--source-revision", "revision-1",
            "--dataset-fingerprint", "dataset-1", "--metric-version", "rubric-1"]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text())
    assert payload["run"]["source_revision"] == "revision-1"
    assert payload["metadata"]["dataset_fingerprint"] == "dataset-1"
    assert payload["metadata"]["metric_version"] == "rubric-1"
    args[-1] = " "
    output.unlink()
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 2
    assert not output.exists()


@pytest.mark.parametrize("adapter,options", [
    ("ragas", ["--producer-version", "0.2.12", "--metric", "faithfulness"]),
    ("deepeval", ["--producer-version", "4.2.2"]),
])
def test_invalid_import_has_exit_two_and_no_output(tmp_path, adapter, options):
    source, output = tmp_path / "invalid.json", tmp_path / "artifact.json"
    source.write_text('{}')
    result = CliRunner().invoke(app, [
        "import", adapter, str(source), *options, "--output", str(output)
    ])
    assert result.exit_code == 2
    assert not output.exists()
