from types import SimpleNamespace

from evalforge.gates import (
    compare_experiment_summaries,
    evaluate_quality_gate,
)
from evalforge.reproducibility import config_snapshot, dataset_fingerprint


def test_quality_gate_reports_each_threshold():
    summary = {
        "retrieval_recall_at_k": 0.9,
        "answer_correctness": 0.7,
        "hallucination_rate": 0.05,
        "security_pass_rate": 1.0,
        "total_cost_usd": 0.05,
    }
    result = evaluate_quality_gate(
        summary,
        {
            "retrieval_recall_at_k": 0.8,
            "answer_correctness": 0.8,
            "hallucination_rate": 0.1,
            "security_pass_rate": 1.0,
            "total_cost_usd": 0.1,
            "latency_ms": None,
        },
    )
    assert result["passed"] is False
    assert len(result["checks"]) == 5
    failed = [check for check in result["checks"] if not check["passed"]]
    assert failed[0]["metric"] == "answer_correctness"
    assert failed[0]["operator"] == ">="


def test_comparison_understands_metric_direction_and_fingerprint():
    baseline = {
        "dataset_fingerprint": "same",
        "answer_correctness": 0.6,
        "hallucination_rate": 0.1,
        "latency_ms": 10.0,
    }
    candidate = {
        "dataset_fingerprint": "same",
        "answer_correctness": 0.8,
        "hallucination_rate": 0.2,
        "latency_ms": 8.0,
    }
    result = compare_experiment_summaries("base", baseline, "candidate", candidate)
    assert result["dataset_fingerprint_match"] is True
    assert result["metrics"]["answer_correctness"]["verdict"] == "improved"
    assert result["metrics"]["hallucination_rate"]["verdict"] == "regressed"
    assert result["metrics"]["latency_ms"]["verdict"] == "improved"
    assert result["improvements"] == 2
    assert result["regressions"] == 1


def test_reproducibility_fingerprint_and_config_snapshot():
    documents = [SimpleNamespace(id="doc", title="Title", content="Stable content")]
    tests = [
        SimpleNamespace(
            id="test",
            question="Question?",
            expected_answer="Answer.",
            relevant_document_ids=["doc"],
        )
    ]
    first = dataset_fingerprint(documents, tests)
    second = dataset_fingerprint(list(reversed(documents)), list(reversed(tests)))
    assert first == second
    assert len(first) == 16

    config = SimpleNamespace(
        id="config",
        name="Config",
        provider="local",
        model="extractive-v1",
        system_prompt="Ground answers.",
        retrieval_method="bm25",
        top_k=3,
        temperature=0.0,
        input_cost_per_million=0.0,
        output_cost_per_million=0.0,
    )
    assert config_snapshot(config)["top_k"] == 3
