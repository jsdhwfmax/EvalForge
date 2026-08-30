import json
from pathlib import Path
from typing import Any, Dict, Iterable, List
from xml.etree import ElementTree

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
    checks = []
    for metric, threshold in thresholds.items():
        if threshold is None or metric not in METRIC_RULES:
            continue
        operator, label = METRIC_RULES[metric]
        actual = summary.get(metric)
        passed = actual is not None and (
            actual >= threshold if operator == "min" else actual <= threshold
        )
        checks.append(
            {
                "metric": metric,
                "label": label,
                "actual": actual,
                "operator": ">=" if operator == "min" else "<=",
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


def write_json_report(path: Path, report: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def write_junit_report(path: Path, checks: Iterable[Dict[str, Any]], suite_name: str) -> None:
    check_list: List[Dict[str, Any]] = list(checks)
    failures = sum(not check["passed"] for check in check_list)
    suite = ElementTree.Element(
        "testsuite",
        name=suite_name,
        tests=str(len(check_list)),
        failures=str(failures),
        errors="0",
    )
    for check in check_list:
        case = ElementTree.SubElement(
            suite,
            "testcase",
            classname="evalforge.quality_gate",
            name=check["metric"],
        )
        if not check["passed"]:
            failure = ElementTree.SubElement(
                case,
                "failure",
                message=(
                    "%s: actual %s, expected %s %s"
                    % (
                        check["label"],
                        check["actual"],
                        check["operator"],
                        check["threshold"],
                    )
                ),
            )
            failure.text = json.dumps(check, sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    ElementTree.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)
