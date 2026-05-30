"""In-memory restaurant store with optional Parquet cache."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import DATA_CACHE_PATH
from src.logging_config import setup_logging
from src.models.restaurant import BudgetTier, Restaurant

logger = setup_logging(__name__)

_CACHE_META_FILE = "restaurants.meta.json"


class RestaurantStore:
    """Read-only store of normalized restaurants."""

    def __init__(
        self,
        restaurants: list[Restaurant],
        *,
        ingested_at: datetime | None = None,
        source: str = "memory",
    ) -> None:
        self._restaurants = restaurants
        self._by_id = {r.id: r for r in restaurants}
        self.ingested_at = ingested_at or datetime.now(timezone.utc)
        self.source = source

        # Precompute unique locations (cities + neighborhoods)
        locs = set()
        self._city_lowers = {}
        self._area_lowers = {}
        self._cuisine_lowers = {}
        for r in restaurants:
            if r.location:
                locs.add(r.location)
                self._city_lowers[r.id] = r.location.lower()
            else:
                self._city_lowers[r.id] = ""

            area = r.metadata.get("area")
            if area:
                locs.add(area)
                self._area_lowers[r.id] = area.lower()
            else:
                self._area_lowers[r.id] = ""

            self._cuisine_lowers[r.id] = r.cuisine.lower()

        self.unique_locations = sorted(list(locs))

    @property
    def record_count(self) -> int:
        return len(self._restaurants)

    def get_all(self) -> list[Restaurant]:
        return list(self._restaurants)

    def get_by_ids(self, ids: list[str]) -> list[Restaurant]:
        return [self._by_id[i] for i in ids if i in self._by_id]

    def get_by_id(self, restaurant_id: str) -> Restaurant | None:
        return self._by_id.get(restaurant_id)

    @classmethod
    def from_restaurants(cls, restaurants: list[Restaurant]) -> RestaurantStore:
        return cls(restaurants, source="memory")

    @classmethod
    def load(cls, cache_path: Path | None = None) -> RestaurantStore:
        """Load store from Parquet cache. Raises FileNotFoundError if missing."""
        path = cache_path or DATA_CACHE_PATH
        if not path.exists():
            raise FileNotFoundError(
                f"Cache not found at {path}. Run: python -m scripts.ingest"
            )

        logger.info("Loading restaurant cache from %s", path)
        df = pd.read_parquet(path)
        restaurants = [_row_to_restaurant(row) for row in df.to_dict(orient="records")]

        meta_path = path.parent / _CACHE_META_FILE
        ingested_at = None
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("ingested_at"):
                ingested_at = datetime.fromisoformat(meta["ingested_at"])

        logger.info("Loaded %d restaurants from cache", len(restaurants))
        return cls(restaurants, ingested_at=ingested_at, source="cache")

    def save(self, cache_path: Path | None = None) -> Path:
        """Persist store to Parquet and write metadata sidecar."""
        path = cache_path or DATA_CACHE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)

        records = [_restaurant_to_dict(r) for r in self._restaurants]
        df = pd.DataFrame(records)
        df.to_parquet(path, index=False)

        meta = {
            "ingested_at": self.ingested_at.isoformat(),
            "record_count": self.record_count,
            "source": self.source,
        }
        meta_path = path.parent / _CACHE_META_FILE
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        logger.info("Saved %d restaurants to %s", self.record_count, path)
        return path


def _restaurant_to_dict(restaurant: Restaurant) -> dict[str, Any]:
    return {
        "id": restaurant.id,
        "name": restaurant.name,
        "location": restaurant.location,
        "cuisine": restaurant.cuisine,
        "cost": restaurant.cost,
        "budget_tier": restaurant.budget_tier.value,
        "rating": restaurant.rating,
        "metadata": json.dumps(restaurant.metadata),
    }


def _row_to_restaurant(row: dict[str, Any]) -> Restaurant:
    metadata = row.get("metadata")
    if isinstance(metadata, str):
        metadata = json.loads(metadata) if metadata else {}
    elif metadata is None:
        metadata = {}

    rating = row.get("rating")
    if pd.isna(rating):
        rating = None
    else:
        rating = float(rating)

    return Restaurant(
        id=str(row["id"]),
        name=str(row["name"]),
        location=str(row["location"]),
        cuisine=str(row["cuisine"]),
        cost=str(row["cost"]) if row.get("cost") is not None and not pd.isna(row.get("cost")) else None,
        budget_tier=BudgetTier(str(row["budget_tier"])),
        rating=rating,
        metadata=metadata,
    )
