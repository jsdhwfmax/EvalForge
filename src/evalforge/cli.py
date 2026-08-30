import json
import os
from importlib.util import find_spec
from pathlib import Path
from typing import Optional

import typer

from evalforge.adapters.promptfoo import load_promptfoo_export
from evalforge.artifacts import artifact_from_summary, load_artifact, write_artifact
from evalforge.gates import (
    GateCheck,
    GatePolicy,
    compare_experiment_summaries,
    evaluate_gate,
    evaluate_quality_gate,
    load_policy,
    render_json,
    render_junit,
    render_sarif,
    render_terminal,
    write_report,
)

app = typer.Typer(help="EvalForge command-line tools")
import_app = typer.Typer(help="Convert an explicit evaluator format to EvalForge evidence")
app.add_typer(import_app, name="import")


@import_app.command("promptfoo")
def import_promptfoo(
    source: Path,
    output: Path = typer.Option(..., "--output", "-o"),
    source_revision: Optional[str] = typer.Option(
        None,
        "--source-revision",
        help="Candidate source revision evaluated by promptfoo",
    ),
) -> None:
    """Convert a promptfoo JSON OutputFile (results schema v3)."""

    try:
        artifact = load_promptfoo_export(source, source_revision=source_revision)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    write_artifact(output, artifact)
    typer.echo("Wrote promptfoo evaluation artifact to %s" % output)


def _require_rag_dependencies() -> None:
    if find_spec("sqlalchemy") is None:
        typer.echo(
            "This command needs the built-in RAG evaluator. "
            "Install it with: pip install 'evalforge-ci[rag]'",
            err=True,
        )
        raise typer.Exit(code=2)


@app.command()
def init() -> None:
    """Create database tables."""
    _require_rag_dependencies()
    from evalforge.database import init_db

    init_db()
    typer.echo("Database initialized.")


@app.command()
def import_data(path: Path) -> None:
    """Import documents and test cases from an EvalForge JSON dataset."""
    _require_rag_dependencies()
    from evalforge.database import init_db, session_scope
    from evalforge.schemas import DatasetImport
    from evalforge.services import import_dataset

    init_db()
    payload = DatasetImport.model_validate(json.loads(path.read_text(encoding="utf-8")))
    with session_scope() as db:
        documents, tests, skipped = import_dataset(db, payload)
    typer.echo(
        "Imported %s documents and %s test cases (%s skipped)." % (documents, tests, skipped)
    )


@app.command()
def seed(dataset: Path = Path("examples/demo_dataset.json")) -> None:
    """Load the demo dataset and two comparable configurations."""
    _require_rag_dependencies()
    from sqlalchemy import select

    from evalforge.database import init_db, session_scope
    from evalforge.models import RagConfig
    from evalforge.schemas import DatasetImport, RagConfigCreate
    from evalforge.services import create_config, import_dataset

    init_db()
    payload = DatasetImport.model_validate(json.loads(dataset.read_text(encoding="utf-8")))
    with session_scope() as db:
        documents, tests, skipped = import_dataset(db, payload)
        existing = set(db.scalars(select(RagConfig.name)))
        if "BM25 · top 1" not in existing:
            create_config(
                db,
                RagConfigCreate(
                    id="baseline_top1", name="BM25 · top 1", retrieval_method="bm25", top_k=1
                ),
            )
        if "Hybrid · top 3" not in existing:
            create_config(
                db,
                RagConfigCreate(
                    id="hybrid_top3", name="Hybrid · top 3", retrieval_method="hybrid", top_k=3
                ),
            )
    typer.echo("Demo ready: %s documents, %s tests, %s skipped." % (documents, tests, skipped))


@app.command()
def run(
    config_id: str,
    name: str = "CLI experiment",
    test_case_id: Optional[str] = None,
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
) -> None:
    """Run one stored RAG configuration against the test suite."""
    _require_rag_dependencies()
    from evalforge.database import init_db, session_scope
    from evalforge.models import RagConfig
    from evalforge.services import run_experiment, select_test_cases

    init_db()
    with session_scope() as db:
        config = db.get(RagConfig, config_id)
        if not config:
            raise typer.BadParameter("Unknown config ID: %s" % config_id)
        test_cases = select_test_cases(db, [test_case_id] if test_case_id else None)
        experiment = run_experiment(db, name, config, test_cases, include_security=True)
        typer.echo(json.dumps(experiment.summary, indent=2))
        if output:
            artifact = artifact_from_summary(
                experiment.summary,
                run_id=experiment.id,
                source_revision=os.getenv("GITHUB_SHA"),
                metadata={"experiment_name": experiment.name, "config_id": config_id},
            )
            write_artifact(output, artifact)
            typer.echo("Wrote evaluation artifact to %s" % output)


@app.command()
def gate(
    candidate: Path,
    policy: Path = typer.Option(..., "--policy", "-p"),
    baseline: Optional[Path] = typer.Option(None, "--baseline", "-b"),
    json_output: Optional[Path] = typer.Option(None, "--json", help="Write the gate report"),
    junit_output: Optional[Path] = typer.Option(None, "--junit", help="Write JUnit XML"),
    sarif_output: Optional[Path] = typer.Option(None, "--sarif", help="Write SARIF 2.1.0"),
) -> None:
    """Enforce a portable evaluation policy and return a CI-safe exit code."""

    try:
        candidate_artifact = load_artifact(candidate)
        baseline_artifact = load_artifact(baseline) if baseline else None
        loaded_policy = load_policy(policy)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    report = evaluate_gate(loaded_policy, candidate_artifact, baseline_artifact)
    typer.echo(render_terminal(report))
    if json_output:
        write_report(json_output, render_json(report))
    if junit_output:
        write_report(junit_output, render_junit(report))
    if sarif_output:
        write_report(sarif_output, render_sarif(report))
    if not report.passed:
        raise typer.Exit(code=1)


