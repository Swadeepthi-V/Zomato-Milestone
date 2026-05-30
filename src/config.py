"""Application configuration from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_CACHE_PATH = DATA_DIR / "restaurants.parquet"

# Data ingestion
HF_DATASET_NAME = os.getenv(
    "HF_DATASET_NAME", "ManikaSaini/zomato-restaurant-recommendation"
)
HF_DATASET_SPLIT = os.getenv("HF_DATASET_SPLIT", "train")
MAX_INGEST_RECORDS = int(os.getenv("MAX_INGEST_RECORDS", "15000"))
DATA_CACHE_PATH = Path(os.getenv("DATA_CACHE_PATH", str(DEFAULT_CACHE_PATH)))

# Recommendation
MAX_CANDIDATES = int(os.getenv("MAX_CANDIDATES", "30"))
TOP_K = int(os.getenv("TOP_K", "5"))

# LLM / Groq (Phase 3–4)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "") or os.getenv("LLM_API_KEY", "")
LLM_API_KEY = GROQ_API_KEY  # backward-compatible alias
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
