import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from evalforge.database import Base


def utcnow():
    return datetime.now(timezone.utc)


def new_id():
    return str(uuid.uuid4())


class PortableVector(TypeDecorator):
    """Use pgvector on Postgres and JSON everywhere else."""

    impl = JSON
    cache_ok = True

    def __init__(self, dimensions=256, *args, **kwargs):
        self.dimensions = dimensions
        super().__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(JSON())


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(512), default="manual")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding: Mapped[list] = mapped_column(PortableVector(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str] = mapped_column(Text, nullable=False)
    relevant_document_ids: Mapped[list] = mapped_column(JSON, default=list)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RagConfig(Base):
    __tablename__ = "rag_configs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), default="local")
    model: Mapped[str] = mapped_column(String(120), default="extractive-v1")
    api_base: Mapped[str] = mapped_column(String(512), default="")
    api_key_env: Mapped[str] = mapped_column(String(128), default="OPENAI_API_KEY")
    system_prompt: Mapped[str] = mapped_column(Text, default="Answer only from the context.")
    retrieval_method: Mapped[str] = mapped_column(String(32), default="bm25")
    top_k: Mapped[int] = mapped_column(Integer, default=3)
    temperature: Mapped[float] = mapped_column(Float, default=0.0)
    input_cost_per_million: Mapped[float] = mapped_column(Float, default=0.0)
    output_cost_per_million: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    experiments = relationship("Experiment", back_populates="config")


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    config_id: Mapped[str] = mapped_column(ForeignKey("rag_configs.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="running")
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    config = relationship("RagConfig", back_populates="experiments")
    results = relationship("EvaluationResult", back_populates="experiment", cascade="all, delete")
    security_results = relationship(
        "SecurityResult", back_populates="experiment", cascade="all, delete"
    )


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    experiment_id: Mapped[str] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False
    )
    test_case_id: Mapped[str] = mapped_column(ForeignKey("test_cases.id"), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    retrieved_document_ids: Mapped[list] = mapped_column(JSON, default=list)
    retrieval_recall_at_k: Mapped[float] = mapped_column(Float, default=0.0)
    answer_correctness: Mapped[float] = mapped_column(Float, default=0.0)
    citation_support: Mapped[float] = mapped_column(Float, default=0.0)
    hallucination_rate: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)

    experiment = relationship("Experiment", back_populates="results")
    test_case = relationship("TestCase")


class SecurityResult(Base):
    __tablename__ = "security_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    experiment_id: Mapped[str] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)

    experiment = relationship("Experiment", back_populates="security_results")
