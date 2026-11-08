"""Tool execution engine: validation, org scoping, audit, bounded failure.

Execution invariants (Phase 11):

- Only specs from the registry run; there is no dynamic import, no eval,
  no SQL/Python generation. Declarations (``executable=False``) always fail
  with an explicit "declared only" error — there is no execution path.
- Parameters are validated with a Pydantic model generated from the spec's
  JSON schema (extra fields forbidden, required fields enforced).
- Authorization uses ``spec.required_roles`` (admin bypasses); failures are
  403-equivalent tool errors.
- Every attempt — success, validation failure, refusal — is audited as
  ``ai.tool.call`` write-once into ``audit_events``.
- Unexpected exceptions are logged server-side and returned as a generic
  tool error; internals are never exposed to the model or the caller.
"""

import logging
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model

from backend.app.ai import audit
from backend.app.ai.registry import ToolContext, ToolRegistry, ToolSpec
from backend.app.core.errors import APIError, ErrorCode
from backend.app.core.security import AuthContext

logger = logging.getLogger("supplysense.ai.executor")

_TYPE_MAP: dict[str, Any] = {
    "string": str,
    "number": float,
    "integer": int,
    "boolean": bool,
    "object": dict,
}

_MODEL_CACHE: dict[str, type[BaseModel]] = {}


class DeclaredOnlyError(APIError):
    """Raised when a declaration is invoked (no execution path exists)."""

    def __init__(self, tool_name: str) -> None:
        super().__init__(
            ErrorCode.CONFLICT,
            (
                f"Tool {tool_name!r} is a declared action only. It has no "
                "execution path; record a human decision via POST /ai/approval."
            ),
        )


def _build_model(spec: ToolSpec) -> type[BaseModel]:
    """Generate (and cache) a Pydantic model from the JSON parameter schema."""
    cached = _MODEL_CACHE.get(spec.name)
    if cached is not None:
        return cached
    properties: dict[str, Any] = spec.parameters.get("properties", {})
    required = set(spec.parameters.get("required", []))
    fields: dict[str, Any] = {}
    for name, schema in properties.items():
        schema_type = schema.get("type", "string")
        if schema_type == "array":
            item_type = _TYPE_MAP.get(
                (schema.get("items") or {}).get("type", "string"), str
            )
            annotation: Any = list[item_type]
            field_kwargs: dict[str, Any] = {
                "default": None if name not in required else ...,
                "description": schema.get("description", ""),
            }
            if name not in required:
                annotation = annotation | None
        else:
            annotation = _TYPE_MAP.get(schema_type, str)
            field_kwargs = {
                "default": None if name not in required else ...,
                "description": schema.get("description", ""),
            }
            if schema.get("maxLength") is not None and annotation is str:
                field_kwargs["max_length"] = int(schema["maxLength"])
            if name not in required:
                annotation = annotation | None
        fields[name] = (annotation, Field(**field_kwargs))
    model = create_model(
        f"{spec.name.replace('-', '_')}_params",
        __config__=ConfigDict(extra="forbid"),
        **fields,
    )
    _MODEL_CACHE[spec.name] = model
    return model


def validate_params(spec: ToolSpec, raw: dict[str, Any]) -> dict[str, Any]:
    """Validate raw parameters against the generated model (fail closed)."""
    model = _build_model(spec)
    try:
        parsed = model.model_validate(raw)
    except ValidationError as exc:
        details = [
            {"location": [str(part) for part in err.get("loc", ())],
             "message": err.get("msg", "invalid value"),
             "type": err.get("type", "value_error")}
            for err in exc.errors()
        ]
        raise APIError(
            ErrorCode.VALIDATION_ERROR,
            f"Invalid parameters for tool {spec.name!r}.",
            details=details,
        ) from exc
    return {
        key: value
        for key, value in parsed.model_dump(exclude_none=True).items()
        if value is not None
    }


def _check_roles(spec: ToolSpec, auth: AuthContext) -> None:
    """Authorize the tool against its required roles (admin bypasses)."""
    if not spec.required_roles:
        return
    if auth.is_admin or auth.role in spec.required_roles:
        return
    raise APIError(
        ErrorCode.FORBIDDEN,
        f"Tool {spec.name!r} requires role: "
        f"{', '.join(sorted(spec.required_roles))}.",
    )


