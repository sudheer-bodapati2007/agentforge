"""Workflow run endpoints, including a Server-Sent Events stream of run events."""

import asyncio
import io
import json
import re
import uuid
import zipfile
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.api.dependencies import CurrentUser, RunServiceDep, build_run_service
from app.api.schemas.common import ErrorResponse
from app.api.schemas.runs import (
    AgentExecutionRead,
    ApprovalDecision,
    ApprovalRead,
    ArtifactContent,
    ArtifactRead,
    EventRead,
    FindingRead,
    RunCreate,
    RunList,
    RunRead,
    TestResultRead,
)
from app.application.runs.models import CreateRunCommand
from app.domain.enums import RunStatus
from app.domain.errors import EntityNotFoundError
from app.domain.run import is_terminal
from app.domain.workspace import normalize_path

router = APIRouter(
    prefix="/api",
    tags=["runs"],
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9_.:-]{8,80}$")
STREAM_POLL_SECONDS = 0.75
STREAM_HEARTBEAT_SECONDS = 15


def _run_read(view) -> RunRead:
    return RunRead.model_validate(view)


@router.post(
    "/projects/{project_id}/runs",
    response_model=RunRead,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}, 429: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def start_run(
    project_id: uuid.UUID,
    user: CurrentUser,
    service: RunServiceDep,
    response: Response,
    payload: RunCreate | None = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> RunRead:
    if idempotency_key is not None and not _IDEMPOTENCY_KEY.match(idempotency_key):
        idempotency_key = None
    payload = payload or RunCreate()
    run, created = service.start(
        user, project_id, CreateRunCommand(require_approval=payload.require_approval, idempotency_key=idempotency_key)
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return _run_read(run)


@router.get("/runs", response_model=RunList)
def list_runs(
    user: CurrentUser,
    service: RunServiceDep,
    project_id: uuid.UUID | None = None,
    status_filter: Annotated[RunStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RunList:
    items, total = service.list_runs(user, project_id=project_id, status=status_filter, limit=limit, offset=offset)
    return RunList(items=[_run_read(r) for r in items], total=total)


@router.get("/runs/{run_id}", response_model=RunRead)
def get_run(run_id: uuid.UUID, user: CurrentUser, service: RunServiceDep) -> RunRead:
    return _run_read(service.get(user, run_id))


@router.post("/runs/{run_id}/cancel", response_model=RunRead, responses={409: {"model": ErrorResponse}})
def cancel_run(run_id: uuid.UUID, user: CurrentUser, service: RunServiceDep) -> RunRead:
    return _run_read(service.cancel(user, run_id))


@router.post("/runs/{run_id}/resume", response_model=RunRead, responses={409: {"model": ErrorResponse}})
def resume_run(run_id: uuid.UUID, user: CurrentUser, service: RunServiceDep) -> RunRead:
    return _run_read(service.resume(user, run_id))


@router.get("/runs/{run_id}/events", response_model=list[EventRead])
def list_events(
    run_id: uuid.UUID,
    user: CurrentUser,
    service: RunServiceDep,
    after: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
) -> list[EventRead]:
    return [EventRead.model_validate(e) for e in service.events(user, run_id, after, limit)]


@router.get("/runs/{run_id}/stream", response_class=StreamingResponse)
async def stream_events(
    run_id: uuid.UUID,
    request: Request,
    user: CurrentUser,
    after: Annotated[int, Query(ge=0)] = 0,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    """SSE stream of run events. Reconnecting clients send Last-Event-ID and receive
    only what they missed; the event log in the database is the source of truth."""
    container = request.app.state.container
    cursor = int(last_event_id) if last_event_id and last_event_id.isdigit() else after

    def poll(cursor_id: int):
        with container.session_factory() as session:
            service = build_run_service(session, container)
            run = service.get(user, run_id)
            return run.status, service.events(user, run_id, cursor_id, 200)

    await run_in_threadpool(poll, cursor)  # authorisation check before streaming starts

    async def events():
        nonlocal cursor
        idle = 0.0
        while not await request.is_disconnected():
            try:
                run_status, batch = await run_in_threadpool(poll, cursor)
            except EntityNotFoundError:
                yield "event: end\ndata: {}\n\n"
                return
            for event in batch:
                cursor = event.id
                data = EventRead.model_validate(event).model_dump_json()
                yield f"id: {event.id}\nevent: {event.type}\ndata: {data}\n\n"
            if batch:
                idle = 0.0
                continue
            if is_terminal(run_status):
                yield f"event: end\ndata: {json.dumps({'status': run_status.value})}\n\n"
                return
            await asyncio.sleep(STREAM_POLL_SECONDS)
            idle += STREAM_POLL_SECONDS
            if idle >= STREAM_HEARTBEAT_SECONDS:
                idle = 0.0
                yield ": keep-alive\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/runs/{run_id}/agents", response_model=list[AgentExecutionRead])
def list_agent_executions(run_id: uuid.UUID, user: CurrentUser, service: RunServiceDep) -> list[AgentExecutionRead]:
    return [AgentExecutionRead.model_validate(a) for a in service.agent_executions(user, run_id)]


@router.get("/runs/{run_id}/artifacts", response_model=list[ArtifactRead])
def list_artifacts(run_id: uuid.UUID, user: CurrentUser, service: RunServiceDep) -> list[ArtifactRead]:
    return [ArtifactRead.model_validate(a) for a in service.artifacts(user, run_id)]


@router.get("/runs/{run_id}/artifacts/content", response_model=ArtifactContent)
def get_artifact(
    run_id: uuid.UUID, user: CurrentUser, service: RunServiceDep, path: Annotated[str, Query(max_length=200)]
) -> ArtifactContent:
    normalized = normalize_path(path)
    contents = service.artifact_contents(user, run_id)
    if normalized not in contents:
        raise EntityNotFoundError("Artifact", normalized)
    return ArtifactContent(path=normalized, content=contents[normalized])


@router.get("/runs/{run_id}/download", response_class=Response)
def download_artifacts(run_id: uuid.UUID, user: CurrentUser, service: RunServiceDep) -> Response:
    run = service.get(user, run_id)
    contents = service.artifact_contents(user, run_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, content in sorted(contents.items()):
            archive.writestr(normalize_path(path), content)  # paths re-validated: no zip-slip
    slug = re.sub(r"[^a-z0-9]+", "-", run.project_name.lower()).strip("-")[:40] or "project"
    return Response(
        buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{slug}-{str(run_id)[:8]}.zip"'},
    )


@router.get("/runs/{run_id}/tests", response_model=list[TestResultRead])
def list_test_results(run_id: uuid.UUID, user: CurrentUser, service: RunServiceDep) -> list[TestResultRead]:
    return [TestResultRead.model_validate(t) for t in service.test_results(user, run_id)]


@router.get("/runs/{run_id}/reviews", response_model=list[FindingRead])
def list_findings(run_id: uuid.UUID, user: CurrentUser, service: RunServiceDep) -> list[FindingRead]:
    return [FindingRead.model_validate(f) for f in service.findings(user, run_id)]


@router.get("/runs/{run_id}/approvals", response_model=list[ApprovalRead])
def list_approvals(run_id: uuid.UUID, user: CurrentUser, service: RunServiceDep) -> list[ApprovalRead]:
    return [ApprovalRead.model_validate(a) for a in service.approvals(user, run_id)]


@router.post(
    "/runs/{run_id}/approvals/{approval_id}",
    response_model=ApprovalRead,
    responses={409: {"model": ErrorResponse}},
)
def decide_approval(
    run_id: uuid.UUID, approval_id: uuid.UUID, payload: ApprovalDecision, user: CurrentUser, service: RunServiceDep
) -> ApprovalRead:
    return ApprovalRead.model_validate(service.decide(user, run_id, approval_id, payload.approve, payload.comment))
