"""Phase 11 tool integration tests (Phase 7/8/9/10 engines via the registry)."""

import re

import pytest
from sqlalchemy import select

from backend.app.ai import audit as audit_mod
from backend.app.ai.executor import execute_tool
from backend.app.ai.registry import ToolContext
from backend.app.ai.tools import build_default_registry as build_registry
from backend.app.core.data_labels import DataSourceLabel
from backend.app.core.errors import ErrorCode
from backend.app.core.security import AuthContext
from backend.app.models import AuditEvent
from backend.app.models import Product as ProductModel
from backend.app.tests.conftest import (
    TestSessionLocal,
    first_organization_id,
    load_tiny_dataset,
    seed_api_user,
)

RAW_ANALYST_1 = "ssk_test_tools_an1_" + "a" * 32
RAW_ANALYST_2 = "ssk_test_tools_an2_" + "b" * 32
RAW_MANAGER_1 = "ssk_test_tools_mgr_" + "c" * 32

BANNED = re.compile(
    r"\b(best|should|recommend\w*|preferred|rank\w*|top choice)\b", re.IGNORECASE
)


async def _seed_orgs():
    """Load a two-organization dataset and seed one analyst + one manager."""
    async with TestSessionLocal() as session:
        from backend.app.data.config import GenerationConfig
        from backend.app.data.ingestion.pipeline import generate_dataset, load_dataset

        config = GenerationConfig(
            seed=21, product_count=6, supplier_count=3, warehouse_count=2,
            history_days=120, organization_count=2,
        )
        dataset = generate_dataset(config)
        await load_dataset(session, dataset)
        await session.commit()
        org_rows = (
            await session.execute(select(ProductModel.organization_id).distinct())
        ).scalars().all()
        org_ids = sorted(str(value) for value in org_rows)
        assert len(org_ids) == 2, org_ids
        analyst_1 = await seed_api_user(session, org_ids[0], "analyst", RAW_ANALYST_1)
        manager_1 = await seed_api_user(session, org_ids[0], "manager", RAW_MANAGER_1)
        analyst_2 = await seed_api_user(session, org_ids[1], "analyst", RAW_ANALYST_2)
        await session.commit()
    return org_ids, (analyst_1.id, manager_1.id, analyst_2.id)


def _auth(user_id: str, org_id: str, role: str) -> AuthContext:
    return AuthContext(
        user_id=user_id, organization_id=org_id, role=role, is_active=True
    )


