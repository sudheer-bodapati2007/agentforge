"""Knowledge base use cases: upload, list, inspect, re-index, delete and search documents.

Every operation first checks that the actor owns the project (another user's project is
"not found"). Ingestion is idempotent: uploading the same file name replaces that document
and all of its chunks atomically; uploading identical content again changes nothing.
"""

import hashlib
import uuid
from dataclasses import dataclass

from app.application.knowledge.pipeline import RetrievalHit, RetrievalPipeline, embedding_text
from app.application.knowledge.ports import (
    DocumentView,
    Embedder,
    EmbeddingError,
    KnowledgeRepository,
    NewChunk,
    StoredChunk,
)
from app.application.workflow.secret_scanner import scan_for_secrets
from app.domain.errors import CapabilityUnavailableError, ConflictError, EntityNotFoundError
from app.domain.knowledge import (
    MAX_CHUNKS_PER_PROJECT,
    MAX_DOCUMENTS_PER_PROJECT,
    DocumentKind,
    chunk_document,
    normalize_content,
    validate_filename,
)
from app.domain.ports import ProjectRepository
from app.domain.user import User

REDACTED = "[redacted by AgentForge: possible secret]"
EMBED_BATCH = 32


@dataclass(frozen=True)
class UploadResult:
    document: DocumentView
    created: bool  # False when the same name already existed (replaced or unchanged)
    unchanged: bool


def redact_secrets(filename: str, text: str) -> tuple[str, int]:
    """Replace lines that look like credentials before anything is stored or embedded:
    documents end up in model prompts, so a pasted key must never travel further."""
    lines = {f.line for f in scan_for_secrets({f"docs/{filename}": text}) if f.line}
    if not lines:
        return text, 0
    out = text.split("\n")
    for number in lines:
        out[number - 1] = REDACTED
    return "\n".join(out), len(lines)


class KnowledgeService:
    def __init__(
        self,
        *,
        projects: ProjectRepository,
        documents: KnowledgeRepository,
        embedder: Embedder,
        pipeline: RetrievalPipeline,
    ) -> None:
        self._projects = projects
        self._documents = documents
        self._embedder = embedder
        self._pipeline = pipeline

    @property
    def embedder_name(self) -> str:
        return self._embedder.name

    def _owned(self, actor: User, project_id: uuid.UUID) -> None:
        if self._projects.get(actor.id, project_id) is None:
            raise EntityNotFoundError("Project", project_id)

    def _document(self, actor: User, project_id: uuid.UUID, document_id: uuid.UUID) -> DocumentView:
        self._owned(actor, project_id)
        document = self._documents.get_document(project_id, document_id)
        if document is None:
            raise EntityNotFoundError("Document", document_id)
        return document

    # ------------------------------------------------------------------ commands

    def upload(self, actor: User, project_id: uuid.UUID, filename: str, content: str) -> UploadResult:
        self._owned(actor, project_id)
        name, kind = validate_filename(filename)
        text = normalize_content(content)
        sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()

        existing = self._documents.find_by_filename(project_id, name)
        if existing and existing.sha256 == sha256 and existing.embedder == self._embedder.name:
            return UploadResult(existing, created=False, unchanged=True)
        if existing is None and len(self._documents.list_documents(project_id)) >= MAX_DOCUMENTS_PER_PROJECT:
            raise ConflictError(f"A project can hold at most {MAX_DOCUMENTS_PER_PROJECT} documents; delete one first")

        document = self._index(project_id, name, kind, text, sha256, replacing=existing)
        return UploadResult(document, created=existing is None, unchanged=False)

    def reindex(self, actor: User, project_id: uuid.UUID, document_id: uuid.UUID) -> DocumentView:
        """Re-chunk and re-embed with the current embedder (needed after switching models)."""
        document = self._document(actor, project_id, document_id)
        text = self._documents.document_content(project_id, document_id)
        if text is None:
            raise EntityNotFoundError("Document", document_id)
        return self._index(project_id, document.filename, document.kind, text, document.sha256, replacing=document)

    def delete(self, actor: User, project_id: uuid.UUID, document_id: uuid.UUID) -> None:
        self._owned(actor, project_id)
        if not self._documents.delete_document(project_id, document_id):
            raise EntityNotFoundError("Document", document_id)

    def _index(
        self, project_id: uuid.UUID, name: str, kind: DocumentKind, text: str, sha256: str, *, replacing: DocumentView | None
    ) -> DocumentView:
        safe, redacted = redact_secrets(name, text)
        drafts = chunk_document(safe, kind)
        others = sum(d.chunk_count for d in self._documents.list_documents(project_id) if not replacing or d.id != replacing.id)
        if others + len(drafts) > MAX_CHUNKS_PER_PROJECT:
            raise ConflictError(
                f"This document would bring the project to {others + len(drafts)} chunks; the limit is "
                f"{MAX_CHUNKS_PER_PROJECT}. Delete or shorten other documents first."
            )
        inputs = [embedding_text(name, d.heading, d.text) for d in drafts]
        try:
            vectors = [v for i in range(0, len(inputs), EMBED_BATCH) for v in self._embedder.embed_documents(inputs[i : i + EMBED_BATCH])]
        except EmbeddingError as exc:
            raise CapabilityUnavailableError(f"The embedding model is unavailable: {exc}") from exc
        if len(vectors) != len(drafts):
            raise CapabilityUnavailableError("The embedding model returned the wrong number of vectors")
        return self._documents.save_document(
            project_id=project_id,
            filename=name,
            kind=kind,
            content=safe,  # the redacted text: the secret is not kept anywhere
            sha256=sha256,  # of the uploaded text, so re-uploading it is recognised
            embedder=self._embedder.name,
            redacted_lines=redacted,
            chunks=[NewChunk(d, v) for d, v in zip(drafts, vectors, strict=True)],
        )

    # ------------------------------------------------------------------ queries

    def documents(self, actor: User, project_id: uuid.UUID) -> list[DocumentView]:
        self._owned(actor, project_id)
        return self._documents.list_documents(project_id)

    def chunks(self, actor: User, project_id: uuid.UUID, document_id: uuid.UUID) -> list[StoredChunk]:
        self._document(actor, project_id, document_id)
        return self._documents.chunks(project_id, document_id)

    def search(self, actor: User, project_id: uuid.UUID, query: str, k: int) -> list[RetrievalHit]:
        self._owned(actor, project_id)
        try:
            return self._pipeline.search(project_id, query, k)
        except EmbeddingError as exc:
            raise CapabilityUnavailableError(f"The embedding model is unavailable: {exc}") from exc
