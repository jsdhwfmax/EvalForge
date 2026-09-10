import json
import math
from pathlib import Path

import jsonschema
import pytest

from evalforge.adapters.ragas import load_ragas_export, ragas_artifact_from_export
from evalforge.gates import evaluate_gate, load_policy

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ragas" / "evaluation-result-records.json"


def _payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _artifact(payload, **kwargs):
    options = {"producer_version": "0.2.12", "metrics": ["faithfulness", "answer_relevancy"]}
    options.update(kwargs)
    return ragas_artifact_from_export(payload, **options)


def test_ragas_records_fixture_produces_schema_valid_aggregate_only_artifact():
    artifact = load_ragas_export(
        FIXTURE,
        producer_version="0.2.12",
        metrics=["faithfulness", "answer_relevancy"],
        source_revision="abc123",
        dataset_fingerprint="sha256:synthetic-dataset",
    )

    assert artifact.producer.name == "ragas"
    assert artifact.producer.version == "0.2.12"
    assert artifact.run.source_revision == "abc123"
    assert artifact.run.id is None
    assert set(artifact.metrics) == {"faithfulness", "answer_relevancy", "test_cases"}
    assert artifact.metrics["faithfulness"].value == pytest.approx(0.75)
    assert artifact.metrics["answer_relevancy"].value == pytest.approx(0.9)
    assert artifact.metrics["faithfulness"].unit == "score"
    assert artifact.metrics["faithfulness"].direction == "neutral"
    assert artifact.metrics["test_cases"].value == 2
    assert artifact.metrics["test_cases"].unit == "count"
    assert artifact.metadata == {
        "adapter": "evalforge.ragas",
        "adapter_mapping_version": "1",
        "source_format": "ragas.evaluation_result.pandas.records",
        "aggregation": "mean",
        "metric_columns": ["faithfulness", "answer_relevancy"],
        "dataset_fingerprint": "sha256:synthetic-dataset",
    }
    serialized = artifact.model_dump(mode="json", exclude_none=True, by_alias=True)
    jsonschema.validate(
        serialized,
        json.loads((ROOT / "schemas" / "evaluation-artifact-v1.schema.json").read_text()),
    )
    assert "must-not-leak" not in json.dumps(serialized)


def test_ragas_preserves_only_selected_scores_even_when_extra_columns_are_numeric():
    rows = _payload()
    rows[0]["user_input"] = 123456
    rows[0]["private_numeric_field"] = 987654321
    rows[0]["metadata"] = {"api_key": "must-not-leak"}
    rows[0]["trace"] = ["must-not-leak"]
    artifact = _artifact(rows, metrics=["answer_correctness"])

    assert set(artifact.metrics) == {"answer_correctness", "test_cases"}
    assert artifact.metrics["answer_correctness"].value == 0.5
    # Preserve source scores without equating them with EvalForge's own metrics.
    assert artifact.metrics["answer_correctness"].unit == "score"
    assert artifact.metrics["answer_correctness"].direction == "neutral"
    assert "dataset_fingerprint" not in artifact.metadata
    assert "987654321" not in artifact.model_dump_json()
    assert "must-not-leak" not in artifact.model_dump_json()


@pytest.mark.parametrize("value", [None, True, False, "0.9", [], {}, math.nan, math.inf, -math.inf])
def test_ragas_rejects_bad_selected_score_without_dropping_the_row(value):
    rows = _payload()
    rows[1]["faithfulness"] = value

    with pytest.raises(ValueError, match="row 1 score column faithfulness.*finite number"):
        _artifact(rows)


def test_ragas_missing_score_fails_instead_of_improving_the_mean():
    rows = _payload()
    del rows[1]["faithfulness"]

    with pytest.raises(ValueError, match="row 1 is missing score column faithfulness"):
        _artifact(rows)


@pytest.mark.parametrize("payload", [[], {}, {"faithfulness": 1}, {"scores": []}, None, [None]])
def test_ragas_rejects_empty_exports_and_other_serialization_formats(payload):
    with pytest.raises(ValueError, match="JSON"):
        _artifact(payload)


