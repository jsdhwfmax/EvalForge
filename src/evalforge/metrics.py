import re
from collections import Counter
from statistics import mean
from typing import Any, Dict, Iterable, Sequence

from evalforge.retrieval import tokenize


def clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def retrieval_recall_at_k(retrieved_ids: Sequence[str], relevant_ids: Sequence[str]) -> float:
    relevant = set(relevant_ids)
    if not relevant:
        return 1.0
    return clamp(len(relevant & set(retrieved_ids)) / len(relevant))


def answer_correctness(answer: str, expected_answer: str) -> float:
    """Token F1: deterministic, transparent, and suitable as a CI baseline."""
    answer_tokens = Counter(tokenize(re.sub(r"\[doc:[^\]]+\]", "", answer)))
    expected_tokens = Counter(tokenize(expected_answer))
    if not answer_tokens or not expected_tokens:
        return 0.0
    common = sum((answer_tokens & expected_tokens).values())
    precision = common / sum(answer_tokens.values())
    recall = common / sum(expected_tokens.values())
    if precision + recall == 0:
        return 0.0
    return clamp(2 * precision * recall / (precision + recall))


def _content_tokens(documents: Iterable[Any]) -> set:
    tokens = set()
    for document in documents:
        tokens.update(tokenize(document.content))
    return tokens


def citation_support(answer: str, citation_ids: Sequence[str], documents: Sequence[Any]) -> float:
    if not citation_ids:
        return 0.0
    by_id = {document.id: document for document in documents}
    plain_answer = re.sub(r"\[doc:[^\]]+\]", "", answer)
    answer_tokens = set(tokenize(plain_answer))
    if not answer_tokens:
        return 0.0
    support = []
    for citation_id in citation_ids:
        document = by_id.get(citation_id)
        if document is None:
            support.append(0.0)
            continue
        doc_tokens = set(tokenize(document.content))
        coverage = len(answer_tokens & doc_tokens) / len(answer_tokens)
        support.append(1.0 if coverage >= 0.25 else coverage / 0.25)
    return clamp(mean(support))


def hallucination_rate(answer: str, documents: Sequence[Any]) -> float:
    plain_answer = re.sub(r"\[doc:[^\]]+\]", "", answer)
    answer_tokens = tokenize(plain_answer)
    if not answer_tokens:
        return 0.0
    if (
        "don't have enough information" in plain_answer.lower()
        or "can't comply" in plain_answer.lower()
    ):
        return 0.0
    context_tokens = _content_tokens(documents)
    unsupported = sum(1 for token in answer_tokens if token not in context_tokens)
    return clamp(unsupported / len(answer_tokens))


def aggregate_results(results: Sequence[Any], security_results: Sequence[Any]) -> Dict[str, Any]:
    quality: Dict[str, Any]
    if not results:
        quality = {
            "retrieval_recall_at_k": 0.0,
            "answer_correctness": 0.0,
            "citation_support": 0.0,
            "hallucination_rate": 0.0,
            "latency_ms": 0.0,
            "total_cost_usd": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
        }
    else:
        quality = {
            "retrieval_recall_at_k": round(mean(row.retrieval_recall_at_k for row in results), 4),
            "answer_correctness": round(mean(row.answer_correctness for row in results), 4),
            "citation_support": round(mean(row.citation_support for row in results), 4),
            "hallucination_rate": round(mean(row.hallucination_rate for row in results), 4),
            "latency_ms": round(mean(row.latency_ms for row in results), 2),
            "total_cost_usd": round(sum(row.cost_usd for row in results), 8),
            "input_tokens": sum(row.input_tokens for row in results),
            "output_tokens": sum(row.output_tokens for row in results),
        }
    quality["test_cases"] = len(results)
    quality["security_cases"] = len(security_results)
    quality["security_pass_rate"] = (
        round(sum(row.passed for row in security_results) / len(security_results), 4)
        if security_results
        else None
    )
    return quality
