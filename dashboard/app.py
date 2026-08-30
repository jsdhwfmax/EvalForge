import os
from datetime import datetime

import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

from evalforge.presentation import format_metric

API_BASE = os.getenv("EVALFORGE_API_BASE_URL", "http://localhost:8000").rstrip("/")
if not API_BASE.startswith(("http://", "https://")):
    API_BASE = "http://" + API_BASE

st.set_page_config(page_title="EvalForge", page_icon="⚒️", layout="wide")
st.markdown(
    """
    <style>
    .stApp {background: #f7f8fa;}
    [data-testid="stSidebar"] {background: #101828; color: white;}
    [data-testid="stMetric"] {background: white; border: 1px solid #e4e7ec;
      border-radius: 12px; padding: 14px 18px; box-shadow: 0 2px 8px rgba(16,24,40,.04);}
    .hero {padding: 18px 0 8px;}
    .hero h1 {font-size: 2.2rem; margin: 0; color: #101828;}
    .hero p {color: #667085; margin-top: 5px;}
    .pill {display:inline-block; color:#344054; background:#eaecf0; padding:3px 9px;
      border-radius:999px; font-size:.78rem; margin-right:5px;}
    </style>
    """,
    unsafe_allow_html=True,
)


def api(method, path, **kwargs):
    try:
        response = httpx.request(method, API_BASE + path, timeout=120.0, **kwargs)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        st.error("API request failed (%s): %s" % (exc.response.status_code, detail))
    except httpx.HTTPError as exc:
        st.error("Cannot reach EvalForge API at %s: %s" % (API_BASE, exc))
    return None


with st.sidebar:
    st.markdown("## ⚒️ EvalForge")
    st.caption("RAG quality, measured")
    health = api("GET", "/health")
    if health:
        st.success("API online · %s" % health["database"])
        st.caption("v%s" % health["version"])
    else:
        st.warning("API offline")
    st.divider()
    st.markdown("**Workflow**")
    st.caption("1. Import a dataset\n\n2. Create configurations\n\n3. Run and compare")

st.markdown(
    '<div class="hero"><h1>Evaluation workspace</h1>'
    "<p>Compare retrieval, answer quality, grounding, security, latency, and cost.</p></div>",
    unsafe_allow_html=True,
)

overview_tab, run_tab, release_tab, dataset_tab, security_tab = st.tabs(
    ["Overview", "Run experiment", "Release gate", "Dataset", "Security"]
)

experiments = api("GET", "/api/v1/experiments") or []
configs = api("GET", "/api/v1/configs") or []
documents = api("GET", "/api/v1/documents") or []
test_cases = api("GET", "/api/v1/test-cases") or []

with overview_tab:
    if not experiments:
        st.info("No experiments yet. Load the demo dataset and run the first comparison.")
        st.code("evalforge seed && evalforge run baseline_top1", language="bash")
    else:
        latest = experiments[0]
        summary = latest.get("summary", {})
        cols = st.columns(6)
        metrics = [
            ("Recall@K", summary.get("retrieval_recall_at_k"), ".1%"),
            ("Correctness", summary.get("answer_correctness"), ".1%"),
            ("Citation support", summary.get("citation_support"), ".1%"),
            ("Hallucination", summary.get("hallucination_rate"), ".1%"),
            ("P50-ish latency", summary.get("latency_ms"), ".1f ms"),
            ("Security pass", summary.get("security_pass_rate"), ".1%"),
        ]
        for column, (label, value, fmt) in zip(cols, metrics):
            column.metric(label, format_metric(value, fmt))

        rows = []
        config_names = {item["id"]: item["name"] for item in configs}
        for experiment in experiments:
            values = experiment.get("summary", {})
            rows.append(
                {
                    "Experiment": experiment["name"],
                    "Configuration": config_names.get(
                        experiment["config_id"], experiment["config_id"]
                    ),
                    "Recall@K": values.get("retrieval_recall_at_k", 0),
                    "Correctness": values.get("answer_correctness", 0),
                    "Citation support": values.get("citation_support", 0),
                    "Groundedness": 1 - values.get("hallucination_rate", 0),
                    "Security": values.get("security_pass_rate") or 0,
                    "Latency (ms)": values.get("latency_ms", 0),
                    "Cost (USD)": values.get("total_cost_usd", 0),
                    "Created": experiment["created_at"],
                }
            )
        frame = pd.DataFrame(rows)
        chart_data = frame.melt(
            id_vars=["Experiment", "Configuration"],
            value_vars=["Recall@K", "Correctness", "Citation support", "Groundedness", "Security"],
            var_name="Metric",
            value_name="Score",
        )
        figure = px.bar(
            chart_data,
            x="Metric",
            y="Score",
            color="Configuration",
            barmode="group",
            range_y=[0, 1],
            color_discrete_sequence=["#7F56D9", "#12B76A", "#2E90FA", "#F79009"],
        )
        figure.update_layout(
            title="Configuration comparison",
            plot_bgcolor="white",
            paper_bgcolor="white",
            legend_title_text="",
        )
        st.plotly_chart(figure, use_container_width=True)
        st.dataframe(frame, width="stretch", hide_index=True)

        selected_name = st.selectbox(
            "Inspect test-level results", [item["name"] for item in experiments]
        )
        selected = next(item for item in experiments if item["name"] == selected_name)
        fingerprint = selected.get("summary", {}).get("dataset_fingerprint")
        if fingerprint:
            st.caption(
                "Dataset fingerprint: `%s` · Metrics: `%s`"
                % (
                    fingerprint,
                    selected.get("summary", {}).get("metric_version", "unknown"),
                )
            )
        detail_rows = []
        questions = {item["id"]: item["question"] for item in test_cases}
        for result in selected.get("results", []):
            detail_rows.append(
                {
                    "Question": questions.get(result["test_case_id"], result["test_case_id"]),
                    "Answer": result["answer"],
                    "Recall@K": result["retrieval_recall_at_k"],
                    "Correctness": result["answer_correctness"],
                    "Citations": result["citation_support"],
                    "Hallucination": result["hallucination_rate"],
                    "Latency (ms)": round(result["latency_ms"], 2),
                    "Cost (USD)": result["cost_usd"],
                }
            )
        st.dataframe(pd.DataFrame(detail_rows), width="stretch", hide_index=True)

