import json
from pathlib import Path

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
    assert (
        experiments[1]["summary"]["retrieval_recall_at_k"]
        >= experiments[0]["summary"]["retrieval_recall_at_k"]
    )

    listed = client.get("/api/v1/experiments")
    assert listed.status_code == 200
    assert len(listed.json()) == 2
    detail = client.get("/api/v1/experiments/%s" % experiments[0]["id"])
    assert detail.status_code == 200


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


def test_missing_config_after_tests_exist(client):
    client.post("/api/v1/datasets/import", json=load_demo())
    response = client.post(
        "/api/v1/experiments/run", json={"name": "Missing", "config_ids": ["not-there"]}
    )
    assert response.status_code == 404
    assert response.json()["detail"]["missing_config_ids"] == ["not-there"]
