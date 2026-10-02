from types import SimpleNamespace

import numpy as np
import pytest

from evalforge.retrieval import Retriever, cosine_similarity, hashing_embedding, tokenize


def document(identifier, title, content):
    return SimpleNamespace(
        id=identifier,
        title=title,
        content=content,
        embedding=hashing_embedding(title + " " + content),
    )


def test_tokenize_supports_english_and_chinese():
    assert tokenize("What is the refund window? 退款期限") == [
        "refund",
        "window",
        "退",
        "款",
        "期",
        "限",
    ]


def test_embedding_is_deterministic_and_normalized():
    first = hashing_embedding("refund within thirty days")
    second = hashing_embedding("refund within thirty days")
    assert first == second
    assert cosine_similarity(first, second) == pytest.approx(1.0)


@pytest.mark.parametrize("method", ["vector", "hybrid"])
def test_retrieval_accepts_numpy_vectors_returned_by_supported_pgvector_versions(method):
    docs = [
        document("refund", "Refunds", "Request refunds within thirty days."),
        document("password", "Passwords", "Reset links expire in twenty minutes."),
    ]
    query = "When does the password reset link expire?"
    expected = Retriever(docs).search(query, top_k=2, method=method)
    for item in docs:
        item.embedding = np.asarray(item.embedding, dtype=np.float32)

    actual = Retriever(docs).search(query, top_k=2, method=method)

    assert [row.document.id for row in actual] == [row.document.id for row in expected]
    assert [row.score for row in actual] == pytest.approx([row.score for row in expected])


def test_cosine_similarity_handles_empty_numpy_vectors():
    assert cosine_similarity(np.array([]), np.array([1.0])) == 0.0
    assert cosine_similarity(np.array([1.0]), np.array([])) == 0.0


@pytest.mark.parametrize("method", ["bm25", "vector", "hybrid"])
def test_retriever_ranks_relevant_document(method):
    docs = [
        document("refund", "Refunds", "Request refunds within thirty days."),
        document("password", "Passwords", "Reset links expire in twenty minutes."),
    ]
    result = Retriever(docs).search("When does the password reset link expire?", 1, method)
    assert result[0].document.id == "password"


def test_retriever_handles_empty_and_invalid_method():
    assert Retriever([]).search("anything") == []
    docs = [document("one", "One", "Some text")]
    with pytest.raises(ValueError, match="Unsupported retrieval"):
        Retriever(docs).search("text", method="unknown")


@pytest.mark.parametrize(
    "query, expected_scores, expected_order",
    [
        (
            "refund refund 退款",
            [2.7530648058972926, 0.6203042503282302, 0.0, 2.7530648058972926],
            ["m-refund", "z-refund", "a-reset", "empty"],
        ),
        (
            "reset",
            [0.0, 1.5535132959044335, 0.0, 0.0],
            ["a-reset", "empty", "m-refund", "z-refund"],
        ),
        ("what are the", [0.0] * 4, ["a-reset", "empty", "m-refund", "z-refund"]),
        ("missing-token", [0.0] * 4, ["a-reset", "empty", "m-refund", "z-refund"]),
        ("", [0.0] * 4, ["a-reset", "empty", "m-refund", "z-refund"]),
    ],
)
def test_bm25_scores_and_ties_preserve_reference_results(query, expected_scores, expected_order):
    docs = [
        document("z-refund", "Refund", "refund refund 退款"),
        document("a-reset", "Reset", "password reset 退款"),
        document("empty", "the", "and is"),
        document("m-refund", "Refund", "refund refund 退款"),
    ]
    retriever = Retriever(docs)

    # Reference scores cover repeated query terms, term frequency, and unequal document lengths.
    assert retriever._bm25_scores(query) == pytest.approx(expected_scores)
    assert [row.document.id for row in retriever.search(query, top_k=4)] == expected_order
    # Reusing the index for a different query must not alter the original scores.
    retriever.search("password refund", method="hybrid")
    assert retriever._bm25_scores(query) == pytest.approx(expected_scores)


@pytest.mark.parametrize("query", ["", "the and is", "refund"])
def test_bm25_handles_corpora_without_searchable_tokens(query):
    assert Retriever([])._bm25_scores(query) == []
    retriever = Retriever([document("z", "", ""), document("a", "the", "and is")])
    assert retriever._bm25_scores(query) == [0.0, 0.0]
    assert [row.document.id for row in retriever.search(query)] == ["a", "z"]


def test_hybrid_keeps_input_order_for_identical_ranked_documents():
    docs = [
        document("z-refund", "Refund", "refund refund 退款"),
        document("a-reset", "Reset", "password reset 退款"),
        document("empty", "the", "and is"),
        document("m-refund", "Refund", "refund refund 退款"),
    ]
    result = Retriever(docs).search("refund refund 退款", top_k=4, method="hybrid")
    assert [row.document.id for row in result] == ["z-refund", "m-refund", "a-reset", "empty"]
