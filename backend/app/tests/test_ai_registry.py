"""Registry and executor tests (C2 boundaries, validation, audit write-once)."""

import re

import pytest
from sqlalchemy import select

from backend.app.ai import audit as audit_mod
from backend.app.ai import executor as executor_mod
from backend.app.ai.executor import execute_tool, validate_params
from backend.app.ai.registry import (
    APPROVAL_REQUIRED,
    MUTATION,
    OPTIMIZATION,
    READ_ONLY_ANALYTICS,
    SIMULATION,
    DECISION_REPLAY,
    ToolContext,
    ToolRegistry,
    ToolSpec,
    get_tool_registry,
    reset_tool_registry,
)
from backend.app.ai.tools import build_default_registry
from backend.app.core.errors import APIError, ErrorCode
from backend.app.core.security import AuthContext
from backend.app.models import AuditEvent
from backend.app.tests.conftest import (
    TestSessionLocal,
    first_organization_id,
    load_tiny_dataset,
    seed_api_user,
)

RAW_KEY = "ssk_test_reg_analyst_" + "a" * 32
BANNED = re.compile(
    r"\b(best|should|recommend\w*|preferred|rank\w*|top choice)\b", re.IGNORECASE
)


@pytest.fixture(autouse=True)
def _clean_caches():
    reset_tool_registry()
    executor_mod._MODEL_CACHE.clear()
    yield
    reset_tool_registry()
    executor_mod._MODEL_CACHE.clear()


async def _seed():
    async with TestSessionLocal() as session:
        await load_tiny_dataset(session)
        org_id = await first_organization_id(session)
        user = await seed_api_user(session, org_id, "analyst", RAW_KEY)
        await session.commit()
    return org_id, user.id


def _auth(user_id: str, org_id: str, role: str = "analyst") -> AuthContext:
    return AuthContext(
        user_id=user_id, organization_id=org_id, role=role, is_active=True
    )


def test_default_registry_invariants():
    registry = build_default_registry()
    names = registry.names()
    assert len(names) == 13
    assert registry.list(category=MUTATION) == []
    declarations = registry.list(category=APPROVAL_REQUIRED)
    assert [spec.name for spec in declarations] == [
        "inventory_adjustment",
        "procurement_order_change",
        "scenario_deployment",
    ]
    assert all(spec.is_declaration for spec in declarations)
    assert all(spec.requires_approval for spec in declarations)
    assert all(spec.handler is None for spec in declarations)
    for category in (READ_ONLY_ANALYTICS, SIMULATION, DECISION_REPLAY, OPTIMIZATION):
        assert registry.list(category=category), category
    for spec in registry.list():
        assert not BANNED.search(spec.name), spec.name
        assert not BANNED.search(spec.description), spec.name
    assert "rank_options" not in names and "get_recommendation" not in names


def test_register_rejects_duplicates_and_bad_categories():
    registry = ToolRegistry()
    spec = ToolSpec(
        name="t1", description="d", category=READ_ONLY_ANALYTICS,
        parameters={}, handler=None, executable=False,
    )
    registry.register(spec)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(spec)
    with pytest.raises(ValueError, match="unknown tool category"):
        registry.register(
            ToolSpec(name="t2", description="d", category="RECOMMEND", parameters={})
        )


async def _noop_handler(context: ToolContext) -> dict:
    return {"data": {}}


def test_register_rejects_executable_mutation():
    registry = ToolRegistry()
    with pytest.raises(ValueError, match="prohibited"):
        registry.register(
            ToolSpec(
                name="mut", description="d", category=MUTATION,
                parameters={}, handler=_noop_handler,
            )
        )
    registry.register(
        ToolSpec(
            name="mut_decl", description="d", category=MUTATION,
            parameters={}, handler=None, executable=False,
        )
    )


def test_register_enforces_declaration_rules():
    registry = ToolRegistry()
    with pytest.raises(ValueError, match="declarations without an"):
        registry.register(
            ToolSpec(
                name="ap1", description="d", category=APPROVAL_REQUIRED,
                parameters={}, handler=_noop_handler, requires_approval=True,
            )
        )
    with pytest.raises(ValueError, match="must set requires_approval"):
        registry.register(
            ToolSpec(
                name="ap2", description="d", category=APPROVAL_REQUIRED,
                parameters={}, handler=None,
            )
        )
    with pytest.raises(ValueError, match="needs a handler"):
        registry.register(
            ToolSpec(
                name="ex1", description="d", category=READ_ONLY_ANALYTICS,
                parameters={}, handler=None, executable=True,
            )
        )
    with pytest.raises(ValueError, match="must not have a handler"):
        registry.register(
            ToolSpec(
                name="ex2", description="d", category=READ_ONLY_ANALYTICS,
                parameters={}, handler=_noop_handler, executable=False,
            )
        )


def test_get_unknown_tool_is_404():
    registry = ToolRegistry()
    with pytest.raises(APIError) as excinfo:
        registry.get("nope")
    assert excinfo.value.code == ErrorCode.NOT_FOUND


def test_list_is_sorted_and_category_filtered():
    registry = build_default_registry()
    all_names = [spec.name for spec in registry.list()]
    assert all_names == sorted(all_names)
    forecast_only = registry.list(category=READ_ONLY_ANALYTICS)
    assert all(spec.category == READ_ONLY_ANALYTICS for spec in forecast_only)
    assert "get_forecast" in [spec.name for spec in forecast_only]


