"""CLI: load Hugging Face dataset, normalize, and cache locally."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on path when run as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DATA_CACHE_PATH, HF_DATASET_NAME
from src.ingestion.pipeline import ingest_dataset
from src.logging_config import setup_logging

logger = setup_logging("ingest")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest Zomato dataset into local cache")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download from Hugging Face even if cache exists",
    )
    parser.add_argument(
        "--cache-path",
        type=Path,
        default=None,
        help=f"Parquet output path (default: {DATA_CACHE_PATH})",
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help=f"Hugging Face dataset id (default: {HF_DATASET_NAME})",
    )
    args = parser.parse_args()

    try:
        store = ingest_dataset(
            cache_path=args.cache_path,
            dataset_name=args.dataset,
            force_refresh=args.force,
        )
    except Exception:
        logger.exception("Ingestion failed")
        return 1

    logger.info(
        "Ingestion succeeded | records=%d | ingested_at=%s | source=%s",
        store.record_count,
        store.ingested_at.isoformat(),
        store.source,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
