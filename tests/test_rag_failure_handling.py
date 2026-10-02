import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from evalforge.database import SessionLocal
from evalforge.models import Experiment, RagConfig
from evalforge.providers import ModelResponse
from evalforge.schemas import ExperimentRun, QualityGateRequest, RagConfigCreate
from evalforge.services import ExperimentExecutionError, run_experiment, select_test_cases


def seed(client, case_count=1):
    for index in range(case_count):
        assert client.post("/api/v1/test-cases", json={
            "id": "case-%s" % index, "question": "Question?", "expected_answer": "Answer."
        }).status_code == 201


def add_config(client, identifier, **fields):
    response = client.post("/api/v1/configs", json={
        "id": identifier, "name": identifier, **fields,
    })
    assert response.status_code == 201, response.text


def run_batch(client, identifiers, **fields):
    return client.post("/api/v1/experiments/run", json={
        "name": "Failure handling", "config_ids": identifiers, "include_security": False,
        **fields,
    })


@pytest.mark.parametrize("field", ["input_cost_per_million", "output_cost_per_million"])
@pytest.mark.parametrize("value", ["Infinity", "-Infinity", "NaN"])
def test_nonfinite_config_prices_are_rejected_before_persistence(client, field, value):
    response = client.post("/api/v1/configs", json={"name": "Bad price", field: value})
    assert response.status_code == 422
    assert client.get("/api/v1/configs").json() == []


