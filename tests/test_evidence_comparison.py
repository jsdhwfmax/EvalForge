import json
from xml.etree import ElementTree

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from evalforge.artifacts import MetricValue, artifact_from_summary, load_artifact, write_artifact
from evalforge.cli import app
from evalforge.gates import (
    ComparisonPolicy,
    GateCheck,
    GatePolicy,
    evaluate_gate,
    render_junit,
    render_markdown,
    render_sarif,
)


def artifact(score=0.9, **metadata):
    return artifact_from_summary(
        {"quality": score}, source_revision="abc123",
        metadata={"dataset_fingerprint": "golden-v1", "metric_version": "judge-v1", **metadata},
    )


def policy(**comparison):
    return GatePolicy(
        checks=[GateCheck(id="regression", metric="quality", op="delta_gte", value=-0.05)],
        comparison=ComparisonPolicy(**comparison),
    )


@pytest.mark.parametrize("key,field", [
    ("require_same_dataset", "dataset_fingerprint"),
    ("require_same_metric_version", "metric_version"),
])
@pytest.mark.parametrize("value", ["different", None, "", " ", 1, [], {}])
def test_identity_mismatch_blocks_even_when_candidate_score_is_higher(key, field, value):
    report = evaluate_gate(policy(**{key: True}), artifact(1.0, **{field: value}), artifact())
    assert not report.passed
    assert report.checks[0].outcome == "error"
    assert field in report.checks[0].message


def test_matching_identities_pass_and_legacy_policy_is_unchanged():
    strict = policy(
        require_same_dataset=True, require_same_producer=True, require_same_metric_version=True
    )
    assert evaluate_gate(strict, artifact(), artifact()).passed
    assert evaluate_gate(policy(), artifact(dataset_fingerprint="changed"), artifact()).passed


def test_strict_context_applies_without_delta_checks_and_cannot_be_advisory():
    strict = policy(require_same_dataset=True)
    strict.checks[0] = GateCheck(
        id="quality", metric="quality", op="gte", value=0.5, severity="warning"
    )
    report = evaluate_gate(strict, artifact())
    assert not report.passed
    assert "requires a baseline" in report.checks[0].message


@pytest.mark.parametrize("producer_name,producer_version", [
    ("other", "0.4.0"), ("evalforge", "unknown"), ("evalforge", "different")
])
def test_producer_identity_must_match_with_known_version(producer_name, producer_version):
    candidate = artifact_from_summary(
        {"quality": 1}, producer_name=producer_name, producer_version=producer_version
    )
    report = evaluate_gate(policy(require_same_producer=True), candidate, artifact())
    assert not report.passed
    assert "producer" in report.checks[0].message


def test_blank_producer_identity_cannot_pass_strict_comparison():
    candidate = artifact_from_summary({"quality": 1}, producer_name=" ", producer_version=" ")
    report = evaluate_gate(policy(require_same_producer=True), candidate, candidate)
    assert not report.passed


@pytest.mark.parametrize("candidate,baseline", [(1e308, -1e308), (-1e308, 1e308)])
def test_delta_overflow_fails_closed_and_reports_remain_serializable(candidate, baseline):
    advisory = policy()
    advisory.checks[0].severity = "warning"
    report = evaluate_gate(advisory, artifact(candidate), artifact(baseline))
    assert not report.passed
    assert report.checks[0].outcome == "error"
    assert report.checks[0].observed is None
    assert "not finite" in report.checks[0].message
    assert json.dumps(report.model_dump(), allow_nan=False)


def test_api_summary_preserves_comparison_identity(tmp_path):
    path = tmp_path / "summary.json"
    path.write_text(json.dumps({"summary": {
        "quality": 0.9, "dataset_fingerprint": "v1", "metric_version": "m1",
        "answer": "private response"
    }}))
    loaded = load_artifact(path)
    assert loaded.metadata == {"dataset_fingerprint": "v1", "metric_version": "m1"}
    assert list(loaded.metrics) == ["quality"]


@pytest.mark.parametrize("value", [True, False, "0.9", None])
def test_canonical_numbers_reject_schema_incompatible_coercion(value):
    with pytest.raises(ValidationError):
        MetricValue(value=value)
    with pytest.raises(ValidationError):
        GateCheck(id="bad", metric="quality", op="gte", value=value)


def test_nonportable_metadata_rejected():
    with pytest.raises(ValueError, match="portable JSON"):
        artifact(secret=float("nan"))


def test_evidence_digests_are_deterministic_and_sensitive_to_input():
    candidate = artifact()
    first = evaluate_gate(policy(), candidate, artifact()).evidence
    assert first == evaluate_gate(policy(), candidate, artifact()).evidence
    reordered = candidate.model_copy(update={"metadata": dict(reversed(
        list(candidate.metadata.items())
    ))})
    assert first == evaluate_gate(policy(), reordered, artifact()).evidence
    changed = evaluate_gate(policy(), artifact(0.8), artifact()).evidence
    assert first["candidate"]["sha256"] != changed["candidate"]["sha256"]
    assert first["policy_sha256"] == changed["policy_sha256"]
    modified_policy = policy()
    modified_policy.checks[0].value = -0.1
    assert first["policy_sha256"] != evaluate_gate(
        modified_policy, candidate, artifact()
    ).evidence["policy_sha256"]
    assert first["candidate"]["run"]["source_revision"] == "abc123"


def test_all_reports_carry_same_evidence_and_markdown_escapes_untrusted_text():
    strict = policy(require_same_dataset=True)
    strict.name = "evil | table\n<script>alert(1)</script> [link](https://example.test)"
    report = evaluate_gate(strict, artifact(dataset_fingerprint="v2"), artifact())
    markdown = render_markdown(report)
    assert "EvalForge gate: FAIL" in markdown
    assert "ERROR" in markdown and "does not match" in markdown
    assert "<script>" not in markdown
    assert "evil &#124; table" in markdown
    assert "\\[link\\]" in markdown
    assert report.evidence["candidate"]["sha256"] in markdown
    junit = ElementTree.fromstring(render_junit(report))
    evidence = junit.find("./properties/property[@name='evalforge.evidence']")
    assert json.loads(evidence.attrib["value"]) == report.evidence
    sarif = json.loads(render_sarif(report))
    assert sarif["runs"][0]["properties"]["evalforgeEvidence"] == report.evidence


def test_malformed_identity_does_not_copy_raw_objects_to_reports():
    candidate = artifact(dataset_fingerprint={"raw_document": "PRIVATE-SENTINEL"})
    report = evaluate_gate(policy(require_same_dataset=True), candidate, artifact())
    assert not report.passed
    assert "PRIVATE-SENTINEL" not in report.model_dump_json()
    assert "PRIVATE-SENTINEL" not in render_junit(report)
    assert report.evidence["candidate"]["dataset_fingerprint"] is None


def test_cli_writes_failure_summary_and_json_evidence(tmp_path):
    candidate, baseline, policy_path = (tmp_path / p for p in ("c.json", "b.json", "p.json"))
    write_artifact(candidate, artifact(dataset_fingerprint="changed"))
    write_artifact(baseline, artifact())
    policy_path.write_text(policy(require_same_dataset=True).model_dump_json())
    markdown, report_path = tmp_path / "summary.md", tmp_path / "report.json"
    result = CliRunner().invoke(app, [
        "gate", str(candidate), "--baseline", str(baseline), "--policy", str(policy_path),
        "--markdown", str(markdown), "--json", str(report_path),
    ])
    assert result.exit_code == 1
    assert "does not match" in markdown.read_text()
    assert json.loads(report_path.read_text())["evidence"]["candidate"]["sha256"]
