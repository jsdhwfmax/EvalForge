from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

DASHBOARD = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"


def widget(elements, label):
    return next(element for element in elements if element.label == label)


@pytest.fixture
def dashboard(monkeypatch):
    experiments = []
    for identifier in ("first-run", "second-run"):
        experiments.append(
            {
                "id": identifier,
                "name": "Repeated experiment name",
                "config_id": "config",
                "status": "completed",
                "summary": {"security_pass_rate": 1.0},
                "created_at": "2026-01-01T00:00:00Z",
                "results": [
                    {
                        "test_case_id": "test-case",
                        "answer": "Answer from " + identifier,
                        "retrieval_recall_at_k": 1.0,
                        "answer_correctness": 1.0,
                        "citation_support": 1.0,
                        "hallucination_rate": 0.0,
                        "latency_ms": 1.0,
                        "cost_usd": 0.0,
                    }
                ],
                "security_results": [],
            }
        )
    responses = {
        "/health": {"database": "sqlite", "version": "test"},
        "/api/v1/experiments": experiments,
        "/api/v1/configs": [{"id": "config", "name": "Local"}],
        "/api/v1/documents": [],
        "/api/v1/test-cases": [{
            "id": "test-case", "question": "Question", "relevant_document_ids": [], "tags": []
        }],
    }
    calls = []
    failures = set()

    def request(method, url, **kwargs):
        path = urlsplit(url).path
        calls.append((method, path, kwargs))
        if path in failures:
            return httpx.Response(
                503, json={"detail": "Unavailable"}, request=httpx.Request(method, url)
            )
        if path.endswith("/compare"):
            result = {
                "baseline_experiment_id": kwargs["params"]["baseline_id"],
                "candidate_experiment_id": kwargs["params"]["candidate_id"],
                "improvements": 1,
                "regressions": 0,
                "dataset_fingerprint_match": True,
                "metric_version_match": True,
                "comparable": True,
                "incompatibilities": [],
                "metrics": {},
            }
            result.update(responses.get("comparison_override", {}))
        elif path.endswith("/gate"):
            result = {"experiment_id": path.split("/")[-2], "passed": True, "checks": []}
        else:
            result = responses[path]
        return httpx.Response(200, json=result, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "request", request)
    app = AppTest.from_file(str(DASHBOARD), default_timeout=10).run()
    assert not app.exception
    return app, calls, failures, responses


def test_duplicate_names_inspect_the_selected_experiment(dashboard):
    app, _, _, _ = dashboard

    widget(app.selectbox, "Inspect test-level results").set_value("second-run").run()

    assert not app.exception
    results = next(item.value for item in app.dataframe if "Answer" in item.value.columns)
    assert list(results["Answer"]) == ["Answer from second-run"]


@pytest.mark.parametrize("selector", ["Baseline experiment", "Candidate experiment"])
def test_comparison_is_cleared_when_either_experiment_changes(dashboard, selector):
    app, calls, _, _ = dashboard
    widget(app.button, "Compare baseline and candidate").click().run()
    assert app.session_state["comparison_report"]["improvements"] == 1
    assert app.session_state["comparison_request"] == calls[-1][2]["params"]
    assert any(item.label == "Improvements" for item in app.metric)

    selection = widget(app.selectbox, selector)
    selection.set_value("first-run" if selection.value == "second-run" else "second-run").run()

    assert not app.exception
    assert "comparison_report" not in app.session_state
    assert not any(item.label == "Improvements" for item in app.metric)


@pytest.mark.parametrize("change", ["experiment", "threshold", "cost"])
def test_gate_pass_is_cleared_when_its_request_changes(dashboard, change):
    app, calls, _, _ = dashboard
    widget(app.button, "Evaluate release gate").click().run()
    assert app.session_state["gate_result"]["passed"]
    assert app.session_state["gate_request"]["thresholds"] == calls[-1][2]["json"]
    assert any(item.value.startswith("PASS") for item in app.success)

    if change == "experiment":
        widget(app.selectbox, "Experiment to gate").set_value("second-run").run()
    elif change == "threshold":
        widget(app.number_input, "Minimum correctness").set_value(0.9).run()
    else:
        widget(app.checkbox, "Enforce a total cost ceiling").check().run()

    assert not app.exception
    assert "gate_result" not in app.session_state
    assert not any(item.value.startswith("PASS") for item in app.success)


@pytest.mark.parametrize(
    ("button", "path", "state_key"),
    [
        ("Compare baseline and candidate", "/api/v1/experiments/compare", "comparison_report"),
        ("Evaluate release gate", "/api/v1/experiments/first-run/gate", "gate_result"),
    ],
)
def test_failed_retry_clears_previous_result(dashboard, button, path, state_key):
    app, _, failures, _ = dashboard
    widget(app.button, button).click().run()
    assert state_key in app.session_state
    failures.add(path)

    widget(app.button, button).click().run()

    assert not app.exception
    assert state_key not in app.session_state
    assert any("API request failed (503)" in item.value for item in app.error)


def test_unrelated_widget_change_preserves_matching_gate_result(dashboard):
    app, _, _, _ = dashboard
    widget(app.button, "Evaluate release gate").click().run()

    widget(app.selectbox, "Inspect test-level results").set_value("second-run").run()

    assert not app.exception
    assert app.session_state["gate_result"]["passed"]
    assert any(item.value.startswith("PASS") for item in app.success)


def test_incompatible_metric_versions_show_comparison_warning(dashboard):
    app, _, _, responses = dashboard
    responses["comparison_override"] = {
        "metric_version_match": False,
        "comparable": False,
        "incompatibilities": ["Metric versions do not match; rerun the baseline."],
        "improvements": 0,
        "regressions": 0,
    }

    widget(app.button, "Compare baseline and candidate").click().run()

    assert not app.exception
    assert widget(app.metric, "Comparable evidence").value == "No"
    assert any("Metric versions do not match" in item.value for item in app.warning)


def test_partial_batch_failure_stays_visible_after_refresh(dashboard):
    app, calls, _, responses = dashboard
    failed = dict(responses["/api/v1/experiments"][1])
    failed.update(id="failed-run", status="failed", error="Provider unavailable", summary={})
    responses["/api/v1/experiments/run"] = {
        "experiments": [responses["/api/v1/experiments"][0], failed]
    }
    responses["/api/v1/experiments"] = responses["/api/v1/experiments/run"]["experiments"]

    widget(app.button, "Run evaluation").click().run()

    assert not app.exception
    assert any("1 completed, 1 failed" in item.value for item in app.error)
    assert not any("Last batch" in item.value for item in app.success)
    failed_rows = next(item.value for item in app.dataframe if "Error" in item.value.columns)
    assert failed_rows.iloc[0]["Experiment ID"] == "failed-run"
    overview = next(item.value for item in app.dataframe if "Status" in item.value.columns)
    row = overview[overview["Status"] == "failed"].iloc[0]
    assert all(pd.isna(row[column]) for column in (
        "Recall@K", "Groundedness", "Security", "Cost (USD)"
    ))
    assert sum(method == "POST" and path.endswith("/run") for method, path, _ in calls) == 1
