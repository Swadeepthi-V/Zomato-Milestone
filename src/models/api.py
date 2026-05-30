"""HTTP API request/response schemas (architecture §7)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.models.preferences import UserPreferences
from src.models.restaurant import BudgetTier


class RecommendRequest(BaseModel):
    """POST /recommend body."""

    location: str = Field(..., min_length=1)
    budget: BudgetTier
    cuisine: str = ""
    min_rating: float | None = Field(default=None, ge=0.0, le=5.0)
    additional_preferences: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)

    def to_preferences(self) -> UserPreferences:
        return UserPreferences(
            location=self.location.strip(),
            budget=self.budget,
            cuisine=self.cuisine.strip() if self.cuisine else "",
            min_rating=self.min_rating,
            additional_preferences=(
                self.additional_preferences.strip()
                if self.additional_preferences
                else None
            ),
        )


class HealthResponse(BaseModel):
    status: str
    dataset_loaded: bool
    record_count: int = 0
    ingested_at: str | None = None
