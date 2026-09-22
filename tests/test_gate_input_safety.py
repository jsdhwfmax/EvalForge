import json
from xml.etree import ElementTree

import pytest
from typer.testing import CliRunner

from evalforge.artifacts import load_artifact
from evalforge.cli import app
from evalforge.gates import CheckResult, GateReport, load_policy, render_junit


def _policy(**changes):
    payload = {
        "version": 1,
        "checks": [{"id": "quality", "metric": "quality", "op": "gte", "value": 0.8}],
    }
    payload.update(changes)
    return payload


@pytest.mark.parametrize("source", [
    '{"quality":0.1,"quality":0.99}',
    '{"summary":{"quality":0.1,"quality":0.99}}',
    '{"producer":{"name":"test","version":"1"},'
    '"metrics":{"quality":{"value":0.1,"value":0.99}}}',
    '{"producer":{"name":"test","version":"1"},'
    '"metrics":{"quality":{"value":0.9}},'
    '"metadata":{"nested":[{"must-not-leak-key":1,"must-not-leak-key":2}]}}',
])
def test_artifact_rejects_duplicate_keys_at_every_depth(tmp_path, source):
    path = tmp_path / "artifact.json"
    path.write_text(source, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON object keys") as exc:
        load_artifact(path)
    assert "must-not-leak-key" not in str(exc.value)


@pytest.mark.parametrize("source", [
    '{"version":1,"checks":[],"checks":[{"id":"q","metric":"quality",'
    '"op":"gte","value":0.0}]}',
    '{"version":1,"checks":[{"id":"q","metric":"quality","op":"gte",'
    '"value":0.8,"value":0.0}]}',
    '{"version":1,"checks":[],"comparison":{"require_same_dataset":true,'
    '"require_same_dataset":false}}',
])
def test_policy_rejects_duplicate_keys_before_model_validation(tmp_path, source):
    path = tmp_path / "policy.json"
    path.write_text(source, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON object keys"):
        load_policy(path)


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity", "1e999", "-1e999"])
@pytest.mark.parametrize("loader", [load_artifact, load_policy])
def test_non_finite_json_is_rejected_even_in_unknown_fields(tmp_path, token, loader):
    path = tmp_path / "input.json"
    path.write_text('{"ignored":{"nested":[' + token + ']}}', encoding="utf-8")
    with pytest.raises(ValueError, match="finite numbers"):
        loader(path)


def test_arbitrary_finite_artifact_metadata_remains_supported(tmp_path):
    path = tmp_path / "artifact.json"
    metadata = {"nested": [None, False, {"note": "Unicode 数据", "number": 1.2e3}]}
    path.write_text(json.dumps({
        "producer": {"name": "test", "version": "1"},
        "metrics": {"quality": {"value": 0.9}},
        "metadata": metadata,
    }), encoding="utf-8")
    assert load_artifact(path).metadata == metadata


@pytest.mark.parametrize("source", [
    '{"ignored":{"private-value":["must-not-leak-\\ud800"]}}',
    '{"ignored":{"must-not-leak-\\udfff":"value"}}',
    '{"ignored":["\\ud800x\\udfff"]}',
])
@pytest.mark.parametrize("loader", [load_artifact, load_policy])
def test_unpaired_surrogates_are_rejected_in_values_and_keys(tmp_path, source, loader):
    path = tmp_path / "input.json"
    path.write_text(source, encoding="utf-8")
    with pytest.raises(ValueError, match="valid Unicode scalar values") as exc:
        loader(path)
    assert "must-not-leak" not in str(exc.value)


def test_valid_escaped_surrogate_pair_remains_supported(tmp_path):
    path = tmp_path / "artifact.json"
    path.write_text(
        '{"producer":{"name":"test","version":"1"},'
        '"metrics":{"quality":{"value":0.9}},'
        '"metadata":{"emoji":"\\ud83d\\ude00"}}',
        encoding="utf-8",
    )
    assert load_artifact(path).metadata["emoji"] == "😀"


@pytest.mark.parametrize("loader", [load_artifact, load_policy])
@pytest.mark.parametrize("content,pattern", [
    (b'\xff', "not valid UTF-8 JSON"),
    (b'{"private":"must-not-leak-value",', "not valid JSON.*line 1, column"),
])
def test_invalid_json_has_clear_content_free_diagnostics(tmp_path, loader, content, pattern):
    path = tmp_path / "input.json"
    path.write_bytes(content)
    with pytest.raises(ValueError, match=pattern) as exc:
        loader(path)
    assert "must-not-leak-value" not in str(exc.value)


@pytest.mark.parametrize("loader,label", [(load_artifact, "artifact"), (load_policy, "policy")])
def test_missing_files_report_a_read_error(tmp_path, loader, label):
    with pytest.raises(ValueError, match="Could not read " + label):
        loader(tmp_path / "missing.json")


@pytest.mark.parametrize("target", ["candidate", "policy"])
@pytest.mark.parametrize("source", [
    b'{"quality":0.1,"quality":0.99}',
    b'{"ignored":NaN}',
    b'{"ignored":1e999}',
    b'{"ignored":"must-not-leak-\\ud800"}',
    b'\xff',
])
def test_cli_invalid_inputs_exit_two_without_emitting_reports(tmp_path, target, source):
    candidate = tmp_path / "candidate.json"
    policy = tmp_path / "policy.json"
    candidate.write_text('{"quality":0.9}', encoding="utf-8")
    policy.write_text(json.dumps(_policy()), encoding="utf-8")
    (candidate if target == "candidate" else policy).write_bytes(source)
    output = tmp_path / "report.json"
    result = CliRunner().invoke(app, [
        "gate", str(candidate), "--policy", str(policy), "--json", str(output),
    ])
    assert result.exit_code == 2, result.output
    assert "Invalid value" in result.output
    assert "must-not-leak" not in result.output
    assert not output.exists()


def test_out_of_range_integer_metric_is_a_cli_input_error(tmp_path):
    candidate = tmp_path / "candidate.json"
    policy = tmp_path / "policy.json"
    candidate.write_text('{"quality":' + str(10**400) + '}', encoding="utf-8")
    policy.write_text(json.dumps(_policy()), encoding="utf-8")
    result = CliRunner().invoke(app, ["gate", str(candidate), "--policy", str(policy)])
    assert result.exit_code == 2, result.output
    assert "finite numbers" in result.output


@pytest.mark.parametrize("outcome", ["fail", "error", "warn"])
def test_junit_replaces_xml_forbidden_characters_without_changing_outcome(outcome):
    invalid = "\x00\x01\x0b\x0c\x1b\x1f\ud800\ufffe\uffff"
    valid = "数据 <&> \t\r\n😀"
    report = GateReport(
        policy_name="release" + invalid + valid,
        passed=outcome == "warn",
        checks=[CheckResult(
            id="quality" + invalid,
            metric="quality",
            op="gte",
            expected=0.8,
            actual=0.1,
            observed=0.1,
            severity="warning" if outcome == "warn" else "error",
            outcome=outcome,
            message="quality failed " + invalid + valid,
        )],
    )
    serialized = render_junit(report)
    root = ElementTree.fromstring(serialized)
    assert root.attrib["failures"] == str(int(outcome == "fail"))
    assert root.attrib["errors"] == str(int(outcome == "error"))
    assert root.find("properties/property").attrib["value"] == "release" + "\ufffd" * 9 + valid
    case = root.find("testcase")
    assert case.attrib["name"] == "quality" + "\ufffd" * 9
    child = case.find({"fail": "failure", "error": "error", "warn": "system-out"}[outcome])
    # XML normalizes literal CR in element text to LF, but all valid characters survive.
    assert "数据 <&>" in child.text
    assert "😀" in child.text
    assert "\ufffd" * 9 in child.text
    assert all(char not in serialized for char in invalid)


def test_cli_passing_gate_emits_parseable_junit_for_control_character_policy_name(tmp_path):
    candidate = tmp_path / "candidate.json"
    policy = tmp_path / "policy.json"
    output = tmp_path / "report.xml"
    candidate.write_text('{"quality":0.9}', encoding="utf-8")
    policy.write_text(json.dumps(_policy(name="release\u0000gate")), encoding="utf-8")
    result = CliRunner().invoke(app, [
        "gate", str(candidate), "--policy", str(policy), "--junit", str(output),
    ])
    assert result.exit_code == 0, result.output
    junit = ElementTree.parse(output).getroot()
    assert junit.attrib["failures"] == "0"
    assert junit.find("properties/property").attrib["value"] == "release\ufffdgate"
