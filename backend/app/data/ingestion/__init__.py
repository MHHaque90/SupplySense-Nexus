"""Data ingestion pipeline for SupplySense Nexus (Phase 2).

Separates generation (pure, deterministic record dicts) from
persistence (batched SQLAlchemy inserts with transaction boundaries).
"""

from backend.app.data.ingestion.loaders import insert_batch
from backend.app.data.ingestion.pipeline import (
    DatasetExistsError,
    GeneratedDataset,
    dataset_exists,
    generate_dataset,
    load_dataset,
    reset_dataset,
)

__all__ = [
    "DatasetExistsError",
    "GeneratedDataset",
    "dataset_exists",
    "generate_dataset",
    "insert_batch",
    "load_dataset",
    "reset_dataset",
]
