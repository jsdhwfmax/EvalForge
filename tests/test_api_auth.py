import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from evalforge.api import app
from evalforge.config import get_settings


@pytest.fixture
def protected_api(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "access_key", SecretStr("test-maintainer-access-key"))
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("GET", "/api/v1/documents", None),
        ("GET", "/api/v1/test-cases", None),
        ("GET", "/api/v1/configs", None),
        ("GET", "/api/v1/experiments", None),
        ("GET", "/api/v1/experiments/missing", None),
        (
            "GET",
            "/api/v1/experiments/compare?baseline_id=old&candidate_id=new",
            None,
        ),
        ("POST", "/api/v1/documents", {"title": "Private", "content": "Private data"}),
        ("POST", "/api/v1/test-cases", {"question": "Question", "expected_answer": "Answer"}),
        ("POST", "/api/v1/configs", {"name": "Config"}),
        ("POST", "/api/v1/datasets/import", {}),
        ("POST", "/api/v1/experiments/run", {"name": "Run", "config_ids": ["config"]}),
        ("POST", "/api/v1/experiments/missing/gate", {}),
    ],
)
def test_all_data_routes_require_access(protected_api, method, path, payload):
    response = protected_api.request(method, path, json=payload)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_upload_requires_access(protected_api):
    response = protected_api.post(
        "/api/v1/datasets/upload",
        files={"file": ("dataset.json", b"{}", "application/json")},
    )
    assert response.status_code == 401


@pytest.mark.parametrize("authorization", ["Bearer wrong-key", "Basic unrelated", "Bearer"])
def test_invalid_access_key_does_not_leak_secrets(protected_api, authorization):
    response = protected_api.get("/api/v1/documents", headers={"Authorization": authorization})
    assert response.status_code == 401
    assert "test-maintainer-access-key" not in response.text
    assert "wrong-key" not in response.text


def test_valid_access_key_can_create_and_read_data(protected_api):
    headers = {"Authorization": "Bearer test-maintainer-access-key"}
    response = protected_api.post(
        "/api/v1/documents", headers=headers, json={"title": "Private", "content": "Private data"}
    )
    assert response.status_code == 201
    assert protected_api.get("/api/v1/documents", headers=headers).json()[0]["title"] == "Private"


def test_health_and_openapi_remain_available(protected_api):
    assert protected_api.get("/health").status_code == 200
    schema = protected_api.get("/openapi.json").json()
    assert schema["paths"]["/api/v1/documents"]["get"]["security"] == [{"HTTPBearer": []}]
    assert "security" not in schema["paths"]["/health"]["get"]


@pytest.mark.parametrize("environment", ["production", "prod"])
@pytest.mark.parametrize("key", [None, SecretStr(""), SecretStr("   ")])
def test_production_refuses_startup_without_access_key(monkeypatch, environment, key):
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", environment)
    monkeypatch.setattr(settings, "access_key", key)
    with pytest.raises(ValueError, match="EVALFORGE_ACCESS_KEY must be configured"):
        with TestClient(app):
            pass


def test_production_without_lifespan_still_fails_closed(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "access_key", None)
    response = TestClient(app).get("/api/v1/documents")
    assert response.status_code == 503
    assert response.json() == {"detail": "API access is not configured"}


def test_development_can_keep_local_unauthenticated_workflow(monkeypatch, client):
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "access_key", None)
    assert client.get("/api/v1/documents").status_code == 200


def test_configured_key_also_protects_development(monkeypatch, client):
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "access_key", SecretStr("local-private-key"))
    assert client.get("/api/v1/documents").status_code == 401
    assert client.get(
        "/api/v1/documents", headers={"Authorization": "Bearer local-private-key"}
    ).status_code == 200
