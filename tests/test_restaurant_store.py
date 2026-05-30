"""Unit tests for RestaurantStore (Phase 1.8)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
import pytest

from src.models.restaurant import BudgetTier, Restaurant
from src.store.restaurant_store import RestaurantStore, _CACHE_META_FILE


@pytest.fixture
def two_restaurants() -> list[Restaurant]:
    return [
        Restaurant(
            id="r_aaa",
            name="Alpha",
            location="Bangalore",
            cuisine="Italian",
            cost="800",
            budget_tier=BudgetTier.MEDIUM,
            rating=4.5,
        ),
        Restaurant(
            id="r_bbb",
            name="Beta",
            location="Bangalore",
            cuisine="Chinese",
            cost="400",
            budget_tier=BudgetTier.LOW,
            rating=4.0,
        ),
    ]


def test_get_all_and_by_ids(two_restaurants):
    store = RestaurantStore.from_restaurants(two_restaurants)
    assert store.record_count == 2
    assert len(store.get_all()) == 2

    by_ids = store.get_by_ids(["r_bbb", "r_missing", "r_aaa"])
    assert len(by_ids) == 2
    assert by_ids[0].id == "r_bbb"
    assert by_ids[1].id == "r_aaa"


def test_get_by_id(two_restaurants):
    store = RestaurantStore.from_restaurants(two_restaurants)
    assert store.get_by_id("r_aaa").name == "Alpha"
    assert store.get_by_id("nope") is None


def test_save_and_load_roundtrip(two_restaurants, tmp_path):
    cache = tmp_path / "restaurants.parquet"
    ingested = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
    store = RestaurantStore(two_restaurants, ingested_at=ingested, source="test")
    store.save(cache)

    assert cache.exists()
    meta_file = tmp_path / _CACHE_META_FILE
    assert meta_file.exists()
    meta = json.loads(meta_file.read_text())
    assert meta["record_count"] == 2

    loaded = RestaurantStore.load(cache)
    assert loaded.record_count == 2
    assert loaded.source == "cache"
    assert loaded.get_by_id("r_aaa").name == "Alpha"
    assert loaded.get_by_id("r_aaa").budget_tier == BudgetTier.MEDIUM
    assert loaded.get_by_id("r_aaa").metadata == {}


def test_load_missing_cache_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        RestaurantStore.load(tmp_path / "missing.parquet")


def test_metadata_roundtrip(two_restaurants, tmp_path):
    r = two_restaurants[0].model_copy(
        update={"metadata": {"area": "Koramangala", "votes": "10"}}
    )
    cache = tmp_path / "restaurants.parquet"
    RestaurantStore([r], source="test").save(cache)
    loaded = RestaurantStore.load(cache)
    assert loaded.get_by_id("r_aaa").metadata["area"] == "Koramangala"


def test_null_rating_roundtrip(two_restaurants, tmp_path):
    r = two_restaurants[0].model_copy(update={"rating": None})
    cache = tmp_path / "restaurants.parquet"
    RestaurantStore([r], source="test").save(cache)
    loaded = RestaurantStore.load(cache)
    assert loaded.get_by_id("r_aaa").rating is None
