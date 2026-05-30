"""Tests for RecommendationService (Phase 4)."""

from __future__ import annotations

import json

import pytest

from src.llm.client import MockLLMClient, mock_response_for_candidates
from src.llm.engine import RecommendationEngine
from src.models.preferences import UserPreferences
from src.models.restaurant import BudgetTier, Restaurant
from src.services.recommendation_service import RecommendationService
from src.store.restaurant_store import RestaurantStore


@pytest.fixture
def small_store() -> RestaurantStore:
    restaurants = [
        Restaurant(
            id="r1",
            name="Alpha",
            location="Bangalore",
            cuisine="Italian",
            budget_tier=BudgetTier.MEDIUM,
            rating=4.8,
            cost="800",
        ),
        Restaurant(
            id="r2",
            name="Beta",
            location="Bangalore",
            cuisine="Chinese",
            budget_tier=BudgetTier.MEDIUM,
            rating=4.0,
            cost="500",
        ),
    ]
    return RestaurantStore.from_restaurants(restaurants)


def test_empty_candidates_skips_llm(small_store):
    prefs = UserPreferences(
        location="Delhi",
        budget=BudgetTier.MEDIUM,
        cuisine="Italian",
    )
    client = MockLLMClient([""])
    service = RecommendationService(
        small_store, llm_client=client
    )
    response = service.recommend(prefs)
    assert response.recommendations == []
    assert response.meta.llm_called is False
    assert response.meta.candidate_count == 0
    assert "No restaurants match" in (response.message or "")
    assert len(client.calls) == 0


def test_full_pipeline_with_mock(small_store):
    prefs = UserPreferences(
        location="Bangalore",
        budget=BudgetTier.MEDIUM,
        cuisine="Italian",
        min_rating=4.5,
    )
    candidates = [
        Restaurant(
            id="r1",
            name="Alpha",
            location="Bangalore",
            cuisine="Italian",
            budget_tier=BudgetTier.MEDIUM,
            rating=4.8,
            cost="800",
        )
    ]
    mock_json = mock_response_for_candidates(candidates, top_k=1)
    client = MockLLMClient([mock_json])
    service = RecommendationService(small_store, llm_client=client)

    response = service.recommend(prefs, top_k=1)
    assert len(response.recommendations) == 1
    assert response.recommendations[0].restaurant.name == "Alpha"
    assert response.meta.candidate_count == 1
    assert response.meta.llm_called is True
    assert len(client.calls) >= 1


def test_hallucinated_id_stripped_via_service(small_store):
    prefs = UserPreferences(
        location="Bangalore",
        budget=BudgetTier.MEDIUM,
        cuisine="any",
    )
    raw = json.dumps(
        {
            "recommendations": [
                {"restaurant_id": "r1", "rank": 1, "explanation": "Good."},
                {"restaurant_id": "fake", "rank": 2, "explanation": "Bad."},
            ]
        }
    )
    service = RecommendationService(
        small_store, llm_client=MockLLMClient([raw])
    )
    response = service.recommend(prefs, top_k=5)
    assert len(response.recommendations) == 1
    assert response.meta.hallucination_count == 1
