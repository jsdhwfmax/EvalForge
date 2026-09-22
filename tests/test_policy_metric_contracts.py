import json

import pytest
from typer.testing import CliRunner

from evalforge.artifacts import EvaluationArtifact
from evalforge.cli import app
from evalforge.gates import GateCheck, GatePolicy, evaluate_gate


def _artifact(value, unit, direction="lower"):
    return EvaluationArtifact.model_validate({
        "producer": {"name": "test", "version": "1"},
        "metrics": {"measurement": {"value": value, "unit": unit, "direction": direction}},
    })


def _policy(**changes):
    check = {"id": "measurement", "metric": "measurement", "op": "lte", "value": 500}
    check.update(changes)
    return GatePolicy(checks=[GateCheck(**check)])


@pytest.mark.parametrize("severity", ["error", "warning"])
def test_seconds_cannot_pass_a_millisecond_threshold(severity):
    candidate = _artifact(2, "seconds")
    report = evaluate_gate(_policy(unit="ms", severity=severity), candidate)
    assert not report.passed
    assert report.checks[0].outcome == "error"
    assert "unit does not match policy" in report.checks[0].message
    assert "expected=ms, actual=seconds" in report.checks[0].message


def test_percentages_cannot_pass_a_ratio_threshold():
    candidate = _artifact(80, "percent", "higher")
    report = evaluate_gate(_policy(op="gte", value=0.9, unit="ratio"), candidate)
    assert not report.passed
    assert report.checks[0].outcome == "error"
    assert "unit does not match policy" in report.checks[0].message


@pytest.mark.parametrize("actual", ["higher", "neutral"])
@pytest.mark.parametrize("severity", ["error", "warning"])
def test_metric_direction_changes_are_errors_even_for_warning_checks(actual, severity):
    candidate = _artifact(0.2, "ratio", actual)
    report = evaluate_gate(
        _policy(value=0.5, direction="lower", severity=severity), candidate
    )
    assert not report.passed
    assert report.checks[0].outcome == "error"
    assert "direction does not match policy" in report.checks[0].message


@pytest.mark.parametrize("direction", ["higher", "lower", "neutral"])
def test_matching_contracts_evaluate_the_normal_numeric_rule(direction):
    policy = _policy(unit="ms", direction=direction)
    assert evaluate_gate(policy, _artifact(400, "ms", direction)).passed
    failed = evaluate_gate(policy, _artifact(600, "ms", direction))
    assert not failed.passed
    assert failed.checks[0].outcome == "fail"


def test_matching_contract_does_not_promote_warning_threshold_failures_to_errors():
    report = evaluate_gate(
        _policy(unit="ms", direction="lower", severity="warning"),
        _artifact(600, "ms"),
    )
    assert report.passed
    assert report.checks[0].outcome == "warn"


def test_omitted_contracts_preserve_existing_policy_behavior():
    policy = _policy()
    assert policy.checks[0].unit is None
    assert policy.checks[0].direction is None
    assert evaluate_gate(policy, _artifact(2, "seconds", "neutral")).passed


@pytest.mark.parametrize("unit", ["", " ", "\t\n", 123, False])
def test_policy_units_must_be_nonempty_strings(unit):
    with pytest.raises(ValueError):
        _policy(unit=unit)


@pytest.mark.parametrize("direction", ["", "up", "higher_is_better", 1, False])
def test_policy_direction_accepts_only_the_portable_enum(direction):
    with pytest.raises(ValueError):
        _policy(direction=direction)


def test_explicit_null_contracts_are_equivalent_to_omission():
    assert _policy(unit=None, direction=None) == _policy()


@pytest.mark.parametrize("baseline_unit,baseline_direction,expected_error", [
    ("seconds", "lower", "Metric units do not match"),
    ("ms", "higher", "Metric directions do not match"),
])
def test_delta_contracts_still_require_compatible_baseline_metadata(
    baseline_unit, baseline_direction, expected_error
):
    report = evaluate_gate(
        _policy(op="delta_lte", value=0, unit="ms", direction="lower"),
        _artifact(2, "ms"),
        _artifact(3, baseline_unit, baseline_direction),
    )
    assert not report.passed
    assert report.checks[0].outcome == "error"
    assert expected_error in report.checks[0].message


def test_delta_contracts_reject_two_consistently_wrong_units():
    report = evaluate_gate(
        _policy(op="delta_lte", value=0, unit="ms"),
        _artifact(2, "seconds"),
        _artifact(3, "seconds"),
    )
    assert not report.passed
    assert report.checks[0].outcome == "error"
    assert "unit does not match policy" in report.checks[0].message


def test_matching_delta_contract_preserves_delta_calculation():
    report = evaluate_gate(
        _policy(op="delta_lte", value=0, unit="ms", direction="lower"),
        _artifact(200, "ms"),
        _artifact(300, "ms"),
    )
    assert report.passed
    assert report.checks[0].observed == -100


def test_cli_unit_mismatch_exits_one_with_consistent_json_report(tmp_path):
    candidate = tmp_path / "candidate.json"
    policy = tmp_path / "policy.json"
    output = tmp_path / "report.json"
    candidate.write_text(_artifact(2, "seconds").model_dump_json(), encoding="utf-8")
    policy.write_text(_policy(unit="ms").model_dump_json(), encoding="utf-8")
    result = CliRunner().invoke(app, [
        "gate", str(candidate), "--policy", str(policy), "--json", str(output),
    ])
    assert result.exit_code == 1, result.output
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["passed"] is False
    assert report["checks"][0]["outcome"] == "error"
    assert "[ERROR]" in result.output
