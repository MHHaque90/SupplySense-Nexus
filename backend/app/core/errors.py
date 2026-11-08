"""Typed API errors and JSON envelopes for all SupplySense Nexus endpoints.

Envelope contract (fixed by the Phase 11 audit):

- Success: ``{"success": true, "data": ..., "error": null, "meta": {...}}``
- Error:   ``{"success": false, "error": {"code", "message"[, "details"]},
  "meta": {...}}``

``meta`` always carries ``timestamp`` and ``data_source_label``; AI endpoints
add ``conversation_id`` and ``session_id`` when known. Error messages are
fixed per code: internal details are logged, never returned.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("supplysense.api")


class ErrorCode:
    """Machine-readable error codes (HTTP status mapping is fixed)."""

    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    AI_UNAVAILABLE = "AI_UNAVAILABLE"
    FEATURE_DISABLED = "FEATURE_DISABLED"

    _STATUS = {
        UNAUTHORIZED: 401,
        FORBIDDEN: 403,
        NOT_FOUND: 404,
        CONFLICT: 409,
        VALIDATION_ERROR: 422,
        RATE_LIMIT_EXCEEDED: 429,
        INTERNAL_ERROR: 500,
        AI_UNAVAILABLE: 503,
        FEATURE_DISABLED: 403,
    }

    _MESSAGES = {
        UNAUTHORIZED: "Authentication failed.",
        FORBIDDEN: "You do not have permission to perform this action.",
        NOT_FOUND: "The requested resource was not found.",
        CONFLICT: "The request conflicts with the current resource state.",
        VALIDATION_ERROR: "The request payload failed validation.",
        RATE_LIMIT_EXCEEDED: "Rate limit exceeded. Try again later.",
        INTERNAL_ERROR: "An unexpected internal error occurred.",
        AI_UNAVAILABLE: (
            "The AI assistant is unavailable. The configured provider could "
            "not be reached or is not configured."
        ),
        FEATURE_DISABLED: "This capability is disabled by configuration.",
    }

    @classmethod
    def status_for(cls, code: str) -> int:
        """Return the HTTP status for a code (500 when unknown)."""
        return cls._STATUS.get(code, 500)

    @classmethod
    def message_for(cls, code: str) -> str:
        """Return the fixed public message for a code."""
        return cls._MESSAGES.get(code, cls._MESSAGES[cls.INTERNAL_ERROR])


class APIError(Exception):
    """Application error rendered as a JSON error envelope."""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message or ErrorCode.message_for(code))
        self.code = code
        self.message = message or ErrorCode.message_for(code)
        self.details = details
        self.headers = headers or {}
        self.status_code = ErrorCode.status_for(code)

    def to_payload(self) -> dict[str, Any]:
        """Return the error object (without envelope/meta)."""
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details is not None:
            error["details"] = self.details
        return error


def _meta(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "data_source_label": "synthetic",
    }
    if extra:
        meta.update(extra)
    return meta


def error_response(
    code: str,
    message: str | None = None,
    details: Any = None,
    headers: dict[str, str] | None = None,
    meta: dict[str, Any] | None = None,
) -> JSONResponse:
    """Build a JSON error response with the standard envelope."""
    error: dict[str, Any] = {
        "code": code,
        "message": message or ErrorCode.message_for(code),
    }
    if details is not None:
        error["details"] = details
    return JSONResponse(
        status_code=ErrorCode.status_for(code),
        content={"success": False, "error": error, "meta": _meta(meta)},
        headers=headers,
    )


def success_envelope(data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the standard success envelope."""
    return {"success": True, "data": data, "error": None, "meta": _meta(meta)}


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Render :class:`APIError` as the standard envelope."""
    return error_response(exc.code, exc.message, exc.details, exc.headers)


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Render FastAPI validation failures as VALIDATION_ERROR (422)."""
    details = [
        {
            "location": [str(part) for part in error.get("loc", ())],
            "message": error.get("msg", "invalid value"),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]
    return error_response(
        ErrorCode.VALIDATION_ERROR,
        ErrorCode.message_for(ErrorCode.VALIDATION_ERROR),
        details=details,
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Map framework HTTP errors onto the fixed code table."""
    code = {
        401: ErrorCode.UNAUTHORIZED,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.NOT_FOUND,
        409: ErrorCode.CONFLICT,
        422: ErrorCode.VALIDATION_ERROR,
        429: ErrorCode.RATE_LIMIT_EXCEEDED,
        503: ErrorCode.AI_UNAVAILABLE,
    }.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    message = exc.detail if isinstance(exc.detail, str) else ErrorCode.message_for(code)
    return error_response(code, message, headers=getattr(exc, "headers", None))


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log unexpected failures and return a generic INTERNAL_ERROR."""
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return error_response(ErrorCode.INTERNAL_ERROR)


def register_error_handlers(app: FastAPI) -> None:
    """Attach the standard error handlers to a FastAPI application."""
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


__all__ = [
    "APIError",
    "ErrorCode",
    "error_response",
    "register_error_handlers",
    "success_envelope",
]
