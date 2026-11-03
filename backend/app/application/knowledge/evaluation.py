"""Retrieval evaluation: labelled queries -> hit@k, MRR and negative rejection.

A result counts as relevant when it comes from the expected file AND contains the expected
text (case-insensitive), so the labels survive changes to chunk sizes. Negative queries have
no relevant document; the right answer is an empty result.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from app.application.knowledge.pipeline import RetrievalHit


@dataclass(frozen=True)
class RetrievalCase:
    query: str
    category: str  # keyword | paraphrase | code | negative
    source: str | None = None
    contains: str | None = None

    @property
    def negative(self) -> bool:
        return self.source is None

    def matches(self, hit: RetrievalHit) -> bool:
        return (
            self.source is not None
            and hit.chunk.filename == self.source
            and (self.contains or "").lower() in hit.chunk.text.lower()
        )


@dataclass(frozen=True)
class RetrievalMetrics:
    cases: int
    hit_at_1: float | None
    hit_at_3: float | None
    hit_at_k: float | None
    mrr: float | None
    negative_rejection: float | None  # share of negative queries answered with nothing
    by_category: dict[str, float] = field(default_factory=dict)  # hit@k per category (rejection for negatives)
    misses: list[str] = field(default_factory=list)


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def evaluate(search: Callable[[str, int], list[RetrievalHit]], cases: list[RetrievalCase], k: int = 5) -> RetrievalMetrics:
    ranks: list[int | None] = []  # 1-based rank of the first relevant hit, per positive case
    categories: dict[str, list[float]] = {}
    rejected: list[float] = []
    misses: list[str] = []
    for case in cases:
        hits = search(case.query, k)
        if case.negative:
            ok = float(not hits)
            rejected.append(ok)
            categories.setdefault(case.category, []).append(ok)
            if not ok:
                misses.append(f"[negative] {case.query!r} -> {hits[0].chunk.filename}")
            continue
        rank = next((i for i, hit in enumerate(hits, start=1) if case.matches(hit)), None)
        ranks.append(rank)
        categories.setdefault(case.category, []).append(float(rank is not None))
        if rank is None:
            got = hits[0].chunk.filename if hits else "nothing"
            misses.append(f"[{case.category}] {case.query!r} expected {case.source} -> {got}")
    return RetrievalMetrics(
        cases=len(cases),
        hit_at_1=_mean([float(r == 1) for r in ranks]),
        hit_at_3=_mean([float(r is not None and r <= 3) for r in ranks]),
        hit_at_k=_mean([float(r is not None) for r in ranks]),
        mrr=_mean([1 / r if r else 0.0 for r in ranks]),
        negative_rejection=_mean(rejected),
        by_category={name: _mean(values) for name, values in sorted(categories.items())},
        misses=misses,
    )
