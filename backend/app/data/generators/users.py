"""Synthetic user generator.

Passwords are never real: the ``password_hash`` field carries a
deterministic test-only marker, never a production credential.
"""

import hashlib

from backend.app.data.config import GenerationConfig
from backend.app.data.generators.base import stream_rng

_SYNTHETIC_USERS: list[tuple[str, str, str]] = [
    ("admin", "admin", "admin"),
    ("analyst", "supply-chain-analyst", "analyst"),
    ("planner", "inventory-planner", "planner"),
    ("procurement", "procurement-manager", "manager"),
    ("executive", "executive-viewer", "executive"),
]


def _test_password_hash(seed: int, email: str) -> str:
    """Build a deterministic test-only password marker (not a credential)."""
    digest = hashlib.sha256(f"synthetic:{seed}:{email}".encode()).hexdigest()[:16]
    return f"hashed:synthetic-test-only:{digest}"


def generate_users(
    config: GenerationConfig, organization_keys: list[str]
) -> list[dict[str, str | bool]]:
    """Generate synthetic users attached to the given organizations.

    Args:
        config: Generation configuration.
        organization_keys: Business keys of organizations (their names),
            used positionally to assign each user an organization.
    """
    rng = stream_rng(config.seed, "users")
    records: list[dict[str, str | bool]] = []
    for index, (local, username, role) in enumerate(_SYNTHETIC_USERS):
        email = f"{local}@supplysense.local"
        org_key = organization_keys[index % len(organization_keys)] if organization_keys else ""
        records.append(
            {
                "email": email,
                "username": f"{username}-{rng.randint(100, 999)}",
                "password_hash": _test_password_hash(config.seed, email),
                "role": role,
                "organization_key": org_key,
                "is_active": True,
            }
        )
    return records
