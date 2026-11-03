"""Knowledge base tables (Phase 4). Documents belong to a project; chunks carry the
project id too, so search filters on one indexed column without a join."""

import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.knowledge import DocumentKind
from app.infrastructure.persistence.orm.base import Base, TimestampMixin, str_enum
from app.infrastructure.persistence.orm.vector import Vector


class KnowledgeDocumentModel(TimestampMixin, Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (UniqueConstraint("project_id", "filename", name="uq_knowledge_documents_project_id_filename"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[DocumentKind] = mapped_column(str_enum(DocumentKind), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # The (redacted) text, kept so documents can be re-indexed with a different embedder.
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedder: Mapped[str] = mapped_column(String(120), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    redacted_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class KnowledgeChunkModel(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal", name="uq_knowledge_chunks_document_id_ordinal"),
        Index("ix_knowledge_chunks_project_id_embedder", "project_id", "embedder"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    heading: Mapped[str | None] = mapped_column(String(300))
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    embedder: Mapped[str] = mapped_column(String(120), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector, nullable=False)