def test_validate_params_extra_field_rejected():
    spec = build_default_registry().get("get_forecast")
    with pytest.raises(APIError) as excinfo:
        validate_params(spec, {"sneaky": "value"})
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR
    assert excinfo.value.details


def test_validate_params_type_and_bounds():
    spec = build_default_registry().get("get_forecast")
    parsed = validate_params(spec, {"horizon": 7, "product_id": None})
    assert parsed == {"horizon": 7}
    with pytest.raises(APIError):
        validate_params(spec, {"horizon": "seven"})


@pytest.mark.asyncio
async def test_execute_success_is_audited_once():
    org_id, user_id = await _seed()
    registry = ToolRegistry()

    async def handler(context: ToolContext) -> dict:
        return {"data": {"value": 1}, "label": "synthetic", "limitations": ["n"]}

    registry.register(
        ToolSpec(
            name="test_ok_tool", description="d", category=READ_ONLY_ANALYTICS,
            parameters={}, handler=handler,
        )
    )
    async with TestSessionLocal() as session:
        context = ToolContext(
            session=session, auth=_auth(user_id, org_id), params={},
            conversation_id=None, session_id="s-1",
        )
        result = await execute_tool(registry, "test_ok_tool", {}, context)
        assert result["status"] == "ok"
        assert result["data"] == {"value": 1}
        assert result["label"] == "synthetic"
        rows = (
            await session.execute(
                select(AuditEvent).where(AuditEvent.action == audit_mod.TOOL_CALL)
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].entity_id == "test_ok_tool"
        await session.commit()


@pytest.mark.asyncio
async def test_execute_validation_failure_is_audited():
    org_id, user_id = await _seed()
    registry = build_default_registry()
    async with TestSessionLocal() as session:
        context = ToolContext(
            session=session, auth=_auth(user_id, org_id), params={},
            session_id="s-2",
        )
        result = await execute_tool(
            registry, "get_forecast", {"bogus": 1}, context
        )
        assert result["status"] == "error"
        assert result["error"]["code"] == ErrorCode.VALIDATION_ERROR
        rows = (
            await session.execute(
                select(AuditEvent).where(AuditEvent.action == audit_mod.TOOL_CALL)
            )
        ).scalars().all()
        assert len(rows) == 1
        await session.commit()


@pytest.mark.asyncio
async def test_execute_declaration_has_no_execution_path():
    org_id, user_id = await _seed()
    registry = build_default_registry()
    async with TestSessionLocal() as session:
        context = ToolContext(
            session=session, auth=_auth(user_id, org_id), params={}, session_id="s-3"
        )
        result = await execute_tool(
            registry, "procurement_order_change", {"order_reference": "PO-1"}, context
        )
        assert result["status"] == "error"
        assert result["error"]["code"] == ErrorCode.CONFLICT
        assert "declared action only" in result["error"]["message"]
        await session.commit()


@pytest.mark.asyncio
async def test_execute_unknown_tool_fails_closed():
    org_id, user_id = await _seed()
    async with TestSessionLocal() as session:
        context = ToolContext(
            session=session, auth=_auth(user_id, org_id), params={}, session_id="s-4"
        )
        result = await execute_tool(
            build_default_registry(), "run_sql", {}, context
        )
        assert result["status"] == "error"
        assert result["error"]["code"] == ErrorCode.NOT_FOUND
        await session.commit()


@pytest.mark.asyncio
async def test_execute_role_gate_and_admin_bypass():
    org_id, user_id = await _seed()
    registry = ToolRegistry()

    async def handler(context: ToolContext) -> dict:
        return {"data": {"ok": True}}

    registry.register(
        ToolSpec(
            name="test_role_tool", description="d", category=READ_ONLY_ANALYTICS,
            parameters={}, handler=handler, required_roles=("manager",),
        )
    )
    async with TestSessionLocal() as session:
        denied = await execute_tool(
            registry, "test_role_tool", {},
            ToolContext(session=session, auth=_auth(user_id, org_id, "analyst"), params={}),
        )
        assert denied["status"] == "error"
        assert denied["error"]["code"] == ErrorCode.FORBIDDEN
        allowed = await execute_tool(
            registry, "test_role_tool", {},
            ToolContext(session=session, auth=_auth(user_id, org_id, "manager"), params={}),
        )
        assert allowed["status"] == "ok"
        bypass = await execute_tool(
            registry, "test_role_tool", {},
            ToolContext(session=session, auth=_auth(user_id, org_id, "admin"), params={}),
        )
        assert bypass["status"] == "ok"
        await session.commit()


@pytest.mark.asyncio
async def test_execute_crash_is_masked_as_internal_error():
    org_id, user_id = await _seed()
    registry = ToolRegistry()

    async def handler(context: ToolContext) -> dict:
        raise RuntimeError("secret internal detail")

    registry.register(
        ToolSpec(
            name="test_crash_tool", description="d", category=READ_ONLY_ANALYTICS,
            parameters={}, handler=handler,
        )
    )
    async with TestSessionLocal() as session:
        result = await execute_tool(
            registry, "test_crash_tool", {},
            ToolContext(session=session, auth=_auth(user_id, org_id), params={}),
        )
        assert result["status"] == "error"
        assert result["error"]["code"] == ErrorCode.INTERNAL_ERROR
        assert "secret" not in result["error"]["message"]
        assert result["error"]["message"] == "Tool execution failed."
        await session.commit()


def test_get_tool_registry_is_cached_and_resettable():
    first = get_tool_registry()
    second = get_tool_registry()
    assert first is second
    reset_tool_registry()
    third = get_tool_registry()
    assert third is not first
