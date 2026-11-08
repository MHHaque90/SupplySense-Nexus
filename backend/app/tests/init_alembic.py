"""Initialize alembic version table."""
import asyncio

from sqlalchemy import text

from backend.app.core.database import engine


async def main():
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR(32) NOT NULL PRIMARY KEY
            )
        """))
        await conn.execute(text(
            "INSERT INTO alembic_version (version_num) VALUES ('initial') "
            "ON CONFLICT (version_num) DO NOTHING"
        ))
    await engine.dispose()
    print("Alembic version table ready")

asyncio.run(main())