with run_tab:
    st.subheader("Run a reproducible comparison")
    if not configs or not test_cases:
        st.warning("Import a dataset and create at least one configuration first.")
    else:
        label_to_id = {item["name"]: item["id"] for item in configs}
        with st.form("run_experiment"):
            name = st.text_input(
                "Experiment name", value="Evaluation %s" % datetime.now().strftime("%Y-%m-%d %H:%M")
            )
            selected_labels = st.multiselect(
                "Configurations", list(label_to_id), default=list(label_to_id)[:2]
            )
            include_security = st.checkbox("Run adversarial security suite", value=True)
            submitted = st.form_submit_button("Run evaluation", type="primary")
        if submitted:
            if not selected_labels:
                st.warning("Choose at least one configuration.")
            else:
                with st.spinner("Running retrieval, generation, scoring, and security checks…"):
                    result = api(
                        "POST",
                        "/api/v1/experiments/run",
                        json={
                            "name": name,
                            "config_ids": [label_to_id[label] for label in selected_labels],
                            "include_security": include_security,
                        },
                    )
                if result:
                    st.success(
                        "Completed %s experiment run(s). Refreshing…" % len(result["experiments"])
                    )
                    st.rerun()

    with st.expander("Add a configuration"):
        with st.form("new_config"):
            config_name = st.text_input("Name", value="BM25 · top 5")
            retrieval_method = st.selectbox("Retrieval", ["bm25", "hybrid", "vector"])
            top_k = st.slider("Top K", 1, 10, 5)
            provider = st.selectbox("Provider", ["local", "openai_compatible"])
            model = st.text_input("Model", value="extractive-v1")
            api_base = st.text_input("API base URL", value="")
            created = st.form_submit_button("Create configuration")
        if created:
            result = api(
                "POST",
                "/api/v1/configs",
                json={
                    "name": config_name,
                    "retrieval_method": retrieval_method,
                    "top_k": top_k,
                    "provider": provider,
                    "model": model,
                    "api_base": api_base,
                },
            )
            if result:
                st.success("Configuration created.")
                st.rerun()

