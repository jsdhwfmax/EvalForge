import copy
import json
import math
from pathlib import Path

import jsonschema
import pytest

from evalforge.adapters.deepeval import (
    SUPPORTED_VERSIONS,
    deepeval_artifact_from_export,
    load_deepeval_export,
)
from evalforge.gates import evaluate_gate, load_policy

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "deepeval"


def _payload(version="4.2.2"):
    return json.loads((FIXTURES / ("evaluation-result-%s.json" % version)).read_text())


def _convert(payload, version="4.2.2"):
    return deepeval_artifact_from_export(payload, producer_version=version)


@pytest.mark.parametrize("version", SUPPORTED_VERSIONS)
def test_official_model_serialization_becomes_private_schema_valid_artifact(version):
    artifact = load_deepeval_export(
        FIXTURES / ("evaluation-result-%s.json" % version),
        producer_version=version,
        source_revision="abc123",
        dataset_fingerprint="sha256:synthetic-example",
    )
    assert artifact.producer.name == "deepeval"
    assert artifact.producer.version == version
    assert artifact.run.id is None
    assert artifact.run.source_revision == "abc123"
    assert artifact.metrics["test_cases"].value == 3
    assert artifact.metrics["deepeval_pass_rate"].value == pytest.approx(2 / 3)
    assert artifact.metrics["deepeval_pass_rate"].direction == "higher"
    assert artifact.metrics["deepeval_answer_relevancy"].value == pytest.approx(2.3 / 3)
    assert artifact.metrics["deepeval_answer_relevancy"].unit == "ratio"
    legacy = version == "3.8.1"
    metric_name = "deepeval_v%s_hallucination" % ("3" if legacy else "4")
    assert artifact.metrics[metric_name].value == pytest.approx((1.1 if legacy else 1.9) / 3)
    assert artifact.metrics[metric_name].direction == ("lower" if legacy else "higher")
    assert set(artifact.metrics) == {
        "test_cases",
        "deepeval_pass_rate",
        "deepeval_answer_relevancy",
        metric_name,
    }
    assert artifact.metadata == {
        "adapter": "evalforge.deepeval",
        "adapter_mapping_version": "1",
        "source_format": "EvaluationResult.model_dump(mode=json,by_alias=False)",
        "source_schema_commit": SUPPORTED_VERSIONS[version],
        "dataset_fingerprint": "sha256:synthetic-example",
    }
    serialized = artifact.model_dump(mode="json", exclude_none=True, by_alias=True)
    jsonschema.validate(
        serialized,
        json.loads((ROOT / "schemas" / "evaluation-artifact-v1.schema.json").read_text()),
    )
    assert "must-not-leak" not in json.dumps(serialized)


@pytest.mark.parametrize("version", SUPPORTED_VERSIONS)
@pytest.mark.parametrize("name", ["Hallucination", "Bias", "Toxicity"])
def test_reversed_metric_semantics_are_versioned_and_not_inferred_from_success(version, name):
    payload = _payload(version)
    legacy = version == "3.8.1"
    for row in payload["test_results"]:
        row["success"] = True
        row["metrics_data"] = [
            {
                "name": name,
                "score": 0.2 if legacy else 0.8,
                "threshold": 0.5,
                "success": True,
                "error": None,
            }
        ]
    artifact = _convert(payload, version)
    target = "deepeval_v%s_%s" % ("3" if legacy else "4", name.lower())
    assert artifact.metrics[target].direction == ("lower" if legacy else "higher")
    payload["test_results"][0]["metrics_data"][0]["score"] = 0.8 if legacy else 0.2
    with pytest.raises(ValueError, match="inconsistent score/threshold"):
        _convert(payload, version)


@pytest.mark.parametrize(
    "name,target",
    [
        ("Answer Relevancy", "answer_relevancy"),
        ("Faithfulness", "faithfulness"),
        ("Contextual Precision", "contextual_precision"),
        ("Contextual Recall", "contextual_recall"),
        ("Contextual Relevancy", "contextual_relevancy"),
        ("Tool Correctness", "tool_correctness"),
        ("Task Completion", "task_completion"),
    ],
)
def test_builtin_name_allowlist_uses_explicit_namespaced_metrics(name, target):
    payload = _payload()
    for row in payload["test_results"]:
        row["success"] = True
        row["metrics_data"] = [
            {
                "name": name,
                "score": 0.8,
                "threshold": 0.5,
                "success": True,
            }
        ]
    artifact = _convert(payload)
    metric = artifact.metrics["deepeval_" + target]
    assert metric.value == pytest.approx(0.8)
    assert metric.direction == "higher"


def test_custom_names_only_export_test_count_and_explicit_verdicts():
    payload = _payload()
    for index, row in enumerate(payload["test_results"]):
        row["success"] = index != 1
        row["metrics_data"] = [
            {
                "name": "must-not-leak-arbitrary-name",
                "score": 70,
                "threshold": 50,
                "success": index != 1,
            }
        ]
    artifact = _convert(payload)
    assert set(artifact.metrics) == {"test_cases", "deepeval_pass_rate"}
    assert artifact.metrics["deepeval_pass_rate"].value == pytest.approx(2 / 3)
    assert "must-not-leak" not in artifact.model_dump_json()


