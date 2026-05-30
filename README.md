# AI-Powered Restaurant Recommendation System (Zomato Milestone)

An AI-powered restaurant recommendation service that combines structured Zomato data with LLM ranking and explanations.

## Documentation

- [Project context](docs/context.md)
- [Architecture](docs/architecture.md)
- [Implementation plan](docs/implementation-plan.md)
- [Edge cases](docs/edge-case.md)

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
cp .env.example .env          # optional; defaults work for ingestion
```

## Phase 1: Data ingestion

Load the Hugging Face dataset, normalize records, and cache locally:

```bash
python -m scripts.ingest
```

Force re-download from Hugging Face:

```bash
python -m scripts.ingest --force
```

Cache path defaults to `data/restaurants.parquet` (see `.env.example`).

## Phase 2: Preference filtering

Filter candidates by location, budget, cuisine, and rating (no LLM):

```bash
python -m scripts.filter_candidates -l Bangalore -b medium -c Italian -r 4.0
python -m scripts.filter_candidates -l Bangalore -b medium -c any --json
```

`additional_preferences` is accepted but not applied in the hard filter (reserved for the LLM in Phase 3).

## Phase 3: LLM integration

Rank and explain filtered candidates with grounded JSON output:

```bash
# Mock LLM (no API key, for CI/local)
python -m scripts.recommend -l Bangalore -b medium -c Italian -r 4.0 --mock

# Live Groq (set GROQ_API_KEY in .env)
python -m scripts.recommend -l Bangalore -b medium -c Italian -r 4.0 --json
```

Display fields (name, cuisine, rating, cost) always come from the dataset; the LLM supplies ranks and explanations only.

## Phase 4: Orchestration & API

End-to-end service with **Groq** for live LLM calls:

```bash
# Set GROQ_API_KEY in .env (https://console.groq.com/keys)

# CLI (mock or Groq)
python -m src.app.main recommend -l Bangalore -b medium -c Italian -r 4.0 --mock
python -m src.app.main recommend -l Bangalore -b medium -c Italian -r 4.0 --json

# API server
python -m src.app.main serve --port 8000
# GET  http://127.0.0.1:8000/health
# POST http://127.0.0.1:8000/recommend
```

Example API request:

```json
{
  "location": "Bangalore",
  "budget": "medium",
  "cuisine": "Italian",
  "min_rating": 4.0,
  "top_k": 5
}
```

## Tests

```bash
pytest
```

## Project structure

```text
src/
  models/restaurant.py       # Canonical Restaurant model
  models/preferences.py      # UserPreferences model
  ingestion/                 # HF loader, normalizer, pipeline
  filters/preference_filter.py
  llm/                       # Groq client, prompt_builder, response_parser, engine
  services/recommendation_service.py
  app/                       # FastAPI routes, CLI (main.py)
  store/restaurant_store.py  # In-memory store + Parquet cache
scripts/ingest.py            # Ingestion CLI
scripts/filter_candidates.py # Filter-only CLI
scripts/recommend.py         # Thin wrapper around app CLI
tests/                       # Unit tests
data/                        # Cached dataset (gitignored)
```

## Environment variables

| Variable | Purpose |
|----------|---------|
| `DATA_CACHE_PATH` | Parquet cache location |
| `HF_DATASET_NAME` | Hugging Face dataset id |
| `HF_DATASET_SPLIT` | Dataset split (default `train`) |
| `LOG_LEVEL` | Logging level |

See `.env.example` for LLM and recommendation settings used in later phases.
