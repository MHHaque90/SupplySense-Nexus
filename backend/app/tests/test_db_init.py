"""Test database initialization and table creation."""
import asyncio
import sys

sys.path.insert(0, '.')

from backend.app.core.database import dispose_engine, engine, init_db
from backend.app.models import *


async def main():
    await init_db()
    print("Database initialized successfully")

    # Check tables
    async with engine.begin() as conn:
        from sqlalchemy import text
        result = await conn.execute(text(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"
        ))
        count = result.scalar()
        print(f"Tables found: {count}")

        # List all tables
        result2 = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
        ))
        tables = [row[0] for row in result2.all()]
        for t in tables:
            print(f"  - {t}")

    await dispose_engine()

if __name__ == "__main__":
    asyncio.run(main())
