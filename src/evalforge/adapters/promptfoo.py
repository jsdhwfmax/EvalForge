"""Import the documented promptfoo JSON output format without copying raw content."""

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from evalforge.artifacts import EvaluationArtifact, artifact_from_summary

PROMPTFOO_SCHEMA_VERSION = 3
ADAPTER_MAPPING_VERSION = "1"
_SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")


def _object(value: Any, path: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("promptfoo %s must be a JSON object" % path)
    return value


def _array(value: Any, path: str) -> List[Any]:
    if not isinstance(value, list):
        raise ValueError("promptfoo %s must be a JSON array" % path)
    return value


def _nonempty_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("promptfoo %s must be a non-empty string" % path)
    return value.strip()


def _finite_number(value: Any, path: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("promptfoo %s must be a finite number" % path)
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("promptfoo %s must be a finite number" % path)
    if nonnegative and number < 0:
        raise ValueError("promptfoo %s must be a non-negative finite number" % path)
    return number


def _count(value: Any, path: str) -> int:
    number = _finite_number(value, path, nonnegative=True)
    if not number.is_integer():
        raise ValueError("promptfoo %s must be an integer count" % path)
    return int(number)


def _optional_metric(
    target: Dict[str, float], source: Dict[str, Any], source_name: str, target_name: str
) -> None:
    if source_name not in source or source[source_name] is None:
        return
    target[target_name] = _finite_number(
        source[source_name], "results.stats.tokenUsage.%s" % source_name, nonnegative=True
    )


def promptfoo_artifact_from_export(
    payload: Dict[str, Any], *, source_revision: Optional[str] = None
) -> EvaluationArtifact:
    """Convert a promptfoo OutputFile with EvaluateSummaryV3 into aggregate evidence.

    Raw prompts, responses, test variables, configuration, traces, named scores, and
    arbitrary metadata are intentionally excluded from the returned artifact.
    """

    root = _object(payload, "export")
    metadata = _object(root.get("metadata"), "metadata")
    producer_version = _nonempty_string(
        metadata.get("promptfooVersion"), "metadata.promptfooVersion"
    )
    if not _SEMVER.fullmatch(producer_version):
        raise ValueError("promptfoo metadata.promptfooVersion must be a semantic version")

    summary = _object(root.get("results"), "results")
    version = summary.get("version")
    if isinstance(version, bool) or version != PROMPTFOO_SCHEMA_VERSION:
        raise ValueError(
            "promptfoo export must use supported results schema version %s"
            % PROMPTFOO_SCHEMA_VERSION
        )
    source_timestamp = _nonempty_string(summary.get("timestamp"), "results.timestamp")
    rows = _array(summary.get("results"), "results.results")
    if not rows:
        raise ValueError("promptfoo results.results must contain at least one result row")

    successes = 0
    failures = 0
    errors = 0
    scores: List[float] = []
    latencies: List[float] = []
    costs: List[float] = []
    all_rows_have_cost = True

    for index, raw_row in enumerate(rows):
        row = _object(raw_row, "results.results[%s]" % index)
        success = row.get("success")
        if not isinstance(success, bool):
            raise ValueError(
                "promptfoo results.results[%s].success must be a boolean" % index
            )
        failure_reason = _count(
            row.get("failureReason"), "results.results[%s].failureReason" % index
        )
        if failure_reason not in {0, 1, 2}:
            raise ValueError(
                "promptfoo results.results[%s].failureReason is not supported" % index
            )
        if success:
            if failure_reason != 0:
                raise ValueError(
                    "promptfoo results.results[%s] has inconsistent success evidence" % index
                )
            successes += 1
        elif failure_reason == 2:
            errors += 1
        else:
            failures += 1

        scores.append(_finite_number(row.get("score"), "results.results[%s].score" % index))
        latencies.append(
            _finite_number(
                row.get("latencyMs"),
                "results.results[%s].latencyMs" % index,
                nonnegative=True,
            )
        )
        if "cost" not in row or row["cost"] is None:
            all_rows_have_cost = False
        else:
            costs.append(
                _finite_number(
                    row["cost"], "results.results[%s].cost" % index, nonnegative=True
                )
            )

    stats = _object(summary.get("stats"), "results.stats")
    declared_counts = (
        _count(stats.get("successes"), "results.stats.successes"),
        _count(stats.get("failures"), "results.stats.failures"),
        _count(stats.get("errors"), "results.stats.errors"),
    )
    if declared_counts != (successes, failures, errors):
        raise ValueError("promptfoo results.stats counts do not match result rows")

    metrics: Dict[str, float] = {
        "promptfoo_pass_rate": successes / len(rows),
        "promptfoo_mean_score": sum(scores) / len(scores),
        "latency_ms": sum(latencies) / len(latencies),
        "test_cases": float(len(rows)),
    }
    if all_rows_have_cost:
        metrics["total_cost_usd"] = sum(costs)

    token_usage = _object(stats.get("tokenUsage"), "results.stats.tokenUsage")
    _optional_metric(metrics, token_usage, "prompt", "input_tokens")
    _optional_metric(metrics, token_usage, "completion", "output_tokens")

    run_id_value = root.get("evalId")
    if run_id_value is not None:
        run_id = _nonempty_string(run_id_value, "evalId")
    else:
        run_id = None

    sanitized_metadata: Dict[str, Any] = {
        "adapter": "evalforge.promptfoo",
        "adapter_mapping_version": ADAPTER_MAPPING_VERSION,
        "source_schema_version": PROMPTFOO_SCHEMA_VERSION,
        "source_timestamp": source_timestamp,
    }
    if metadata.get("exportedAt") is not None:
        sanitized_metadata["source_exported_at"] = _nonempty_string(
            metadata["exportedAt"], "metadata.exportedAt"
        )

    return artifact_from_summary(
        metrics,
        producer_name="promptfoo",
        producer_version=producer_version,
        run_id=run_id,
        source_revision=source_revision,
        metadata=sanitized_metadata,
    )


def load_promptfoo_export(
    path: Path, *, source_revision: Optional[str] = None
) -> EvaluationArtifact:
    """Read and convert a promptfoo JSON export from disk."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError("Could not read promptfoo export %s: %s" % (path, exc)) from exc
    except json.JSONDecodeError as exc:
        raise ValueError("promptfoo export %s is not valid JSON: %s" % (path, exc)) from exc
    return promptfoo_artifact_from_export(payload, source_revision=source_revision)
