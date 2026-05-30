"""Build structured prompts for LLM ranking (architecture §3.6)."""

from __future__ import annotations

import json

from src.models.preferences import UserPreferences
from src.models.restaurant import Restaurant


class PromptBuilder:
    """Construct prompts with candidate list and output schema."""

    @staticmethod
    def build(
        preferences: UserPreferences,
        candidates: list[Restaurant],
        top_k: int,
    ) -> str:
        candidate_json = json.dumps(
            [_candidate_for_prompt(r) for r in candidates],
            indent=2,
        )
        additional = preferences.additional_preferences or "None"
        min_rating = (
            str(preferences.min_rating) if preferences.min_rating is not None else "None"
        )

        return f"""[System]
You are a restaurant recommendation assistant. You may ONLY recommend restaurants from the CANDIDATE_LIST below. Do not invent restaurants or restaurant_id values.
Return valid JSON only, matching the output schema exactly. No markdown fences or extra text.

[User preferences]
- Location: {preferences.location}
- Budget: {preferences.budget.value}
- Cuisine: {preferences.cuisine or "any"}
- Minimum rating: {min_rating}
- Additional: {additional}

[CANDIDATE_LIST]
{candidate_json}

[Task]
1. Rank the top {top_k} restaurants from CANDIDATE_LIST for these preferences.
2. For each, write a 1-2 sentence explanation referencing specific user preferences.
3. Optionally provide a brief summary of the overall selection.

[Output schema]
{{
  "summary": "string (optional)",
  "recommendations": [
    {{
      "restaurant_id": "string (must match an id from CANDIDATE_LIST)",
      "rank": 1,
      "explanation": "string"
    }}
  ]
}}"""

    @staticmethod
    def build_repair_prompt(invalid_response: str) -> str:
        """Ask the model to fix invalid JSON from a prior attempt."""
        truncated = invalid_response[:2000]
        return f"""The previous response was not valid JSON. Fix it and return ONLY valid JSON matching this schema:

{{
  "summary": "string (optional)",
  "recommendations": [
    {{
      "restaurant_id": "string",
      "rank": 1,
      "explanation": "string"
    }}
  ]
}}

Invalid response:
{truncated}
"""


def _candidate_for_prompt(restaurant: Restaurant) -> dict:
    """Compact candidate payload for the prompt (includes restaurant_id)."""
    return {
        "restaurant_id": restaurant.id,
        "name": restaurant.name,
        "location": restaurant.location,
        "cuisine": restaurant.cuisine,
        "rating": restaurant.rating,
        "cost": restaurant.cost,
        "budget_tier": restaurant.budget_tier.value,
    }
