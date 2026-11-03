import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import CurrentUser, ProjectServiceDep
from app.api.schemas.common import ErrorResponse
from app.api.schemas.project import ProjectCreate, ProjectList, ProjectRead, ProjectUpdate

router = APIRouter(
    prefix="/api/projects",
    tags=["projects"],
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)


@router.get("", response_model=ProjectList)
def list_projects(
    user: CurrentUser,
    service: ProjectServiceDep,
    q: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProjectList:
    return ProjectList.from_page(service.list(user, search=q, limit=limit, offset=offset))


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, user: CurrentUser, service: ProjectServiceDep) -> ProjectRead:
    return ProjectRead.from_overview(service.create(user, payload.to_command()))


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: uuid.UUID, user: CurrentUser, service: ProjectServiceDep) -> ProjectRead:
    return ProjectRead.from_overview(service.get(user, project_id))


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: uuid.UUID, payload: ProjectUpdate, user: CurrentUser, service: ProjectServiceDep
) -> ProjectRead:
    return ProjectRead.from_overview(service.update(user, project_id, payload.to_command()))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: uuid.UUID, user: CurrentUser, service: ProjectServiceDep) -> Response:
    service.delete(user, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
