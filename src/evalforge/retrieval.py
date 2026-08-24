import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, List, Sequence

TOKEN_RE = re.compile(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "with",
}


def tokenize(text: str) -> List[str]:
    return [token for token in TOKEN_RE.findall(text.lower()) if token not in STOP_WORDS]


def hashing_embedding(text: str, dimensions: int = 256) -> List[float]:
    vector = [0.0] * dimensions
    for token in tokenize(text):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        index = value % dimensions
        sign = 1.0 if value & 1 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right:
        return 0.0
    return sum(a * b for a, b in zip(left, right))


@dataclass
class RetrievedDocument:
    document: Any
    score: float


class Retriever:
    def __init__(self, documents: Iterable[Any]):
        self.documents = list(documents)
        self._tokens = [
            tokenize(document.title + " " + document.content) for document in self.documents
        ]
        self._doc_freq: Counter = Counter()
        for tokens in self._tokens:
            self._doc_freq.update(set(tokens))
        self._avg_length = (
            sum(len(tokens) for tokens in self._tokens) / len(self._tokens) if self._tokens else 1.0
        )

    def _bm25_scores(self, query: str) -> List[float]:
        query_tokens = tokenize(query)
        total_docs = len(self.documents)
        scores = []
        k1, b = 1.5, 0.75
        for tokens in self._tokens:
            counts = Counter(tokens)
            score = 0.0
            for token in query_tokens:
                frequency = counts[token]
                if not frequency:
                    continue
                document_frequency = self._doc_freq[token]
                idf = math.log(
                    1 + (total_docs - document_frequency + 0.5) / (document_frequency + 0.5)
                )
                denominator = frequency + k1 * (1 - b + b * len(tokens) / self._avg_length)
                score += idf * (frequency * (k1 + 1)) / denominator
            scores.append(score)
        return scores

    def _vector_scores(self, query: str) -> List[float]:
        query_vector = hashing_embedding(query)
        return [cosine_similarity(query_vector, document.embedding) for document in self.documents]

    @staticmethod
    def _rank_normalize(scores: Sequence[float]) -> List[float]:
        order = sorted(range(len(scores)), key=lambda index: scores[index], reverse=True)
        normalized = [0.0] * len(scores)
        for rank, index in enumerate(order):
            normalized[index] = 1.0 / (60.0 + rank + 1)
        return normalized

    def search(self, query: str, top_k: int = 3, method: str = "bm25") -> List[RetrievedDocument]:
        if not self.documents:
            return []
        if method == "bm25":
            scores = self._bm25_scores(query)
        elif method == "vector":
            scores = self._vector_scores(query)
        elif method == "hybrid":
            lexical = self._rank_normalize(self._bm25_scores(query))
            semantic = self._rank_normalize(self._vector_scores(query))
            scores = [0.65 * left + 0.35 * right for left, right in zip(lexical, semantic)]
        else:
            raise ValueError("Unsupported retrieval method: %s" % method)

        ranked = sorted(
            (RetrievedDocument(document, score) for document, score in zip(self.documents, scores)),
            key=lambda result: (-result.score, result.document.id),
        )
        return ranked[: min(top_k, len(ranked))]
