import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import ContainerDep, CurrentUser, KnowledgeServiceDep
from app.api.schemas.knowledge import (
    ChunkRead,
    DocumentList,
    DocumentRead,
    DocumentUpload,
    DocumentUploadResult,
    SearchHit,
    SearchResponse,
)
from app.application.knowledge.ports import DocumentView

router = APIRouter(prefix="/api/projects/{project_id}", tags=["knowledge"])


def _read(document: DocumentView, current_embedder: str) -> DocumentRead:
    return DocumentRead.model_validate(document).model_copy(update={"stale": document.embedder != current_embedder})


@router.get("/documents", response_model=DocumentList)
def list_documents(project_id: uuid.UUID, user: CurrentUser, service: KnowledgeServiceDep) -> DocumentList:
    embedder = service.embedder_name
    return DocumentList(items=[_read(d, embedder) for d in service.documents(user, project_id)], embedder=embedder)


@router.post(
    "/documents",
    response_model=DocumentUploadResult,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "A document with this name existed and was replaced, or is unchanged"}},
)
def upload_document(
    project_id: uuid.UUID, payload: DocumentUpload, user: CurrentUser, service: KnowledgeServiceDep, response: Response
) -> DocumentUploadResult:
    result = service.upload(user, project_id, payload.filename, payload.content)
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return DocumentUploadResult(
        document=_read(result.document, service.embedder_name), created=result.created, unchanged=result.unchanged
    )


@router.get("/documents/{document_id}/chunks", response_model=list[ChunkRead])
def document_chunks(
    project_id: uuid.UUID, document_id: uuid.UUID, user: CurrentUser, service: KnowledgeServiceDep
) -> list[ChunkRead]:
    return [ChunkRead.model_validate(c) for c in service.chunks(user, project_id, document_id)]


@router.post("/documents/{document_id}/reindex", response_model=DocumentRead)
def reindex_document(
    project_id: uuid.UUID, document_id: uuid.UUID, user: CurrentUser, service: KnowledgeServiceDep
) -> DocumentRead:
    return _read(service.reindex(user, project_id, document_id), service.embedder_name)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(project_id: uuid.UUID, document_id: uuid.UUID, user: CurrentUser, service: KnowledgeServiceDep) -> Response:
    service.delete(user, project_id, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/knowledge/search", response_model=SearchResponse)
def search_knowledge(
    project_id: uuid.UUID,
    user: CurrentUser,
    service: KnowledgeServiceDep,
    container: ContainerDep,
    q: Annotated[str, Query(min_length=1, max_length=2000)],
    k: Annotated[int, Query(ge=1, le=20)] = 5,
) -> SearchResponse:
    """The exact pipeline the agents use, with every stage's score, for testing a knowledge base."""
    hits = service.search(user, project_id, q, k)
    return SearchResponse(
        query=q,
        embedder=service.embedder_name,
        mode=container.retrieval_settings.mode,
        reranker=container.reranker.name if container.reranker else None,
        results=[
            SearchHit(
                document_id=h.chunk.document_id,
                source=h.chunk.filename,
                location=h.chunk.location,
                heading=h.chunk.heading,
                start_line=h.chunk.start_line,
                end_line=h.chunk.end_line,
                text=h.chunk.text,
                dense_score=h.dense_score,
                sparse_score=h.sparse_score,
                fused_score=h.fused_score,
                rerank_score=h.rerank_score,
                score=h.score,
            )
            for h in hits
        ],
    )