@pytest.mark.parametrize("literal", ["1e999", "Infinity", "-Infinity", "NaN"])
@pytest.mark.parametrize("path,field", [
    ("/api/v1/configs", "input_cost_per_million"),
    ("/api/v1/experiments/missing/gate", "total_cost_usd"),
])
def test_nonfinite_json_literals_return_safe_validation_errors(client, literal, path, field):
    response = client.post(
        path,
        content='{"name":"PRIVATE-SENTINEL","' + field + '":' + literal + '}',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", field]
    assert "PRIVATE-SENTINEL" not in response.text
    for error in response.json()["detail"]:
        assert "input" not in error
        assert "ctx" not in error
    json.dumps(response.json(), allow_nan=False)
    assert client.get("/api/v1/configs").json() == []


@pytest.mark.parametrize("field", ["latency_ms", "total_cost_usd"])
@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_unbounded_gate_thresholds_still_require_finite_numbers(field, value):
    with pytest.raises(ValidationError, match="finite number"):
        QualityGateRequest(**{field: value})


def test_numeric_string_compatibility_is_preserved():
    config = RagConfigCreate(name="Prices", input_cost_per_million="1.5")
    gate = QualityGateRequest(latency_ms="500", total_cost_usd="0.25")
    assert config.input_cost_per_million == 1.5
    assert gate.latency_ms == 500.0
    assert gate.total_cost_usd == 0.25


def test_nonfinite_gate_request_is_a_validation_error(client):
    seed(client)
    add_config(client, "normal")
    experiment = run_batch(client, ["normal"]).json()["experiments"][0]
    response = client.post(
        "/api/v1/experiments/%s/gate" % experiment["id"], json={"total_cost_usd": "Infinity"}
    )
    assert response.status_code == 422
    assert client.get("/api/v1/experiments").status_code == 200


def test_duplicate_configs_are_rejected_before_any_experiment_runs(client):
    seed(client)
    add_config(client, "once")
    with pytest.raises(ValidationError, match="Configuration IDs must be unique"):
        ExperimentRun(name="Duplicate", config_ids=["once", "once"])
    response = run_batch(client, ["once", "once"])
    assert response.status_code == 422
    assert client.get("/api/v1/experiments").json() == []


def test_model_validation_errors_do_not_echo_the_request_or_exception_context(client):
    response = run_batch(client, ["PRIVATE-CONFIG", "PRIVATE-CONFIG"])
    assert response.status_code == 422
    assert "PRIVATE-CONFIG" not in response.text
    assert response.json()["detail"][0]["msg"] == "Value error, Configuration IDs must be unique"
    assert "ctx" not in response.json()["detail"][0]
    assert "input" not in response.json()["detail"][0]


def test_batch_returns_saved_provider_failure_and_continues_remaining_configs(client, monkeypatch):
    seed(client)
    add_config(client, "before")
    missing_key = "EVALFORGE_TEST_MISSING_PROVIDER_KEY"
    monkeypatch.delenv(missing_key, raising=False)
    add_config(
        client, "fails", provider="openai_compatible", api_base="https://example.invalid/v1",
        api_key_env=missing_key,
    )
    add_config(client, "after")

    response = run_batch(client, ["before", "fails", "after"])

    assert response.status_code == 200
    experiments = response.json()["experiments"]
    assert [row["config_id"] for row in experiments] == ["before", "fails", "after"]
    assert [row["status"] for row in experiments] == ["completed", "failed", "completed"]
    failed = experiments[1]
    assert "Missing API key environment variable" in failed["error"]
    assert failed["summary"] == {}
    assert failed["results"] == []
    assert failed["completed_at"] is not None
    assert len(client.get("/api/v1/experiments").json()) == 3
    assert client.get("/api/v1/experiments/%s" % failed["id"]).json() == failed
    assert client.post("/api/v1/experiments/%s/gate" % failed["id"], json={}).status_code == 409


@pytest.mark.parametrize("overflow_stage", ["quality", "security", "aggregate"])
def test_overflow_fails_the_run_without_persisting_nonfinite_results(
    client, monkeypatch, overflow_stage
):
    seed(client)
    add_config(client, "overflow", input_cost_per_million=1e308)
    calls = []

    class MeteredProvider:
        def generate(self, question, documents, config):
            calls.append(question)
            tokens = 100 if overflow_stage == "quality" or len(calls) > 1 else 1
            return ModelResponse(
                answer="I can't comply.", citations=[], input_tokens=tokens, output_tokens=0
            )

    monkeypatch.setattr("evalforge.services.get_provider", lambda _name: MeteredProvider())
    if overflow_stage == "aggregate":
        monkeypatch.setattr(
            "evalforge.services.metrics.aggregate_results",
            lambda _quality, _security: {"total_cost_usd": float("inf")},
        )
    response = run_batch(client, ["overflow"], include_security=overflow_stage == "security")

    assert response.status_code == 200
    experiment = response.json()["experiments"][0]
    assert experiment["status"] == "failed"
    assert "cost must be finite" in experiment["error"]
    assert experiment["summary"] == {}
    assert experiment["results"] == []
    assert experiment["security_results"] == []
    assert experiment["completed_at"] is not None
    assert client.get("/api/v1/experiments").status_code == 200
    assert client.get("/api/v1/configs").status_code == 200
    json.dumps(response.json(), allow_nan=False)


def test_service_keeps_database_errors_distinct_from_saved_evaluation_failures(client, monkeypatch):
    seed(client)
    add_config(client, "database-failure")
    database_error = OperationalError("test statement", {}, RuntimeError("database unavailable"))

    def fail_search(*args, **kwargs):
        raise database_error

    monkeypatch.setattr(
        "evalforge.services.Retriever",
        lambda _documents: SimpleNamespace(search=fail_search),
    )
    with SessionLocal() as db:
        config = db.get(RagConfig, "database-failure")
        with pytest.raises(OperationalError) as caught:
            run_experiment(db, "Database failure", config, select_test_cases(db), False)
        assert caught.value is database_error
        assert not isinstance(caught.value, ExperimentExecutionError)
        assert db.query(Experiment).one().status == "failed"


def test_api_does_not_swallow_unrecoverable_database_errors(client, monkeypatch):
    seed(client)
    add_config(client, "database-failure")
    database_error = OperationalError("test statement", {}, RuntimeError("database unavailable"))

    def fail_database(*args, **kwargs):
        raise database_error

    monkeypatch.setattr("evalforge.api.run_experiment", fail_database)
    with pytest.raises(OperationalError) as caught:
        run_batch(client, ["database-failure"])
    assert caught.value is database_error
