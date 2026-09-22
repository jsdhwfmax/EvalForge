import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_demo():
    return json.loads((ROOT / "examples" / "demo_dataset.json").read_text(encoding="utf-8"))


def test_health_and_dataset_import(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["database"] == "sqlite"

    imported = client.post("/api/v1/datasets/import", json=load_demo())
    assert imported.status_code == 200
    assert imported.json() == {"documents_created": 6, "test_cases_created": 5, "skipped": 0}

    repeated = client.post("/api/v1/datasets/import", json=load_demo())
    assert repeated.json()["skipped"] == 11
    assert len(client.get("/api/v1/documents").json()) == 6
    assert len(client.get("/api/v1/test-cases").json()) == 5


def test_full_experiment_comparison(client):
    assert client.post("/api/v1/datasets/import", json=load_demo()).status_code == 200
    baseline = client.post(
        "/api/v1/configs",
        json={"id": "baseline", "name": "Baseline", "retrieval_method": "bm25", "top_k": 1},
    )
    candidate = client.post(
        "/api/v1/configs",
        json={"id": "candidate", "name": "Candidate", "retrieval_method": "hybrid", "top_k": 3},
    )
    assert baseline.status_code == candidate.status_code == 201

    response = client.post(
        "/api/v1/experiments/run",
        json={
            "name": "API comparison",
            "config_ids": ["baseline", "candidate"],
            "include_security": True,
        },
    )
    assert response.status_code == 200
    experiments = response.json()["experiments"]
    assert len(experiments) == 2
    for experiment in experiments:
        assert experiment["status"] == "completed"
        assert len(experiment["results"]) == 5
        assert len(experiment["security_results"]) == 4
        assert experiment["summary"]["security_pass_rate"] == 1.0
        assert experiment["summary"]["test_cases"] == 5
        assert len(experiment["summary"]["dataset_fingerprint"]) == 16
        assert experiment["summary"]["metric_version"] == "deterministic-v2"
        assert experiment["summary"]["config_snapshot"]["id"] in {"baseline", "candidate"}
    assert (
        experiments[1]["summary"]["retrieval_recall_at_k"]
        >= experiments[0]["summary"]["retrieval_recall_at_k"]
    )

    listed = client.get("/api/v1/experiments")
    assert listed.status_code == 200
    assert len(listed.json()) == 2
    detail = client.get("/api/v1/experiments/%s" % experiments[0]["id"])
    assert detail.status_code == 200

    comparison = client.get(
        "/api/v1/experiments/compare",
        params={"baseline_id": experiments[0]["id"], "candidate_id": experiments[1]["id"]},
    )
    assert comparison.status_code == 200
    assert comparison.json()["dataset_fingerprint_match"] is True
    assert comparison.json()["metrics"]["retrieval_recall_at_k"]["verdict"] == "improved"

    default_gate = client.post("/api/v1/experiments/%s/gate" % experiments[1]["id"], json={})
    assert default_gate.status_code == 200
    assert default_gate.json()["passed"] is True
    strict_gate = client.post(
        "/api/v1/experiments/%s/gate" % experiments[1]["id"],
        json={"answer_correctness": 0.99},
    )
    assert strict_gate.status_code == 200
    assert strict_gate.json()["passed"] is False


def test_create_resources_and_conflicts(client):
    document = {"id": "doc", "title": "Title", "content": "Useful content"}
    assert client.post("/api/v1/documents", json=document).status_code == 201
    assert client.post("/api/v1/documents", json=document).status_code == 409

    test_case = {
        "id": "test",
        "question": "What is useful?",
        "expected_answer": "Useful content",
        "relevant_document_ids": ["doc"],
    }
    assert client.post("/api/v1/test-cases", json=test_case).status_code == 201
    assert client.post("/api/v1/test-cases", json=test_case).status_code == 409

    config = {"id": "config", "name": "Config", "top_k": 1}
    assert client.post("/api/v1/configs", json=config).status_code == 201
    assert client.post("/api/v1/configs", json=config).status_code == 409


def test_api_validation_and_missing_resources(client):
    assert client.get("/api/v1/experiments/missing").status_code == 404
    no_tests = client.post(
        "/api/v1/experiments/run", json={"name": "No tests", "config_ids": ["missing"]}
    )
    assert no_tests.status_code == 400

    assert (
        client.post(
            "/api/v1/configs",
            json={"name": "Bad", "provider": "openai_compatible", "api_base": ""},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/configs", json={"name": "Bad retrieval", "retrieval_method": "magic"}
        ).status_code
        == 422
    )

    upload = client.post(
        "/api/v1/datasets/upload", files={"file": ("data.txt", b"{}", "text/plain")}
    )
    assert upload.status_code == 415
    invalid_json = client.post(
        "/api/v1/datasets/upload", files={"file": ("data.json", b"not-json", "application/json")}
    )
    assert invalid_json.status_code == 422
    missing_compare = client.get(
        "/api/v1/experiments/compare",
        params={"baseline_id": "missing-a", "candidate_id": "missing-b"},
    )
    assert missing_compare.status_code == 404
    assert client.post("/api/v1/experiments/missing/gate", json={}).status_code == 404


def test_missing_config_after_tests_exist(client):
    client.post("/api/v1/datasets/import", json=load_demo())
    response = client.post(
        "/api/v1/experiments/run", json={"name": "Missing", "config_ids": ["not-there"]}
    )
    assert response.status_code == 404
    assert response.json()["detail"]["missing_config_ids"] == ["not-there"]


@pytest.mark.parametrize(
    "test_case_ids,status_code,error_text",
    [
        ([], 422, "test_case_ids"),
        (["refund_window", "missing-hard-case"], 400, "missing-hard-case"),
        (["missing-only"], 400, "missing-only"),
        (["refund_window", "refund_window"], 400, "unique"),
    ],
)
def test_invalid_explicit_selection_does_not_start_any_batch_config(
    client, test_case_ids, status_code, error_text
):
    assert client.post("/api/v1/datasets/import", json=load_demo()).status_code == 200
    for identifier in ["first", "second"]:
        assert client.post(
            "/api/v1/configs", json={"id": identifier, "name": identifier}
        ).status_code == 201

    response = client.post(
        "/api/v1/experiments/run",
        json={
            "name": "Explicit selection",
            "config_ids": ["first", "second"],
            "test_case_ids": test_case_ids,
            "include_security": False,
        },
    )

    assert response.status_code == status_code
    assert error_text in response.text
    assert client.get("/api/v1/experiments").json() == []


@pytest.mark.parametrize("test_case_ids", [None, ["refund_window", "password_link"]])
def test_null_selection_runs_all_and_explicit_selection_runs_exact_subset(client, test_case_ids):
    dataset = load_demo()
    assert client.post("/api/v1/datasets/import", json=dataset).status_code == 200
    assert client.post(
        "/api/v1/configs", json={"id": "selection", "name": "Selection"}
    ).status_code == 201

    response = client.post(
        "/api/v1/experiments/run",
        json={
            "name": "Valid selection",
            "config_ids": ["selection"],
            "test_case_ids": test_case_ids,
            "include_security": False,
        },
    )

    assert response.status_code == 200
    experiment = response.json()["experiments"][0]
    expected = test_case_ids if test_case_ids is not None else [
        row["id"] for row in dataset["test_cases"]
    ]
    assert sorted(row["test_case_id"] for row in experiment["results"]) == sorted(expected)
    assert experiment["summary"]["test_cases"] == len(expected)


@pytest.mark.parametrize("include_security", [False, True])
def test_total_cost_gate_counts_every_quality_and_security_provider_call(
    client, monkeypatch, include_security
):
    from evalforge.providers import ModelResponse
    from evalforge.security import SECURITY_CASES

    calls = []

    class MeteredProvider:
        def generate(self, question, documents, config):
            calls.append(question)
            return ModelResponse(
                answer="I can't comply.", citations=[], input_tokens=100, output_tokens=20,
                raw={"token_usage_source": {
                    "prompt_tokens": "estimated", "completion_tokens": "reported",
                }},
            )

    monkeypatch.setattr("evalforge.services.get_provider", lambda _name: MeteredProvider())
    assert client.post("/api/v1/datasets/import", json=load_demo()).status_code == 200
    assert client.post(
        "/api/v1/configs",
        json={
            "id": "metered", "name": "Metered",
            "input_cost_per_million": 1000.0, "output_cost_per_million": 500.0,
        },
    ).status_code == 201

    response = client.post(
        "/api/v1/experiments/run",
        json={
            "name": "Metered run", "config_ids": ["metered"],
            "test_case_ids": ["refund_window"], "include_security": include_security,
        },
    )

    assert response.status_code == 200
    experiment = response.json()["experiments"][0]
    call_count = 1 + (len(SECURITY_CASES) if include_security else 0)
    assert len(calls) == call_count
    assert experiment["summary"]["input_tokens"] == 100 * call_count
    assert experiment["summary"]["output_tokens"] == 20 * call_count
    assert experiment["summary"]["total_cost_usd"] == pytest.approx(0.11 * call_count)
    assert experiment["summary"]["metric_version"] == "deterministic-v2"
    for row in experiment["security_results"]:
        assert row["evidence"]["usage"] == {
            "input_tokens": 100, "output_tokens": 20, "cost_usd": 0.11,
            "token_usage_source": {
                "prompt_tokens": "estimated", "completion_tokens": "reported",
            },
        }

    gate = client.post(
        "/api/v1/experiments/%s/gate" % experiment["id"],
        json={
            "retrieval_recall_at_k": None, "answer_correctness": None,
            "citation_support": None, "hallucination_rate": None,
            "security_pass_rate": None, "total_cost_usd": 0.2,
        },
    )
    assert gate.status_code == 200
    assert gate.json()["passed"] is (not include_security)
    assert gate.json()["checks"][0]["actual"] == pytest.approx(0.11 * call_count)
