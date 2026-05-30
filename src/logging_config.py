"""Shared logging configuration for ingestion and API."""

from __future__ import annotations

import logging
import sys

from src.config import LOG_LEVEL


def setup_logging(name: str | None = None) -> logging.Logger:
    """Configure root logging once and return a named logger."""
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root.addHandler(handler)
        root.setLevel(level)
    return logging.getLogger(name or "zomato")
