"""AI Decision Copilot package (Phase 11).

Import submodules directly (``from backend.app.ai import service``) rather
than relying on package-level re-exports: the package init stays minimal so
:mod:`backend.app.integration.llm_provider` can import
:mod:`backend.app.ai.intents` without circular imports.
"""

__all__: list[str] = []