async def execute_tool(
    registry: ToolRegistry,
    name: str,
    raw_params: dict[str, Any],
    context: ToolContext,
) -> dict[str, Any]:
    """Execute one registered tool and return its normalized result.

    Returns a dict: ``tool``, ``status`` (``ok``/``error``), ``data``,
    ``source``, ``label``, ``limitations``, ``duration_ms``, and on error
    ``error`` = ``{code, message}``. Never raises for tool-level problems
    (the service decides how to surface them); authorization/validation
    failures are audited and returned as ``status="error"`` results.
    """
    started = time.perf_counter()
    auth = context.auth
    try:
        spec = registry.get(name)
    except APIError as exc:
        await _audit_failure(context, name, exc.code, exc.message, started)
        return _error_result(name, exc.code, exc.message, started)
    if spec.is_declaration:
        await _audit_failure(
            context, name, ErrorCode.CONFLICT, "declaration-only tool", started
        )
        return _error_result(
            name,
            ErrorCode.CONFLICT,
            DeclaredOnlyError(name).message,
            started,
        )
    try:
        _check_roles(spec, auth)
        params = validate_params(spec, raw_params)
    except APIError as exc:
        await _audit_failure(context, name, exc.code, exc.message, started)
        return _error_result(name, exc.code, exc.message, started)

    context.params = params
    try:
        assert spec.handler is not None
        result = await spec.handler(context)
    except APIError as exc:
        await _audit_failure(context, name, exc.code, exc.message, started)
        return _error_result(name, exc.code, exc.message, started)
    except ValueError as exc:
        message = str(exc)
        await _audit_failure(context, name, ErrorCode.VALIDATION_ERROR, message, started)
        return _error_result(name, ErrorCode.VALIDATION_ERROR, message, started)
    except Exception:  # noqa: BLE001 - boundary: never leak internals
        logger.exception("tool %s crashed", name)
        await _audit_failure(
            context, name, ErrorCode.INTERNAL_ERROR, "tool execution failed", started
        )
        return _error_result(
            name, ErrorCode.INTERNAL_ERROR, "Tool execution failed.", started
        )

    duration_ms = (time.perf_counter() - started) * 1000
    normalized = {
        "tool": name,
        "status": "ok",
        "data": result.get("data"),
        "source": result.get("source", name),
        "label": result.get("label", "synthetic"),
        "limitations": list(result.get("limitations", [])),
        "duration_ms": round(duration_ms, 3),
    }
    if "analysis_date" in result:
        normalized["analysis_date"] = result["analysis_date"]
    if "provenance" in result:
        normalized["provenance"] = result["provenance"]
    await audit.record(
        context.session,
        action=audit.TOOL_CALL,
        user_id=auth.user_id,
        entity_type="ai_tool",
        entity_id=name,
        session_id=context.session_id,
        parameters={
            "tool": name,
            "status": "ok",
            "params": params,
            "duration_ms": normalized["duration_ms"],
            "label": normalized["label"],
        },
    )
    return normalized


async def _audit_failure(
    context: ToolContext,
    name: str,
    code: str,
    message: str,
    started: float,
) -> None:
    """Audit one failed/refused tool attempt (best effort)."""
    try:
        await audit.record(
            context.session,
            action=audit.TOOL_CALL,
            user_id=context.auth.user_id,
            entity_type="ai_tool",
            entity_id=name,
            session_id=context.session_id,
            parameters={
                "tool": name,
                "status": "error",
                "code": code,
                "message": message,
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            },
        )
    except Exception:  # noqa: BLE001 - auditing must not break the request
        logger.exception("failed to audit tool call for %s", name)


def _error_result(
    name: str, code: str, message: str, started: float
) -> dict[str, Any]:
    """Build the normalized error result payload."""
    return {
        "tool": name,
        "status": "error",
        "error": {"code": code, "message": message},
        "data": None,
        "source": name,
        "label": "synthetic",
        "limitations": [],
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
    }


__all__ = [
    "DeclaredOnlyError",
    "execute_tool",
    "validate_params",
]
