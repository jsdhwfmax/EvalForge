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


def test_run_artifact_supports_strict_comparison(client, tmp_path, monkeypatch):
    from evalforge.artifacts import load_artifact
    from evalforge.gates import ComparisonPolicy, GateCheck, GatePolicy, evaluate_gate
    from evalforge.reproducibility import METRIC_VERSION

    client.post("/api/v1/datasets/import", json=load_demo())
    client.post("/api/v1/configs", json={"id": "export", "name": "Export"})
    monkeypatch.setenv("GITHUB_SHA", "source-revision-under-test")
    path = tmp_path / "run.json"
    result = runner.invoke(app, ["run", "export", "--output", str(path)])
    assert result.exit_code == 0, result.output
    artifact = load_artifact(path)
    assert artifact.metadata["dataset_fingerprint"]
    assert artifact.metadata["metric_version"] == METRIC_VERSION
    assert artifact.metadata["config_snapshot"]["id"] == "export"
    assert artifact.run.source_revision == "source-revision-under-test"
    policy = GatePolicy(
        comparison=ComparisonPolicy(
            require_same_dataset=True, require_same_producer=True,
            require_same_metric_version=True,
        ),
        checks=[GateCheck(id="recall", metric="retrieval_recall_at_k", op="gte", value=0)],
    )
    assert evaluate_gate(policy, artifact, artifact).passed


def test_run_rejects_unknown_or_empty_selected_case(client, tmp_path):
    client.post("/api/v1/datasets/import", json=load_demo())
    client.post("/api/v1/configs", json={"id": "selection", "name": "Selection"})
    for case_id in ["does-not-exist", ""]:
        output = tmp_path / "run.json"
        result = runner.invoke(
            app, ["run", "selection", "--test-case-id", case_id, "--output", str(output)]
        )
        assert result.exit_code == 2, result.output
        assert not output.exists()
    assert client.get("/api/v1/experiments").json() == []


def test_run_rejects_empty_dataset(client):
    client.post("/api/v1/configs", json={"id": "empty", "name": "Empty"})
    result = runner.invoke(app, ["run", "empty"])
    assert result.exit_code == 2
    assert "No test cases" in result.output


def test_gate_experiment_rejects_unfinished_summary(client):
    from evalforge.database import session_scope
    from evalforge.models import Experiment

    experiment_id = _prepare_experiment(client)
    with session_scope() as db:
        experiment = db.get(Experiment, experiment_id)
        experiment.status = "failed"
        db.commit()
    result = runner.invoke(app, ["gate-experiment", experiment_id])
    assert result.exit_code == 2
    assert "must be completed" in result.output
