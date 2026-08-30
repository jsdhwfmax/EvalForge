"""Policy-as-code gates and CI report renderers for evaluation artifacts."""

import json
import operator
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional
from xml.etree import ElementTree

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from evalforge.artifacts import EvaluationArtifact

GateOperator = Literal["gte", "lte", "delta_gte", "delta_lte"]


class GateCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
    metric: str = Field(min_length=1)
    op: GateOperator
    value: float
    severity: Literal["error", "warning"] = "error"
    description: str = ""


class GatePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_uri: Optional[str] = Field(default=None, alias="$schema")
    version: Literal[1] = 1
    name: str = Field(default="EvalForge quality policy", min_length=1)
    checks: List[GateCheck] = Field(min_length=1)


class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    metric: str
    op: GateOperator
    expected: float
    actual: Optional[float] = None
    baseline: Optional[float] = None
    observed: Optional[float] = None
    severity: Literal["error", "warning"]
    outcome: Literal["pass", "fail", "warn", "error"]
    message: str


class GateReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    policy_name: str
    candidate_run_id: Optional[str] = None
    baseline_run_id: Optional[str] = None
    passed: bool
    checks: List[CheckResult]


COMPARATORS: Dict[str, Callable[[float, float], bool]] = {
    "gte": operator.ge,
    "lte": operator.le,
    "delta_gte": operator.ge,
    "delta_lte": operator.le,
}

OPERATOR_LABELS = {
    "gte": ">=",
    "lte": "<=",
    "delta_gte": "delta >=",
    "delta_lte": "delta <=",
}


def load_policy(path: Path) -> GatePolicy:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError("Could not read policy %s: %s" % (path, exc)) from exc
    except json.JSONDecodeError as exc:
        raise ValueError("Policy %s is not valid JSON: %s" % (path, exc)) from exc
    try:
        return GatePolicy.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("Policy does not match schema version 1: %s" % exc) from exc


def _error_result(check: GateCheck, message: str) -> CheckResult:
    return CheckResult(
        id=check.id,
        metric=check.metric,
        op=check.op,
        expected=check.value,
        severity=check.severity,
        outcome="error",
        message=message,
    )


def evaluate_gate(
    policy: GatePolicy,
    candidate: EvaluationArtifact,
    baseline: Optional[EvaluationArtifact] = None,
) -> GateReport:
    results: List[CheckResult] = []
    for check in policy.checks:
        candidate_metric = candidate.metrics.get(check.metric)
        if candidate_metric is None:
            results.append(_error_result(check, "Candidate metric is missing: %s" % check.metric))
            continue

        actual = candidate_metric.value
        baseline_value: Optional[float] = None
        observed = actual
        if check.op.startswith("delta_"):
            if baseline is None:
                results.append(
                    _error_result(check, "Baseline artifact is required for %s" % check.op)
                )
                continue
            baseline_metric = baseline.metrics.get(check.metric)
            if baseline_metric is None:
                results.append(
                    _error_result(check, "Baseline metric is missing: %s" % check.metric)
                )
                continue
            baseline_value = baseline_metric.value
            observed = actual - baseline_value

        passed = COMPARATORS[check.op](observed, check.value)
        outcome: Literal["pass", "fail", "warn", "error"]
        if passed:
            outcome = "pass"
        elif check.severity == "warning":
            outcome = "warn"
        else:
            outcome = "fail"
        message = "%s: %.6g %s %.6g" % (
            check.metric,
            observed,
            OPERATOR_LABELS[check.op],
            check.value,
        )
        if check.description:
            message = "%s — %s" % (message, check.description)
        results.append(
            CheckResult(
                id=check.id,
                metric=check.metric,
                op=check.op,
                expected=check.value,
                actual=actual,
                baseline=baseline_value,
                observed=observed,
                severity=check.severity,
                outcome=outcome,
                message=message,
            )
        )

    gate_passed = all(result.outcome in {"pass", "warn"} for result in results)
    return GateReport(
        policy_name=policy.name,
        candidate_run_id=candidate.run.id,
        baseline_run_id=baseline.run.id if baseline else None,
        passed=gate_passed,
        checks=results,
    )


def render_terminal(report: GateReport) -> str:
    symbols = {"pass": "PASS", "fail": "FAIL", "warn": "WARN", "error": "ERROR"}
    lines = ["EvalForge gate: %s" % ("PASS" if report.passed else "FAIL")]
    for result in report.checks:
        lines.append("[%s] %s — %s" % (symbols[result.outcome], result.id, result.message))
    return "\n".join(lines)