READ_TOOLS = [
    "get_forecast",
    "get_inventory_position",
    "get_inventory_health",
    "get_supplier_scorecard",
    "get_inventory_kpis",
    "get_data_quality_report",
    "get_risk_report",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", READ_TOOLS)
async def test_read_tools_return_labeled_evidence(tool_name):
    org_ids, (analyst_id, _, _) = await _seed_orgs()
    registry = build_registry()
    async with TestSessionLocal() as session:
        result = await execute_tool(
            registry, tool_name, {},
            ToolContext(
                session=session, auth=_auth(analyst_id, org_ids[0], "analyst"),
                params={}, session_id="s-read",
            ),
        )
        assert result["status"] == "ok", result
        assert result["label"] in DataSourceLabel.values()
        assert result["data"] is not None
        assert isinstance(result["limitations"], list)
        await session.commit()


@pytest.mark.asyncio
async def test_inventory_position_is_org_scoped_for_second_org():
    org_ids, (analyst_id, _, analyst_2_id) = await _seed_orgs()
    registry = build_registry()
    async with TestSessionLocal() as session:
        org2_products = {
            str(value)
            for value in (
                await session.execute(
                    select(ProductModel.id).where(
                        ProductModel.organization_id == org_ids[1]
                    )
                )
            ).scalars()
        }
        result = await execute_tool(
            registry, "get_inventory_position", {},
            ToolContext(
                session=session, auth=_auth(analyst_2_id, org_ids[1], "analyst"),
                params={}, session_id="s-iso",
            ),
        )
        assert result["status"] == "ok", result
        positions = result["data"]["positions"]
        assert positions, "expected org-2 inventory series"
        returned = {str(row.get("product_id")) for row in positions}
        assert returned <= org2_products, returned - org2_products
        await session.commit()


@pytest.mark.asyncio
async def test_foreign_product_id_is_rejected():
    org_ids, (analyst_id, _, analyst_2_id) = await _seed_orgs()
    registry = build_registry()
    async with TestSessionLocal() as session:
        foreign_product = (
            await session.execute(
                select(ProductModel.id).where(
                    ProductModel.organization_id == org_ids[0]
                )
            )
        ).scalars().first()
        result = await execute_tool(
            registry, "get_forecast", {"product_id": str(foreign_product)},
            ToolContext(
                session=session, auth=_auth(analyst_2_id, org_ids[1], "analyst"),
                params={"product_id": str(foreign_product)}, session_id="s-foreign",
            ),
        )
        assert result["status"] == "error"
        assert result["error"]["code"] == ErrorCode.VALIDATION_ERROR
        assert "not available in your organization" in result["error"]["message"]
        await session.commit()


@pytest.mark.asyncio
async def test_planning_tools_require_planning_roles():
    org_ids, (analyst_id, _, _) = await _seed_orgs()
    registry = build_registry()
    async with TestSessionLocal() as session:
        result = await execute_tool(
            registry, "run_disruption_simulation", {},
            ToolContext(
                session=session, auth=_auth(analyst_id, org_ids[0], "analyst"),
                params={}, session_id="s-role",
            ),
        )
        assert result["status"] == "error"
        assert result["error"]["code"] == ErrorCode.FORBIDDEN
        await session.commit()


@pytest.mark.asyncio
async def test_simulation_tool_phase8_integration():
    org_ids, (_, manager_id, _) = await _seed_orgs()
    registry = build_registry()
    async with TestSessionLocal() as session:
        result = await execute_tool(
            registry, "run_disruption_simulation", {"simulation_count": 10},
            ToolContext(
                session=session, auth=_auth(manager_id, org_ids[0], "manager"),
                params={"simulation_count": 10}, session_id="s-sim",
            ),
        )
        assert result["status"] == "ok", result
        assert result["label"] == "simulated"
        assert result["data"]["data_source_label"] == "simulated"
        joined = " ".join(result["limitations"]).lower()
        assert "simulated" in joined
        assert "no_action" in joined or "control arm" in joined
        await session.commit()


@pytest.mark.asyncio
async def test_replay_tool_phase9_integration_with_declared_arms():
    org_ids, (_, manager_id, _) = await _seed_orgs()
    registry = build_registry()
    params = {
        "simulation_count": 10,
        "decisions": [
            {
                "decision_type": "EXPEDITE_INBOUND",
                "quantities": {"expedite_units": 25.0},
                "timing": {"start_day": 0, "end_day": 10, "delay_reduction_days": 2},
                "description": "declared test arm",
            }
        ],
    }
    async with TestSessionLocal() as session:
        result = await execute_tool(
            registry, "run_decision_comparison", params,
            ToolContext(
                session=session, auth=_auth(manager_id, org_ids[0], "manager"),
                params=params, session_id="s-replay",
            ),
        )
        assert result["status"] == "ok", result
        assert result["label"] == "simulated"
        assert result["data"]["data_source_label"] == "simulated"
        joined = " ".join(result["limitations"]).lower()
        assert "common random numbers" in joined
        assert not BANNED.search(joined)
        await session.commit()


@pytest.mark.asyncio
async def test_replay_tool_default_arm_is_labeled_offline_demo():
    org_ids, (_, manager_id, _) = await _seed_orgs()
    registry = build_registry()
    params = {"simulation_count": 10}
    async with TestSessionLocal() as session:
        result = await execute_tool(
            registry, "run_decision_comparison", params,
            ToolContext(
                session=session, auth=_auth(manager_id, org_ids[0], "manager"),
                params=params, session_id="s-replay-default",
            ),
        )
        assert result["status"] == "ok", result
        joined = " ".join(result["limitations"])
        assert "offline demo arm" in joined
        await session.commit()


@pytest.mark.asyncio
async def test_optimization_tool_phase10_integration():
    from backend.app.analytics.optimization.types import OBJECTIVES, STATUSES

    org_ids, (_, manager_id, _) = await _seed_orgs()
    registry = build_registry()
    params = {"objective": "minimize_total_cost", "simulation_count": 5}
    async with TestSessionLocal() as session:
        result = await execute_tool(
            registry, "run_optimization_analysis", params,
            ToolContext(
                session=session, auth=_auth(manager_id, org_ids[0], "manager"),
                params=params, session_id="s-opt",
            ),
        )
        assert result["status"] == "ok", result
        assert result["label"] == "simulated"
        status = result["data"]["feasibility_status"]["status"]
        assert status in STATUSES
        assert "minimize_total_cost" in " ".join(result["limitations"])
        assert OBJECTIVES[0] == "minimize_total_cost"
        joined = " ".join(result["limitations"]).lower()
        assert "simulated" in joined
        assert not BANNED.search(joined)
        await session.commit()


@pytest.mark.asyncio
async def test_optimization_rejects_unknown_objective_and_tradeoff_without_penalty():
    from backend.app.analytics.optimization.types import OBJECTIVES

    org_ids, (_, manager_id, _) = await _seed_orgs()
    registry = build_registry()
    async with TestSessionLocal() as session:
        bad = await execute_tool(
            registry, "run_optimization_analysis",
            {"objective": "maximize_profit"},
            ToolContext(
                session=session, auth=_auth(manager_id, org_ids[0], "manager"),
                params={"objective": "maximize_profit"}, session_id="s-opt-bad",
            ),
        )
        assert bad["status"] == "error"
        assert bad["error"]["code"] == ErrorCode.VALIDATION_ERROR
        assert "minimize_total_cost" in bad["error"]["message"]
        tradeoff = await execute_tool(
            registry, "run_optimization_analysis",
            {"objective": "cost_shortage_tradeoff"},
            ToolContext(
                session=session, auth=_auth(manager_id, org_ids[0], "manager"),
                params={"objective": "cost_shortage_tradeoff"}, session_id="s-opt-bad2",
            ),
        )
        assert tradeoff["status"] == "error"
        assert tradeoff["error"]["code"] == ErrorCode.VALIDATION_ERROR
        assert len(OBJECTIVES) == 4
        await session.commit()


@pytest.mark.asyncio
async def test_scenario_parameter_validation():
    org_ids, (_, manager_id, _) = await _seed_orgs()
    registry = build_registry()
    async with TestSessionLocal() as session:
        bad_horizon = {"horizon_days": 999}
        result = await execute_tool(
            registry, "run_disruption_simulation", bad_horizon,
            ToolContext(
                session=session, auth=_auth(manager_id, org_ids[0], "manager"),
                params=bad_horizon, session_id="s-bad-h",
            ),
        )
        assert result["status"] == "error"
        assert result["error"]["code"] == ErrorCode.VALIDATION_ERROR
        bad_template = {"event_template": "MADE_UP_TEMPLATE"}
        result2 = await execute_tool(
            registry, "run_disruption_simulation", bad_template,
            ToolContext(
                session=session, auth=_auth(manager_id, org_ids[0], "manager"),
                params=bad_template, session_id="s-bad-t",
            ),
        )
        assert result2["status"] == "error"
        assert result2["error"]["code"] == ErrorCode.VALIDATION_ERROR
        await session.commit()


@pytest.mark.asyncio
async def test_declarations_cannot_execute_and_audit_accumulates():
    org_ids, (_, manager_id, _) = await _seed_orgs()
    registry = build_registry()
    async with TestSessionLocal() as session:
        context = ToolContext(
            session=session, auth=_auth(manager_id, org_ids[0], "manager"),
            params={}, session_id="s-decl",
        )
        for declaration in ("procurement_order_change", "inventory_adjustment",
                            "scenario_deployment"):
            result = await execute_tool(registry, declaration, {}, context)
            assert result["status"] == "error"
            assert result["error"]["code"] == ErrorCode.CONFLICT
        rows = (
            await session.execute(
                select(AuditEvent).where(AuditEvent.action == audit_mod.TOOL_CALL)
            )
        ).scalars().all()
        assert len(rows) == 3
        assert all(row.entity_id in {
            "procurement_order_change", "inventory_adjustment", "scenario_deployment"
        } for row in rows)
        await session.commit()


def test_registry_module_exports_build_default_registry():
    from backend.app.ai.registry import get_tool_registry

    fresh = build_registry()
    assert set(fresh.names()) == set(get_tool_registry().names())
