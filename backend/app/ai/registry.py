"""Central tool registry: only registered tools may ever execute (C2/C4).

Categories are fixed by the Phase 11 decisions:

- ``READ_ONLY_ANALYTICS`` — factual retrieval over existing analyses.
- ``SIMULATION`` — disruption simulation (compute-only, labeled simulated).
- ``DECISION_REPLAY`` — factual replay deltas between declared decisions.
- ``OPTIMIZATION`` — thin adapter over the Phase 10 engine (solver status
  vocabulary only; never phrased as advice).
- ``MUTATION`` — **zero executable tools are registered, ever**; registration
  of a handler in this category raises.
- ``APPROVAL_REQUIRED`` — declarations only (no handler, no execution path);
  they appear in listings and can be referenced by approval records.

Handlers receive a :class:`ToolContext` and return a JSON-safe dict with
the keys ``data``, ``source``, ``label`` (a ``DataSourceLabel`` value), and
optionally ``limitations``, ``analysis_date``, ``provenance``.
"""

import builtins
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import APIError, ErrorCode
from backend.app.core.security import AuthContext

READ_ONLY_ANALYTICS = "READ_ONLY_ANALYTICS"
SIMULATION = "SIMULATION"
DECISION_REPLAY = "DECISION_REPLAY"
OPTIMIZATION = "OPTIMIZATION"
MUTATION = "MUTATION"
APPROVAL_REQUIRED = "APPROVAL_REQUIRED"

CATEGORIES = (
    READ_ONLY_ANALYTICS,
    SIMULATION,
    DECISION_REPLAY,
    OPTIMIZATION,
    MUTATION,
    APPROVAL_REQUIRED,
)

ToolHandler = Callable[["ToolContext"], Awaitable[dict[str, Any]]]


@dataclass
class ToolContext:
    """Everything one tool execution is allowed to touch."""

    session: AsyncSession
    auth: AuthContext
    params: dict[str, Any]
    conversation_id: str | None = None
    session_id: str | None = None


@dataclass(frozen=True)
class ToolSpec:
    """One registered tool (executable) or declaration (non-executable)."""

    name: str
    description: str
    category: str
    parameters: dict[str, Any]
    handler: ToolHandler | None = None
    required_roles: tuple[str, ...] = ()
    executable: bool = True
    requires_approval: bool = False

    @property
    def is_declaration(self) -> bool:
        """True for declared-only entries (no execution path exists)."""
        return self.handler is None or not self.executable

    def to_summary(self) -> dict[str, Any]:
        """JSON view for ``GET /ai/tools`` (never exposes the handler)."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": self.parameters,
            "executable": self.executable and self.handler is not None,
            "requires_approval": self.requires_approval,
        }


class ToolRegistry:
    """Name-keyed registry with category and mutation invariants."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        """Register one tool; enforces the zero-mutation invariant."""
        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        if spec.category not in CATEGORIES:
            raise ValueError(f"unknown tool category: {spec.category}")
        if spec.category == MUTATION and spec.handler is not None:
            raise ValueError(
                "executable mutation tools are prohibited: category MUTATION "
                "accepts declarations only"
            )
        if spec.category == APPROVAL_REQUIRED:
            if spec.handler is not None:
                raise ValueError(
                    "APPROVAL_REQUIRED tools are declarations without an "
                    "execution path"
                )
            if not spec.requires_approval:
                raise ValueError("APPROVAL_REQUIRED declarations must set requires_approval")
        if spec.executable and spec.handler is None:
            raise ValueError(f"executable tool needs a handler: {spec.name}")
        if not spec.executable and spec.handler is not None:
            raise ValueError(f"non-executable tool must not have a handler: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        """Return one spec or raise 404 NOT_FOUND (fail closed)."""
        spec = self._tools.get(name)
        if spec is None:
            raise APIError(
                ErrorCode.NOT_FOUND,
                f"Unknown tool: {name!r}. Only registered tools exist.",
            )
        return spec

    def list(self, category: str | None = None) -> builtins.list[ToolSpec]:
        """Return specs sorted by name, optionally filtered by category."""
        specs = sorted(self._tools.values(), key=lambda spec: spec.name)
        if category is not None:
            specs = [spec for spec in specs if spec.category == category]
        return specs

    def names(self) -> builtins.list[str]:
        """Return all registered names (sorted)."""
        return sorted(self._tools)


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Cached default registry resolver (FastAPI dependency)."""
    global _registry
    if _registry is None:
        from backend.app.ai.tools import build_default_registry

        _registry = build_default_registry()
    return _registry


def reset_tool_registry() -> None:
    """Drop the cached registry (tests)."""
    global _registry
    _registry = None


__all__ = [
    "APPROVAL_REQUIRED",
    "CATEGORIES",
    "DECISION_REPLAY",
    "MUTATION",
    "OPTIMIZATION",
    "READ_ONLY_ANALYTICS",
    "SIMULATION",
    "ToolContext",
    "ToolHandler",
    "ToolRegistry",
    "ToolSpec",
    "get_tool_registry",
    "reset_tool_registry",
]
