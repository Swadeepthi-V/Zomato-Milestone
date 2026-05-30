"""Integration tests: mock LLM → parse path (Phase 3.8)."""

from __future__ import annotations

import json

import pytest

from src.llm.client import LLMError, MockLLMClient
from src.llm.engine import RecommendationEngine
from src.llm.response_parser import LLMResponseError
from src.models.preferences import UserPreferences
from src.models.restaurant import BudgetTier, Restaurant


def _candidates() -> list[Restaurant]:
    return [
        Restaurant(
            id="r1",
            name="Alpha Italian",
            location="Bangalore",
            cuisine="Italian, Pizza",
            budget_tier=BudgetTier.MEDIUM,
            rating=4.8,
            cost="800",
        ),
        Restaurant(
            id="r2",
            name="Beta Italian",
            location="Bangalore",
            cuisine="Italian",
            budget_tier=BudgetTier.MEDIUM,
            rating=4.2,
            cost="600",
        ),
        Restaurant(
            id="r3",
            name="Gamma Chinese",
            location="Bangalore",
            cuisine="Chinese",
            budget_tier=BudgetTier.MEDIUM,
            rating=4.5,
            cost="700",
        ),
    ]


def _valid_response() -> str:
    return json.dumps(
        {
            "summary": "Strong Italian options for your trip.",
            "recommendations": [
                {
                    "restaurant_id": "r1",
                    "rank": 1,
                    "explanation": "Top Italian choice in Bangalore with high rating.",
                },
                {
                    "restaurant_id": "r2",
                    "rank": 2,
                    "explanation": "Solid medium-budget Italian option.",
                },
                {
                    "restaurant_id": "r_hallucinated",
                    "rank": 3,
                    "explanation": "Should be dropped.",
                },
            ],
        }
    )


def test_mock_llm_full_pipeline():
    client = MockLLMClient([_valid_response()])
    engine = RecommendationEngine(client)
    prefs = UserPreferences(
        location="Bangalore",
        budget=BudgetTier.MEDIUM,
        cuisine="Italian",
        min_rating=4.0,
    )

    response = engine.rank_and_explain(prefs, _candidates(), top_k=2)

    assert response.summary is not None
    assert len(response.recommendations) == 2
    assert response.recommendations[0].restaurant.id == "r1"
    assert response.recommendations[0].restaurant.name == "Alpha Italian"
    assert response.meta.hallucination_count == 1
    assert response.meta.llm_called is True
    assert "Bangalore" in response.recommendations[0].explanation or "Italian" in response.recommendations[0].explanation


def test_sorted_by_rank():
    shuffled = json.dumps(
        {
            "recommendations": [
                {"restaurant_id": "r2", "rank": 2, "explanation": "Second."},
                {"restaurant_id": "r1", "rank": 1, "explanation": "First."},
            ]
        }
    )
    client = MockLLMClient([shuffled])
    engine = RecommendationEngine(client)
    prefs = UserPreferences(location="Bangalore", budget=BudgetTier.MEDIUM, cuisine="Italian")

    response = engine.rank_and_explain(prefs, _candidates()[:2], top_k=2)
    assert response.recommendations[0].restaurant.id == "r1"
    assert response.recommendations[1].restaurant.id == "r2"


def test_invalid_json_triggers_repair():
    bad = "Sorry, here are picks: not valid json {{{"
    good = _valid_response()
    client = MockLLMClient([bad, good])
    engine = RecommendationEngine(client, max_llm_retries=1)
    prefs = UserPreferences(location="Bangalore", budget=BudgetTier.MEDIUM, cuisine="Italian")

    response = engine.rank_and_explain(prefs, _candidates(), top_k=2)
    assert len(response.recommendations) >= 1
    assert response.meta.parse_retries == 1
    assert len(client.calls) == 2


def test_all_hallucinated_after_repair_raises():
    bad = "not json"
    still_bad = json.dumps(
        {
            "recommendations": [
                {"restaurant_id": "fake", "rank": 1, "explanation": "Nope."}
            ]
        }
    )
    client = MockLLMClient([bad, still_bad])
    engine = RecommendationEngine(client, max_llm_retries=1)
    prefs = UserPreferences(location="Bangalore", budget=BudgetTier.MEDIUM, cuisine="Italian")

    with pytest.raises(LLMResponseError):
        engine.rank_and_explain(prefs, _candidates(), top_k=2)


def test_empty_candidates_skips_llm():
    client = MockLLMClient([_valid_response()])
    engine = RecommendationEngine(client)
    prefs = UserPreferences(location="Bangalore", budget=BudgetTier.MEDIUM, cuisine="Italian")

    response = engine.rank_and_explain(prefs, [], top_k=5)
    assert response.recommendations == []
    assert response.meta.llm_called is False
    assert len(client.calls) == 0


def test_llm_retry_on_retryable_error():
    class FailingThenMock(MockLLMClient):
        def __init__(self):
            super().__init__([_valid_response()])
            self.attempt = 0

        def complete(self, prompt, config=None):
            self.attempt += 1
            if self.attempt == 1:
                raise LLMError("timeout", retryable=True)
            return super().complete(prompt, config)

    engine = RecommendationEngine(FailingThenMock(), max_llm_retries=2)
    prefs = UserPreferences(location="Bangalore", budget=BudgetTier.MEDIUM, cuisine="Italian")
    response = engine.rank_and_explain(prefs, _candidates()[:2], top_k=2)
    assert len(response.recommendations) == 2
