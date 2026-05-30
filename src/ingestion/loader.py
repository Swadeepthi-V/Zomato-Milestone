"""Load raw records from Hugging Face."""

from __future__ import annotations

from typing import Any

from datasets import load_dataset

from src.config import HF_DATASET_NAME, HF_DATASET_SPLIT, MAX_INGEST_RECORDS
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
    
    # Strip slicing brackets from split if present to prevent streaming error
    if "[" in dataset_split:
        dataset_split = dataset_split.split("[")[0]
        
    logger.info("Loading dataset %s (split=%s) via streaming from Hugging Face", name, dataset_split)
    
    try:
        dataset = load_dataset(name, split=dataset_split, streaming=True)
        records = []
        for i, row in enumerate(dataset):
            if i >= MAX_INGEST_RECORDS:
                break
            records.append(dict(row))
        logger.info("Successfully streamed %d records from Hugging Face", len(records))
    except Exception as e:
        logger.warning("Streaming failed: %s. Falling back to default download.", e)
        dataset = load_dataset(name, split=dataset_split)
        records = [dict(row) for row in dataset[:MAX_INGEST_RECORDS]]
        
    logger.info("Loaded %d raw records from Hugging Face", len(records))
    return records