def render_json(report: GateReport) -> str:
    payload = report.model_dump(mode="json", exclude_none=True)
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_junit(report: GateReport) -> str:
    failures = sum(result.outcome == "fail" for result in report.checks)
    errors = sum(result.outcome == "error" for result in report.checks)
    suite = ElementTree.Element(
        "testsuite",
        {
            "name": "evalforge",
            "tests": str(len(report.checks)),
            "failures": str(failures),
            "errors": str(errors),
            "skipped": "0",
        },
    )
    properties = ElementTree.SubElement(suite, "properties")
    ElementTree.SubElement(properties, "property", {"name": "policy", "value": report.policy_name})
    for result in report.checks:
        case = ElementTree.SubElement(
            suite,
            "testcase",
            {"classname": "evalforge.gate", "name": result.id},
        )
        if result.outcome == "fail":
            failure = ElementTree.SubElement(case, "failure", {"message": result.message})
            failure.text = result.message
        elif result.outcome == "error":
            error = ElementTree.SubElement(case, "error", {"message": result.message})
            error.text = result.message
        elif result.outcome == "warn":
            output = ElementTree.SubElement(case, "system-out")
            output.text = "warning: %s" % result.message
    ElementTree.indent(suite, space="  ")
    return ElementTree.tostring(suite, encoding="unicode", xml_declaration=True) + "\n"


def render_sarif(report: GateReport) -> str:
    rules = []
    results = []
    for check in report.checks:
        rules.append(
            {
                "id": check.id,
                "name": check.id,
                "shortDescription": {"text": "Evaluation policy check for %s" % check.metric},
                "properties": {"metric": check.metric, "operator": check.op},
            }
        )
        if check.outcome == "pass":
            continue
        level = "warning" if check.outcome == "warn" else "error"
        results.append(
            {
                "ruleId": check.id,
                "level": level,
                "message": {"text": check.message},
                "properties": {
                    "metric": check.metric,
                    "outcome": check.outcome,
                    "expected": check.expected,
                    "actual": check.actual,
                    "baseline": check.baseline,
                    "observed": check.observed,
                },
            }
        )
    payload = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "EvalForge",
                        "informationUri": "https://github.com/jsdhwfmax/EvalForge",
                        "rules": rules,
                    }
                },
                "invocations": [
                    {"executionSuccessful": True, "exitCode": 0 if report.passed else 1}
                ],
                "results": results,
            }
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


METRIC_RULES = {
    "retrieval_recall_at_k": ("min", "Retrieval Recall@K"),
    "answer_correctness": ("min", "Answer correctness"),
    "citation_support": ("min", "Citation support"),
    "hallucination_rate": ("max", "Hallucination rate"),
    "security_pass_rate": ("min", "Security pass rate"),
    "latency_ms": ("max", "Mean latency"),
    "total_cost_usd": ("max", "Total cost"),
}


def evaluate_quality_gate(summary: Dict[str, Any], thresholds: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate dashboard/API thresholds against a stored experiment summary."""

    checks = []
    for metric, threshold in thresholds.items():
        if threshold is None or metric not in METRIC_RULES:
            continue
        operator_name, label = METRIC_RULES[metric]
        actual = summary.get(metric)
        passed = actual is not None and (
            actual >= threshold if operator_name == "min" else actual <= threshold
        )
        checks.append(
            {
                "metric": metric,
                "label": label,
                "actual": actual,
                "operator": ">=" if operator_name == "min" else "<=",
                "threshold": threshold,
                "passed": passed,
            }
        )
    return {
        "passed": bool(checks) and all(check["passed"] for check in checks),
        "checks": checks,
    }


def compare_experiment_summaries(
    baseline_id: str,
    baseline_summary: Dict[str, Any],
    candidate_id: str,
    candidate_summary: Dict[str, Any],
) -> Dict[str, Any]:
    """Build direction-aware deltas for two stored RAG experiments."""

    metrics = {}
    for metric, (direction, label) in METRIC_RULES.items():
        baseline = baseline_summary.get(metric)
        candidate = candidate_summary.get(metric)
        if baseline is None or candidate is None:
            continue
        delta = round(candidate - baseline, 8)
        preferred_delta = delta if direction == "min" else -delta
        if abs(preferred_delta) < 1e-12:
            verdict = "unchanged"
        elif preferred_delta > 0:
            verdict = "improved"
        else:
            verdict = "regressed"
        metrics[metric] = {
            "label": label,
            "baseline": baseline,
            "candidate": candidate,
            "delta": delta,
            "direction": "higher_is_better" if direction == "min" else "lower_is_better",
            "verdict": verdict,
        }
    baseline_fingerprint = baseline_summary.get("dataset_fingerprint")
    candidate_fingerprint = candidate_summary.get("dataset_fingerprint")
    return {
        "baseline_experiment_id": baseline_id,
        "candidate_experiment_id": candidate_id,
        "dataset_fingerprint_match": bool(baseline_fingerprint)
        and baseline_fingerprint == candidate_fingerprint,
        "metrics": metrics,
        "improvements": sum(item["verdict"] == "improved" for item in metrics.values()),
        "regressions": sum(item["verdict"] == "regressed" for item in metrics.values()),
    }
