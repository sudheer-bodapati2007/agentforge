"""Ports and read models for the knowledge base. Implementations live in infrastructure/."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.knowledge import ChunkDraft, DocumentKind


class EmbeddingError(Exception):
    """The embedding model could not be reached or returned something unusable."""


class Embedder(Protocol):
    @property
    def name(self) -> str:
        """Identifies the vector space (model and size). Vectors from different embedders
        are never compared: switching embedders requires re-indexing."""
        ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


@dataclass(frozen=True)
class DocumentView:
    id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    kind: DocumentKind
    size_bytes: int
    sha256: str
    chunk_count: int
    embedder: str
    redacted_lines: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class StoredChunk:
    id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    ordinal: int
    text: str
    heading: str | None
    start_line: int
    end_line: int

    @property
    def location(self) -> str:
        lines = f"lines {self.start_line}-{self.end_line}" if self.end_line != self.start_line else f"line {self.start_line}"
        return f"{lines}{f' ({self.heading})' if self.heading else ''}"


@dataclass(frozen=True)
class NewChunk:
    draft: ChunkDraft
    embedding: list[float]


@dataclass(frozen=True)
class ScoredChunk:
    chunk: StoredChunk
    score: float


class KnowledgeRepository(Protocol):
    """Project-scoped storage. Callers check that the actor owns the project first."""

    def list_documents(self, project_id: uuid.UUID) -> list[DocumentView]: ...

    def get_document(self, project_id: uuid.UUID, document_id: uuid.UUID) -> DocumentView | None: ...

    def find_by_filename(self, project_id: uuid.UUID, filename: str) -> DocumentView | None: ...

    def document_content(self, project_id: uuid.UUID, document_id: uuid.UUID) -> str | None: ...

    def save_document(
        self,
        *,
        project_id: uuid.UUID,
        filename: str,
        kind: DocumentKind,
        content: str,
        sha256: str,
        embedder: str,
        redacted_lines: int,
        chunks: list[NewChunk],
    ) -> DocumentView:
        """Insert, or replace the document with this filename and all of its chunks, atomically."""
        ...

    def delete_document(self, project_id: uuid.UUID, document_id: uuid.UUID) -> bool: ...

    def chunks(self, project_id: uuid.UUID, document_id: uuid.UUID) -> list[StoredChunk]: ...

    def all_chunks(self, project_id: uuid.UUID, embedder: str) -> list[StoredChunk]:
        """Every searchable chunk of the project in this embedder's space (for sparse search)."""
        ...

    def dense_search(self, project_id: uuid.UUID, embedder: str, vector: list[float], limit: int) -> list[ScoredChunk]:
        """Nearest chunks by cosine similarity (1 = identical direction), best first."""
        ...


class Reranker(Protocol):
    @property
    def name(self) -> str: ...

    def score(self, query: str, candidates: list[StoredChunk]) -> list[float]:
        """A relevance score in [0, 1] for each candidate, in the same order."""
        ...
