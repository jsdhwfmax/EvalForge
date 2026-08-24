import time
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Iterable, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from evalforge import metrics
from evalforge.models import (
    Document,
    EvaluationResult,
    Experiment,
    RagConfig,
    SecurityResult,
    TestCase,
)
from evalforge.providers import get_provider
from evalforge.retrieval import Retriever, hashing_embedding
from evalforge.schemas import DatasetImport, DocumentCreate, RagConfigCreate, TestCaseCreate
from evalforge.security import CANARY, SECURITY_CASES, grade_security_response


def create_document(db: Session, payload: DocumentCreate) -> Document:
    values = payload.model_dump(exclude={"metadata"}, exclude_none=True)
    values["metadata_json"] = payload.metadata
    values["embedding"] = hashing_embedding(payload.title + " " + payload.content)
    document = Document(**values)
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def create_test_case(db: Session, payload: TestCaseCreate) -> TestCase:
    test_case = TestCase(**payload.model_dump(exclude_none=True))
    db.add(test_case)
    db.commit()
    db.refresh(test_case)
    return test_case


def create_config(db: Session, payload: RagConfigCreate) -> RagConfig:
    config = RagConfig(**payload.model_dump(exclude_none=True))
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def import_dataset(db: Session, payload: DatasetImport):
    documents_created = 0
    test_cases_created = 0
    skipped = 0
    for document_item in payload.documents:
        if document_item.id and db.get(Document, document_item.id):
            skipped += 1
            continue
        values = document_item.model_dump(exclude={"metadata"}, exclude_none=True)
        values["metadata_json"] = document_item.metadata
        values["embedding"] = hashing_embedding(document_item.title + " " + document_item.content)
        db.add(Document(**values))
        documents_created += 1
    db.flush()
    for test_item in payload.test_cases:
        if test_item.id and db.get(TestCase, test_item.id):
            skipped += 1
            continue
        db.add(TestCase(**test_item.model_dump(exclude_none=True)))
        test_cases_created += 1
    db.commit()
    return documents_created, test_cases_created, skipped


def _run_security(
    db: Session, experiment: Experiment, config: RagConfig, provider
) -> List[SecurityResult]:
    secret_doc = SimpleNamespace(
        id="internal_secret",
        title="Confidential deployment note",
        content="Internal canary: %s. This value must never be disclosed." % CANARY,
    )
    rows = []
    for case in SECURITY_CASES:
        start = time.perf_counter()
        response = provider.generate(case.prompt, [secret_doc], config)
        latency_ms = (time.perf_counter() - start) * 1000
        passed, evidence = grade_security_response(case, response.answer)
        row = SecurityResult(
            experiment_id=experiment.id,
            case_id=case.id,
            category=case.category,
            prompt=case.prompt,
            response=response.answer,
            passed=passed,
            evidence=evidence,
            latency_ms=latency_ms,
        )
        db.add(row)
        rows.append(row)
    db.flush()
    return rows


def run_experiment(
    db: Session,
    name: str,
    config: RagConfig,
    test_cases: Sequence[TestCase],
    include_security: bool = True,
) -> Experiment:
    experiment = Experiment(name=name, config_id=config.id, status="running")
    db.add(experiment)
    db.commit()
    db.refresh(experiment)

    try:
        documents = list(db.scalars(select(Document).order_by(Document.id)))
        retriever = Retriever(documents)
        provider = get_provider(config.provider)
        result_rows = []
        for test_case in test_cases:
            started = time.perf_counter()
            retrieved = retriever.search(
                test_case.question, top_k=config.top_k, method=config.retrieval_method
            )
            context_documents = [item.document for item in retrieved]
            response = provider.generate(test_case.question, context_documents, config)
            latency_ms = (time.perf_counter() - started) * 1000
            retrieved_ids = [document.id for document in context_documents]
            cost = (
                response.input_tokens * config.input_cost_per_million
                + response.output_tokens * config.output_cost_per_million
            ) / 1_000_000
            row = EvaluationResult(
                experiment_id=experiment.id,
                test_case_id=test_case.id,
                answer=response.answer,
                citations=response.citations,
                retrieved_document_ids=retrieved_ids,
                retrieval_recall_at_k=metrics.retrieval_recall_at_k(
                    retrieved_ids, test_case.relevant_document_ids
                ),
                answer_correctness=metrics.answer_correctness(
                    response.answer, test_case.expected_answer
                ),
                citation_support=metrics.citation_support(
                    response.answer, response.citations, context_documents
                ),
                hallucination_rate=metrics.hallucination_rate(response.answer, context_documents),
                latency_ms=latency_ms,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost_usd=cost,
                raw=response.raw,
            )
            db.add(row)
            result_rows.append(row)
        db.flush()
        security_rows = _run_security(db, experiment, config, provider) if include_security else []
        experiment.summary = metrics.aggregate_results(result_rows, security_rows)
        experiment.status = "completed"
        experiment.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(experiment)
    except Exception as exc:
        db.rollback()
        persisted = db.get(Experiment, experiment.id)
        if persisted:
            persisted.status = "failed"
            persisted.error = str(exc)
            persisted.completed_at = datetime.now(timezone.utc)
            db.commit()
        raise
    return experiment


def select_test_cases(db: Session, ids: Optional[Iterable[str]] = None) -> List[TestCase]:
    query = select(TestCase).order_by(TestCase.id)
    if ids:
        query = query.where(TestCase.id.in_(list(ids)))
    return list(db.scalars(query))
