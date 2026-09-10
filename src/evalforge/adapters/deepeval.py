"""Import explicitly supported DeepEval EvaluationResult JSON exports offline."""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set, Tuple

from evalforge.artifacts import (
    ArtifactProducer,
    ArtifactRun,
    EvaluationArtifact,
    MetricValue,
)

ADAPTER_MAPPING_VERSION = "1"
SUPPORTED_VERSIONS = {
    "3.8.1": "fc268fa3fc04e0f5ebb25db3631788913c02b38a",
    "4.2.2": "f94d940c1e5afc4b280420fe73fe17d146274018",
}

# These are exact upstream built-in display names, not user-controlled slugs.
# Unknown names are validated but never included in artifacts or diagnostics.
_COMMON_METRICS = {
    "Answer Relevancy": "deepeval_answer_relevancy",
    "Faithfulness": "deepeval_faithfulness",
    "Contextual Precision": "deepeval_contextual_precision",
    "Contextual Recall": "deepeval_contextual_recall",
    "Contextual Relevancy": "deepeval_contextual_relevancy",
    "Tool Correctness": "deepeval_tool_correctness",
    "Task Completion": "deepeval_task_completion",
}
_REVERSED_METRICS = {
    "Hallucination": "hallucination",
    "Bias": "bias",
    "Toxicity": "toxicity",
}
Direction = Literal["higher", "lower"]


