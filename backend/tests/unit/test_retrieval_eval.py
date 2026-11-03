"""The retrieval evaluation set as a regression guard (deterministic hash embedder).

Thresholds sit a little below the measured values (22 Oct 2026: hybrid + lexical rerank
hit@1 0.88, hit@3 0.94, MRR 0.91, negative rejection 0.75), so a change that makes
retrieval worse fails here instead of silently degrading the agents' context.
"""

from pathlib import Path

import pytest

from app.application.knowledge.pipeline import RetrievalSettings
from app.application.knowledge.rerank import LexicalReranker
from app.domain.errors import InvariantViolationError
from app.infrastructure.knowledge.embedders import HashEmbedder
from app.infrastructure.knowledge.eval_dataset import index_corpus, load_cases, run_configuration

DATASET = Path(__file__).resolve().parents[3] / "evals" / "datasets" / "retrieval"


@pytest.fixture(scope="module")
def setup():
    embedder = HashEmbedder()
    return embedder, index_corpus(DATASET / "docs", embedder), load_cases(DATASET / "queries.jsonl")


def test_every_label_points_at_text_that_exists():
    cases = load_cases(DATASET / "queries.jsonl")
    assert len(cases) >= 30 and {c.category for c in cases} == {"keyword", "paraphrase", "code", "negative"}
    for case in cases:
        if not case.negative:
            text = (DATASET / "docs" / case.source).read_text(encoding="utf-8")
            assert case.contains.lower() in text.lower(), f"label for {case.query!r} is not in {case.source}"


def test_default_pipeline_meets_the_measured_quality(setup):
    embedder, corpus, cases = setup
    metrics = run_configuration(corpus, embedder, LexicalReranker(), RetrievalSettings(), cases, k=5)
    assert metrics.hit_at_1 >= 0.85
    assert metrics.hit_at_3 >= 0.90
    assert metrics.mrr >= 0.88
    assert metrics.negative_rejection >= 0.75
    assert metrics.by_category["keyword"] == 1.0


def test_fusion_beats_either_retriever_alone(setup):
    embedder, corpus, cases = setup
    mrr = {
        mode: run_configuration(corpus, embedder, None, RetrievalSettings(mode=mode), cases, k=5).mrr
        for mode in ("dense", "sparse", "hybrid")
    }
    assert mrr["hybrid"] >= max(mrr["dense"], mrr["sparse"])


def test_without_a_gate_nonsense_queries_still_get_context(setup):
    """Why the reranker gate exists: without it every query returns something."""
    embedder, corpus, cases = setup
    assert run_configuration(corpus, embedder, None, RetrievalSettings(), cases, k=5).negative_rejection == 0.0


def test_malformed_query_files_are_rejected(tmp_path):
    bad = tmp_path / "queries.jsonl"
    bad.write_text('{"query": "q", "category": "keyword"}\n', encoding="utf-8")  # positive without a source
    with pytest.raises(InvariantViolationError, match="line 1"):
        load_cases(bad)
    bad.write_text("not json\n", encoding="utf-8")
    with pytest.raises(InvariantViolationError, match="line 1"):
        load_cases(bad)
