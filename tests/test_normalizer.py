"""Unit tests for ingestion normalizer (Phase 1.8)."""

from __future__ import annotations

from src.ingestion.normalizer import normalize_records
from src.models.restaurant import BudgetTier


def test_normalize_valid_row(sample_raw_row):
    result = normalize_records([sample_raw_row])
    assert len(result.restaurants) == 1
    assert result.skipped_count == 0

    r = result.restaurants[0]
    assert r.name == "Test Bistro"
    assert r.location == "Bangalore"
    assert r.cuisine == "Italian, Pizza"
    assert r.cost == "800"
    assert r.budget_tier == BudgetTier.MEDIUM
    assert r.rating == 4.2
    assert r.id.startswith("r_")


def test_missing_name_skipped():
    result = normalize_records([{"name": "", "address": "MG Road, Bangalore"}])
    assert len(result.restaurants) == 0
    assert result.skipped_count == 1
    assert result.skip_reasons.get("missing_name") == 1


def test_missing_location_skipped():
    result = normalize_records([{"name": "No City Cafe", "address": "", "location": ""}])
    assert len(result.restaurants) == 0
    assert result.skip_reasons.get("missing_location") == 1


def test_missing_rating_parsed_as_none():
    row = {
        "name": "New Place",
        "address": "1 Road, Bangalore",
        "cuisines": "Cafe",
        "approx_cost(for two people)": "300",
        "rate": "NEW",
    }
    result = normalize_records([row])
    assert result.restaurants[0].rating is None


def test_null_rating():
    row = {
        "name": "Unrated",
        "address": "2 Road, Bangalore",
        "cuisines": "Cafe",
        "approx_cost(for two people)": "300",
        "rate": None,
    }
    result = normalize_records([row])
    assert result.restaurants[0].rating is None


def test_rating_fraction_format():
    row = {
        "name": "Rated",
        "address": "3 Road, Bangalore",
        "cuisines": "Cafe",
        "approx_cost(for two people)": "300",
        "rate": "3.8/5",
    }
    assert normalize_records([row]).restaurants[0].rating == 3.8


def test_budget_tier_low_medium_high():
    cases = [
        ("150", BudgetTier.LOW),
        ("400", BudgetTier.LOW),
        ("500", BudgetTier.MEDIUM),
        ("800", BudgetTier.MEDIUM),
        ("1,200", BudgetTier.HIGH),
    ]
    for cost, expected in cases:
        row = {
            "name": f"R {cost}",
            "address": "X, Bangalore",
            "cuisines": "Indian",
            "approx_cost(for two people)": cost,
            "rate": "4.0/5",
        }
        tier = normalize_records([row]).restaurants[0].budget_tier
        assert tier == expected, f"cost={cost}"


def test_ambiguous_cost_defaults_medium():
    row = {
        "name": "Mystery Cost",
        "address": "4 Road, Bangalore",
        "cuisines": "Cafe",
        "approx_cost(for two people)": "",
        "rate": "4.0/5",
    }
    assert normalize_records([row]).restaurants[0].budget_tier == BudgetTier.MEDIUM


def test_multi_cuisine_string_preserved():
    row = {
        "name": "Multi",
        "address": "5 Road, Bangalore",
        "cuisines": "North Indian, Mughlai, Chinese",
        "approx_cost(for two people)": "600",
        "rate": "4.0/5",
    }
    assert normalize_records([row]).restaurants[0].cuisine == "North Indian, Mughlai, Chinese"


def test_bengaluru_normalized_to_bangalore():
    row = {
        "name": "South Indian",
        "address": "10 Street, Bengaluru",
        "cuisines": "South Indian",
        "approx_cost(for two people)": "500",
        "rate": "4.0/5",
    }
    assert normalize_records([row]).restaurants[0].location == "Bangalore"


def test_stable_id_from_url():
    row = {
        "url": "https://www.zomato.com/bangalore/unique-place",
        "name": "Unique",
        "address": "6 Road, Bangalore",
        "cuisines": "Cafe",
        "approx_cost(for two people)": "500",
        "rate": "4.0/5",
    }
    r1 = normalize_records([row]).restaurants[0]
    r2 = normalize_records([row]).restaurants[0]
    assert r1.id == r2.id


def test_duplicate_ids_get_suffix():
    url = "https://www.zomato.com/bangalore/duplicate-place"
    base = {
        "url": url,
        "name": "Dup",
        "address": "7 Road, Bangalore",
        "cuisines": "Cafe",
        "approx_cost(for two people)": "500",
        "rate": "4.0/5",
    }
    result = normalize_records([base, dict(base)])
    assert len(result.restaurants) == 2
    assert result.restaurants[0].id != result.restaurants[1].id
    assert "_" in result.restaurants[1].id


def test_hyderabad_mock_seeding():
    # Calling normalize_records with seed_hyderabad=True should append the 12 Hyderabad records
    result = normalize_records([], seed_hyderabad=True)
    assert len(result.restaurants) == 12

    # Verify we got Hyderabad restaurants
    hyderabad_res = [r for r in result.restaurants if r.location == "Hyderabad"]
    assert len(hyderabad_res) == 12

    # Check for areas like Madhapur, Bachupally, Miyapur, Suchitra
    areas = {r.metadata.get("area") for r in hyderabad_res}
    expected_areas = {"Madhapur", "Bachupally", "Miyapur", "Suchitra"}
    assert expected_areas.issubset(areas)

    # Verify details of a specific seeded record
    bawarchi = next(r for r in hyderabad_res if r.name == "Bawarchi")
    assert bawarchi.location == "Hyderabad"
    assert bawarchi.metadata.get("area") == "Madhapur"
    assert bawarchi.cuisine == "Biryani, North Indian, Kebabs"
    assert bawarchi.rating == 4.5