@app.command()
def compare(baseline_id: str, candidate_id: str) -> None:
    """Compare two completed experiments and print metric deltas."""
    _require_rag_dependencies()
    from evalforge.database import init_db, session_scope
    from evalforge.models import Experiment

    init_db()
    with session_scope() as db:
        baseline = db.get(Experiment, baseline_id)
        candidate = db.get(Experiment, candidate_id)
        if not baseline or not candidate:
            raise typer.BadParameter("Both experiment IDs must exist")
        if baseline.status != "completed" or candidate.status != "completed":
            raise typer.BadParameter("Both experiments must be completed")
        report = compare_experiment_summaries(
            baseline.id, baseline.summary, candidate.id, candidate.summary
        )
    typer.echo(json.dumps(report, indent=2))


@app.command("gate-experiment")
def gate_experiment(
    experiment_id: str,
    min_recall: float = 0.8,
    min_correctness: float = 0.5,
    min_citation_support: float = 0.8,
    max_hallucination: float = 0.1,
    min_security_pass_rate: float = 1.0,
    max_latency_ms: Optional[float] = None,
    max_cost_usd: Optional[float] = None,
) -> None:
    """Apply release thresholds to an existing experiment; exit non-zero on failure."""
    _require_rag_dependencies()
    from evalforge.database import init_db, session_scope
    from evalforge.models import Experiment
    from evalforge.schemas import QualityGateRequest

    init_db()
    thresholds = QualityGateRequest(
        retrieval_recall_at_k=min_recall,
        answer_correctness=min_correctness,
        citation_support=min_citation_support,
        hallucination_rate=max_hallucination,
        security_pass_rate=min_security_pass_rate,
        latency_ms=max_latency_ms,
        total_cost_usd=max_cost_usd,
    )
    with session_scope() as db:
        experiment = db.get(Experiment, experiment_id)
        if not experiment:
            raise typer.BadParameter("Unknown experiment ID: %s" % experiment_id)
        result = evaluate_quality_gate(experiment.summary, thresholds.model_dump())
    typer.echo(json.dumps({"experiment_id": experiment_id, **result}, indent=2))
    if not result["passed"]:
        raise typer.Exit(code=1)


@app.command()
def check(
    config_id: str,
    name: str = "CI release gate",
    report_dir: Path = Path("artifacts"),
    min_recall: float = 0.8,
    min_correctness: float = 0.5,
    min_citation_support: float = 0.8,
    max_hallucination: float = 0.1,
    min_security_pass_rate: float = 1.0,
    max_latency_ms: Optional[float] = 5000.0,
    max_cost_usd: Optional[float] = None,
) -> None:
    """Run a RAG config and emit portable JSON, JUnit, and SARIF evidence."""
    _require_rag_dependencies()
    from evalforge.database import init_db, session_scope
    from evalforge.models import RagConfig
    from evalforge.schemas import QualityGateRequest
    from evalforge.services import run_experiment, select_test_cases

    init_db()
    thresholds = QualityGateRequest(
        retrieval_recall_at_k=min_recall,
        answer_correctness=min_correctness,
        citation_support=min_citation_support,
        hallucination_rate=max_hallucination,
        security_pass_rate=min_security_pass_rate,
        latency_ms=max_latency_ms,
        total_cost_usd=max_cost_usd,
    )
    with session_scope() as db:
        config = db.get(RagConfig, config_id)
        if not config:
            raise typer.BadParameter("Unknown config ID: %s" % config_id)
        test_cases = select_test_cases(db)
        if not test_cases:
            raise typer.BadParameter("No test cases are stored")
        experiment = run_experiment(db, name, config, test_cases, include_security=True)
        summary = dict(experiment.summary)
        artifact = artifact_from_summary(
            summary,
            run_id=experiment.id,
            source_revision=os.getenv("GITHUB_SHA"),
            metadata={
                "experiment_name": experiment.name,
                "config_id": config.id,
                "dataset_fingerprint": summary.get("dataset_fingerprint"),
                "config_snapshot": summary.get("config_snapshot"),
                "metric_version": summary.get("metric_version"),
            },
        )
    policy_checks = []
    for metric, threshold in thresholds.model_dump().items():
        if threshold is None:
            continue
        lower_is_better = metric in {"hallucination_rate", "latency_ms", "total_cost_usd"}
        policy_checks.append(
            GateCheck(
                id="%s-threshold" % metric.replace("_", "-"),
                metric=metric,
                op="lte" if lower_is_better else "gte",
                value=threshold,
                description="Built-in RAG release threshold",
            )
        )
    report = evaluate_gate(
        GatePolicy(name="EvalForge RAG release gate", checks=policy_checks), artifact
    )
    write_artifact(report_dir / "evaluation-artifact.json", artifact)
    write_report(report_dir / "evalforge-report.json", render_json(report))
    write_report(report_dir / "evalforge-junit.xml", render_junit(report))
    write_report(report_dir / "evalforge.sarif", render_sarif(report))
    typer.echo(json.dumps(summary, indent=2))
    typer.echo(render_terminal(report))
    typer.echo("Reports: %s" % report_dir.resolve())
    if not report.passed:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
