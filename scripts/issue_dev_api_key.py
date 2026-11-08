"""Local development API-key provisioning CLI.

This module provides a secure, explicit, and development-only mechanism to issue
or rotate local SupplySense Nexus API keys without needing external AI keys.

Safeguards:
- Fail-closed: Blocked unless running in local development mode.
- Blocked in production environments under ALL circumstances (flags cannot override production).
- Requires ENVIRONMENT to be explicitly 'development' or 'dev' AND (DEBUG=True or explicit --dev-mode).
- If ENVIRONMENT is missing, 'production', or unrecognized, execution is rejected.
- Reuses the existing `generate_api_key()` and `hash_api_key()` core functions.
- Raw keys are output exactly once to stdout and never logged or stored.
- Only the SHA-256 hash is saved to `users.api_key_hash`.
- Supports rotating keys for existing users or provisioning a development user.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.database import AsyncSessionLocal, dispose_engine, run_async
from backend.app.core.security import API_KEY_PREFIX, generate_api_key, hash_api_key
from backend.app.models import Organization, Role, User

DEV_ORGANIZATION_NAME = "SupplySense Local Dev Org"
ALLOWED_DEV_ENVIRONMENTS = {"development", "dev", "local", "test"}


class DevKeySecurityError(RuntimeError):
    """Raised when key generation is attempted without development safeguards."""


def assert_development_environment(allow_dev_flag: bool = False) -> None:
    """Verify that development mode safeguards are satisfied.

    Guards against accidental execution in production.
    Fail-closed policy:
    1. Production is strictly blocked. Flags cannot override production.
    2. Missing, unknown, or unrecognized environments are strictly blocked.
    3. Within an allowed development environment, requires either DEBUG=True or
       an explicit --dev-mode flag.
    """
    env = getattr(settings, "ENVIRONMENT", "")
    env_normalized = (env or "").strip().lower()

    # Rule 1: Production is strictly blocked (flag CANNOT override)
    if env_normalized in ("production", "prod"):
        raise DevKeySecurityError(
            "CRITICAL: Local development API-key issuance is strictly prohibited in production. "
            "No override flags are permitted in production."
        )

    # Rule 2: Unrecognized / missing environment fails closed
    if env_normalized not in ALLOWED_DEV_ENVIRONMENTS:
        raise DevKeySecurityError(
            f"CRITICAL: Refusing development API-key issuance in unrecognized environment '{env}'. "
            f"Allowed development environments: {', '.join(sorted(ALLOWED_DEV_ENVIRONMENTS))}."
        )

    # Rule 3: Requires explicit authorization (DEBUG=True or --dev-mode flag)
    if not (settings.DEBUG or allow_dev_flag):
        raise DevKeySecurityError(
            "Local development API-key issuance requires explicit confirmation. "
            "Set DEBUG=true in .env or pass --dev-mode."
        )


async def provision_development_key(
    session: AsyncSession,
    email: str = "planner@supplysense.local",
    username: str = "dev-planner",
    role: str = Role.PLANNER.value,
    allow_dev_flag: bool = False,
) -> tuple[str, User, bool]:
    """Issue a local development API key for a specified user.

    Returns:
        tuple[raw_key, user, is_new_user]

    Guarantees:
        - Raw key starts with `ssk_`.
        - Raw key is never stored in DB.
        - Persisted hash equals `hash_api_key(raw_key)`.
        - User is active (`is_active=True`).
    """
    assert_development_environment(allow_dev_flag)

    role_val = role.lower()
    if role_val not in Role.values():
        valid_roles = ", ".join(Role.values())
        raise ValueError(f"Invalid role: '{role}'. Must be one of: {valid_roles}")

    # Check for existing user by email
    stmt = select(User).where(User.email == email)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    # Generate raw key and hash via existing core security functions
    raw_key, key_hash = generate_api_key()
    assert raw_key.startswith(API_KEY_PREFIX)
    assert key_hash == hash_api_key(raw_key)

    is_new = False
    if user is None:
        # Locate or create organization
        org_stmt = select(Organization).order_by(Organization.created_at)
        org = (await session.execute(org_stmt)).scalars().first()
        if org is None:
            org = Organization(
                id=str(uuid.uuid4()),
                name=DEV_ORGANIZATION_NAME,
                industry="Supply Chain Intelligence",
                data_source_label="synthetic",
            )
            session.add(org)
            await session.flush()

        user = User(
            id=str(uuid.uuid4()),
            email=email,
            username=username,
            password_hash=f"hashed:synthetic-dev-marker:{uuid.uuid4().hex[:12]}",
            api_key_hash=key_hash,
            role=role_val,
            organization_id=org.id,
            is_active=True,
        )
        session.add(user)
        is_new = True
    else:
        # Rotate existing user's key hash and ensure active
        user.api_key_hash = key_hash
        user.is_active = True
        if role_val and user.role != role_val:
            user.role = role_val

    await session.commit()
    await session.refresh(user)
    return raw_key, user, is_new


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SupplySense Nexus — Local Development API Key Provisioning CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--email",
        type=str,
        default="planner@supplysense.local",
        help="Email address of the development user.",
    )
    parser.add_argument(
        "--username",
        type=str,
        default="dev-planner",
        help="Username for a new development user.",
    )
    parser.add_argument(
        "--role",
        type=str,
        default=Role.PLANNER.value,
        choices=Role.values(),
        help="Role to assign (analyst, planner, manager, executive, admin).",
    )
    parser.add_argument(
        "--dev-mode",
        action="store_true",
        help="Explicit flag confirming local development execution (bypasses DEBUG requirement).",
    )
    return parser.parse_args(argv)


async def async_main(args: argparse.Namespace) -> int:
    try:
        assert_development_environment(args.dev_mode)
    except DevKeySecurityError as exc:
        print(f"\n[SECURITY ERROR] {exc}\n", file=sys.stderr)
        return 1

    async with AsyncSessionLocal() as session:
        try:
            raw_key, user, is_new = await provision_development_key(
                session=session,
                email=args.email,
                username=args.username,
                role=args.role,
                allow_dev_flag=args.dev_mode,
            )
        except Exception as exc:
            print(f"\n[PROVISIONING FAILED] {exc}\n", file=sys.stderr)
            return 2

    action_label = "Created new development user" if is_new else "Rotated API key for existing user"
    print("\n" + "=" * 72)
    print(" SupplySense Nexus — Local Development API Key Provisioned")
    print("=" * 72)
    print(f" Status:          {action_label}")
    print(f" User Email:      {user.email}")
    print(f" User ID:         {user.id}")
    print(f" Assigned Role:   {user.role.upper()}")
    print(f" Active:          {user.is_active}")
    print(f" Organization ID: {user.organization_id}")
    print("-" * 72)
    print(f" RAW API KEY:     {raw_key}")
    print("-" * 72)
    print(" Instructions:")
    print(" 1. Copy the RAW API KEY above (begins with 'ssk_').")
    print(" 2. Open the SupplySense Nexus Dashboard in your browser (e.g. http://localhost:5173).")
    print(" 3. Go to the Settings page and paste this key into the API key field.")
    print(" 4. Click 'Save and verify'.")
    print(" NOTE: This raw key is printed ONLY ONCE and is NOT stored in the database.")
    print("=" * 72 + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run_async(async_main(args))
    finally:
        run_async(dispose_engine())


if __name__ == "__main__":
    sys.exit(main())