def _object(value: Any, path: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("DeepEval %s must be a JSON object" % path)
    return value


def _nonempty_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("DeepEval %s must be a non-empty string" % path)
    return value


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError("DeepEval %s must be a boolean" % path)
    return value


def _finite_number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("DeepEval %s must be a finite number" % path)
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError("DeepEval %s must be a finite number" % path) from exc
    if not math.isfinite(number):
        raise ValueError("DeepEval %s must be a finite number" % path)
    return number


def _metric_mapping(producer_version: str) -> Dict[str, Tuple[str, Direction]]:
    mapping: Dict[str, Tuple[str, Direction]] = {
        name: (target, "higher") for name, target in _COMMON_METRICS.items()
    }
    legacy = producer_version == "3.8.1"
    for name, suffix in _REVERSED_METRICS.items():
        # DeepEval reversed all three scores in v4. Separate names prevent a
        # historical lower-is-better score from becoming a v4 gate baseline.
        mapping[name] = (
            "deepeval_v%s_%s" % ("3" if legacy else "4", suffix),
            "lower" if legacy else "higher",
        )
    return mapping


def deepeval_artifact_from_export(
    payload: Dict[str, Any],
    *,
    producer_version: str,
    source_revision: Optional[str] = None,
    dataset_fingerprint: Optional[str] = None,
) -> EvaluationArtifact:
    """Convert ``EvaluationResult.model_dump(mode='json', by_alias=False)``.

    Only DeepEval 3.8.1 and 4.2.2 are verified. Each row must contain the same
    nonempty metric suite, with finite scores and explicit pass/fail verdicts.
    Score-only, errored, and flaky metrics are rejected. The built-in name
    allowlist controls score export; custom names and all raw content stay local.
    """

    version = _nonempty_string(producer_version, "producer_version")
    if version not in SUPPORTED_VERSIONS:
        raise ValueError("DeepEval producer_version must be a verified version: 3.8.1 or 4.2.2")
    if source_revision is not None:
        _nonempty_string(source_revision, "source_revision")
    if dataset_fingerprint is not None:
        _nonempty_string(dataset_fingerprint, "dataset_fingerprint")

    root = _object(payload, "export")
    rows = root.get("test_results")
    if not isinstance(rows, list) or not rows:
        raise ValueError("DeepEval test_results must be a non-empty JSON array")

    mapping = _metric_mapping(version)
    suite: Optional[Set[str]] = None
    conversational: Optional[bool] = None
    scores: Dict[str, List[float]] = {}
    successes = 0
    for index, raw_row in enumerate(rows):
        row_path = "test_results[%s]" % index
        row = _object(raw_row, row_path)
        _nonempty_string(row.get("name"), row_path + ".name")
        success = _boolean(row.get("success"), row_path + ".success")
        row_conversational = _boolean(row.get("conversational"), row_path + ".conversational")
        if conversational is not None and conversational != row_conversational:
            raise ValueError("DeepEval test_results must use one conversation mode")
        conversational = row_conversational
        metric_rows = row.get("metrics_data")
        if not isinstance(metric_rows, list) or not metric_rows:
            raise ValueError("DeepEval %s.metrics_data must be a non-empty JSON array" % row_path)

        names: Set[str] = set()
        metric_successes: List[bool] = []
        for metric_index, raw_metric in enumerate(metric_rows):
            metric_path = "%s.metrics_data[%s]" % (row_path, metric_index)
            metric = _object(raw_metric, metric_path)
            name = _nonempty_string(metric.get("name"), metric_path + ".name")
            if name in names:
                raise ValueError("DeepEval %s contains a duplicate metric name" % row_path)
            names.add(name)
            if metric.get("error") is not None:
                raise ValueError("DeepEval %s contains an errored metric" % metric_path)
            # A flaky failure can legitimately leave TestResult.success=True.
            # It needs a different gate policy; do not silently ignore it here.
            flaky = _boolean(metric.get("flaky", False), metric_path + ".flaky")
            if flaky:
                raise ValueError("DeepEval %s contains an unsupported flaky metric" % metric_path)
            score = _finite_number(metric.get("score"), metric_path + ".score")
            threshold = _finite_number(metric.get("threshold"), metric_path + ".threshold")
            metric_success = _boolean(metric.get("success"), metric_path + ".success")
            metric_successes.append(metric_success)

            if name not in mapping:
                continue
            if not 0 <= score <= 1 or not 0 <= threshold <= 1:
                raise ValueError(
                    "DeepEval %s built-in score and threshold must be in [0, 1]" % metric_path
                )
            target, direction = mapping[name]
            expected_success = score >= threshold if direction == "higher" else score <= threshold
            if metric_success != expected_success:
                raise ValueError(
                    "DeepEval %s has inconsistent score/threshold success evidence" % metric_path
                )
            scores.setdefault(target, []).append(score)

        if suite is not None and names != suite:
            raise ValueError("DeepEval every test result must contain the same metric suite")
        suite = names
        if success != all(metric_successes):
            raise ValueError("DeepEval %s has inconsistent test success evidence" % row_path)
        successes += int(success)

    metrics = {
        "test_cases": MetricValue(value=len(rows), unit="count", direction="neutral"),
        "deepeval_pass_rate": MetricValue(
            value=successes / len(rows), unit="ratio", direction="higher"
        ),
    }
    directions = {target: direction for target, direction in mapping.values()}
    for target, values in scores.items():
        metrics[target] = MetricValue(
            value=math.fsum(values) / len(rows), unit="ratio", direction=directions[target]
        )

    metadata: Dict[str, Any] = {
        "adapter": "evalforge.deepeval",
        "adapter_mapping_version": ADAPTER_MAPPING_VERSION,
        "source_format": "EvaluationResult.model_dump(mode=json,by_alias=False)",
        "source_schema_commit": SUPPORTED_VERSIONS[version],
    }
    if dataset_fingerprint is not None:
        metadata["dataset_fingerprint"] = dataset_fingerprint
    return EvaluationArtifact(
        producer=ArtifactProducer(name="deepeval", version=version),
        run=ArtifactRun(source_revision=source_revision),
        metrics=metrics,
        metadata=metadata,
    )


def _unique_object(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DeepEval export contains duplicate JSON object keys")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise ValueError("DeepEval export contains a non-standard numeric JSON constant")


def load_deepeval_export(
    path: Path,
    *,
    producer_version: str,
    source_revision: Optional[str] = None,
    dataset_fingerprint: Optional[str] = None,
) -> EvaluationArtifact:
    """Read one explicit DeepEval JSON export without importing DeepEval itself."""

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except OSError as exc:
        raise ValueError("Could not read DeepEval export") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("DeepEval export is not valid UTF-8 JSON") from exc
    return deepeval_artifact_from_export(
        payload,
        producer_version=producer_version,
        source_revision=source_revision,
        dataset_fingerprint=dataset_fingerprint,
    )
