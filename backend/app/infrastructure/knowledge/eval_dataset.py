"""Loads the retrieval evaluation set and runs it through the real ingestion and retrieval
code, with in-memory storage:

    <dataset>/docs/*            the corpus (any supported document type)
    <dataset>/queries.jsonl     {"query", "category", "source"?, "contains"?} per line;
                                no "source" means a negative query (nothing should be found)
"""

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.application.knowledge.evaluation import RetrievalCase, RetrievalMetrics, evaluate
from app.application.knowledge.pipeline import RetrievalPipeline, RetrievalSettings
from app.application.knowledge.ports import Embedder, Reranker
from app.application.knowledge.service import KnowledgeService
from app.domain.errors import InvariantViolationError
from app.domain.user import User
from app.infrastructure.knowledge.memory_repository import InMemoryKnowledgeRepository

EVAL_USER = User(id=uuid.UUID("00000000-0000-4000-8000-00000000e7a1"), email="eval@agentforge.local", name="Evaluation")
EVAL_PROJECT = uuid.UUID("00000000-0000-4000-8000-00000000e7a1")


class _EvalProjects:
    def get(self, owner_id, project_id):
        return object() if (owner_id, project_id) == (EVAL_USER.id, EVAL_PROJECT) else None


def load_cases(path: Path) -> list[RetrievalCase]:
    cases = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            case = RetrievalCase(item["query"], item["category"], item.get("source"), item.get("contains"))
        except (ValueError, KeyError, TypeError) as exc:
            raise InvariantViolationError("queries", f"line {number} is not a valid case: {exc}") from exc
        if (case.source is None) != (case.category == "negative"):
            raise InvariantViolationError("queries", f"line {number}: only negative cases may omit 'source'")
        cases.append(case)
    return cases


@dataclass
class IndexedCorpus:
    repository: InMemoryKnowledgeRepository
    documents: int
    chunks: int


def index_corpus(docs_dir: Path, embedder: Embedder) -> IndexedCorpus:
    """Ingest every document exactly as an upload would (validation, redaction, chunking,
    embedding), so the evaluation measures the production path."""
    repository = InMemoryKnowledgeRepository()
    service = KnowledgeService(
        projects=_EvalProjects(), documents=repository, embedder=embedder,
        pipeline=RetrievalPipeline(repository, embedder, None),
    )
    chunks = 0
    files = sorted(p for p in docs_dir.iterdir() if p.is_file())
    for path in files:
        chunks += service.upload(EVAL_USER, EVAL_PROJECT, path.name, path.read_text(encoding="utf-8")).document.chunk_count
    return IndexedCorpus(repository, len(files), chunks)


def run_configuration(
    corpus: IndexedCorpus, embedder: Embedder, reranker: Reranker | None, settings: RetrievalSettings, cases: list[RetrievalCase], k: int
) -> RetrievalMetrics:
    pipeline = RetrievalPipeline(corpus.repository, embedder, reranker, settings)
    return evaluate(lambda query, top: pipeline.search(EVAL_PROJECT, query, top), cases, k)
