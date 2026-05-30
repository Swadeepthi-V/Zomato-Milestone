"""Unit tests for preference filter (Phase 2.9)."""

from __future__ import annotations

import time

import pytest
from pydantic import ValidationError

from src.filters.preference_filter import PreferenceFilter
from src.models.preferences import UserPreferences
from src.models.restaurant import BudgetTier, Restaurant
from src.store.restaurant_store import RestaurantStore


def _restaurant(
    *,
    id: str,
    name: str,
    location: str = "Bangalore",
    cuisine: str = "Italian",
    budget_tier: BudgetTier = BudgetTier.MEDIUM,
    rating: float | None = 4.0,
) -> Restaurant:
    return Restaurant(
        id=id,
        name=name,
        location=location,
        cuisine=cuisine,
        budget_tier=budget_tier,
        rating=rating,
        cost="800",
    )


@pytest.fixture
def filter_store() -> RestaurantStore:
    restaurants = [
        _restaurant(id="r1", name="Italian High", cuisine="Italian, Pizza", rating=4.8),
        _restaurant(id="r2", name="Italian Mid", cuisine="Italian", rating=4.2),
        _restaurant(id="r3", name="Chinese Mid", cuisine="Chinese", rating=4.5),
        _restaurant(
            id="r4",
            name="Italian Low Budget",
            cuisine="Italian",
            budget_tier=BudgetTier.LOW,
            rating=4.0,
        ),
        _restaurant(
            id="r5",
            name="Italian Unrated",
            cuisine="Italian",
            rating=None,
        ),
        _restaurant(
            id="r6",
            name="Delhi Italian",
            location="Delhi",
            cuisine="Italian",
            rating=4.6,
        ),
        _restaurant(
            id="r7",
            name="Italian Low Rated",
            cuisine="Italian",
            rating=3.2,
        ),
    ]
    return RestaurantStore.from_restaurants(restaurants)


def test_location_filter(filter_store):
    prefs = UserPreferences(
        location="Bangalore",
        budget=BudgetTier.MEDIUM,
        cuisine="any",
    )
    result = PreferenceFilter.apply(filter_store, prefs)
    names = {r.name for r in result}
    assert "Delhi Italian" not in names
    assert "Italian High" in names


def test_location_substring_typo(filter_store):
    prefs = UserPreferences(
        location="bang",
        budget=BudgetTier.MEDIUM,
        cuisine="any",
    )
    result = PreferenceFilter.apply(filter_store, prefs)
    assert len(result) >= 1
    assert all("bangalore" in r.location.lower() for r in result)


def test_bengaluru_alias_normalization(filter_store):
    prefs = UserPreferences(
        location="bengaluru",
        budget=BudgetTier.MEDIUM,
        cuisine="any",
    )
    result = PreferenceFilter.apply(filter_store, prefs)
    assert "Italian High" in {r.name for r in result}


def test_budget_filter(filter_store):
    prefs = UserPreferences(
        location="Bangalore",
        budget=BudgetTier.LOW,
        cuisine="Italian",
    )
    result = PreferenceFilter.apply(filter_store, prefs)
    assert len(result) == 1
    assert result[0].name == "Italian Low Budget"


def test_cuisine_substring_multi_value(filter_store):
    prefs = UserPreferences(
        location="Bangalore",
        budget=BudgetTier.MEDIUM,
        cuisine="Pizza",
    )
    result = PreferenceFilter.apply(filter_store, prefs)
    assert len(result) == 1
    assert result[0].name == "Italian High"


def test_cuisine_any_skips_filter(filter_store):
    prefs = UserPreferences(
        location="Bangalore",
        budget=BudgetTier.MEDIUM,
        cuisine="any",
    )
    result = PreferenceFilter.apply(filter_store, prefs)
    assert len(result) >= 4


def test_min_rating_excludes_low_and_unrated(filter_store):
    prefs = UserPreferences(
        location="Bangalore",
        budget=BudgetTier.MEDIUM,
        cuisine="Italian",
        min_rating=4.0,
    )
    result = PreferenceFilter.apply(filter_store, prefs)
    names = {r.name for r in result}
    assert "Italian Low Rated" not in names
    assert "Italian Unrated" not in names
    assert "Italian High" in names
    assert all(r.rating is not None and r.rating >= 4.0 for r in result)


def test_empty_result_no_error(filter_store):
    prefs = UserPreferences(
        location="Mumbai",
        budget=BudgetTier.MEDIUM,
        cuisine="Italian",
    )
    result = PreferenceFilter.apply(filter_store, prefs)
    assert result == []


def test_additional_preferences_not_used_in_filter(filter_store):
    prefs_with = UserPreferences(
        location="Bangalore",
        budget=BudgetTier.MEDIUM,
        cuisine="Chinese",
        additional_preferences="family-friendly",
    )
    prefs_without = UserPreferences(
        location="Bangalore",
        budget=BudgetTier.MEDIUM,
        cuisine="Chinese",
    )
    assert PreferenceFilter.apply(filter_store, prefs_with) == PreferenceFilter.apply(
        filter_store, prefs_without
    )


def test_candidate_cap(filter_store):
    prefs = UserPreferences(
        location="Bangalore",
        budget=BudgetTier.MEDIUM,
        cuisine="any",
    )
    result = PreferenceFilter.apply(filter_store, prefs, max_candidates=2)
    assert len(result) == 2
    assert result[0].rating == 4.8
    assert result[1].rating == 4.5


def test_sorted_by_rating_desc(filter_store):
    prefs = UserPreferences(
        location="Bangalore",
        budget=BudgetTier.MEDIUM,
        cuisine="Italian",
        min_rating=4.0,
    )
    result = PreferenceFilter.apply(filter_store, prefs, max_candidates=10)
    ratings = [r.rating for r in result if r.rating is not None]
    assert ratings == sorted(ratings, reverse=True)


def test_user_preferences_validation():
    with pytest.raises(ValidationError):
        UserPreferences(location="", budget=BudgetTier.LOW)

    with pytest.raises(ValidationError):
        UserPreferences(location="X", budget=BudgetTier.LOW, min_rating=6.0)


def test_filter_performance_on_full_cache():
    """Acceptance: filter < 100 ms on full dataset (local)."""
    from src.config import DATA_CACHE_PATH

    if not DATA_CACHE_PATH.exists():
        pytest.skip("Full cache not available; run scripts.ingest first")

    store = RestaurantStore.load()
    prefs = UserPreferences(
        location="Bangalore",
        budget=BudgetTier.MEDIUM,
        cuisine="Italian",
        min_rating=4.0,
    )
    start = time.perf_counter()
    result = PreferenceFilter.apply(store, prefs)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 100, f"Filter took {elapsed_ms:.1f} ms"
    assert len(result) <= 30
    assert len(result) > 0
