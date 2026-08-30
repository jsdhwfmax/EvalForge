import json

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
    report = json.loads((tmp_path / "evaluation.json").read_text())
    assert report["quality_gate"]["passed"] is True
    assert report["summary"]["dataset_fingerprint"]
    assert (tmp_path / "quality-gate.xml").exists()


def test_gate_command_returns_nonzero_for_regression(client):
    experiment_id = _prepare_experiment(client)
    result = runner.invoke(
        app,
        ["gate", experiment_id, "--min-correctness", "0.99"],
    )
    assert result.exit_code == 1
    assert '"passed": false' in result.output
