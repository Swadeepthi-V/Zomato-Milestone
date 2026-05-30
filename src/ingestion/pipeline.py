"""Orchestrate load → normalize → cache."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.config import DATA_CACHE_PATH, HF_DATASET_NAME
from src.ingestion.loader import load_raw_dataset
from src.ingestion.normalizer import normalize_records
from src.logging_config import setup_logging
from src.store.restaurant_store import RestaurantStore

logger = setup_logging(__name__)


def ingest_dataset(
    *,
    cache_path: Path | None = None,
    dataset_name: str | None = None,
    force_refresh: bool = False,
    seed_hyderabad: bool = True,
) -> RestaurantStore:
    """
    Load from Hugging Face, normalize, and persist to Parquet cache.

    If cache exists and force_refresh is False, loads from cache only (no HF call).
    """
    path = cache_path or DATA_CACHE_PATH

    if path.exists() and not force_refresh:
        logger.info("Cache hit — loading from %s (skipping Hugging Face)", path)
        return RestaurantStore.load(path)

    logger.info("Starting ingestion from Hugging Face (dataset=%s)", dataset_name or HF_DATASET_NAME)
    raw = load_raw_dataset(dataset_name=dataset_name)
    result = normalize_records(raw, seed_hyderabad=seed_hyderabad)

    logger.info(
        "Normalization complete: %d valid, %d skipped (reasons=%s)",
        len(result.restaurants),
        result.skipped_count,
        result.skip_reasons,
    )

    if not result.restaurants:
        raise RuntimeError("No valid restaurants after normalization")

    store = RestaurantStore(
        result.restaurants,
        ingested_at=datetime.now(timezone.utc),
        source="huggingface",
    )
    store.save(path)
    return store
