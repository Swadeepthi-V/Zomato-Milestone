"""API integration tests with mock LLM (Phase 4.11)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from src.app.factory import create_app
from src.app.state import AppState
from src.llm.client import MockLLMClient, mock_response_for_candidates
from src.models.restaurant import BudgetTier, Restaurant
from src.services.recommendation_service import RecommendationService
from src.store.restaurant_store import RestaurantStore


@pytest.fixture
def test_store() -> RestaurantStore:
    return RestaurantStore.from_restaurants(
        [
            Restaurant(
                id="r1",
                name="Trattoria",
                location="Bangalore",
                cuisine="Italian, Pizza",
                budget_tier=BudgetTier.MEDIUM,
                rating=4.6,
                cost="700",
            ),
            Restaurant(
                id="r2",
                name="Wok House",
                location="Bangalore",
                cuisine="Chinese",
                budget_tier=BudgetTier.LOW,
                rating=4.1,
                cost="400",
            ),
        ]
    )


@pytest.fixture
def client(test_store: RestaurantStore) -> TestClient:
    candidates = test_store.get_all()
    mock_json = mock_response_for_candidates(
        [r for r in candidates if "Italian" in r.cuisine],
        top_k=1,
    )
    service = RecommendationService(
        test_store, llm_client=MockLLMClient([mock_json])
    )
    app = create_app(app_state=AppState(store=test_store, service=service))
    return TestClient(app)


def test_root_ui_ok(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert "CulinaryMind" in response.text


def test_get_locations_ok(client: TestClient):
    response = client.get("/locations")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert "Bangalore" in data


def test_health_ok(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["dataset_loaded"] is True
    assert data["record_count"] == 2


def test_health_unavailable():
    app = create_app(app_state=AppState(store=None, service=None))
    response = TestClient(app).get("/health")
    assert response.status_code == 503


def test_recommend_success(client: TestClient):
    response = client.post(
        "/recommend",
        json={
            "location": "Bangalore",
            "budget": "medium",
            "cuisine": "Italian",
            "min_rating": 4.0,
            "top_k": 3,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["recommendations"]) >= 1
    assert data["recommendations"][0]["restaurant"]["name"] == "Trattoria"
    assert data["meta"]["candidate_count"] >= 1
    assert data["meta"]["llm_called"] is True


def test_recommend_validation_error(client: TestClient):
    response = client.post(
        "/recommend",
        json={"location": "", "budget": "medium"},
    )
    assert response.status_code == 422


def test_recommend_empty_filters(client: TestClient):
    response = client.post(
        "/recommend",
        json={
            "location": "Mumbai",
            "budget": "medium",
            "cuisine": "Italian",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["recommendations"] == []
    assert data["meta"]["llm_called"] is False
    assert "No restaurants match" in data.get("message", "")


def test_recommend_invalid_budget(client: TestClient):
    response = client.post(
        "/recommend",
        json={
            "location": "Bangalore",
            "budget": "luxury",
            "cuisine": "Italian",
        },
    )
    assert response.status_code == 422
