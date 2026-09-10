"""Import explicit Ragas score columns from a pandas records JSON export."""

import json
import math
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

from evalforge.artifacts import (
    ArtifactProducer,
    ArtifactRun,
    EvaluationArtifact,
    MetricValue,
)

ADAPTER_MAPPING_VERSION = "1"
SOURCE_FORMAT = "ragas.evaluation_result.pandas.records"

# These are sample data in Ragas, including names used by older dataset schemas.
# A numeric-looking reference or response is never evaluation score evidence.
_SAMPLE_COLUMNS = {
    "user_input",
    "retrieved_contexts",
    "reference_contexts",
    "response",
    "multi_responses",
    "reference",
    "rubric",
    "rubrics",
    "reference_tool_calls",
    "reference_topics",
    "question",
    "answer",
    "contexts",
    "ground_truth",
    "ground_truths",
}


def _nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Ragas %s must be a non-empty string" % name)
    return value.strip()


def _metric_columns(metrics: List[str]) -> List[str]:
    if not isinstance(metrics, list) or not metrics:
        raise ValueError("Ragas metrics must be an explicit non-empty list of score columns")
    columns: List[str] = []
    for column in metrics:
        name = _nonempty_string(column, "metric column")
        if name != column:
            raise ValueError("Ragas metric columns must not have surrounding whitespace")
        if name in _SAMPLE_COLUMNS:
            raise ValueError("Ragas metric column %s is a reserved dataset column" % name)
        if name == "test_cases":
            raise ValueError("Ragas metric column test_cases is reserved for the sample count")
        if name in columns:
            raise ValueError("Ragas metric columns must be unique")
        columns.append(name)
    return columns


def _finite_score(value: Any, index: int, column: str) -> float:
    message = "Ragas row %s score column %s must be a finite number" % (index, column)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(message)
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError(message) from exc
    if not math.isfinite(number):
        raise ValueError(message)
    return number


def ragas_artifact_from_export(
    payload: Any,
    *,
    producer_version: str,
    metrics: List[str],
    source_revision: Optional[str] = None,
    dataset_fingerprint: Optional[str] = None,
) -> EvaluationArtifact:
    """Aggregate selected columns of EvaluationResult.to_pandas() JSON records.

    Every selected score must be finite on every row. No rows are dropped, and
    no metric is inferred from dataset columns. The caller supplies provenance
    because the records format contains neither the SDK version nor a dataset ID.
    """

    version = _nonempty_string(producer_version, "producer_version")
    columns = _metric_columns(metrics)
    if source_revision is not None:
        source_revision = _nonempty_string(source_revision, "source_revision")
    if dataset_fingerprint is not None:
        dataset_fingerprint = _nonempty_string(dataset_fingerprint, "dataset_fingerprint")
    if not isinstance(payload, list) or not payload:
        raise ValueError("Ragas export must be a non-empty JSON array of records")

    scores: Dict[str, List[float]] = {column: [] for column in columns}
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            raise ValueError("Ragas row %s must be a JSON object" % index)
        for column in columns:
            if column not in row:
                raise ValueError("Ragas row %s is missing score column %s" % (index, column))
            scores[column].append(_finite_score(row[column], index, column))

    # statistics.mean avoids overflow when the sum of finite scores overflows.
    values = {
        column: MetricValue(value=mean(scores[column]), unit="score", direction="neutral")
        for column in columns
    }
    values["test_cases"] = MetricValue(value=len(payload), unit="count", direction="neutral")
    metadata: Dict[str, Any] = {
        "adapter": "evalforge.ragas",
        "adapter_mapping_version": ADAPTER_MAPPING_VERSION,
        "source_format": SOURCE_FORMAT,
        "aggregation": "mean",
        "metric_columns": columns,
    }
    if dataset_fingerprint is not None:
        metadata["dataset_fingerprint"] = dataset_fingerprint

    return EvaluationArtifact(
        producer=ArtifactProducer(name="ragas", version=version),
        run=ArtifactRun(source_revision=source_revision),
        metrics=values,
        metadata=metadata,
    )


def _unique_object(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Ragas export contains duplicate JSON object keys")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError("Ragas export contains a non-finite JSON number")


def load_ragas_export(
    path: Path,
    *,
    producer_version: str,
    metrics: List[str],
    source_revision: Optional[str] = None,
    dataset_fingerprint: Optional[str] = None,
) -> EvaluationArtifact:
    """Read a Ragas pandas records JSON export without importing the Ragas SDK."""

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_invalid_constant,
        )
    except OSError as exc:
        raise ValueError("Could not read Ragas export %s: %s" % (path, exc)) from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Ragas export %s is not valid UTF-8 JSON" % path) from exc
    return ragas_artifact_from_export(
        payload,
        producer_version=producer_version,
        metrics=metrics,
        source_revision=source_revision,
        dataset_fingerprint=dataset_fingerprint,
    )
