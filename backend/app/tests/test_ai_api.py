"""Phase 11 AI Copilot API tests: envelopes, C1 auth, roles, persistence."""

import re

import pytest
from sqlalchemy import select

from backend.app.core.security import generate_api_key, hash_api_key
from backend.app.models import AuditEvent, User
from backend.app.models.ai import AiConversation, AiMessage
from backend.app.tests.conftest import (
    TestSessionLocal,
    first_organization_id,
    load_tiny_dataset,
    seed_api_user,
)

RAW_ANALYST_KEY = "ssk_test_analyst_" + "a" * 32
RAW_MANAGER_KEY = "ssk_test_manager_" + "b" * 32

CHAT_FIELDS = {"response", "confidence", "evidence", "limitations", "approved"}
BANNED = re.compile(
    r"\b(best|should|recommend\w*|preferred|rank\w*|top choice)\b", re.IGNORECASE
)


async def _seed_users():
    """Seed the tiny dataset plus an analyst and a manager (same org)."""
    async with TestSessionLocal() as session:
        await load_tiny_dataset(session)
        org_id = await first_organization_id(session)
        await seed_api_user(session, org_id, "analyst", RAW_ANALYST_KEY)
        await seed_api_user(session, org_id, "manager", RAW_MANAGER_KEY)
        await session.commit()
    return org_id


def _auth(raw_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw_key}"}


@pytest.mark.asyncio
async def test_health_endpoints_stay_public(ai_client):
    for path in ("/api/v1/health", "/api/v1/health/live", "/api/v1/health/ready"):
        response = await ai_client.get(path)
        assert response.status_code == 200, path


@pytest.mark.asyncio
async def test_chat_missing_header_401(ai_client):
    response = await ai_client.post("/api/v1/ai/chat", json={"message": "hello"})
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert body["error"]["message"] == "Authentication failed."
    assert "meta" in body and "timestamp" in body["meta"]


@pytest.mark.asyncio
async def test_chat_malformed_and_unknown_keys_401(ai_client):
    malformed = await ai_client.post(
        "/api/v1/ai/chat",
        json={"message": "hello"},
        headers={"Authorization": "Token abc"},
    )
    assert malformed.status_code == 401
    unknown = await ai_client.post(
        "/api/v1/ai/chat",
        json={"message": "hello"},
        headers=_auth("ssk_not_a_real_key_" + "c" * 32),
    )
    assert unknown.status_code == 401
    assert unknown.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_chat_rejects_identity_in_body(ai_client):
    await _seed_users()
    response = await ai_client.post(
        "/api/v1/ai/chat",
        json={"message": "hello", "user_id": "attacker-supplied"},
        headers=_auth(RAW_ANALYST_KEY),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_chat_happy_path_and_persistence(ai_client):
    org_id = await _seed_users()
    response = await ai_client.post(
        "/api/v1/ai/chat",
        json={"message": "What is the status of our data?", "session_id": "s-123"},
        headers=_auth(RAW_ANALYST_KEY),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True and body["error"] is None
    data = body["data"]
    assert set(data.keys()) == CHAT_FIELDS
    assert data["response"]
    assert 0.0 <= data["confidence"] <= 1.0
    assert data["approved"] is True
    assert body["meta"]["data_source_label"] == "derived"
    assert body["meta"]["conversation_id"]
    assert body["meta"]["session_id"] == "s-123"
    assert body["meta"]["provider"] == "mock"

    async with TestSessionLocal() as session:
        conversation = (
            await session.execute(
                select(AiConversation).where(
                    AiConversation.id == body["meta"]["conversation_id"]
                )
            )
        ).scalar_one()
        assert conversation.organization_id == org_id
        assert conversation.last_intent
        messages = (
            await session.execute(
                select(AiMessage)
                .where(AiMessage.conversation_id == conversation.id)
                .order_by(AiMessage.sequence)
            )
        ).scalars().all()
        assert [m.role for m in messages] == ["user", "assistant"]
        audit_rows = (
            await session.execute(
                select(AuditEvent).where(AuditEvent.action == "ai.chat")
            )
        ).scalars().all()
        assert len(audit_rows) == 1
        assert audit_rows[0].session_id == "s-123"
        raw_keys = (await session.execute(select(User.api_key_hash))).scalars().all()
        assert RAW_ANALYST_KEY not in raw_keys
        assert all(h is None or len(h) == 64 for h in raw_keys)


@pytest.mark.asyncio
async def test_foreign_conversation_404(ai_client):
    await _seed_users()
    first = await ai_client.post(
        "/api/v1/ai/chat",
        json={"message": "hello"},
        headers=_auth(RAW_ANALYST_KEY),
    )
    conversation_id = first.json()["meta"]["conversation_id"]
    response = await ai_client.post(
        "/api/v1/ai/chat",
        json={"message": "continue", "conversation_id": conversation_id},
        headers=_auth(RAW_MANAGER_KEY),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_role_separation_on_endpoints(ai_client):
    await _seed_users()
    analyst_approval = await ai_client.post(
        "/api/v1/ai/approval",
        json={"approval_id": "x" * 36, "decision": "approve"},
        headers=_auth(RAW_ANALYST_KEY),
    )
    assert analyst_approval.status_code == 403
    assert analyst_approval.json()["error"]["code"] == "FORBIDDEN"

    analyst_tools = await ai_client.get("/api/v1/ai/tools", headers=_auth(RAW_ANALYST_KEY))
    assert analyst_tools.status_code == 200

    manager_tools = await ai_client.get("/api/v1/ai/tools", headers=_auth(RAW_MANAGER_KEY))
    assert manager_tools.status_code == 200


@pytest.mark.asyncio
async def test_ai_tools_listing_and_no_banned_names(ai_client):
    await _seed_users()
    response = await ai_client.get(
        "/api/v1/ai/tools", headers=_auth(RAW_ANALYST_KEY)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    tools = body["data"]["tools"]
    assert body["data"]["count"] == len(tools) == 13
    names = {tool["name"] for tool in tools}
    assert not any(BANNED.search(name) for name in names)
    assert "rank_options" not in names and "get_recommendation" not in names
    declarations = [t for t in tools if t["requires_approval"]]
    assert len(declarations) == 3
    assert all(t["executable"] is False for t in declarations)
    mutation = [t for t in tools if t["category"] == "MUTATION"]
    assert mutation == []
    categories = {t["category"] for t in tools}
    assert categories <= {
        "READ_ONLY_ANALYTICS",
        "SIMULATION",
        "DECISION_REPLAY",
        "OPTIMIZATION",
        "APPROVAL_REQUIRED",
        "MUTATION",
    }


@pytest.mark.asyncio
async def test_inactive_user_401(ai_client):
    async with TestSessionLocal() as session:
        await load_tiny_dataset(session)
        org_id = await first_organization_id(session)
        raw_key = "ssk_test_inactive_" + "d" * 32
        await seed_api_user(session, org_id, "analyst", raw_key, active=False)
        await session.commit()
    response = await ai_client.post(
        "/api/v1/ai/chat", json={"message": "hello"}, headers=_auth(raw_key)
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_generated_key_format_and_hash():
    raw_key, digest = generate_api_key()
    assert raw_key.startswith("ssk_")
    assert len(raw_key) == 4 + 43
    assert digest == hash_api_key(raw_key)
    assert len(digest) == 64
    assert raw_key != digest
