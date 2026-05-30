"""Canonical restaurant data model (architecture §5.1)."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class BudgetTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Restaurant(BaseModel):
    """Normalized restaurant record used by the store and filter."""

    id: str
    name: str
    location: str
    cuisine: str
    cost: str | None = None
    budget_tier: BudgetTier
    rating: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}
