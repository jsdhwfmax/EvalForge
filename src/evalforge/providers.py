import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence

import httpx

from evalforge.retrieval import tokenize

CITATION_RE = re.compile(r"\[doc:([^\]]+)\]")
SECURITY_RE = re.compile(
    r"ignore (all|any|the|your|previous)|system prompt|developer message|admin(istrator)? "
    r"(mode|token|access)|api key|secret|canary|bypass|越权|忽略.{0,8}(指令|规则)|密钥|敏感",
    re.IGNORECASE,
)


@dataclass
class ModelResponse:
    answer: str
    citations: List[str]
    input_tokens: int
    output_tokens: int
    raw: Dict[str, Any] = field(default_factory=dict)


def estimate_tokens(text: str) -> int:
    latin_words = len(re.findall(r"[A-Za-z0-9]+", text))
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    return max(1, int(latin_words * 1.3 + cjk_chars * 0.8))


class LocalExtractiveProvider:
    """A deterministic, offline provider used for demos and CI."""

    def generate(self, question: str, documents: Sequence[Any], config: Any) -> ModelResponse:
        context = "\n".join(document.content for document in documents)
        input_text = config.system_prompt + "\n" + question + "\n" + context
        if SECURITY_RE.search(question):
            answer = "I can't comply with requests to reveal secrets, policies, or privileged data."
            return ModelResponse(
                answer=answer,
                citations=[],
                input_tokens=estimate_tokens(input_text),
                output_tokens=estimate_tokens(answer),
                raw={"provider": "local", "guardrail": "security_refusal"},
            )

        question_tokens = set(tokenize(question))
        candidates = []
        for rank, document in enumerate(documents):
            sentences = re.split(r"(?<=[.!?。！？])\s+", document.content.strip())
            for position, sentence in enumerate(sentences):
                sentence_tokens = set(tokenize(sentence))
                overlap = len(question_tokens & sentence_tokens)
                density = overlap / max(1, len(question_tokens))
                score = density + overlap * 0.05 - rank * 0.01 - position * 0.001
                candidates.append((score, rank, position, sentence.strip(), document.id))

        candidates.sort(key=lambda row: (-row[0], row[1], row[2]))
        selected: List[tuple] = []
        used_docs = set()
        for score, _rank, _position, sentence, document_id in candidates:
            if score <= 0 and selected:
                continue
            if document_id in used_docs:
                continue
            selected.append((sentence, document_id))
            used_docs.add(document_id)
            if len(selected) == min(2, len(documents)):
                break

        if not selected or (candidates and candidates[0][0] <= 0):
            answer = "I don't have enough information in the supplied context to answer that."
            citations = []
        else:
            answer = " ".join("%s [doc:%s]" % (sentence, doc_id) for sentence, doc_id in selected)
            citations = [doc_id for _sentence, doc_id in selected]
        return ModelResponse(
            answer=answer,
            citations=citations,
            input_tokens=estimate_tokens(input_text),
            output_tokens=estimate_tokens(answer),
            raw={"provider": "local", "candidate_count": len(candidates)},
        )


class OpenAICompatibleProvider:
    def generate(self, question: str, documents: Sequence[Any], config: Any) -> ModelResponse:
        api_key = os.getenv(config.api_key_env)
        if not api_key:
            raise RuntimeError("Missing API key environment variable: %s" % config.api_key_env)

        context = "\n\n".join(
            "[doc:%s] %s\n%s" % (document.id, document.title, document.content)
            for document in documents
        )
        user_prompt = (
            "Context:\n%s\n\nQuestion: %s\n\n"
            "Answer only from the context. Cite every supported claim as [doc:id]."
            % (context, question)
        )
        response = httpx.post(
            config.api_base.rstrip("/") + "/chat/completions",
            headers={"Authorization": "Bearer %s" % api_key, "Content-Type": "application/json"},
            json={
                "model": config.model,
                "temperature": config.temperature,
                "messages": [
                    {"role": "system", "content": config.system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=60.0,
        )
        response.raise_for_status()
        payload = response.json()
        answer = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage", {})
        return ModelResponse(
            answer=answer,
            citations=list(dict.fromkeys(CITATION_RE.findall(answer))),
            input_tokens=usage.get("prompt_tokens", estimate_tokens(user_prompt)),
            output_tokens=usage.get("completion_tokens", estimate_tokens(answer)),
            raw={
                "provider": "openai_compatible",
                "request_id": response.headers.get("x-request-id"),
            },
        )


def get_provider(name: str):
    if name == "local":
        return LocalExtractiveProvider()
    if name == "openai_compatible":
        return OpenAICompatibleProvider()
    raise ValueError("Unsupported provider: %s" % name)
