"""Portable evaluation artifacts used by EvalForge gates and other tools."""

import json
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from evalforge import __version__

SCHEMA_VERSION: Literal["1.0"] = "1.0"

# Common metrics get portable units and directions. Unknown metrics remain valid
# so external evaluators can use the artifact without waiting for EvalForge changes.
METRIC_METADATA: Dict[str, Tuple[str, str]] = {
    "retrieval_recall_at_k": ("ratio", "higher"),
    "answer_correctness": ("ratio", "higher"),
    "citation_support": ("ratio", "higher"),
    "hallucination_rate": ("ratio", "lower"),
    "latency_ms": ("ms", "lower"),
    "total_cost_usd": ("usd", "lower"),
    "input_tokens": ("tokens", "neutral"),
    "output_tokens": ("tokens", "neutral"),
    "test_cases": ("count", "neutral"),
    "security_cases": ("count", "neutral"),
    "security_pass_rate": ("ratio", "higher"),
}


class MetricValue(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    value: float
    unit: str = Field(default="score", min_length=1)
    direction: Literal["higher", "lower", "neutral"] = "neutral"


class ArtifactProducer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)


class ArtifactRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Optional[str] = None
    source_revision: Optional[str] = None


class EvaluationArtifact(BaseModel):
    """A small, evaluator-neutral envelope for aggregate evaluation metrics."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_uri: Optional[str] = Field(default=None, alias="$schema")
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    producer: ArtifactProducer
    run: ArtifactRun = Field(default_factory=ArtifactRun)
    metrics: Dict[str, MetricValue] = Field(min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


def artifact_from_summary(
    summary: Dict[str, Any],
    *,
    producer_name: str = "evalforge",
    producer_version: str = __version__,
    run_id: Optional[str] = None,
    source_revision: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> EvaluationArtifact:
    """Wrap any flat numeric summary in the portable artifact format."""

    values: Dict[str, MetricValue] = {}
    for name, raw_value in summary.items():
        if raw_value is None or isinstance(raw_value, bool):
            continue
        if not isinstance(raw_value, (int, float)):
            continue
        unit, direction = METRIC_METADATA.get(name, ("score", "neutral"))
        values[name] = MetricValue(value=float(raw_value), unit=unit, direction=direction)
    if not values:
        raise ValueError("Evaluation summary does not contain any numeric metrics")
    return EvaluationArtifact(
        producer=ArtifactProducer(name=producer_name, version=producer_version),
        run=ArtifactRun(id=run_id, source_revision=source_revision),
        metrics=values,
        metadata=metadata or {},
    )


def load_artifact(path: Path) -> EvaluationArtifact:
    """Load a canonical artifact, a flat metric object, or an API summary envelope."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError("Could not read artifact %s: %s" % (path, exc)) from exc
    except json.JSONDecodeError as exc:
        raise ValueError("Artifact %s is not valid JSON: %s" % (path, exc)) from exc
    if not isinstance(payload, dict):
        raise ValueError("Artifact root must be a JSON object")

    if "schema_version" in payload or "producer" in payload or "metrics" in payload:
        try:
            return EvaluationArtifact.model_validate(payload)
        except ValidationError as exc:
            raise ValueError("Artifact does not match schema version 1.0: %s" % exc) from exc

    summary = payload.get("summary", payload)
    if not isinstance(summary, dict):
        raise ValueError("Artifact summary must be a JSON object")
    return artifact_from_summary(summary, producer_name="external", producer_version="unknown")


def write_artifact(path: Path, artifact: EvaluationArtifact) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = artifact.model_dump(mode="json", exclude_none=True, by_alias=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
