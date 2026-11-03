"""Composition root: the only module that chooses concrete implementations.

Everything else depends on ports. Tests build a container with fakes for the LLM,
sandbox, token verifier and retriever, and with workers disabled.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.application.auth import TokenVerifier, UnconfiguredTokenVerifier
from app.application.evaluation.benchmark import BenchmarkRunner
from app.application.evaluation.ports import CodingSystem
from app.application.evaluation.systems import EvaluationJournal, MultiAgentWorkflow, SingleAgentBaseline
from app.application.knowledge.pipeline import RetrievalSettings
from app.application.knowledge.ports import Embedder, Reranker
from app.application.knowledge.rerank import LexicalReranker, LLMReranker
from app.application.llm import Pricing, StructuredLLM
from app.application.runs.ports import WorkflowEngine
from app.application.runs.service import ModelInfo, RunPolicy
from app.application.workflow.ports import NullRetriever, Retriever, Sandbox
from app.application.workflow.steps import WorkflowSteps
from app.domain.errors import CapabilityUnavailableError
from app.domain.evaluation import SystemKind
from app.infrastructure.auth.supabase_jwt import SupabaseJwtVerifier
from app.infrastructure.config import Settings
from app.infrastructure.knowledge.embedders import build_embedder
from app.infrastructure.knowledge.retriever import KnowledgeRetriever
from app.infrastructure.llm.factory import build_llm, build_pricing, describe_model
from app.infrastructure.persistence.database import build_engine, build_session_factory
from app.infrastructure.persistence.evaluation_repository import SqlAlchemyEvaluationRepository
from app.infrastructure.persistence.run_journal import SqlAlchemyRunJournal
from app.infrastructure.sandbox.docker_sandbox import DockerSandbox
from app.infrastructure.worker.background import BackgroundWorker
from app.infrastructure.workflow.checkpointer import Checkpointer, build_checkpointer
from app.infrastructure.workflow.langgraph_engine import LangGraphWorkflowEngine

logger = logging.getLogger("agentforge.bootstrap")


@dataclass
class Container:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    token_verifier: TokenVerifier
    model_info: ModelInfo
    llm: StructuredLLM | None
    pricing: Pricing | None
    sandbox: Sandbox
    retriever: Retriever
    embedder: Embedder
    reranker: Reranker | None
    retrieval_settings: RetrievalSettings
    run_policy: RunPolicy
    run_workers: bool
    checkpointer: Checkpointer | None = None
    workflow_engine: WorkflowEngine | None = None
    worker: BackgroundWorker | None = None
    _started: bool = field(default=False, repr=False)

    # ------------------------------------------------------------------ workflow

    def steps_for(self, run_id: str) -> WorkflowSteps:
        return WorkflowSteps(
            llm=self.llm,
            sandbox=self.sandbox,
            journal=SqlAlchemyRunJournal(self.session_factory, run_id),
            retriever=self.retriever,
            pricing=self.pricing,
        )

    def ensure_engine(self) -> WorkflowEngine | None:
        if self.workflow_engine is None and self.llm is not None:
            self.checkpointer = self.checkpointer or build_checkpointer(self.settings)
            self.workflow_engine = LangGraphWorkflowEngine(
                checkpointer=self.checkpointer.saver, steps_factory=self.steps_for
            )
        return self.workflow_engine

    # ------------------------------------------------------------------ lifecycle

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        if not self.run_workers:
            return
        if self.ensure_engine() is None:
            logger.warning("No LLM configured (%s): run workers not started", self.model_info.detail)
            return
        # A crash mid-run can leave a test database container behind; workers are not running yet.
        removed = self.sandbox.remove_leftovers()
        if removed:
            logger.info("removed %d leftover sandbox container(s)/network(s)", removed)
        self.worker = BackgroundWorker(
            session_factory=self.session_factory,
            engine_factory=lambda: self.workflow_engine,
            concurrency=self.settings.worker_concurrency,
            poll_seconds=self.settings.worker_poll_seconds,
            heartbeat_timeout_seconds=self.settings.run_heartbeat_timeout_seconds,
        )
        self.worker.start()

    def stop(self) -> None:
        if self.worker:
            self.worker.stop()
        if self.checkpointer:
            self.checkpointer.close()
        self.engine.dispose()

    @property
    def workers_running(self) -> bool:
        return self.worker is not None


def build_sandbox(settings: Settings) -> Sandbox:
    return DockerSandbox(
        image=settings.sandbox_image,
        timeout_seconds=settings.sandbox_timeout_seconds,
        memory_mb=settings.sandbox_memory_mb,
        cpus=settings.sandbox_cpus,
        enabled=settings.sandbox_enabled,
        database_image=settings.sandbox_database_image,
    )


@dataclass
class Benchmark:
    """Everything the benchmark command needs, wired from settings."""

    runner: BenchmarkRunner
    systems: dict[SystemKind, CodingSystem]
    close: Callable[[], None]


def build_benchmark(
    settings: Settings,
    *,
    persist: bool = True,
    llm: StructuredLLM | None = None,
    sandbox: Sandbox | None = None,
) -> Benchmark:
    llm = llm or build_llm(settings)
    if llm is None:
        raise CapabilityUnavailableError(f"no model is configured: {describe_model(settings).detail}")
    if llm.is_demo:
        raise CapabilityUnavailableError("the scripted demo model is not AI; benchmarking it would measure nothing")
    sandbox = sandbox or build_sandbox(settings)
    pricing = build_pricing(settings)
    engine = LangGraphWorkflowEngine(
        checkpointer=InMemorySaver(),
        steps_factory=lambda run_id: WorkflowSteps(
            llm=llm, sandbox=sandbox, journal=EvaluationJournal(run_id), retriever=NullRetriever(), pricing=pricing
        ),
    )
    systems: dict[SystemKind, CodingSystem] = {
        SystemKind.MULTI_AGENT: MultiAgentWorkflow(
            engine=engine,
            max_debug_iterations=settings.max_debug_iterations,
            max_review_corrections=settings.max_review_corrections,
        ),
        SystemKind.SINGLE_AGENT: SingleAgentBaseline(llm=llm, sandbox=sandbox),
    }
    repository, close = None, lambda: None
    if persist:
        db = build_engine(settings)
        session = build_session_factory(db)()
        repository = SqlAlchemyEvaluationRepository(session)

        def close() -> None:
            session.close()
            db.dispose()

    runner = BenchmarkRunner(
        sandbox=sandbox, repository=repository, model_name=llm.model_name, demo_model=llm.is_demo, pricing=pricing
    )
    return Benchmark(runner=runner, systems=systems, close=close)


def build_reranker(settings: Settings, llm: StructuredLLM | None) -> Reranker | None:
    if settings.rag_reranker == "none":
        return None
    if settings.rag_reranker == "llm":
        if llm is not None and not llm.is_demo:
            return LLMReranker(llm)
        logger.warning("RAG_RERANKER=llm needs a configured (non-demo) model; using the lexical reranker")
    return LexicalReranker()


def build_token_verifier(settings: Settings) -> TokenVerifier:
    if settings.supabase_url:
        return SupabaseJwtVerifier(settings.supabase_url, audience=settings.auth_audience)
    logger.warning("SUPABASE_URL is not set: authentication is unavailable and protected routes return 503")
    return UnconfiguredTokenVerifier()


def build_container(
    settings: Settings,
    *,
    token_verifier: TokenVerifier | None = None,
    llm: StructuredLLM | None = None,
    sandbox: Sandbox | None = None,
    retriever: Retriever | None = None,
    embedder: Embedder | None = None,
    run_workers: bool | None = None,
) -> Container:
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    model_info = describe_model(settings)
    if llm is not None:
        model_info = ModelInfo(True, llm.model_name, llm.is_demo)
    llm = llm if llm is not None else build_llm(settings)
    embedder = embedder or build_embedder(settings)
    reranker = build_reranker(settings, llm)
    retrieval_settings = RetrievalSettings(
        mode=settings.rag_mode,
        candidates=settings.rag_candidates,
        top_k=settings.rag_top_k,
        min_score=settings.rag_min_score,
    )
    return Container(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        token_verifier=token_verifier or build_token_verifier(settings),
        model_info=model_info,
        llm=llm,
        pricing=build_pricing(settings),
        sandbox=sandbox or build_sandbox(settings),
        retriever=retriever or KnowledgeRetriever(session_factory, embedder, reranker, retrieval_settings),
        embedder=embedder,
        reranker=reranker,
        retrieval_settings=retrieval_settings,
        run_policy=RunPolicy(
            max_debug_iterations=settings.max_debug_iterations,
            max_review_corrections=settings.max_review_corrections,
            max_active_runs_per_user=settings.max_active_runs_per_user,
            max_runs_per_user_per_hour=settings.max_runs_per_user_per_hour,
        ),
        run_workers=settings.worker_enabled if run_workers is None else run_workers,
    )
