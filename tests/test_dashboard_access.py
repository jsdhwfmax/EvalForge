from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pytest
from pydantic import SecretStr
from streamlit.testing.v1 import AppTest

from evalforge.config import get_settings

DASHBOARD = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
ACCESS_KEY = "test-dashboard-maintainer-access-key"


@pytest.fixture
def protected_dashboard(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "access_key", SecretStr(ACCESS_KEY))
    calls = []

    def request(method, url, **kwargs):
        calls.append(kwargs)
        payload = (
            {"database": "sqlite", "version": "test"}
            if urlsplit(url).path == "/health"
            else []
        )
        return httpx.Response(200, json=payload, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "request", request)
    return AppTest.from_file(str(DASHBOARD), default_timeout=10), calls, settings


def sign_in(app, key):
    app.text_input(key="_access_key_input").set_value(key)
    next(button for button in app.button if button.label == "Sign in").click().run()
    assert not app.exception


def test_dashboard_never_fetches_private_data_before_successful_sign_in(protected_dashboard):
    app, calls, _ = protected_dashboard
    app.run()
    assert not app.exception
    assert calls == []
    assert len(app.tabs) == 0

    sign_in(app, "wrong-key")
    assert calls == []
    assert app.error[0].value == "The access key is not valid."
    assert app.text_input(key="_access_key_input").value == ""

    sign_in(app, ACCESS_KEY)
    assert len(app.tabs) == 5
    assert len(calls) == 5
    assert all(call["headers"]["Authorization"] == "Bearer " + ACCESS_KEY for call in calls)
    assert "_access_key_input" not in app.session_state
    assert ACCESS_KEY not in repr(app.session_state)


def test_sign_out_clears_private_session_state_and_stops_data_fetching(protected_dashboard):
    app, calls, _ = protected_dashboard
    app.run()
    sign_in(app, ACCESS_KEY)
    app.session_state["gate_result"] = {"passed": True}
    calls.clear()

    next(button for button in app.button if button.label == "Sign out").click().run()

    assert not app.exception
    assert not app.tabs
    assert calls == []
    assert "gate_result" not in app.session_state
    assert "_access_fingerprint" not in app.session_state


def test_rotating_key_requires_sign_in_again(protected_dashboard, monkeypatch):
    app, calls, settings = protected_dashboard
    app.run()
    sign_in(app, ACCESS_KEY)
    calls.clear()
    monkeypatch.setattr(settings, "access_key", SecretStr("rotated-maintainer-access-key"))

    app.run()

    assert not app.exception
    assert calls == []
    assert not app.tabs
    assert app.title[0].value == "Sign in to EvalForge"


@pytest.mark.parametrize("key", [None, SecretStr(""), SecretStr("   ")])
def test_production_dashboard_without_key_fails_closed(protected_dashboard, monkeypatch, key):
    app, calls, settings = protected_dashboard
    monkeypatch.setattr(settings, "access_key", key)

    app.run()

    assert not app.exception
    assert calls == []
    assert not app.tabs
    assert app.error[0].value.startswith("Dashboard access is not configured")
