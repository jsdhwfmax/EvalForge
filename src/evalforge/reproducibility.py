import hashlib
import json
from typing import Any, Dict, Sequence

METRIC_VERSION = "deterministic-v1"


def dataset_fingerprint(documents: Sequence[Any], test_cases: Sequence[Any]) -> str:
    payload = {
        "documents": [
            {"id": item.id, "title": item.title, "content": item.content}
            for item in sorted(documents, key=lambda row: row.id)
        ],
        "test_cases": [
            {
                "id": item.id,
                "question": item.question,
                "expected_answer": item.expected_answer,
                "relevant_document_ids": sorted(item.relevant_document_ids),
            }
            for item in sorted(test_cases, key=lambda row: row.id)
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def config_snapshot(config: Any) -> Dict[str, Any]:
    return {
        "id": config.id,
        "name": config.name,
        "provider": config.provider,
        "model": config.model,
        "system_prompt": config.system_prompt,
        "retrieval_method": config.retrieval_method,
        "top_k": config.top_k,
        "temperature": config.temperature,
        "input_cost_per_million": config.input_cost_per_million,
        "output_cost_per_million": config.output_cost_per_million,
    }
