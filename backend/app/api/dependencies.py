"""Composition root for request-scoped dependencies.

This is the only place where the presentation layer learns about concrete
infrastructure classes; routes depend on application services only.
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.application.auth import AuthenticationError, TokenVerifier
from app.application.dashboard import DashboardService
from app.application.evaluation.service import EvaluationService
from app.application.knowledge.pipeline import RetrievalPipeline
from app.application.knowledge.service import KnowledgeService
from app.application.projects import ProjectService
from app.application.runs.service import RunService
from app.application.system import AppInfo, LLMConfiguration, SystemStatusService
from app.bootstrap import Container
from app.domain.user import User
from app.infrastructure.config import Settings
from app.infrastructure.persistence.dashboard_read_model import SqlAlchemyDashboardReadModel
from app.infrastructure.persistence.database import SqlAlchemyDatabaseProbe
from app.infrastructure.persistence.evaluation_repository import SqlAlchemyEvaluationRepository
from app.infrastructure.persistence.knowledge_repository import SqlAlchemyKnowledgeRepository
from app.infrastructure.persistence.project_repository import SqlAlchemyProjectRepository
from app.infrastructure.persistence.run_repository import SqlAlchemyRunRepository


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_session(request: Request) -> Iterator[Session]:
    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
ContainerDep = Annotated[Container, Depends(get_container)]

# auto_error=False so a missing header goes through our uniform 401 error shape.
_bearer = HTTPBearer(auto_error=False, description="Supabase Auth access token")


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """Authenticate every protected request. The backend is the enforcement point."""
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Missing bearer token")
    verifier: TokenVerifier = request.app.state.token_verifier
    return verifier.verify(credentials.credentials)


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_project_service(session: SessionDep) -> ProjectService:
    return ProjectService(SqlAlchemyProjectRepository(session))


def get_dashboard_service(session: SessionDep) -> DashboardService:
    return DashboardService(SqlAlchemyDashboardReadModel(session))


def get_knowledge_service(session: SessionDep, container: ContainerDep) -> KnowledgeService:
    documents = SqlAlchemyKnowledgeRepository(session)
    return KnowledgeService(
        projects=SqlAlchemyProjectRepository(session),
        documents=documents,
        embedder=container.embedder,
        pipeline=RetrievalPipeline(documents, container.embedder, container.reranker, container.retrieval_settings),
    )


def get_evaluation_service(session: SessionDep) -> EvaluationService:
    return EvaluationService(SqlAlchemyEvaluationRepository(session))


def get_system_status_service(
    session: SessionDep, settings: SettingsDep, container: ContainerDep
) -> SystemStatusService:
    model = container.model_info
    return SystemStatusService(
        app_info=AppInfo(
            app_name=settings.app_name,
            version=settings.app_version,
            environment=settings.environment,
            max_debug_iterations=settings.max_debug_iterations,
        ),
        llm=LLMConfiguration(
            provider=settings.llm_provider if container.llm is None or not model.demo else "scripted",
            model=settings.llm_model or model.name,
            api_key_present=settings.llm_api_key_present,
            configured=model.configured,
            demo=model.demo,
            detail=model.detail,
        ),
        database=SqlAlchemyDatabaseProbe(session),
        sandbox=container.sandbox,
        worker_running=container.workers_running,
    )


def build_run_service(session: Session, container: Container) -> RunService:
    return RunService(
        runs=SqlAlchemyRunRepository(session),
        projects=SqlAlchemyProjectRepository(session),
        policy=container.run_policy,
        model=container.model_info,
        notifier=container.worker,
    )


def get_run_service(session: SessionDep, container: ContainerDep) -> RunService:
    return build_run_service(session, container)


ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]
EvaluationServiceDep = Annotated[EvaluationService, Depends(get_evaluation_service)]
KnowledgeServiceDep = Annotated[KnowledgeService, Depends(get_knowledge_service)]
SystemStatusServiceDep = Annotated[SystemStatusService, Depends(get_system_status_service)]
RunServiceDep = Annotated[RunService, Depends(get_run_service)]
