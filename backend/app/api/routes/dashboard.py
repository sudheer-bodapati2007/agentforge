from fastapi import APIRouter

from app.api.dependencies import CurrentUser, DashboardServiceDep
from app.api.schemas.dashboard import DashboardMetrics

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/metrics", response_model=DashboardMetrics)
def dashboard_metrics(user: CurrentUser, service: DashboardServiceDep) -> DashboardMetrics:
    return DashboardMetrics.model_validate(service.metrics(user))
