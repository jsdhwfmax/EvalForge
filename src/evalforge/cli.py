import json
from pathlib import Path
from typing import Optional

import typer
from sqlalchemy import select

from evalforge.database import init_db, session_scope
from evalforge.gates import (
    compare_experiment_summaries,
    evaluate_quality_gate,
    write_json_report,
    write_junit_report,
)
from evalforge.models import Experiment, RagConfig
from evalforge.schemas import DatasetImport, QualityGateRequest, RagConfigCreate
from evalforge.services import create_config, import_dataset, run_experiment, select_test_cases

app = typer.Typer(help="EvalForge command-line tools")


@app.command()
def init() -> None:
    """Create database tables."""
    init_db()
    typer.echo("Database initialized.")


@app.command()
def import_data(path: Path) -> None:
    """Import documents and test cases from an EvalForge JSON dataset."""
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
def run(config_id: str, name: str = "CLI experiment", test_case_id: Optional[str] = None) -> None:
    """Run one stored RAG configuration against the test suite."""
    init_db()
    with session_scope() as db:
        config = db.get(RagConfig, config_id)
        if not config:
            raise typer.BadParameter("Unknown config ID: %s" % config_id)
        test_cases = select_test_cases(db, [test_case_id] if test_case_id else None)
        experiment = run_experiment(db, name, config, test_cases, include_security=True)
        typer.echo(json.dumps(experiment.summary, indent=2))


@app.command()
def compare(baseline_id: str, candidate_id: str) -> None:
    """Compare two completed experiments and print metric deltas."""
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


@app.command()
def gate(
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
    """Run a config, enforce quality gates, and emit JSON plus JUnit evidence."""
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
        gate_result = evaluate_quality_gate(experiment.summary, thresholds.model_dump())
        report = {
            "experiment_id": experiment.id,
            "experiment_name": experiment.name,
            "config_id": config.id,
            "summary": experiment.summary,
            "quality_gate": gate_result,
        }
    write_json_report(report_dir / "evaluation.json", report)
    write_junit_report(
        report_dir / "quality-gate.xml", gate_result["checks"], "EvalForge release gate"
    )
    typer.echo(json.dumps(report, indent=2))
    typer.echo("Reports: %s" % report_dir.resolve())
    if not gate_result["passed"]:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
