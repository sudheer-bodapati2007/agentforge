"""The workflow's `Retriever` port backed by the knowledge base.

Runs inside worker threads, so it opens its own session per call. It re-checks that the
run's owner owns the project, and a retrieval failure (embedding model down) gives the
agents no context instead of failing the run.
"""

import logging
import uuid

from sqlalchemy.orm import Session, sessionmaker

from app.application.knowledge.pipeline import RetrievalPipeline, RetrievalSettings
from app.application.knowledge.ports import Embedder, EmbeddingError, Reranker
from app.application.llm import LLMError
from app.application.workflow.ports import RetrievedChunk
from app.infrastructure.persistence.knowledge_repository import SqlAlchemyKnowledgeRepository
from app.infrastructure.persistence.project_repository import SqlAlchemyProjectRepository

logger = logging.getLogger("agentforge.knowledge")


class KnowledgeRetriever:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        embedder: Embedder,
        reranker: Reranker | None,
        settings: RetrievalSettings,
    ) -> None:
        self._sessions = session_factory
        self._embedder = embedder
        self._reranker = reranker
        self._settings = settings

    def retrieve(self, *, owner_id: str, project_id: str, query: str, k: int = 4) -> list[RetrievedChunk]:
        try:
            owner, project = uuid.UUID(owner_id), uuid.UUID(project_id)
        except ValueError:
            return []  # not a user project (e.g. a benchmark run)
        with self._sessions() as session:
            if SqlAlchemyProjectRepository(session).get(owner, project) is None:
                return []
            pipeline = RetrievalPipeline(SqlAlchemyKnowledgeRepository(session), self._embedder, self._reranker, self._settings)
            try:
                hits = pipeline.search(project, query, k)
            except (EmbeddingError, LLMError) as exc:
                logger.warning("retrieval skipped for project %s: %s", project, exc)
                return []
        return [RetrievedChunk(source=h.chunk.filename, text=h.chunk.text, score=h.score, location=h.chunk.location) for h in hits]
