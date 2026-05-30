"""Normalize raw Hugging Face rows into canonical Restaurant records.

Hugging Face column → canonical field mapping
---------------------------------------------
name                          → name
cuisines                      → cuisine
approx_cost(for two people)   → cost (raw string) + budget_tier (derived)
rate                          → rating (parsed float; NEW/None → None)
url                           → id (stable hash prefix) when present
address + location            → location (normalized city for filtering)
rest_type, votes, phone, ...  → metadata

City extraction: primary city is inferred from `address` (Bangalore variants
normalized). Falls back to `location` when address parsing yields nothing usable.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from src.models.restaurant import BudgetTier, Restaurant

# Budget thresholds (approx cost for two, INR)
_BUDGET_LOW_MAX = 400
_BUDGET_MEDIUM_MAX = 800

_CITY_ALIASES: dict[str, str] = {
    "bangalore": "Bangalore",
    "bengaluru": "Bangalore",
    "banglore": "Bangalore",
    "bengalore": "Bangalore",
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "mumbai": "Mumbai",
    "bombay": "Mumbai",
    "chennai": "Chennai",
    "madras": "Chennai",
    "hyderabad": "Hyderabad",
    "kolkata": "Kolkata",
    "calcutta": "Kolkata",
    "pune": "Pune",
}

_RATE_PATTERN = re.compile(r"([\d.]+)\s*/\s*5", re.IGNORECASE)
_COST_NUMERIC = re.compile(r"[\d,]+")


@dataclass
class NormalizationResult:
    """Outcome of normalizing a batch of raw records."""

    restaurants: list[Restaurant] = field(default_factory=list)
    skipped_count: int = 0
    skip_reasons: dict[str, int] = field(default_factory=dict)


def normalize_records(
    raw_records: list[dict[str, Any]],
    seed_hyderabad: bool = False,
) -> NormalizationResult:
    """Convert raw HF rows to Restaurant instances; skip invalid rows."""
    records_to_process = list(raw_records)
    if seed_hyderabad:
        records_to_process.extend(_get_synthetic_hyderabad_records())

    result = NormalizationResult()
    seen_ids: dict[str, int] = {}

    for index, row in enumerate(records_to_process):
        restaurant, skip_reason = _normalize_row(row, index)
        if skip_reason:
            result.skipped_count += 1
            result.skip_reasons[skip_reason] = result.skip_reasons.get(skip_reason, 0) + 1
            continue
        assert restaurant is not None

        if restaurant.id in seen_ids:
            seen_ids[restaurant.id] += 1
            restaurant = restaurant.model_copy(
                update={"id": f"{restaurant.id}_{seen_ids[restaurant.id]}"}
            )
        else:
            seen_ids[restaurant.id] = 1

        result.restaurants.append(restaurant)

    return result


def _normalize_row(
    row: dict[str, Any], index: int
) -> tuple[Restaurant | None, str | None]:
    name = _clean_str(row.get("name"))
    if not name:
        return None, "missing_name"

    location = _extract_city(row.get("address"), row.get("location"))
    if not location:
        return None, "missing_location"

    cuisine = _clean_str(row.get("cuisines")) or "Unknown"
    cost_raw = _clean_str(row.get("approx_cost(for two people)"))
    budget_tier = _derive_budget_tier(cost_raw)
    rating = _parse_rating(row.get("rate"))
    restaurant_id = _stable_id(row, name, index)

    metadata = {
        k: v
        for k, v in row.items()
        if k
        not in {
            "name",
            "cuisines",
            "approx_cost(for two people)",
            "rate",
            "address",
            "location",
            "url",
        }
        and v is not None
    }
    if row.get("address"):
        metadata["address"] = _clean_str(row.get("address"))
    if row.get("location"):
        metadata["area"] = _clean_str(row.get("location"))

    return (
        Restaurant(
            id=restaurant_id,
            name=name,
            location=location,
            cuisine=cuisine,
            cost=cost_raw,
            budget_tier=budget_tier,
            rating=rating,
            metadata=metadata,
        ),
        None,
    )


def _clean_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _extract_city(address: Any, location: Any) -> str:
    """Infer filterable city from address; normalize aliases."""
    addr = _clean_str(address) or ""
    if addr:
        lower = addr.lower()
        for key, city in _CITY_ALIASES.items():
            if key in lower:
                return city
        parts = [p.strip() for p in addr.split(",") if p.strip()]
        if parts:
            last = parts[-1].rstrip(".")
            normalized = _CITY_ALIASES.get(last.lower())
            if normalized:
                return normalized
            if len(last) <= 30 and not any(c.isdigit() for c in last):
                return last.title()

    loc = _clean_str(location)
    if loc:
        return _CITY_ALIASES.get(loc.lower(), loc)

    return ""


def _parse_rating(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() == "NEW":
        return None
    match = _RATE_PATTERN.search(text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_cost_numeric(cost: str | None) -> int | None:
    if not cost:
        return None
    match = _COST_NUMERIC.search(cost.replace(",", ""))
    if not match:
        return None
    try:
        return int(match.group().replace(",", ""))
    except ValueError:
        return None


def _derive_budget_tier(cost: str | None) -> BudgetTier:
    amount = _parse_cost_numeric(cost)
    if amount is None:
        return BudgetTier.MEDIUM
    if amount <= _BUDGET_LOW_MAX:
        return BudgetTier.LOW
    if amount <= _BUDGET_MEDIUM_MAX:
        return BudgetTier.MEDIUM
    return BudgetTier.HIGH


def _stable_id(row: dict[str, Any], name: str, index: int) -> str:
    url = _clean_str(row.get("url"))
    if url:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
        return f"r_{digest}"
    seed = f"{name}|{row.get('address', '')}|{index}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"r_{digest}"


def _get_synthetic_hyderabad_records() -> list[dict[str, Any]]:
    return [
        {
            "name": "Bawarchi",
            "address": "RTC Cross Roads, Chikkadpally, Hyderabad",
            "location": "Madhapur",
            "cuisines": "Biryani, North Indian, Kebabs",
            "approx_cost(for two people)": "600",
            "rate": "4.5/5",
            "url": "https://www.zomato.com/hyderabad/bawarchi-madhapur"
        },
        {
            "name": "Pista House",
            "address": "Bachupally Road, Hyderabad",
            "location": "Bachupally",
            "cuisines": "Biryani, Fast Food, Haleem",
            "approx_cost(for two people)": "350",
            "rate": "4.2/5",
            "url": "https://www.zomato.com/hyderabad/pista-house-bachupally"
        },
        {
            "name": "Paradise Biryani",
            "address": "Miyapur Main Road, Hyderabad",
            "location": "Miyapur",
            "cuisines": "Biryani, Kebabs, Mughlai",
            "approx_cost(for two people)": "700",
            "rate": "4.0/5",
            "url": "https://www.zomato.com/hyderabad/paradise-miyapur"
        },
        {
            "name": "Kritunga Restaurant",
            "address": "Suchitra Junction, Hyderabad",
            "location": "Suchitra",
            "cuisines": "Rayalaseema, South Indian, Andhra",
            "approx_cost(for two people)": "550",
            "rate": "4.1/5",
            "url": "https://www.zomato.com/hyderabad/kritunga-suchitra"
        },
        {
            "name": "Chutneys",
            "address": "Madhapur High Road, Hyderabad",
            "location": "Madhapur",
            "cuisines": "South Indian, Vegetarian",
            "approx_cost(for two people)": "400",
            "rate": "4.3/5",
            "url": "https://www.zomato.com/hyderabad/chutneys-madhapur"
        },
        {
            "name": "Mehfil",
            "address": "Miyapur X Roads, Hyderabad",
            "location": "Miyapur",
            "cuisines": "Biryani, North Indian, Tandoori",
            "approx_cost(for two people)": "300",
            "rate": "4.2/5",
            "url": "https://www.zomato.com/hyderabad/mehfil-miyapur"
        },
        {
            "name": "Platform 65",
            "address": "Suchitra Road, Hyderabad",
            "location": "Suchitra",
            "cuisines": "Multi-cuisine, Chinese, North Indian",
            "approx_cost(for two people)": "800",
            "rate": "4.3/5",
            "url": "https://www.zomato.com/hyderabad/platform65-suchitra"
        },
        {
            "name": "Exotica",
            "address": "Hitech City, Madhapur, Hyderabad",
            "location": "Madhapur",
            "cuisines": "Mughlai, North Indian, Chinese",
            "approx_cost(for two people)": "1500",
            "rate": "4.6/5",
            "url": "https://www.zomato.com/hyderabad/exotica-madhapur"
        },
        {
            "name": "The Joint Al-Mandi",
            "address": "Miyapur Road, Bachupally, Hyderabad",
            "location": "Bachupally",
            "cuisines": "Arabian, Mandi",
            "approx_cost(for two people)": "600",
            "rate": "4.1/5",
            "url": "https://www.zomato.com/hyderabad/the-joint-mandi-bachupally"
        },
        {
            "name": "Shah Ghouse",
            "address": "Hitech City Road, Madhapur, Hyderabad",
            "location": "Madhapur",
            "cuisines": "Biryani, North Indian, Mughlai",
            "approx_cost(for two people)": "500",
            "rate": "4.4/5",
            "url": "https://www.zomato.com/hyderabad/shah-ghouse-madhapur"
        },
        {
            "name": "Pind Balluchi",
            "address": "Suchitra Circle, Hyderabad",
            "location": "Suchitra",
            "cuisines": "North Indian, Punjabi",
            "approx_cost(for two people)": "750",
            "rate": "3.9/5",
            "url": "https://www.zomato.com/hyderabad/pind-balluchi-suchitra"
        },
        {
            "name": "Burger King",
            "address": "Bachupally Main Road, Hyderabad",
            "location": "Bachupally",
            "cuisines": "Burgers, Fast Food",
            "approx_cost(for two people)": "250",
            "rate": "3.8/5",
            "url": "https://www.zomato.com/hyderabad/burger-king-bachupally"
        }
    ]
