"""Application state: loaded store and recommendation service."""

from __future__ import annotations

from dataclasses import dataclass

from src.services.recommendation_service import RecommendationService
from src.store.restaurant_store import RestaurantStore


@dataclass
class AppState:
    store: RestaurantStore | None
    service: RecommendationService | None

    @property
    def is_ready(self) -> bool:
        return self.store is not None and self.store.record_count > 0
