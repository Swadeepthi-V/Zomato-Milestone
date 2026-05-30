"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from src.models.restaurant import BudgetTier, Restaurant


@pytest.fixture
def sample_raw_row() -> dict:
    return {
        "url": "https://www.zomato.com/bangalore/test-restaurant",
        "name": "Test Bistro",
        "address": "100 MG Road, Koramangala, Bangalore",
        "location": "Koramangala",
        "cuisines": "Italian, Pizza",
        "approx_cost(for two people)": "800",
        "rate": "4.2/5",
        "rest_type": "Casual Dining",
        "votes": "100",
    }


@pytest.fixture
def sample_restaurant() -> Restaurant:
    return Restaurant(
        id="r_test123",
        name="Test Bistro",
        location="Bangalore",
        cuisine="Italian, Pizza",
        cost="800",
        budget_tier=BudgetTier.MEDIUM,
        rating=4.2,
        metadata={"area": "Koramangala"},
    )
