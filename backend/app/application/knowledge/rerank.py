"""Rerankers: re-score a small candidate pool more carefully than first-stage retrieval.

  lexical  deterministic; rewards covering the query's informative terms (IDF-weighted over
           the pool), keeping query word pairs together, and matching the section heading or
           file name. Free, fast, and a good precision filter for small local models.
  llm      asks the configured chat model to grade each passage 0-10 in one structured call.
           Better at paraphrase, but costs a model call per retrieval.
"""

import math

from pydantic import BaseModel, Field

from app.application.agents import prompts
from app.application.knowledge.ports import StoredChunk
from app.application.knowledge.search import tokenize
from app.application.llm import StructuredLLM


class LexicalReranker:
    name = "lexical"

    def score(self, query: str, candidates: list[StoredChunk]) -> list[float]:
        terms = list(dict.fromkeys(tokenize(query)))
        if not terms or not candidates:
            return [0.0] * len(candidates)
        bodies = [tokenize(c.text) for c in candidates]
        labels = [set(tokenize(f"{c.heading or ''} {c.filename}")) for c in candidates]
        n = len(candidates)
        idf = {t: math.log(1 + (n + 1) / (1 + sum(t in set(b) | l for b, l in zip(bodies, labels, strict=True)))) for t in terms}
        total = sum(idf.values())
        pairs = list(zip(terms, terms[1:]))
        scores = []
        for body, label in zip(bodies, labels, strict=True):
            present = set(body) | label
            coverage = sum(idf[t] for t in terms if t in present) / total
            adjacent = set(zip(body, body[1:]))
            proximity = sum(p in adjacent for p in pairs) / len(pairs) if pairs else coverage
            heading_hit = float(any(t in label for t in terms))
            scores.append(round(min(1.0, 0.7 * coverage + 0.2 * proximity + 0.1 * heading_hit), 4))
        return scores


class _Grade(BaseModel):
    id: int = Field(description="The passage number")
    score: int = Field(ge=0, le=10, description="0 = unrelated, 10 = directly answers the query")


class RelevanceGrades(BaseModel):
    grades: list[_Grade]


class LLMReranker:
    name = "llm"

    def __init__(self, llm: StructuredLLM) -> None:
        self._llm = llm

    def score(self, query: str, candidates: list[StoredChunk]) -> list[float]:
        if not candidates:
            return []
        result = self._llm.generate(
            task="reranker",
            system=prompts.RERANKER_SYSTEM,
            user=prompts.reranker_user(query, [(i, c.text) for i, c in enumerate(candidates)]),
            schema=RelevanceGrades,
        )
        grades = {g.id: g.score for g in result.value.grades}
        return [grades.get(i, 0) / 10 for i in range(len(candidates))]
