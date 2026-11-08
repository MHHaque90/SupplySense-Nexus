"""Bulk insertion helpers for the ingestion pipeline."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


async def insert_batch(
    session: AsyncSession,
    objects: list[Any],
    batch_size: int = 500,
) -> int:
    """Insert objects in batches, flushing per batch.

    A single commit is performed by the caller so the whole dataset
    stays inside one transaction boundary. Returns the row count.
    """
    total = 0
    for offset in range(0, len(objects), max(1, batch_size)):
        chunk = objects[offset: offset + max(1, batch_size)]
        session.add_all(chunk)
        await session.flush()
        total += len(chunk)
    return total
