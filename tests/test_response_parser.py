"""Tests for response parser and grounding."""

from __future__ import annotations

import pytest

from src.llm.response_parser import LLMResponseError, ResponseParser, extract_json
from src.models.restaurant import BudgetTier, Restaurant


def _candidate(id: str, name: str, rating: float = 4.5) -> Restaurant:
    return Restaurant(
        id=id,
        name=name,
        location="Bangalore",
        cuisine="Italian",
        budget_tier=BudgetTier.MEDIUM,
        rating=rating,
        cost="800",
    )


@pytest.fixture
def candidates() -> list[Restaurant]:
    return [
        _candidate("r1", "Real Bistro One", 4.8),
        _candidate("r2", "Real Bistro Two", 4.2),
    ]


def test_parse_valid_response(candidates):
    raw = """```json
{
  "summary": "Two great Italian spots.",
  "recommendations": [
    {"restaurant_id": "r2", "rank": 2, "explanation": "Matches your budget."},
    {"restaurant_id": "r1", "rank": 1, "explanation": "Top rated in Bangalore."}
  ]
}
```"""
    response = ResponseParser.parse(raw, candidates, model="mock")

    assert response.summary == "Two great Italian spots."
    assert len(response.recommendations) == 2
    assert response.recommendations[0].rank == 1
    assert response.recommendations[0].restaurant.name == "Real Bistro One"
    assert response.recommendations[1].restaurant.name == "Real Bistro Two"
    assert response.meta.hallucination_count == 0


def test_display_fields_from_store_not_llm(candidates):
    """Names in LLM output must be ignored; store is source of truth."""
    raw = """{
      "recommendations": [
        {
          "restaurant_id": "r1",
          "rank": 1,
          "explanation": "Good fit.",
          "name": "Fake Invented Name",
          "cuisine": "Fake Cuisine"
        }
      ]
    }"""
    response = ResponseParser.parse(raw, candidates)
    assert response.recommendations[0].restaurant.name == "Real Bistro One"
    assert response.recommendations[0].restaurant.cuisine == "Italian"


def test_hallucinated_id_stripped(candidates):
    raw = """{
      "recommendations": [
        {"restaurant_id": "r1", "rank": 1, "explanation": "Valid."},
        {"restaurant_id": "r_ghost", "rank": 2, "explanation": "Hallucinated."}
      ]
    }"""
    response = ResponseParser.parse(raw, candidates)
    assert len(response.recommendations) == 1
    assert response.meta.hallucination_count == 1


def test_all_invalid_ids_raises(candidates):
    raw = """{
      "recommendations": [
        {"restaurant_id": "bad1", "rank": 1, "explanation": "Nope."}
      ]
    }"""
    with pytest.raises(LLMResponseError):
        ResponseParser.parse(raw, candidates)


def test_empty_explanation_fallback(candidates):
    raw = """{
      "recommendations": [
        {"restaurant_id": "r1", "rank": 1, "explanation": ""}
      ]
    }"""
    response = ResponseParser.parse(raw, candidates)
    assert response.recommendations[0].explanation == "Recommended based on your preferences."


def test_extract_json_strips_fences():
    raw = 'Here is output:\n```json\n{"recommendations": []}\n```'
    data = extract_json(raw)
    assert "recommendations" in data


def test_invalid_json_raises():
    with pytest.raises(LLMResponseError):
        extract_json("not json at all")
