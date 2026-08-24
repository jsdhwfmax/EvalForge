import json
from pathlib import Path
from typing import Optional

import typer
from sqlalchemy import select

from evalforge.database import init_db, session_scope
from evalforge.models import RagConfig
from evalforge.schemas import DatasetImport, RagConfigCreate
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


if __name__ == "__main__":
    app()
