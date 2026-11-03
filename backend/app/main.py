import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.middleware import RequestIdMiddleware, RequestSizeLimitMiddleware
from app.api.routes import dashboard, evaluations, knowledge, projects, runs, system
from app.application.auth import TokenVerifier
from app.application.llm import StructuredLLM
from app.application.workflow.ports import Retriever, Sandbox
from app.bootstrap import Container, build_container
from app.infrastructure.config import Settings, get_settings
from app.infrastructure.observability import configure_logging


def create_app(
    settings: Settings | None = None,
    token_verifier: TokenVerifier | None = None,
    *,
    llm: StructuredLLM | None = None,
    sandbox: Sandbox | None = None,
    retriever: Retriever | None = None,
    run_workers: bool | None = None,
    container: Container | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json_logs=settings.environment == "production")
    container = container or build_container(
        settings,
        token_verifier=token_verifier,
        llm=llm,
        sandbox=sandbox,
        retriever=retriever,
        run_workers=run_workers,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        container.start()
        try:
            yield
        finally:
            container.stop()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.container = container
    app.state.settings = settings
    app.state.engine = container.engine
    app.state.session_factory = container.session_factory
    app.state.token_verifier = container.token_verifier

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "Idempotency-Key", "Last-Event-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestIdMiddleware)
    # Added last so it is outermost and rejects oversized bodies before anything else runs.
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=settings.max_request_bytes)

    register_error_handlers(app)
    app.include_router(system.router)
    app.include_router(projects.router)
    app.include_router(dashboard.router)
    app.include_router(runs.router)
    app.include_router(evaluations.router)
    app.include_router(knowledge.router)
    return app


def _default_app() -> FastAPI:
    logging.getLogger("agentforge").info("creating application")
    return create_app()


app = _default_app()
