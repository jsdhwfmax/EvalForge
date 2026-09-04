import json
import math
from pathlib import Path
from xml.etree import ElementTree

import jsonschema
import pytest
from typer.testing import CliRunner

from evalforge.artifacts import artifact_from_summary, load_artifact, write_artifact
from evalforge.cli import app
from evalforge.gates import (
    GateCheck,
    GatePolicy,
    evaluate_gate,
    load_policy,
    render_json,
    render_junit,
    render_sarif,
)

ROOT = Path(__file__).resolve().parents[1]


def test_committed_examples_match_normative_json_schemas():
    artifact_schema = json.loads(
        (ROOT / "schemas" / "evaluation-artifact-v1.schema.json").read_text(encoding="utf-8")
    )
    policy_schema = json.loads(
        (ROOT / "schemas" / "gate-policy-v1.schema.json").read_text(encoding="utf-8")
    )
    for name in ["baseline_summary.json", "candidate_summary.json"]:
        payload = json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))
        jsonschema.validate(payload, artifact_schema)
    for name in ["quality_policy.json", "promptfoo_policy.json"]:
        policy = json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))
        jsonschema.validate(policy, policy_schema)


def test_flat_summary_becomes_portable_artifact(tmp_path):
    path = tmp_path / "summary.json"
    path.write_text(
        json.dumps({"answer_correctness": 0.8, "latency_ms": 12, "note": "ignored"}),
        encoding="utf-8",
    )
    artifact = load_artifact(path)
    assert artifact.producer.name == "external"
    assert artifact.metrics["answer_correctness"].direction == "higher"
    assert artifact.metrics["latency_ms"].unit == "ms"
    assert "note" not in artifact.metrics


def test_artifact_round_trip_uses_schema_alias(tmp_path):
    artifact = artifact_from_summary(
        {"citation_support": 1.0}, run_id="run-1", source_revision="abc123"
    )
    artifact.schema_uri = "https://example.test/evalforge.schema.json"
    path = tmp_path / "artifact.json"
    write_artifact(path, artifact)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["$schema"].startswith("https://")
    assert "schema_uri" not in payload
    assert load_artifact(path) == artifact


def test_demo_policy_passes_with_a_visible_warning():
    policy = load_policy(ROOT / "examples" / "quality_policy.json")
    candidate = load_artifact(ROOT / "examples" / "candidate_summary.json")
    baseline = load_artifact(ROOT / "examples" / "baseline_summary.json")
    report = evaluate_gate(policy, candidate, baseline)
    assert report.passed is True
    assert [result.outcome for result in report.checks].count("warn") == 1
    assert json.loads(render_json(report))["passed"] is True

    junit = ElementTree.fromstring(render_junit(report))
    assert junit.attrib == {
        "name": "evalforge",
        "tests": "5",
        "failures": "0",
        "errors": "0",
        "skipped": "0",
    }
    sarif = json.loads(render_sarif(report))
    assert sarif["version"] == "2.1.0"
    assert sarif["runs"][0]["results"][0]["level"] == "warning"


def test_missing_metric_and_baseline_are_gate_errors():
    candidate = artifact_from_summary({"answer_correctness": 0.8})
    missing_metric = GatePolicy(
        checks=[GateCheck(id="missing", metric="faithfulness", op="gte", value=0.9)]
    )
    report = evaluate_gate(missing_metric, candidate)
    assert report.passed is False
    assert report.checks[0].outcome == "error"

    needs_baseline = GatePolicy(
        checks=[
            GateCheck(
                id="regression", metric="answer_correctness", op="delta_gte", value=-0.01
            )
        ]
    )
    report = evaluate_gate(needs_baseline, candidate)
    assert report.passed is False
    assert "Baseline artifact is required" in report.checks[0].message


def test_non_finite_evidence_and_thresholds_are_rejected(tmp_path):
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps({"answer_correctness": math.nan}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="finite number"):
        load_artifact(artifact_path)

    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "version": 1,
                "checks": [
                    {
                        "id": "quality",
                        "metric": "answer_correctness",
                        "op": "gte",
                        "value": math.inf,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="finite number"):
        load_policy(policy_path)


def test_duplicate_check_ids_are_rejected():
    with pytest.raises(ValueError, match="Gate check IDs must be unique: quality"):
        GatePolicy(
            checks=[
                GateCheck(id="quality", metric="answer_correctness", op="gte", value=0.8),
                GateCheck(id="quality", metric="faithfulness", op="gte", value=0.8),
            ]
        )


@pytest.mark.parametrize(
    ("candidate_kwargs", "baseline_kwargs", "message"),
    [
        ({"unit": "ms"}, {"unit": "seconds"}, "Metric units do not match"),
        (
            {"direction": "lower"},
            {"direction": "higher"},
            "Metric directions do not match",
        ),
    ],
)
def test_delta_checks_reject_incompatible_metric_metadata(
    candidate_kwargs, baseline_kwargs, message
):
    candidate = artifact_from_summary({"latency_ms": 100})
    baseline = artifact_from_summary({"latency_ms": 110})
    candidate.metrics["latency_ms"] = candidate.metrics["latency_ms"].model_copy(
        update=candidate_kwargs
    )
    baseline.metrics["latency_ms"] = baseline.metrics["latency_ms"].model_copy(
        update=baseline_kwargs
    )
    policy = GatePolicy(
        checks=[GateCheck(id="latency", metric="latency_ms", op="delta_lte", value=0)]
    )

    report = evaluate_gate(policy, candidate, baseline)

    assert report.passed is False
    assert report.checks[0].outcome == "error"
    assert message in report.checks[0].message


def test_cli_writes_reports_and_uses_failure_exit_code(tmp_path):
    candidate = tmp_path / "candidate.json"
    policy = tmp_path / "policy.json"
    candidate.write_text(json.dumps({"answer_correctness": 0.5}), encoding="utf-8")
    policy.write_text(
        json.dumps(
            {
                "version": 1,
                "checks": [
                    {
                        "id": "quality",
                        "metric": "answer_correctness",
                        "op": "gte",
                        "value": 0.8,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    report_json = tmp_path / "report.json"
    junit = tmp_path / "report.xml"
    sarif = tmp_path / "report.sarif"
    result = CliRunner().invoke(
        app,
        [
            "gate",
            str(candidate),
            "--policy",
            str(policy),
            "--json",
            str(report_json),
            "--junit",
            str(junit),
            "--sarif",
            str(sarif),
        ],
    )
    assert result.exit_code == 1
    assert "[FAIL] quality" in result.stdout
    assert json.loads(report_json.read_text(encoding="utf-8"))["passed"] is False
    assert ElementTree.parse(junit).getroot().attrib["failures"] == "1"
    assert json.loads(sarif.read_text(encoding="utf-8"))["runs"][0]["results"]


def test_rag_command_explains_optional_extra(monkeypatch):
    monkeypatch.setattr("evalforge.cli.find_spec", lambda _name: None)
    result = CliRunner().invoke(app, ["init"])
    assert result.exit_code == 2
    assert "evalforge-ci[rag]" in result.output
