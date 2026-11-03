"""Retrieval pipeline: dense + sparse candidates -> reciprocal rank fusion -> rerank ->
query-level relevance gate -> blended ranking -> de-duplicated top k.

Design choices measured with the retrieval evaluation (evals/datasets/retrieval):
  - The gate is per query, not per chunk: a paraphrased question shares few words with its
    answer, so judging each chunk by word overlap discarded half of the right answers.
    Instead, if even the best candidate scores below `min_score`, nothing is returned.
  - The final order blends the reranker score with the (normalised) fusion score: fusion
    alone ranked better than the lexical reranker alone; the blend was best of the three.

Every stage's score is kept on the hit, so the UI and the evaluation can show why a chunk
was (or was not) chosen. Modes exist so the evaluation can measure each stage's value.
"""

import uuid
from dataclasses import dataclass, replace
from typing import Literal

from app.application.knowledge.ports import Embedder, KnowledgeRepository, Reranker, StoredChunk
from app.application.knowledge.search import BM25, reciprocal_rank_fusion, tokenize

MAX_QUERY_CHARS = 2000
Mode = Literal["dense", "sparse", "hybrid"]


@dataclass(frozen=True)
class RetrievalSettings:
    mode: Mode = "hybrid"
    candidates: int = 20  # per first-stage retriever, and the size of the rerank pool
    top_k: int = 4
    # If the best candidate's rerank score is below this, the query has no relevant document
    # and nothing is returned (irrelevant context distracts a model more than none).
    # Ignored without a reranker.
    min_score: float = 0.15


@dataclass(frozen=True)
class RetrievalHit:
    chunk: StoredChunk
    dense_score: float | None
    sparse_score: float | None
    fused_score: float
    rerank_score: float | None
    score: float  # the final ranking score in [0, 1]


def embedding_text(filename: str, heading: str | None, text: str) -> str:
    """What gets embedded for a chunk: its text with the file and section it came from, so a
    chunk that never repeats its subject is still found by it."""
    return f"{filename}\n{heading}\n{text}" if heading else f"{filename}\n{text}"


class RetrievalPipeline:
    def __init__(
        self,
        repository: KnowledgeRepository,
        embedder: Embedder,
        reranker: Reranker | None,
        settings: RetrievalSettings | None = None,
    ) -> None:
        self._repository = repository
        self._embedder = embedder
        self._reranker = reranker
        self.settings = settings or RetrievalSettings()

    def search(self, project_id: uuid.UUID, query: str, k: int | None = None) -> list[RetrievalHit]:
        query = query.strip()
        if len(query) > MAX_QUERY_CHARS:
            # Cut at a word boundary: half a word would become a junk search term.
            query = query[:MAX_QUERY_CHARS].rsplit(None, 1)[0]
        if not query:
            return []
        s = self.settings
        k = k or s.top_k

        dense: dict[uuid.UUID, tuple[StoredChunk, float]] = {}
        if s.mode in ("dense", "hybrid"):
            vector = self._embedder.embed_query(query)
            for hit in self._repository.dense_search(project_id, self._embedder.name, vector, s.candidates):
                dense[hit.chunk.id] = (hit.chunk, hit.score)

        sparse: dict[uuid.UUID, tuple[StoredChunk, float]] = {}
        if s.mode in ("sparse", "hybrid"):
            chunks = self._repository.all_chunks(project_id, self._embedder.name)
            if chunks:
                bm25 = BM25([tokenize(f"{c.filename} {c.heading or ''} {c.text}") for c in chunks])
                ranked = sorted(zip(chunks, bm25.scores(tokenize(query)), strict=True), key=lambda p: -p[1])
                sparse = {c.id: (c, score) for c, score in ranked[: s.candidates] if score > 0}

        fused = reciprocal_rank_fusion([list(dense), list(sparse)])
        pool_ids = sorted(fused, key=lambda i: -fused[i])[: s.candidates]
        if not pool_ids:
            return []
        top = fused[pool_ids[0]]
        hits = [
            RetrievalHit(
                chunk=(dense.get(i) or sparse[i])[0],
                dense_score=round(dense[i][1], 4) if i in dense else None,
                sparse_score=round(sparse[i][1], 4) if i in sparse else None,
                fused_score=round(fused[i], 6),
                rerank_score=None,
                score=round(fused[i] / top, 4),
            )
            for i in pool_ids
        ]
        if self._reranker is not None:
            scores = self._reranker.score(query, [h.chunk for h in hits])
            if max(scores) < s.min_score:
                return []  # nothing in the knowledge base is about this query
            hits = [
                replace(h, rerank_score=round(r, 4), score=round(0.5 * r + 0.5 * h.score, 4))
                for position, (h, r) in enumerate(zip(hits, scores, strict=True))
                # Dense search always returns neighbours; one sharing no informative word
                # with the query is padding, unless it is the fusion's own first choice.
                if r > 0 or position == 0
            ]
            hits.sort(key=lambda h: (-h.score, -h.fused_score))
        return _without_overlaps(hits)[:k]


def _without_overlaps(hits: list[RetrievalHit]) -> list[RetrievalHit]:
    """Drop a hit whose lines overlap a better hit from the same document (chunks overlap
    by design); the model should not read the same paragraph twice."""
    kept: list[RetrievalHit] = []
    for hit in hits:
        c = hit.chunk
        if not any(
            k.chunk.document_id == c.document_id and k.chunk.start_line <= c.end_line and c.start_line <= k.chunk.end_line
            for k in kept
        ):
            kept.append(hit)
    return kept
