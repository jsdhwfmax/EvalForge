from types import SimpleNamespace

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
