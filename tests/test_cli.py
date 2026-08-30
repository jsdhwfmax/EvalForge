import json
from xml.etree import ElementTree

from test_api import load_demo
from typer.testing import CliRunner

from evalforge.cli import app

runner = CliRunner()


def _prepare_experiment(client):
    client.post("/api/v1/datasets/import", json=load_demo())
    client.post(
        "/api/v1/configs",
        json={"id": "candidate", "name": "Candidate", "retrieval_method": "hybrid", "top_k": 3},
    )
    response = client.post(
        "/api/v1/experiments/run",
        json={"name": "CLI test", "config_ids": ["candidate"], "include_security": True},
    )
    return response.json()["experiments"][0]["id"]


def test_check_command_writes_ci_reports(client, tmp_path):
    client.post("/api/v1/datasets/import", json=load_demo())
    client.post(
        "/api/v1/configs",
        json={"id": "candidate", "name": "Candidate", "retrieval_method": "hybrid", "top_k": 3},
    )
    result = runner.invoke(
        app,
        ["check", "candidate", "--name", "Test gate", "--report-dir", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    report = json.loads((tmp_path / "evalforge-report.json").read_text())
    artifact = json.loads((tmp_path / "evaluation-artifact.json").read_text())
    assert report["passed"] is True
    assert artifact["metadata"]["dataset_fingerprint"]
    junit = ElementTree.parse(tmp_path / "evalforge-junit.xml").getroot()
    sarif = json.loads((tmp_path / "evalforge.sarif").read_text())
    assert junit.tag == "testsuite"
    assert sarif["version"] == "2.1.0"


def test_gate_command_returns_nonzero_for_regression(client):
    experiment_id = _prepare_experiment(client)
    result = runner.invoke(
        app,
        ["gate-experiment", experiment_id, "--min-correctness", "0.99"],
    )
    assert result.exit_code == 1
    assert '"passed": false' in result.output
