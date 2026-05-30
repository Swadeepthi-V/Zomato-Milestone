"""Deterministic preference filter (architecture §3.5)."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from src.config import MAX_CANDIDATES
from src.logging_config import setup_logging
from src.models.preferences import UserPreferences
from src.models.restaurant import BudgetTier, Restaurant

if TYPE_CHECKING:
    from src.store.restaurant_store import RestaurantStore

logger = setup_logging(__name__)

# Normalize user location input (aligns with ingestion city aliases)
_LOCATION_ALIASES: dict[str, str] = {
    "bangalore": "Bangalore",
    "bengaluru": "Bangalore",
    "banglore": "Bangalore",
    "bengalore": "Bangalore",
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "mumbai": "Mumbai",
    "bombay": "Mumbai",
    "chennai": "Chennai",
    "hyderabad": "Hyderabad",
    "kolkata": "Kolkata",
    "pune": "Pune",
}

_CUISINE_ANY = frozenset({"", "any", "all", "*"})


class PreferenceFilter:
    """Apply AND filters to narrow the restaurant store before LLM ranking."""

    def __init__(self, max_candidates: int | None = None) -> None:
        self.max_candidates = max_candidates if max_candidates is not None else MAX_CANDIDATES

    @classmethod
    def apply(
        cls,
        store: RestaurantStore,
        preferences: UserPreferences,
        *,
        max_candidates: int | None = None,
    ) -> list[Restaurant]:
        """Filter store by preferences, sort by rating desc, cap to max_candidates."""
        filt = cls(max_candidates=max_candidates)
        return filt.filter(store, preferences)

    def filter(
        self,
        store: RestaurantStore,
        preferences: UserPreferences,
    ) -> list[Restaurant]:
        start = time.perf_counter()
        user_location = _normalize_location(preferences.location).lower()

        matched: list[Restaurant] = []
        city_lowers = getattr(store, "_city_lowers", None)
        area_lowers = getattr(store, "_area_lowers", None)
        cuisine_lowers = getattr(store, "_cuisine_lowers", None)

        user_cuisine = preferences.cuisine.strip().lower() if preferences.cuisine else ""
        skip_cuisine = not user_cuisine or user_cuisine in _CUISINE_ANY
        min_rating = preferences.min_rating

        for restaurant in store.get_all():
            rid = restaurant.id

            # 1. Location match
            if city_lowers is not None and area_lowers is not None:
                city_lower = city_lowers.get(rid, "")
                area_lower = area_lowers.get(rid, "")
                
                city_match = city_lower == user_location or (len(user_location) >= 3 and user_location in city_lower) or (len(city_lower) >= 3 and city_lower in user_location)
                if not city_match:
                    area_match = area_lower and (area_lower == user_location or (len(user_location) >= 3 and user_location in area_lower) or (len(area_lower) >= 3 and area_lower in user_location))
                    if not area_match:
                        continue
            else:
                if not _matches_location(restaurant, user_location):
                    continue

            # 2. Budget match
            if restaurant.budget_tier != preferences.budget:
                continue

            # 3. Cuisine match
            if not skip_cuisine:
                if cuisine_lowers is not None:
                    if user_cuisine not in cuisine_lowers.get(rid, ""):
                        continue
                else:
                    if not _matches_cuisine(restaurant.cuisine, user_cuisine):
                        continue

            # 4. Rating match
            if min_rating is not None:
                if restaurant.rating is None or restaurant.rating < min_rating:
                    continue

            matched.append(restaurant)

        capped = _cap_by_rating(matched, self.max_candidates)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Filter applied | location=%s budget=%s cuisine=%s min_rating=%s "
            "| matched=%d returned=%d elapsed_ms=%.1f",
            user_location,
            preferences.budget.value,
            preferences.cuisine or "any",
            preferences.min_rating,
            len(matched),
            len(capped),
            elapsed_ms,
        )
        return capped


def _normalize_location(location: str) -> str:
    key = location.strip().lower()
    return _LOCATION_ALIASES.get(key, location.strip())


def _matches_location(restaurant: Restaurant, user_location: str) -> bool:
    """Case-insensitive exact or substring match for city and area."""
    b = user_location.lower()
    
    city_lower = restaurant.location.lower()
    if city_lower == b or (len(b) >= 3 and b in city_lower) or (len(city_lower) >= 3 and city_lower in b):
        return True
        
    area = restaurant.metadata.get("area")
    if area:
        area_lower = area.lower()
        if area_lower == b or (len(b) >= 3 and b in area_lower) or (len(area_lower) >= 3 and area_lower in b):
            return True
            
    return False


def _matches_cuisine(restaurant_cuisine: str, user_cuisine: str) -> bool:
    """Substring match on multi-value cuisine; 'any' skips filter."""
    if not user_cuisine or user_cuisine.lower() in _CUISINE_ANY:
        return True
    return user_cuisine.lower() in restaurant_cuisine.lower()


def _matches_rating(rating: float | None, min_rating: float | None) -> bool:
    if min_rating is None:
        return True
    if rating is None:
        return False
    return rating >= min_rating


def _cap_by_rating(restaurants: list[Restaurant], max_candidates: int) -> list[Restaurant]:
    """Sort by rating descending; unknown ratings last; limit to max_candidates."""
    sorted_list = sorted(
        restaurants,
        key=lambda r: (r.rating is None, -(r.rating if r.rating is not None else 0.0)),
    )
    return sorted_list[:max_candidates]
