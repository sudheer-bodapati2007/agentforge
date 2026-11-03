from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.dependencies import CurrentUser, SystemStatusServiceDep
from app.api.schemas.system import Health, Me, SystemStatus

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=Health, responses={503: {"model": Health}})
def health(service: SystemStatusServiceDep):
    if service.is_healthy():
        return Health(status="ok")
    return JSONResponse(status_code=503, content=Health(status="degraded").model_dump())


@router.get("/system/status", response_model=SystemStatus)
def system_status(_user: CurrentUser, service: SystemStatusServiceDep) -> SystemStatus:
    return SystemStatus.model_validate(service.status())


@router.get("/me", response_model=Me)
def me(user: CurrentUser) -> Me:
    """The signed-in user, as verified by the backend from the access token."""
    return Me.model_validate(user)
