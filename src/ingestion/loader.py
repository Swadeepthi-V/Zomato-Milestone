"""Load raw records from Hugging Face."""

from __future__ import annotations

from typing import Any

from datasets import load_dataset

from src.config import HF_DATASET_NAME, HF_DATASET_SPLIT
from src.logging_config import setup_logging

logger = setup_logging(__name__)


def load_raw_dataset(
    dataset_name: str | None = None,
    split: str | None = None,
) -> list[dict[str, Any]]:
    """
    Load the Zomato dataset from Hugging Face.

    Returns a list of row dicts (one dict per restaurant).
    """
    name = dataset_name or HF_DATASET_NAME
    dataset_split = split or HF_DATASET_SPLIT
    logger.info("Loading dataset %s (split=%s) from Hugging Face", name, dataset_split)
    dataset = load_dataset(name, split=dataset_split)
    records = [dict(row) for row in dataset]
    logger.info("Loaded %d raw records from Hugging Face", len(records))
    return records
