"""SQLAlchemy implementation of the `KnowledgeRepository` port.

Dense search runs in the database on PostgreSQL (pgvector's cosine distance operator) and
in Python on SQLite, behind the same method, so tests exercise the same contract.
"""

import json
import uuid

from sqlalchemy import Float, cast, delete, literal, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.knowledge.ports import DocumentView, NewChunk, ScoredChunk, StoredChunk
from app.application.knowledge.search import cosine
from app.domain.errors import ConflictError
from app.domain.knowledge import DocumentKind
from app.infrastructure.persistence.mapping import to_view
from app.infrastructure.persistence.orm import KnowledgeChunkModel, KnowledgeDocumentModel
from app.infrastructure.persistence.orm.vector import PgVector

_CHUNK_COLUMNS = (
    KnowledgeChunkModel.id,
    KnowledgeChunkModel.document_id,
    KnowledgeDocumentModel.filename,
    KnowledgeChunkModel.ordinal,
    KnowledgeChunkModel.text,
    KnowledgeChunkModel.heading,
    KnowledgeChunkModel.start_line,
    KnowledgeChunkModel.end_line,
)


def _chunk(row) -> StoredChunk:
    return StoredChunk(*row[: len(_CHUNK_COLUMNS)])


class SqlAlchemyKnowledgeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _chunks_query(self, *columns):
        return select(*_CHUNK_COLUMNS, *columns).join(
            KnowledgeDocumentModel, KnowledgeDocumentModel.id == KnowledgeChunkModel.document_id
        )

    # ------------------------------------------------------------------ documents

    def list_documents(self, project_id: uuid.UUID) -> list[DocumentView]:
        rows = self._session.scalars(
            select(KnowledgeDocumentModel)
            .where(KnowledgeDocumentModel.project_id == project_id)
            .order_by(KnowledgeDocumentModel.filename)
        )
        return [to_view(DocumentView, row) for row in rows]

    def get_document(self, project_id: uuid.UUID, document_id: uuid.UUID) -> DocumentView | None:
        row = self._session.scalar(
            select(KnowledgeDocumentModel).where(
                KnowledgeDocumentModel.project_id == project_id, KnowledgeDocumentModel.id == document_id
            )
        )
        return to_view(DocumentView, row) if row else None

    def find_by_filename(self, project_id: uuid.UUID, filename: str) -> DocumentView | None:
        row = self._session.scalar(
            select(KnowledgeDocumentModel).where(
                KnowledgeDocumentModel.project_id == project_id, KnowledgeDocumentModel.filename == filename
            )
        )
        return to_view(DocumentView, row) if row else None

    def document_content(self, project_id: uuid.UUID, document_id: uuid.UUID) -> str | None:
        return self._session.scalar(
            select(KnowledgeDocumentModel.content).where(
                KnowledgeDocumentModel.project_id == project_id, KnowledgeDocumentModel.id == document_id
            )
        )

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
        s = self._session
        try:
            document = s.scalar(
                select(KnowledgeDocumentModel).where(
                    KnowledgeDocumentModel.project_id == project_id, KnowledgeDocumentModel.filename == filename
                )
            )
            if document is None:
                document = KnowledgeDocumentModel(project_id=project_id, filename=filename)
                s.add(document)
            else:
                s.execute(delete(KnowledgeChunkModel).where(KnowledgeChunkModel.document_id == document.id))
            document.kind = kind
            document.content = content
            document.size_bytes = len(content.encode("utf-8"))
            document.sha256 = sha256
            document.embedder = embedder
            document.redacted_lines = redacted_lines
            document.chunk_count = len(chunks)
            s.flush()
            s.add_all(
                KnowledgeChunkModel(
                    document_id=document.id,
                    project_id=project_id,
                    ordinal=c.draft.ordinal,
                    text=c.draft.text,
                    heading=(c.draft.heading or None) and c.draft.heading[:300],
                    start_line=c.draft.start_line,
                    end_line=c.draft.end_line,
                    embedder=embedder,
                    embedding=c.embedding,
                )
                for c in chunks
            )
            s.commit()  # the document and all of its chunks become visible together
        except IntegrityError as exc:
            s.rollback()
            # Two uploads of the same file name raced; the unique constraint kept one.
            raise ConflictError(f"{filename} was changed by another upload at the same time; try again") from exc
        except Exception:
            s.rollback()
            raise
        s.refresh(document)
        return to_view(DocumentView, document)

    def delete_document(self, project_id: uuid.UUID, document_id: uuid.UUID) -> bool:
        result = self._session.execute(
            delete(KnowledgeDocumentModel).where(
                KnowledgeDocumentModel.project_id == project_id, KnowledgeDocumentModel.id == document_id
            )
        )
        self._session.commit()
        return result.rowcount > 0

    # ------------------------------------------------------------------ chunks

    def chunks(self, project_id: uuid.UUID, document_id: uuid.UUID) -> list[StoredChunk]:
        rows = self._session.execute(
            self._chunks_query()
            .where(KnowledgeChunkModel.project_id == project_id, KnowledgeChunkModel.document_id == document_id)
            .order_by(KnowledgeChunkModel.ordinal)
        )
        return [_chunk(row) for row in rows]

    def all_chunks(self, project_id: uuid.UUID, embedder: str) -> list[StoredChunk]:
        rows = self._session.execute(
            self._chunks_query()
            .where(KnowledgeChunkModel.project_id == project_id, KnowledgeChunkModel.embedder == embedder)
            .order_by(KnowledgeDocumentModel.filename, KnowledgeChunkModel.ordinal)
        )
        return [_chunk(row) for row in rows]

    def dense_search(self, project_id: uuid.UUID, embedder: str, vector: list[float], limit: int) -> list[ScoredChunk]:
        scope = (KnowledgeChunkModel.project_id == project_id, KnowledgeChunkModel.embedder == embedder)
        if self._session.get_bind().dialect.name == "postgresql":
            # pgvector cosine distance (0 = same direction); the query vector is bound as text and cast.
            query = cast(literal(json.dumps([float(x) for x in vector])), PgVector())
            distance = KnowledgeChunkModel.embedding.op("<=>", return_type=Float())(query).label("distance")
            rows = self._session.execute(self._chunks_query(distance).where(*scope).order_by(distance).limit(limit))
            return [ScoredChunk(_chunk(row), 1.0 - float(row.distance)) for row in rows]
        rows = self._session.execute(self._chunks_query(KnowledgeChunkModel.embedding).where(*scope))
        scored = [ScoredChunk(_chunk(row), cosine(vector, row.embedding)) for row in rows]
        return sorted(scored, key=lambda s: -s.score)[:limit]
