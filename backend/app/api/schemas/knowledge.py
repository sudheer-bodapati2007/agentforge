import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.knowledge import DocumentKind


class DocumentUpload(BaseModel):
    filename: str = Field(min_length=1, max_length=300)
    # Text only; the size limit in characters is checked again in bytes by the domain rules.
    content: str = Field(min_length=1, max_length=400_000)


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    kind: DocumentKind
    size_bytes: int
    sha256: str
    chunk_count: int
    embedder: str
    redacted_lines: int
    # True when indexed by a different embedder than the current one: not searchable until re-indexed.
    stale: bool = False
    created_at: datetime
    updated_at: datetime


class DocumentUploadResult(BaseModel):
    document: DocumentRead
    created: bool
    unchanged: bool


class DocumentList(BaseModel):
    items: list[DocumentRead]
    embedder: str


class ChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ordinal: int
    text: str
    heading: str | None
    start_line: int
    end_line: int


class SearchHit(BaseModel):
    document_id: uuid.UUID
    source: str
    location: str
    heading: str | None
    start_line: int
    end_line: int
    text: str
    dense_score: float | None
    sparse_score: float | None
    fused_score: float
    rerank_score: float | None
    score: float


class SearchResponse(BaseModel):
    query: str
    embedder: str
    mode: str
    reranker: str | None
    results: list[SearchHit]
