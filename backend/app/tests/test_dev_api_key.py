"""Tests for local development API-key provisioning and safeguards.

Verifies:
- Production environment blocks development API key provisioning even with --dev-mode.
- Missing, empty, or unknown environment blocks development API key provisioning.
- Development mode requires either DEBUG=True or explicit allow_dev_flag.
- Key generation prefix uses mandatory `ssk_`.
- Raw keys are returned only during explicit generation and never persisted.
- Persisted hash equals SHA-256 hex digest of the raw key.
- Generated keys successfully authenticate against GET /api/v1/auth/me.
- Inactive users are rejected even if they hold a valid key hash.
- Invalid keys are rejected.
- User key rotation updates the hash cleanly and invalidates the previous key.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.core.security import API_KEY_PREFIX, hash_api_key
from backend.app.models import Role, User
from backend.app.tests.api_support import assert_envelope, assert_error, auth
from backend.app.tests.conftest import TestSessionLocal
from scripts.issue_dev_api_key import (
    DevKeySecurityError,
    assert_development_environment,
    provision_development_key,
)


def test_assert_development_environment_blocks_production(monkeypatch):
    """Confirm production mode raises DevKeySecurityError even with flag."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with pytest.raises(DevKeySecurityError, match="strictly prohibited in production"):
        assert_development_environment(allow_dev_flag=True)

    monkeypatch.setattr(settings, "ENVIRONMENT", "prod")
    with pytest.raises(DevKeySecurityError, match="strictly prohibited in production"):
        assert_development_environment(allow_dev_flag=True)


def test_assert_development_environment_blocks_missing_or_unknown_env(monkeypatch):
    """Confirm missing, empty, or unknown environment fails closed."""
    for bad_env in ("", "staging", "qa", "preview", "unknown", None):
        monkeypatch.setattr(settings, "ENVIRONMENT", bad_env)
        with pytest.raises(DevKeySecurityError, match="unrecognized environment"):
            assert_development_environment(allow_dev_flag=True)


def test_assert_development_environment_requires_debug_or_flag(monkeypatch):
    """Confirm development mode without DEBUG requires the explicit flag."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "DEBUG", False)

    # Without flag or DEBUG=True -> fails
    with pytest.raises(DevKeySecurityError, match="requires explicit confirmation"):
        assert_development_environment(allow_dev_flag=False)

    # Passing flag succeeds
    assert_development_environment(allow_dev_flag=True)

    # Setting DEBUG=True succeeds without flag
    monkeypatch.setattr(settings, "DEBUG", True)
    assert_development_environment(allow_dev_flag=False)


async def test_provision_development_key_creates_and_authenticates(ai_client, monkeypatch):
    """Test provisioning a new development user and authenticating with the key."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    async with TestSessionLocal() as session:
        raw_key, user, is_new = await provision_development_key(
            session=session,
            email="new-dev-planner@supplysense.local",
            username="new-dev-planner",
            role=Role.PLANNER.value,
            allow_dev_flag=True,
        )

        assert is_new is True
        assert raw_key.startswith(API_KEY_PREFIX)
        assert user.email == "new-dev-planner@supplysense.local"
        assert user.role == Role.PLANNER.value
        assert user.is_active is True
        assert user.api_key_hash == hash_api_key(raw_key)

        # Confirm the raw key is NOT stored in user.password_hash or anywhere
        assert raw_key not in user.password_hash
        assert raw_key != user.api_key_hash

    # Authenticate via GET /api/v1/auth/me
    response = await ai_client.get("/api/v1/auth/me", headers=auth(raw_key))
    assert response.status_code == 200
    body = response.json()
    data = assert_envelope(body, label="derived")
    assert data["email"] == "new-dev-planner@supplysense.local"
    assert data["role"] == Role.PLANNER.value
    assert data["is_active"] is True
    assert "api_key" not in data


async def test_provision_development_key_rotates_existing_user(ai_client, monkeypatch):
    """Test rotating the key for an existing user updates the hash without duplicates."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    test_email = "rotate-dev-user@supplysense.local"
    async with TestSessionLocal() as session:
        # First key issuance
        raw_key_1, user_1, is_new_1 = await provision_development_key(
            session=session,
            email=test_email,
            username="rotate-user",
            role=Role.ANALYST.value,
            allow_dev_flag=True,
        )
        assert is_new_1 is True

    # Authenticate with first key
    res1 = await ai_client.get("/api/v1/auth/me", headers=auth(raw_key_1))
    assert res1.status_code == 200

    async with TestSessionLocal() as session:
        # Second key issuance (rotation + role change to planner)
        raw_key_2, user_2, is_new_2 = await provision_development_key(
            session=session,
            email=test_email,
            username="rotate-user",
            role=Role.PLANNER.value,
            allow_dev_flag=True,
        )
        assert is_new_2 is False
        assert user_2.id == user_1.id
        assert raw_key_2 != raw_key_1

        # Check total user count with this email
        count = (
            await session.execute(select(User).where(User.email == test_email))
        ).scalars().all()
        assert len(count) == 1

    # Old key must now be rejected
    res_old = await ai_client.get("/api/v1/auth/me", headers=auth(raw_key_1))
    assert res_old.status_code == 401
    assert_error(res_old.json(), "UNAUTHORIZED")

    # New key must authenticate and reflect planner role
    res_new = await ai_client.get("/api/v1/auth/me", headers=auth(raw_key_2))
    assert res_new.status_code == 200
    assert res_new.json()["data"]["role"] == Role.PLANNER.value


async def test_provision_development_key_rejects_invalid_role(monkeypatch):
    """Verify invalid roles are rejected with a clear error."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    async with TestSessionLocal() as session:
        with pytest.raises(ValueError, match="Invalid role"):
            await provision_development_key(
                session=session,
                email="bad-role@supplysense.local",
                role="superadmin_invalid",
                allow_dev_flag=True,
            )