def test_unknown_metadata_traces_aliases_and_direction_fields_are_never_copied():
    payload = _payload()
    payload["metadata"] = {"source_revision": "must-not-leak-untrusted-revision"}
    payload["test_results"][0]["trace"] = {"spans": ["must-not-leak-trace"]}
    payload["test_results"][0]["future_field"] = "must-not-leak-future-field"
    payload["test_results"][0]["metrics_data"][0]["direction"] = "lower"
    artifact = _convert(payload)
    assert "must-not-leak" not in artifact.model_dump_json()
    assert artifact.run.source_revision is None
    assert artifact.metrics["deepeval_answer_relevancy"].direction == "higher"
    assert "dataset_fingerprint" not in artifact.metadata


@pytest.mark.parametrize("version", ["", " ", None, True, 4, "3.8.0", "4.2.0", "4.2.3", "5.0.0"])
def test_unverified_producer_versions_are_rejected(version):
    with pytest.raises(ValueError, match="producer_version"):
        _convert(_payload(), version)


@pytest.mark.parametrize("payload", [None, [], {}, {"test_results": []}, {"testCases": [{}]}])
def test_wrong_export_shapes_are_rejected(payload):
    with pytest.raises(ValueError):
        _convert(payload)


@pytest.mark.parametrize("field", ["name", "success", "conversational", "metrics_data"])
def test_missing_required_test_result_fields_are_rejected(field):
    payload = _payload()
    del payload["test_results"][0][field]
    with pytest.raises(ValueError, match=field):
        _convert(payload)


@pytest.mark.parametrize("value", [None, [], {}, "must-not-leak-invalid-metrics"])
def test_empty_or_invalid_metric_suites_are_rejected(value):
    payload = _payload()
    payload["test_results"][0]["metrics_data"] = value
    with pytest.raises(ValueError, match="non-empty JSON array"):
        _convert(payload)


@pytest.mark.parametrize("field", ["score", "threshold"])
@pytest.mark.parametrize("value", [None, True, "0.9", math.nan, math.inf, -math.inf, 10**400])
@pytest.mark.parametrize("metric_index", [0, 2])
def test_invalid_scores_and_thresholds_reject_even_unknown_metrics(field, value, metric_index):
    payload = _payload()
    payload["test_results"][0]["metrics_data"][metric_index][field] = value
    with pytest.raises(ValueError, match="finite number") as exc:
        _convert(payload)
    assert "must-not-leak" not in str(exc.value)


@pytest.mark.parametrize("field", ["score", "threshold"])
@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_builtin_scores_and_thresholds_outside_unit_interval_are_rejected(field, value):
    payload = _payload()
    payload["test_results"][0]["metrics_data"][0][field] = value
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        _convert(payload)


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("error", "must-not-leak-error", "errored"),
        ("error", "", "errored"),
        ("flaky", True, "flaky"),
        ("flaky", "false", "boolean"),
        ("success", None, "boolean"),
        ("success", 1, "boolean"),
        ("name", "", "non-empty string"),
    ],
)
@pytest.mark.parametrize("metric_index", [0, 2])
def test_invalid_metrics_fail_closed_without_raw_error_details(field, value, match, metric_index):
    payload = _payload()
    payload["test_results"][0]["metrics_data"][metric_index][field] = value
    with pytest.raises(ValueError, match=match) as exc:
        _convert(payload)
    assert "must-not-leak" not in str(exc.value)


def test_partial_metric_coverage_cannot_raise_the_aggregate_by_dropping_a_failure():
    payload = _payload()
    del payload["test_results"][1]["metrics_data"][1]
    payload["test_results"][1]["success"] = True
    with pytest.raises(ValueError, match="same metric suite"):
        _convert(payload)


def test_duplicate_metrics_cannot_reweight_the_average():
    payload = _payload()
    metrics = payload["test_results"][0]["metrics_data"]
    metrics.append(copy.deepcopy(metrics[0]))
    with pytest.raises(ValueError, match="duplicate metric"):
        _convert(payload)


def test_test_success_must_match_every_metric_verdict():
    payload = _payload()
    payload["test_results"][1]["success"] = True
    with pytest.raises(ValueError, match="inconsistent test success"):
        _convert(payload)


def test_mixed_conversation_modes_are_rejected():
    payload = _payload()
    payload["test_results"][1]["conversational"] = True
    with pytest.raises(ValueError, match="one conversation mode"):
        _convert(payload)


@pytest.mark.parametrize(
    "content,match",
    [
        (b'{"test_results": [], "test_results": []}', "duplicate JSON"),
        (b'{"secret": NaN}', "non-standard numeric"),
        (b'{"secret": Infinity}', "non-standard numeric"),
        (b'{"secret": "must-not-leak",', "not valid UTF-8 JSON"),
        (b"\xff", "not valid UTF-8 JSON"),
    ],
)
def test_loader_rejects_ambiguous_or_invalid_json_without_content_leaks(tmp_path, content, match):
    path = tmp_path / "export.json"
    path.write_bytes(content)
    with pytest.raises(ValueError, match=match) as exc:
        load_deepeval_export(path, producer_version="4.2.2")
    assert "must-not-leak" not in str(exc.value)


def test_loader_read_errors_are_actionable(tmp_path):
    with pytest.raises(ValueError, match="Could not read DeepEval export"):
        load_deepeval_export(tmp_path / "missing.json", producer_version="4.2.2")


def test_example_policy_accepts_current_fixture_and_rejects_legacy_score_semantics():
    policy = load_policy(ROOT / "examples" / "deepeval_policy.json")
    assert evaluate_gate(policy, _convert(_payload())).passed
    legacy_report = evaluate_gate(policy, _convert(_payload("3.8.1"), "3.8.1"))
    assert not legacy_report.passed
    assert any(check.outcome == "error" for check in legacy_report.checks)
