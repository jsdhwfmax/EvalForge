import json
import math

import pytest

from evalforge.gates import compare_experiment_summaries, evaluate_quality_gate


def _summary(**changes):
    return {
        "dataset_fingerprint": "dataset-v1",
        "metric_version": "deterministic-v2",
        "answer_correctness": 0.8,
        "total_cost_usd": 0.003,
        **changes,
    }


@pytest.mark.parametrize("metric,threshold", [
    ("answer_correctness", 0.8), ("total_cost_usd", 0.01),
])
@pytest.mark.parametrize("value", [
    True, False, "private-score", None, [], {}, math.nan, math.inf, -math.inf, 10**400,
])
def test_history_gate_rejects_invalid_actuals_without_leaking_them(metric, threshold, value):
    report = evaluate_quality_gate({metric: value}, {metric: threshold})
    assert not report["passed"]
    assert report["checks"][0]["actual"] is None
    assert not report["checks"][0]["passed"]
    assert "finite number" in report["checks"][0]["reason"]
    assert "private-score" not in json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("threshold", [
    True, False, "private-threshold", [], {}, math.nan, math.inf, -math.inf, 10**400,
])
def test_history_gate_rejects_invalid_enabled_thresholds(threshold):
    with pytest.raises(ValueError, match="Threshold for answer_correctness.*finite number") as exc:
        evaluate_quality_gate({"answer_correctness": 1.0}, {"answer_correctness": threshold})
    assert "private-threshold" not in str(exc.value)


def test_history_gate_keeps_disabled_thresholds_and_empty_gate_behavior():
    report = evaluate_quality_gate({"answer_correctness": True}, {"answer_correctness": None})
    assert report == {"passed": False, "checks": []}


def test_history_gate_keeps_valid_integer_and_float_scores():
    report = evaluate_quality_gate(
        {"answer_correctness": 1, "total_cost_usd": 0.003},
        {"answer_correctness": 1.0, "total_cost_usd": 0.003},
    )
    assert report["passed"]
    assert all("reason" not in check for check in report["checks"])
    assert json.dumps(report, allow_nan=False)


def test_cost_definitions_from_v1_and_v2_do_not_produce_a_regression_verdict():
    baseline = _summary(metric_version="deterministic-v1", total_cost_usd=0.002)
    report = compare_experiment_summaries("base", baseline, "candidate", _summary())
    assert report["dataset_fingerprint_match"]
    assert not report["metric_version_match"]
    assert not report["comparable"]
    assert any("metric_version" in reason for reason in report["incompatibilities"])
    assert report["metrics"]["total_cost_usd"]["delta"] == 0.001
    assert report["metrics"]["total_cost_usd"]["baseline"] == 0.002
    assert report["metrics"]["total_cost_usd"]["candidate"] == 0.003
    assert {metric["verdict"] for metric in report["metrics"].values()} == {"not_comparable"}
    assert report["improvements"] == report["regressions"] == 0


@pytest.mark.parametrize("identity", ["dataset_fingerprint", "metric_version"])
@pytest.mark.parametrize("value", [None, "", " \n", False, 1, [], {}, "other-version"])
def test_comparison_requires_nonempty_matching_string_identities(identity, value):
    baseline = _summary()
    candidate = _summary(**{identity: value}, answer_correctness=0.9)
    report = compare_experiment_summaries("base", baseline, "candidate", candidate)
    assert not report["comparable"]
    assert any(identity in reason for reason in report["incompatibilities"])
    assert report["metrics"]["answer_correctness"]["delta"] == 0.1
    assert report["metrics"]["answer_correctness"]["verdict"] == "not_comparable"
    assert report["improvements"] == report["regressions"] == 0


@pytest.mark.parametrize("identity", ["dataset_fingerprint", "metric_version"])
def test_two_legacy_summaries_missing_the_same_identity_are_not_comparable(identity):
    baseline, candidate = _summary(), _summary()
    del baseline[identity]
    del candidate[identity]
    report = compare_experiment_summaries("base", baseline, "candidate", candidate)
    assert not report["comparable"]
    assert not report[identity + "_match"]
    assert report["metrics"]["answer_correctness"]["verdict"] == "not_comparable"


@pytest.mark.parametrize("side", ["baseline", "candidate"])
@pytest.mark.parametrize("value", [
    True, False, "private-score", [], {}, math.nan, math.inf, -math.inf, 10**400,
])
def test_invalid_comparison_scores_make_all_verdicts_incomparable_without_crashing(side, value):
    baseline, candidate = _summary(), _summary(answer_correctness=0.9)
    (baseline if side == "baseline" else candidate)["total_cost_usd"] = value
    report = compare_experiment_summaries("base", baseline, "candidate", candidate)
    assert not report["comparable"]
    assert report["dataset_fingerprint_match"] and report["metric_version_match"]
    assert "total_cost_usd" not in report["metrics"]
    assert report["metrics"]["answer_correctness"]["verdict"] == "not_comparable"
    assert any("total_cost_usd" in reason for reason in report["incompatibilities"])
    assert report["improvements"] == report["regressions"] == 0
    assert "private-score" not in json.dumps(report, allow_nan=False)


def test_unavailable_optional_metrics_are_skipped_without_invalidating_shared_evidence():
    baseline = _summary(total_cost_usd=None)
    candidate = _summary(answer_correctness=0.9)
    report = compare_experiment_summaries("base", baseline, "candidate", candidate)
    assert report["comparable"]
    assert "total_cost_usd" not in report["metrics"]
    assert report["metrics"]["answer_correctness"]["verdict"] == "improved"


def test_delta_overflow_is_incomparable_and_json_safe():
    baseline = _summary(total_cost_usd=-1e308)
    candidate = _summary(total_cost_usd=1e308)
    report = compare_experiment_summaries("base", baseline, "candidate", candidate)
    assert not report["comparable"]
    assert "total_cost_usd" not in report["metrics"]
    assert any("delta for total_cost_usd is not finite" in r for r in report["incompatibilities"])
    assert report["metrics"]["answer_correctness"]["verdict"] == "not_comparable"
    assert json.dumps(report, allow_nan=False)


def test_comparison_without_shared_metrics_does_not_claim_comparability():
    baseline = _summary(answer_correctness=None, total_cost_usd=None)
    report = compare_experiment_summaries("base", baseline, "candidate", _summary())
    assert not report["comparable"]
    assert report["metrics"] == {}
    assert "No shared finite metrics are available" in report["incompatibilities"]
    assert report["improvements"] == report["regressions"] == 0