@pytest.mark.parametrize("version", [None, True, 12, "", " \n"])
def test_ragas_requires_explicit_nonempty_producer_version(version):
    with pytest.raises(ValueError, match="producer_version"):
        _artifact(_payload(), producer_version=version)


@pytest.mark.parametrize(
    "metrics",
    [None, [], "faithfulness", [""], [None], [" faithfulness"], ["faithfulness", "faithfulness"]],
)
def test_ragas_requires_an_explicit_unambiguous_metric_allowlist(metrics):
    with pytest.raises(ValueError, match="metric"):
        _artifact(_payload(), metrics=metrics)


@pytest.mark.parametrize("column", ["user_input", "response", "reference", "ground_truth"])
def test_ragas_dataset_columns_cannot_be_imported_as_metrics(column):
    with pytest.raises(ValueError, match="reserved dataset column"):
        _artifact([{column: 1}], metrics=[column])


def test_ragas_sample_count_cannot_be_overwritten_by_a_score_column():
    with pytest.raises(ValueError, match="reserved for the sample count"):
        _artifact([{"test_cases": 100000}], metrics=["test_cases"])


@pytest.mark.parametrize("field", ["source_revision", "dataset_fingerprint"])
def test_ragas_optional_provenance_must_not_be_empty(field):
    with pytest.raises(ValueError, match=field):
        _artifact(_payload(), **{field: " "})


def test_ragas_uses_an_overflow_safe_mean_for_finite_scores():
    artifact = _artifact([{"custom": 1e308}, {"custom": 1e308}], metrics=["custom"])
    assert artifact.metrics["custom"].value == 1e308


def test_ragas_rejects_integer_scores_that_cannot_be_represented_as_finite_numbers():
    with pytest.raises(ValueError, match="finite number"):
        _artifact([{"custom": 10**400}], metrics=["custom"])


@pytest.mark.parametrize("content", [b"{", b"\xff"])
def test_ragas_file_errors_do_not_expose_source_content(tmp_path, content):
    path = tmp_path / "records.json"
    path.write_bytes(content)
    with pytest.raises(ValueError, match="not valid UTF-8 JSON"):
        load_ragas_export(path, producer_version="0.2.12", metrics=["faithfulness"])


def test_ragas_read_error_is_actionable(tmp_path):
    with pytest.raises(ValueError, match="Could not read Ragas export"):
        load_ragas_export(
            tmp_path / "missing.json", producer_version="0.2.12", metrics=["faithfulness"]
        )


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_ragas_nonfinite_json_score_fails(tmp_path, constant):
    path = tmp_path / "records.json"
    path.write_text('[{"faithfulness": %s}]' % constant)
    with pytest.raises(ValueError, match="finite"):
        load_ragas_export(path, producer_version="0.2.12", metrics=["faithfulness"])


def test_ragas_duplicate_json_keys_cannot_hide_a_bad_score(tmp_path):
    path = tmp_path / "records.json"
    path.write_text('[{"faithfulness": null, "faithfulness": 1}]')
    with pytest.raises(ValueError, match="duplicate JSON object keys"):
        load_ragas_export(path, producer_version="0.2.12", metrics=["faithfulness"])


def test_ragas_invalid_score_error_does_not_repeat_private_value():
    rows = _payload()
    rows[0]["faithfulness"] = "private-value-must-not-leak"
    with pytest.raises(ValueError) as error:
        _artifact(rows)
    assert "private-value-must-not-leak" not in str(error.value)


def test_ragas_example_policy_passes_fixture_and_catches_regression():
    policy = load_policy(ROOT / "examples" / "ragas_policy.json")
    artifact = _artifact(_payload())
    assert evaluate_gate(policy, artifact).passed

    rows = _payload()
    rows[1]["faithfulness"] = 0.0
    report = evaluate_gate(policy, _artifact(rows))
    assert not report.passed
    assert report.checks[0].id == "ragas-faithfulness"
    assert report.checks[0].outcome == "fail"
