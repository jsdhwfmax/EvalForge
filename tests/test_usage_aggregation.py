from types import SimpleNamespace

import pytest

from evalforge.metrics import aggregate_results


def quality_result(cost_usd=0.2):
    return SimpleNamespace(
        retrieval_recall_at_k=0.8, answer_correctness=0.7, citation_support=1.0,
        hallucination_rate=0.0, latency_ms=25.0, input_tokens=100,
        output_tokens=20, cost_usd=cost_usd,
    )


def security_result(cost_usd=0.3):
    return SimpleNamespace(
        passed=True, latency_ms=20000.0,
        evidence={"usage": {"input_tokens": 200, "output_tokens": 40, "cost_usd": cost_usd}},
    )


def test_aggregate_counts_security_usage_without_changing_quality_latency():
    summary = aggregate_results([quality_result()], [security_result()])

    assert summary["total_cost_usd"] == 0.5
    assert summary["input_tokens"] == 300
    assert summary["output_tokens"] == 60
    assert summary["latency_ms"] == 25.0
    assert summary["test_cases"] == 1
    assert summary["security_cases"] == 1


def test_total_cost_rounds_once_after_including_security_calls():
    summary = aggregate_results([quality_result(0.000000004)], [security_result(0.000000004)])
    assert summary["total_cost_usd"] == pytest.approx(0.00000001)


def test_security_usage_is_counted_without_quality_rows():
    summary = aggregate_results([], [security_result()])
    assert summary["total_cost_usd"] == 0.3
    assert summary["input_tokens"] == 200
    assert summary["output_tokens"] == 40
    assert summary["latency_ms"] == 0.0
