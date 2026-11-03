"""Maps domain and framework errors to one response shape: {"error": {code, message, details?}}."""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.application.auth import AuthenticationError, AuthUnavailableError
from app.domain.errors import (
    CapabilityUnavailableError,
    ConflictError,
    EntityNotFoundError,
    InvariantViolationError,
    RateLimitedError,
)

logger = logging.getLogger("agentforge.api")


def error_response(status_code: int, code: str, message: str, details: list | None = None):
    body: dict[str, Any] = {"code": code, "message": message}
    if details:
        body["details"] = details
    return JSONResponse(status_code=status_code, content={"error": body})


_HTTP_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    429: "rate_limited",
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AuthenticationError)
    async def _unauthenticated(_: Request, exc: AuthenticationError):
        response = error_response(status.HTTP_401_UNAUTHORIZED, "unauthorized", str(exc))
        response.headers["WWW-Authenticate"] = "Bearer"
        return response

    @app.exception_handler(AuthUnavailableError)
    async def _auth_unavailable(_: Request, exc: AuthUnavailableError):
        return error_response(status.HTTP_503_SERVICE_UNAVAILABLE, "auth_unavailable", str(exc))

    @app.exception_handler(ConflictError)
    async def _conflict(_: Request, exc: ConflictError):
        return error_response(status.HTTP_409_CONFLICT, "conflict", str(exc))

    @app.exception_handler(RateLimitedError)
    async def _rate_limited(_: Request, exc: RateLimitedError):
        response = error_response(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited", str(exc))
        if exc.retry_after_seconds:
            response.headers["Retry-After"] = str(exc.retry_after_seconds)
        return response

    @app.exception_handler(CapabilityUnavailableError)
    async def _unavailable(_: Request, exc: CapabilityUnavailableError):
        return error_response(status.HTTP_503_SERVICE_UNAVAILABLE, "capability_unavailable", str(exc))

    @app.exception_handler(EntityNotFoundError)
    async def _not_found(_: Request, exc: EntityNotFoundError):
        return error_response(status.HTTP_404_NOT_FOUND, "not_found", str(exc))

    @app.exception_handler(InvariantViolationError)
    async def _invariant(_: Request, exc: InvariantViolationError):
        return error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "validation_error",
            "Request validation failed",
            [{"loc": ["body", exc.field], "msg": exc.message, "type": "domain_invariant"}],
        )

    @app.exception_handler(OperationalError)
    async def _database_unavailable(request: Request, exc: OperationalError):
        # Connection/auth failures are operational, not bugs: one log line, no traceback,
        # and no driver message (it can contain hostnames and usernames) in the response.
        reason = str(exc.orig).strip().splitlines()[-1] if exc.orig else exc.__class__.__name__
        logger.error("Database unavailable on %s %s: %s", request.method, request.url.path, reason)
        return error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "database_unavailable",
            "The database is unavailable. Check DATABASE_URL and that the database is running.",
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        details = [
            # `input` is omitted so rejected payloads are never echoed back.
            {"loc": list(err.get("loc", [])), "msg": err.get("msg"), "type": err.get("type")}
            for err in exc.errors()
        ]
        return error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "validation_error", "Request validation failed", details
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        return error_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "internal_error", "An unexpected error occurred"
        )
