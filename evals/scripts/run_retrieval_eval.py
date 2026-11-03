"""Retrieval evaluation (Phase 4): the labelled query set against the sample corpus, for
each pipeline configuration, so the value of every stage (dense, sparse, fusion, reranking)
is measured rather than assumed.

Run from backend/ with the backend's virtualenv:

    .venv/Scripts/python ../evals/scripts/run_retrieval_eval.py                         # hash embedder
    .venv/Scripts/python ../evals/scripts/run_retrieval_eval.py --embedder ollama       # nomic-embed-text
    .venv/Scripts/python ../evals/scripts/run_retrieval_eval.py --embedder ollama --llm-rerank

Writes evals/reports/retrieval-<embedder>-<timestamp>.json.
"""

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.application.knowledge.pipeline import RetrievalSettings  # noqa: E402
from app.application.knowledge.ports import EmbeddingError  # noqa: E402
from app.application.knowledge.rerank import LexicalReranker, LLMReranker  # noqa: E402
from app.domain.errors import DomainError  # noqa: E402
from app.infrastructure.config import Settings  # noqa: E402
from app.infrastructure.knowledge.embedders import build_embedder  # noqa: E402
from app.infrastructure.knowledge.eval_dataset import index_corpus, load_cases, run_configuration  # noqa: E402
from app.infrastructure.llm.factory import build_llm  # noqa: E402

DATASET = ROOT / "evals" / "datasets" / "retrieval"


def configurations(llm_rerank: bool, llm=None) -> list[tuple[str, str, object]]:
    configs = [
        ("dense", "dense", None),
        ("sparse (BM25)", "sparse", None),
        ("hybrid (RRF)", "hybrid", None),
        ("dense + lexical rerank", "dense", LexicalReranker()),
        ("hybrid + lexical rerank", "hybrid", LexicalReranker()),
    ]
    if llm_rerank:
        configs.append(("hybrid + LLM rerank", "hybrid", LLMReranker(llm)))
    return configs


def fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def main(argv: list[str] | None = None, *, settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--embedder", choices=["hash", "ollama", "google"], default="hash")
    parser.add_argument("--model", help="embedding model (default per provider)")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--llm-rerank", action="store_true", help="also evaluate the LLM reranker (uses LLM_* settings)")
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--report-dir", type=Path, default=ROOT / "evals" / "reports")
    args = parser.parse_args(argv)

    base = settings or Settings()
    settings = base.model_copy(update={"embedding_provider": args.embedder, "embedding_model": args.model})
    try:
        embedder = build_embedder(settings)
        llm = build_llm(settings) if args.llm_rerank else None
        if args.llm_rerank and (llm is None or llm.is_demo):
            raise ValueError("--llm-rerank needs a configured, non-demo LLM (LLM_PROVIDER / LLM_MODEL)")
        cases = load_cases(args.dataset / "queries.jsonl")
        corpus = index_corpus(args.dataset / "docs", embedder)
    except (DomainError, ValueError, EmbeddingError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    defaults = RetrievalSettings()
    print(f"corpus: {corpus.documents} documents, {corpus.chunks} chunks; {len(cases)} queries; embedder {embedder.name}; k={args.k}\n")
    print(f"{'configuration':<26} {'hit@1':>6} {'hit@3':>6} {'hit@k':>6} {'MRR':>6} {'reject':>7}   keyword paraphrase code")
    results = []
    for label, mode, reranker in configurations(args.llm_rerank, llm):
        cfg = RetrievalSettings(mode=mode, candidates=defaults.candidates, top_k=args.k, min_score=defaults.min_score)
        try:
            m = run_configuration(corpus, embedder, reranker, cfg, cases, args.k)
        except (EmbeddingError, DomainError) as exc:
            print(f"{label:<26} failed: {exc}")
            continue
        c = m.by_category
        print(
            f"{label:<26} {fmt(m.hit_at_1):>6} {fmt(m.hit_at_3):>6} {fmt(m.hit_at_k):>6} {fmt(m.mrr):>6} {fmt(m.negative_rejection):>7}"
            f"   {fmt(c.get('keyword')):>7} {fmt(c.get('paraphrase')):>10} {fmt(c.get('code')):>4}"
        )
        results.append({"configuration": label, "mode": mode, "reranker": getattr(reranker, "name", None), **asdict(m)})

    best = max(results, key=lambda r: (r["mrr"] or 0, r["negative_rejection"] or 0), default=None)
    if best and best["misses"]:
        print(f"\nmisses for '{best['configuration']}':")
        for miss in best["misses"]:
            print(f"  {miss}")

    args.report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    path = args.report_dir / f"retrieval-{embedder.name.replace(':', '-')}-{stamp}.json"
    path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "embedder": embedder.name,
                "k": args.k,
                "min_score": defaults.min_score,
                "corpus": {"documents": corpus.documents, "chunks": corpus.chunks},
                "queries": len(cases),
                "results": results,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nreport: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
