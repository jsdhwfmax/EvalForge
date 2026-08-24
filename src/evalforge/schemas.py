from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DocumentCreate(BaseModel):
    id: Optional[str] = None
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    source: str = "manual"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentRead(ORMModel):
    id: str
    title: str
    content: str
    source: str
    metadata_json: Dict[str, Any]
    created_at: datetime


class TestCaseCreate(BaseModel):
    id: Optional[str] = None
    question: str = Field(min_length=1)
    expected_answer: str = Field(min_length=1)
    relevant_document_ids: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class TestCaseRead(TestCaseCreate, ORMModel):
    id: str
    created_at: datetime


class RagConfigCreate(BaseModel):
    id: Optional[str] = None
    name: str = Field(min_length=1, max_length=120)
    provider: str = "local"
    model: str = "extractive-v1"
    api_base: str = ""
    api_key_env: str = "OPENAI_API_KEY"
    system_prompt: str = "Answer only from the supplied context and cite sources as [doc:id]."
    retrieval_method: str = "bm25"
    top_k: int = Field(default=3, ge=1, le=20)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    input_cost_per_million: float = Field(default=0.0, ge=0.0)
    output_cost_per_million: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def validate_provider(self):
        allowed = {"local", "openai_compatible"}
        if self.provider not in allowed:
            raise ValueError("provider must be local or openai_compatible")
        if self.retrieval_method not in {"bm25", "vector", "hybrid"}:
            raise ValueError("retrieval_method must be bm25, vector, or hybrid")
        if self.provider == "openai_compatible" and not self.api_base:
            raise ValueError("api_base is required for openai_compatible providers")
        return self


class RagConfigRead(RagConfigCreate, ORMModel):
    id: str
    created_at: datetime


class ExperimentRun(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    config_ids: List[str] = Field(min_length=1)
    test_case_ids: Optional[List[str]] = None
    include_security: bool = True


class EvaluationResultRead(ORMModel):
    id: str
    test_case_id: str
    answer: str
    citations: List[str]
    retrieved_document_ids: List[str]
    retrieval_recall_at_k: float
    answer_correctness: float
    citation_support: float
    hallucination_rate: float
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    raw: Dict[str, Any]


class SecurityResultRead(ORMModel):
    id: str
    case_id: str
    category: str
    prompt: str
    response: str
    passed: bool
    evidence: Dict[str, Any]
    latency_ms: float


class ExperimentRead(ORMModel):
    id: str
    name: str
    config_id: str
    status: str
    summary: Dict[str, Any]
    error: str
    created_at: datetime
    completed_at: Optional[datetime]
    results: List[EvaluationResultRead] = Field(default_factory=list)
    security_results: List[SecurityResultRead] = Field(default_factory=list)


class DatasetImport(BaseModel):
    documents: List[DocumentCreate] = Field(default_factory=list)
    test_cases: List[TestCaseCreate] = Field(default_factory=list)


class ImportSummary(BaseModel):
    documents_created: int
    test_cases_created: int
    skipped: int


class ExperimentBatchRead(BaseModel):
    experiments: List[ExperimentRead]
