from types import SimpleNamespace

import pytest

from evalforge.metrics import (
    aggregate_results,
    answer_correctness,
    citation_support,
    hallucination_rate,
    retrieval_recall_at_k,
)
from evalforge.presentation import format_metric


def test_retrieval_recall_at_k():
    assert retrieval_recall_at_k(["a", "b"], ["a", "c"]) == 0.5
    assert retrieval_recall_at_k([], []) == 1.0


def test_correctness_uses_token_f1_and_ignores_citations():
    assert answer_correctness("Refund in 30 days. [doc:refund]", "Refund in 30 days.") == 1.0
    assert answer_correctness("unrelated", "refund window") == 0.0
    assert answer_correctness("", "refund window") == 0.0


def test_citation_support_and_hallucination():
    document = SimpleNamespace(id="refund", content="Refunds are available for thirty days.")
    answer = "Refunds are available for thirty days. [doc:refund]"
    assert citation_support(answer, ["refund"], [document]) == 1.0
    assert citation_support(answer, ["missing"], [document]) == 0.0
    assert citation_support(answer, [], [document]) == 0.0
    assert hallucination_rate(answer, [document]) == 0.0
    assert hallucination_rate("Refunds arrive by carrier pigeon.", [document]) > 0.0
    assert hallucination_rate("I don't have enough information in the supplied context.", []) == 0.0


def test_aggregate_results():
    result = SimpleNamespace(
        retrieval_recall_at_k=1.0,
        answer_correctness=0.8,
        citation_support=0.9,
        hallucination_rate=0.1,
        latency_ms=12.345,
        cost_usd=0.001,
        input_tokens=10,
        output_tokens=5,
    )
    security = SimpleNamespace(passed=True)
    summary = aggregate_results([result], [security])
    assert summary["answer_correctness"] == 0.8
    assert summary["latency_ms"] == 12.35
    assert summary["security_pass_rate"] == 1.0
    assert aggregate_results([], [])["security_pass_rate"] is None


@pytest.mark.parametrize(
    ("value", "format_spec", "expected"),
    [(1.0, ".1%", "100.0%"), (12.345, ".1f ms", "12.3 ms"), (None, ".1%", "—")],
)
def test_dashboard_metric_formatting(value, format_spec, expected):
    assert format_metric(value, format_spec) == expected