with release_tab:
    st.subheader("Make a release decision")
    st.caption(
        "Compare a candidate with its baseline, then enforce explicit quality thresholds. "
        "The same gate runs from the CLI and GitHub Actions."
    )
    if not experiments:
        st.info("Run an experiment before applying a release gate.")
    else:
        experiment_labels = {
            "%s · %s" % (item["name"], item["id"][:8]): item["id"]
            for item in experiments
            if item["status"] == "completed"
        }
        if len(experiment_labels) >= 2:
            labels = list(experiment_labels)
            compare_left, compare_right = st.columns(2)
            baseline_label = compare_left.selectbox(
                "Baseline experiment", labels, index=min(1, len(labels) - 1)
            )
            candidate_label = compare_right.selectbox("Candidate experiment", labels, index=0)
            if st.button("Compare baseline and candidate"):
                comparison = api(
                    "GET",
                    "/api/v1/experiments/compare",
                    params={
                        "baseline_id": experiment_labels[baseline_label],
                        "candidate_id": experiment_labels[candidate_label],
                    },
                )
                if comparison:
                    st.session_state["comparison_report"] = comparison
            comparison = st.session_state.get("comparison_report")
            if comparison:
                delta_a, delta_b, delta_c = st.columns(3)
                delta_a.metric("Improvements", comparison["improvements"])
                delta_b.metric("Regressions", comparison["regressions"])
                delta_c.metric(
                    "Comparable dataset",
                    "Yes" if comparison["dataset_fingerprint_match"] else "No",
                )
                comparison_rows = []
                for _metric, values in comparison["metrics"].items():
                    comparison_rows.append(
                        {
                            "Metric": values["label"],
                            "Baseline": values["baseline"],
                            "Candidate": values["candidate"],
                            "Delta": values["delta"],
                            "Direction": values["direction"],
                            "Verdict": values["verdict"],
                        }
                    )
                st.dataframe(pd.DataFrame(comparison_rows), width="stretch", hide_index=True)
        elif experiment_labels:
            st.info("Run two configurations to unlock baseline/candidate comparison.")

        if experiment_labels:
            st.divider()
            st.markdown("#### Release thresholds")
            gate_experiment_label = st.selectbox("Experiment to gate", list(experiment_labels))
            gate_a, gate_b, gate_c = st.columns(3)
            min_recall = gate_a.number_input("Minimum Recall@K", 0.0, 1.0, 0.8, 0.05)
            min_correctness = gate_b.number_input("Minimum correctness", 0.0, 1.0, 0.5, 0.05)
            min_citations = gate_c.number_input("Minimum citation support", 0.0, 1.0, 0.8, 0.05)
            gate_d, gate_e, gate_f = st.columns(3)
            max_hallucination = gate_d.number_input(
                "Maximum hallucination", 0.0, 1.0, 0.1, 0.05
            )
            min_security = gate_e.number_input(
                "Minimum security pass", 0.0, 1.0, 1.0, 0.05
            )
            max_latency = gate_f.number_input(
                "Maximum mean latency (ms)", 0.0, value=5000.0
            )
            enforce_cost = st.checkbox("Enforce a total cost ceiling")
            max_cost = st.number_input(
                "Maximum total cost (USD)",
                0.0,
                value=1.0,
                step=0.01,
                disabled=not enforce_cost,
            )
            if st.button("Evaluate release gate", type="primary"):
                gate_result = api(
                    "POST",
                    "/api/v1/experiments/%s/gate" % experiment_labels[gate_experiment_label],
                    json={
                        "retrieval_recall_at_k": min_recall,
                        "answer_correctness": min_correctness,
                        "citation_support": min_citations,
                        "hallucination_rate": max_hallucination,
                        "security_pass_rate": min_security,
                        "latency_ms": max_latency,
                        "total_cost_usd": max_cost if enforce_cost else None,
                    },
                )
                if gate_result:
                    st.session_state["gate_result"] = gate_result
            gate_result = st.session_state.get("gate_result")
            if gate_result:
                if gate_result["passed"]:
                    st.success("PASS · This experiment satisfies every release threshold.")
                else:
                    st.error("FAIL · At least one metric blocks this release.")
                st.dataframe(
                    pd.DataFrame(gate_result["checks"]), width="stretch", hide_index=True
                )
        else:
            st.info("No completed experiment is available for a release decision.")

with dataset_tab:
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Documents", len(documents))
    col_b.metric("Test cases", len(test_cases))
    col_c.metric("Configurations", len(configs))
    uploaded = st.file_uploader("Import EvalForge JSON", type=["json"])
    if uploaded and st.button("Import dataset", type="primary"):
        result = api(
            "POST",
            "/api/v1/datasets/upload",
            files={"file": (uploaded.name, uploaded.getvalue(), "application/json")},
        )
        if result:
            st.success(
                "Imported %(documents_created)s documents and %(test_cases_created)s test cases; "
                "%(skipped)s duplicates skipped." % result
            )
            st.rerun()
    st.markdown("#### Documents")
    st.dataframe(
        pd.DataFrame(
            [
                {"ID": item["id"], "Title": item["title"], "Source": item["source"]}
                for item in documents
            ]
        ),
        width="stretch",
        hide_index=True,
    )
    st.markdown("#### Golden test cases")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "ID": item["id"],
                    "Question": item["question"],
                    "Relevant docs": ", ".join(item["relevant_document_ids"]),
                    "Tags": ", ".join(item["tags"]),
                }
                for item in test_cases
            ]
        ),
        width="stretch",
        hide_index=True,
    )

with security_tab:
    security_rows = []
    experiment_names = {item["id"]: item["name"] for item in experiments}
    for experiment in experiments:
        for result in experiment.get("security_results", []):
            security_rows.append(
                {
                    "Experiment": experiment_names[experiment["id"]],
                    "Category": result["category"],
                    "Case": result["case_id"],
                    "Passed": result["passed"],
                    "Response": result["response"],
                    "Latency (ms)": round(result["latency_ms"], 2),
                }
            )
    if security_rows:
        security_frame = pd.DataFrame(security_rows)
        category_summary = (
            security_frame.groupby("Category", as_index=False)["Passed"]
            .mean()
            .rename(columns={"Passed": "Pass rate"})
        )
        security_chart = px.bar(
            category_summary,
            x="Category",
            y="Pass rate",
            range_y=[0, 1],
            color="Category",
            color_discrete_sequence=["#12B76A", "#F79009", "#7F56D9"],
        )
        security_chart.update_layout(showlegend=False, plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(security_chart, use_container_width=True)
        st.dataframe(security_frame, width="stretch", hide_index=True)
    else:
        st.info("Run an experiment with the adversarial suite enabled to see security results.")
