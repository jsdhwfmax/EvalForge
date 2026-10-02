import json

import pytest


@pytest.mark.parametrize("upload", [False, True])
def test_duplicate_ids_in_one_import_are_skipped_without_losing_other_records(client, upload):
    document = {"id": "shared", "title": "Original", "content": "Original content"}
    test_case = {
        "id": "shared",
        "question": "Original question?",
        "expected_answer": "Original answer",
        "relevant_document_ids": ["shared"],
    }
    payload = {
        "documents": [document, {**document, "content": "Duplicate"}, {**document, "id": "new"}],
        "test_cases": [test_case, {**test_case, "question": "Duplicate?"}],
    }

    def submit():
        if upload:
            return client.post(
                "/api/v1/datasets/upload",
                files={"file": ("dataset.json", json.dumps(payload), "application/json")},
            )
        return client.post("/api/v1/datasets/import", json=payload)

    imported = submit()
    assert imported.status_code == 200
    assert imported.json() == {"documents_created": 2, "test_cases_created": 1, "skipped": 2}
    documents = {item["id"]: item for item in client.get("/api/v1/documents").json()}
    assert documents["shared"]["content"] == "Original content"
    cases = client.get("/api/v1/test-cases").json()
    assert len(cases) == 1
    assert cases[0]["question"] == "Original question?"
    assert submit().json() == {"documents_created": 0, "test_cases_created": 0, "skipped": 5}


def test_import_without_ids_creates_independent_records(client):
    document = {"title": "Untitled", "content": "Repeated content"}
    response = client.post("/api/v1/datasets/import", json={"documents": [document, document]})
    assert response.status_code == 200
    assert response.json() == {"documents_created": 2, "test_cases_created": 0, "skipped": 0}
    documents = client.get("/api/v1/documents").json()
    assert len({item["id"] for item in documents}) == 2
