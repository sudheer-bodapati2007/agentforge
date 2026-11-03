"""In-memory `KnowledgeRepository` for the retrieval evaluation and tests: same contract
as the database repository, no database needed."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.application.knowledge.ports import DocumentView, NewChunk, ScoredChunk, StoredChunk
from app.application.knowledge.search import cosine
from app.domain.knowledge import DocumentKind


@dataclass
class _Document:
    view: DocumentView
    content: str
    chunks: list[tuple[StoredChunk, str, list[float]]] = field(default_factory=list)  # (chunk, embedder, vector)


class InMemoryKnowledgeRepository:
    def __init__(self) -> None:
        self._docs: dict[uuid.UUID, _Document] = {}

    def _project_docs(self, project_id: uuid.UUID) -> list[_Document]:
        return sorted((d for d in self._docs.values() if d.view.project_id == project_id), key=lambda d: d.view.filename)

    def list_documents(self, project_id: uuid.UUID) -> list[DocumentView]:
        return [d.view for d in self._project_docs(project_id)]

    def get_document(self, project_id: uuid.UUID, document_id: uuid.UUID) -> DocumentView | None:
        doc = self._docs.get(document_id)
        return doc.view if doc and doc.view.project_id == project_id else None

    def find_by_filename(self, project_id: uuid.UUID, filename: str) -> DocumentView | None:
        return next((d.view for d in self._project_docs(project_id) if d.view.filename == filename), None)

    def document_content(self, project_id: uuid.UUID, document_id: uuid.UUID) -> str | None:
        doc = self._docs.get(document_id)
        return doc.content if doc and doc.view.project_id == project_id else None

    def save_document(self, *, project_id, filename, kind: DocumentKind, content, sha256, embedder, redacted_lines, chunks: list[NewChunk]) -> DocumentView:
        existing = self.find_by_filename(project_id, filename)
        now = datetime.now(UTC)
        view = DocumentView(
            id=existing.id if existing else uuid.uuid4(),
            project_id=project_id,
            filename=filename,
            kind=kind,
            size_bytes=len(content.encode("utf-8")),
            sha256=sha256,
            chunk_count=len(chunks),
            embedder=embedder,
            redacted_lines=redacted_lines,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        stored = [
            (StoredChunk(uuid.uuid4(), view.id, filename, c.draft.ordinal, c.draft.text, c.draft.heading, c.draft.start_line, c.draft.end_line), embedder, c.embedding)
            for c in chunks
        ]
        self._docs[view.id] = _Document(view, content, stored)
        return view

    def delete_document(self, project_id: uuid.UUID, document_id: uuid.UUID) -> bool:
        if self.get_document(project_id, document_id) is None:
            return False
        del self._docs[document_id]
        return True

    def chunks(self, project_id: uuid.UUID, document_id: uuid.UUID) -> list[StoredChunk]:
        doc = self._docs.get(document_id)
        return [c for c, _, _ in doc.chunks] if doc and doc.view.project_id == project_id else []

    def all_chunks(self, project_id: uuid.UUID, embedder: str) -> list[StoredChunk]:
        return [c for d in self._project_docs(project_id) for c, e, _ in d.chunks if e == embedder]

    def dense_search(self, project_id: uuid.UUID, embedder: str, vector: list[float], limit: int) -> list[ScoredChunk]:
        scored = [
            ScoredChunk(c, cosine(vector, v)) for d in self._project_docs(project_id) for c, e, v in d.chunks if e == embedder
        ]
        return sorted(scored, key=lambda s: -s.score)[:limit]
