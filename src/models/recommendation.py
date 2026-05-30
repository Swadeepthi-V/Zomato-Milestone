"""Recommendation API models (architecture §5.3–5.4)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.models.restaurant import Restaurant


class RecommendationRestaurant(BaseModel):
    """Restaurant fields shown to the user (always sourced from the dataset)."""

    id: str
    name: str
    cuisine: str
    rating: float | None = None
    cost: str | None = None

    @classmethod
    def from_restaurant(cls, restaurant: Restaurant) -> RecommendationRestaurant:
        return cls(
            id=restaurant.id,
            name=restaurant.name,
            cuisine=restaurant.cuisine,
            rating=restaurant.rating,
            cost=restaurant.cost,
        )


class Recommendation(BaseModel):
    """Single ranked recommendation with LLM explanation."""

    rank: int
    restaurant: RecommendationRestaurant
    explanation: str


class ResponseMeta(BaseModel):
    """Metadata about the recommendation request."""

    candidate_count: int = 0
    model: str | None = None
    latency_ms: int | None = None
    hallucination_count: int = 0
    llm_called: bool = True
    parse_retries: int = 0


class RecommendationResponse(BaseModel):
    """Full response from the recommendation pipeline."""

    summary: str | None = None
    recommendations: list[Recommendation] = Field(default_factory=list)
    message: str | None = None
    meta: ResponseMeta = Field(default_factory=ResponseMeta)
