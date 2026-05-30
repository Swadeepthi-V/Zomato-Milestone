"""User preference model (architecture §5.2)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from src.models.restaurant import BudgetTier


class UserPreferences(BaseModel):
    """Structured preferences collected from the user or API."""

    location: str = Field(..., min_length=1, description="City or area to search in")
    budget: BudgetTier = Field(..., description="Budget tier: low, medium, or high")
    cuisine: str = Field(
        default="",
        description="Cuisine type; empty or 'any' skips cuisine filter",
    )
    min_rating: float | None = Field(
        default=None,
        ge=0.0,
        le=5.0,
        description="Minimum aggregate rating (0–5)",
    )
    additional_preferences: str | None = Field(
        default=None,
        description="Free-text extras for LLM only (not used in hard filter)",
    )

    model_config = {"frozen": True}

    @field_validator("location", "cuisine", "additional_preferences", mode="before")
    @classmethod
    def strip_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("location")
    @classmethod
    def location_not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("location must not be empty")
        return value
