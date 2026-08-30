import json
import math
from pathlib import Path

import jsonschema
import pytest
from typer.testing import CliRunner

from evalforge.adapters.promptfoo import promptfoo_artifact_from_export
from evalforge.cli import app

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "promptfoo" / "results-v3.json"


def _payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_promptfoo_v3_export_becomes_schema_valid_sanitized_artifact():
    artifact = promptfoo_artifact_from_export(_payload(), source_revision="abc123")

    assert artifact.producer.name == "promptfoo"
    assert artifact.producer.version == "0.122.2"
    assert artifact.run.id == "eval-synthetic-001"
    assert artifact.run.source_revision == "abc123"
    assert artifact.metrics["promptfoo_pass_rate"].value == pytest.approx(2 / 3)
    assert artifact.metrics["promptfoo_mean_score"].value == pytest.approx(1.9 / 3)
    assert artifact.metrics["latency_ms"].value == pytest.approx(200)
    assert artifact.metrics["total_cost_usd"].value == pytest.approx(0.006)
    assert artifact.metrics["input_tokens"].value == 30
    assert artifact.metrics["output_tokens"].value == 15
    assert artifact.metrics["test_cases"].value == 3
    assert "unsupported_custom_score" not in artifact.metrics

    serialized = artifact.model_dump(mode="json", exclude_none=True, by_alias=True)
    jsonschema.validate(
        serialized,
        json.loads(
            (ROOT / "schemas" / "evaluation-artifact-v1.schema.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    assert "must-not-leak" not in json.dumps(serialized)
    assert artifact.metadata == {
        "adapter": "evalforge.promptfoo",
        "adapter_mapping_version": "1",
        "source_exported_at": "2026-08-31T08:01:00.000Z",
        "source_schema_version": 3,
        "source_timestamp": "2026-08-31T08:00:00.000Z",
    }


def test_promptfoo_import_ignores_forward_compatible_and_unknown_metric_fields():
    payload = _payload()
    payload["results"]["futureSummaryField"] = {"value": 99}
    payload["results"]["results"][0]["futureResultField"] = math.pi
    payload["results"]["results"][0]["namedScores"]["future_metric"] = 0.99

    artifact = promptfoo_artifact_from_export(payload)

    assert set(artifact.metrics) == {
        "input_tokens",
        "latency_ms",
        "output_tokens",
        "promptfoo_mean_score",
        "promptfoo_pass_rate",
        "test_cases",
        "total_cost_usd",
    }


def test_promptfoo_import_requires_versioned_provenance():
    payload = _payload()
    del payload["metadata"]["promptfooVersion"]

    with pytest.raises(ValueError, match="metadata.promptfooVersion"):
        promptfoo_artifact_from_export(payload)


def test_promptfoo_import_rejects_unknown_schema_version():
    payload = _payload()
    payload["results"]["version"] = 4

    with pytest.raises(ValueError, match="schema version 3"):
        promptfoo_artifact_from_export(payload)


@pytest.mark.parametrize("field", ["score", "latencyMs", "cost"])
def test_promptfoo_import_rejects_non_finite_result_values(field):
    payload = _payload()
    payload["results"]["results"][0][field] = math.nan

    with pytest.raises(ValueError, match="finite number"):
        promptfoo_artifact_from_export(payload)


def test_promptfoo_import_rejects_inconsistent_stats():
    payload = _payload()
    payload["results"]["stats"]["successes"] = 1

    with pytest.raises(ValueError, match="do not match result rows"):
        promptfoo_artifact_from_export(payload)


def test_promptfoo_cli_imports_explicit_format(tmp_path):
    output = tmp_path / "artifact.json"

    result = CliRunner().invoke(
        app,
        [
            "import",
            "promptfoo",
            str(FIXTURE),
            "--output",
            str(output),
            "--source-revision",
            "abc123",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["producer"] == {"name": "promptfoo", "version": "0.122.2"}
    assert payload["run"] == {"id": "eval-synthetic-001", "source_revision": "abc123"}
    assert "Wrote promptfoo evaluation artifact" in result.output
