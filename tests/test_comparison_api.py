import json
import math

import pytest

from evalforge.database import session_scope
from evalforge.models import Experiment, RagConfig


def _summary(**changes):
    return {
        "dataset_fingerprint": "dataset-v1",
        "metric_version": "deterministic-v2",
        "retrieval_recall_at_k": 1.0,
        "answer_correctness": 0.8,
        "citation_support": 1.0,
        "hallucination_rate": 0.0,
        "security_pass_rate": 1.0,
        "total_cost_usd": 0.002,
        **changes,
    }


def _store_experiments(**summaries):
    with session_scope() as db:
        db.add(RagConfig(id="comparison-config", name="Comparison config"))
        db.flush()
        for experiment_id, summary in summaries.items():
            db.add(Experiment(
                id=experiment_id,
                name=experiment_id,
                config_id="comparison-config",
                status="completed",
                summary=summary,
            ))


def _compare(client):
    return client.get(
        "/api/v1/experiments/compare",
        params={"baseline_id": "baseline", "candidate_id": "candidate"},
    )


def test_comparison_api_preserves_evidence_identity_fields(client):
    _store_experiments(
        baseline=_summary(),
        candidate=_summary(answer_correctness=0.9),
    )

    response = _compare(client)

    assert response.status_code == 200
    report = response.json()
    assert report["baseline_experiment_id"] == "baseline"
    assert report["candidate_experiment_id"] == "candidate"
    assert report["dataset_fingerprint_match"] is True
    assert report["metric_version_match"] is True
    assert report["comparable"] is True
    assert report["incompatibilities"] == []
    assert report["metrics"]["answer_correctness"]["verdict"] == "improved"
    assert report["improvements"] == 1
    assert report["regressions"] == 0


@pytest.mark.parametrize("baseline_version", ["deterministic-v1", None])
def test_comparison_api_does_not_grade_different_or_missing_metric_versions(
    client, baseline_version,
):
    baseline = _summary(metric_version=baseline_version)
    if baseline_version is None:
        del baseline["metric_version"]
    _store_experiments(
        baseline=baseline,
        candidate=_summary(answer_correctness=0.9, total_cost_usd=0.003),
    )

    response = _compare(client)

    assert response.status_code == 200
    report = response.json()
    assert report["dataset_fingerprint_match"] is True
    assert report["metric_version_match"] is False
    assert report["comparable"] is False
    assert any("metric_version" in reason for reason in report["incompatibilities"])
    assert report["metrics"]["answer_correctness"]["delta"] == 0.1
    assert report["metrics"]["total_cost_usd"]["delta"] == 0.001
    assert {metric["verdict"] for metric in report["metrics"].values()} == {"not_comparable"}
    assert report["improvements"] == report["regressions"] == 0


@pytest.mark.parametrize("metric,value", [
    ("answer_correctness", True),
    ("answer_correctness", math.inf),
    ("total_cost_usd", False),
    ("total_cost_usd", -math.inf),
])
def test_gate_api_safely_rejects_invalid_stored_summary_numbers(client, metric, value):
    _store_experiments(candidate=_summary(**{metric: value}))

    response = client.post(
        "/api/v1/experiments/candidate/gate", json={"total_cost_usd": 0.01},
    )

    assert response.status_code == 200
    report = response.json()
    assert report["experiment_id"] == "candidate"
    assert report["passed"] is False
    check = next(check for check in report["checks"] if check["metric"] == metric)
    assert check["actual"] is None
    assert check["passed"] is False
    assert "finite number" in check["reason"]
    assert all(check["passed"] for check in report["checks"] if check["metric"] != metric)
    assert json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("value", [True, math.inf])
def test_comparison_api_safely_reports_invalid_stored_summary_numbers(client, value):
    _store_experiments(
        baseline=_summary(total_cost_usd=value),
        candidate=_summary(answer_correctness=0.9),
    )

    response = _compare(client)

    assert response.status_code == 200
    report = response.json()
    assert report["dataset_fingerprint_match"] is True
    assert report["metric_version_match"] is True
    assert report["comparable"] is False
    assert any("total_cost_usd" in reason for reason in report["incompatibilities"])
    assert "total_cost_usd" not in report["metrics"]
    assert report["metrics"]["answer_correctness"]["verdict"] == "not_comparable"
    assert report["improvements"] == report["regressions"] == 0
    assert json.dumps(report, allow_nan=False)
