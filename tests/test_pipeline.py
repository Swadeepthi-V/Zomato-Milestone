"""Tests for ingest pipeline cache behavior."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.ingestion.pipeline import ingest_dataset
from src.models.restaurant import BudgetTier, Restaurant
from src.store.restaurant_store import RestaurantStore


def test_ingest_uses_cache_without_hf_call(tmp_path):
    cache = tmp_path / "restaurants.parquet"
    restaurants = [
        Restaurant(
            id="r_cached",
            name="Cached",
            location="Bangalore",
            cuisine="Cafe",
            budget_tier=BudgetTier.LOW,
        )
    ]
    RestaurantStore(restaurants, source="test").save(cache)

    with patch("src.ingestion.pipeline.load_raw_dataset") as mock_load:
        store = ingest_dataset(cache_path=cache, force_refresh=False)
        mock_load.assert_not_called()

    assert store.record_count == 1
    assert store.get_by_id("r_cached").name == "Cached"


def test_ingest_force_refresh_calls_hf(tmp_path):
    cache = tmp_path / "restaurants.parquet"
    restaurants = [
        Restaurant(
            id="r_old",
            name="Old",
            location="Bangalore",
            cuisine="Cafe",
            budget_tier=BudgetTier.LOW,
        )
    ]
    RestaurantStore(restaurants, source="test").save(cache)

    raw = [
        {
            "url": "https://www.zomato.com/bangalore/new",
            "name": "New Place",
            "address": "1 St, Bangalore",
            "cuisines": "Italian",
            "approx_cost(for two people)": "600",
            "rate": "4.5/5",
        }
    ]

    with patch("src.ingestion.pipeline.load_raw_dataset", return_value=raw):
        store = ingest_dataset(cache_path=cache, force_refresh=True, seed_hyderabad=False)

    assert store.record_count == 1
    assert store.get_by_id(store.get_all()[0].id).name == "New Place"
