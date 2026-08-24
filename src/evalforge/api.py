import json
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from evalforge import __version__
from evalforge.config import get_settings
from evalforge.database import get_db, init_db
from evalforge.models import Document, Experiment, RagConfig, TestCase
from evalforge.schemas import (
    DatasetImport,
    DocumentCreate,
    DocumentRead,
    ExperimentBatchRead,
    ExperimentRead,
    ExperimentRun,
    ImportSummary,
    RagConfigCreate,
    RagConfigRead,
    TestCaseCreate,
    TestCaseRead,
)
from evalforge.services import (
    create_config,
    create_document,
    create_test_case,
    import_dataset,
    run_experiment,
    select_test_cases,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


settings = get_settings()
app = FastAPI(
    title="EvalForge API",
    version=__version__,
    description="Reproducible quality and security evaluation for RAG applications.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    database_name = db.bind.dialect.name if db.bind is not None else "unknown"
    return {"status": "ok", "version": __version__, "database": database_name}


@app.post("/api/v1/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def add_document(payload: DocumentCreate, db: Session = Depends(get_db)):
    try:
        return create_document(db, payload)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Document ID already exists") from exc


@app.get("/api/v1/documents", response_model=list[DocumentRead])
def list_documents(db: Session = Depends(get_db)):
    return list(db.scalars(select(Document).order_by(Document.created_at)))


@app.post("/api/v1/test-cases", response_model=TestCaseRead, status_code=status.HTTP_201_CREATED)
def add_test_case(payload: TestCaseCreate, db: Session = Depends(get_db)):
    try:
        return create_test_case(db, payload)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Test case ID already exists") from exc


@app.get("/api/v1/test-cases", response_model=list[TestCaseRead])
def list_test_cases(db: Session = Depends(get_db)):
    return list(db.scalars(select(TestCase).order_by(TestCase.created_at)))


@app.post("/api/v1/configs", response_model=RagConfigRead, status_code=status.HTTP_201_CREATED)
def add_config(payload: RagConfigCreate, db: Session = Depends(get_db)):
    try:
        return create_config(db, payload)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Configuration name or ID already exists"
        ) from exc


@app.get("/api/v1/configs", response_model=list[RagConfigRead])
def list_configs(db: Session = Depends(get_db)):
    return list(db.scalars(select(RagConfig).order_by(RagConfig.created_at)))


@app.post("/api/v1/datasets/import", response_model=ImportSummary)
def add_dataset(payload: DatasetImport, db: Session = Depends(get_db)):
    created_docs, created_tests, skipped = import_dataset(db, payload)
    return ImportSummary(
        documents_created=created_docs, test_cases_created=created_tests, skipped=skipped
    )


@app.post("/api/v1/datasets/upload", response_model=ImportSummary)
async def upload_dataset(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=415, detail="Upload a JSON dataset file")
    try:
        raw = await file.read()
        payload = DatasetImport.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid dataset: %s" % exc) from exc
    created_docs, created_tests, skipped = import_dataset(db, payload)
    return ImportSummary(
        documents_created=created_docs, test_cases_created=created_tests, skipped=skipped
    )


def _load_experiment(db: Session, experiment_id: str):
    query = (
        select(Experiment)
        .where(Experiment.id == experiment_id)
        .options(selectinload(Experiment.results), selectinload(Experiment.security_results))
    )
    return db.scalar(query)


@app.post("/api/v1/experiments/run", response_model=ExperimentBatchRead)
def run_batch(payload: ExperimentRun, db: Session = Depends(get_db)):
    test_cases = select_test_cases(db, payload.test_case_ids)
    if not test_cases:
        raise HTTPException(status_code=400, detail="No test cases selected")
    resolved_configs = [db.get(RagConfig, config_id) for config_id in payload.config_ids]
    missing = [
        config_id
        for config_id, config in zip(payload.config_ids, resolved_configs)
        if config is None
    ]
    if missing:
        raise HTTPException(status_code=404, detail={"missing_config_ids": missing})
    configs = [config for config in resolved_configs if config is not None]
    experiments = []
    for config in configs:
        experiment = run_experiment(
            db,
            name="%s · %s" % (payload.name, config.name),
            config=config,
            test_cases=test_cases,
            include_security=payload.include_security,
        )
        experiments.append(_load_experiment(db, experiment.id))
    return ExperimentBatchRead(experiments=experiments)


@app.get("/api/v1/experiments", response_model=list[ExperimentRead])
def list_experiments(db: Session = Depends(get_db)):
    query = (
        select(Experiment)
        .options(selectinload(Experiment.results), selectinload(Experiment.security_results))
        .order_by(Experiment.created_at.desc())
    )
    return list(db.scalars(query))


@app.get("/api/v1/experiments/{experiment_id}", response_model=ExperimentRead)
def get_experiment(experiment_id: str, db: Session = Depends(get_db)):
    experiment = _load_experiment(db, experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment
