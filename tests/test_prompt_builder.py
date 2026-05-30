"""Tests for prompt builder."""

from __future__ import annotations

import json

from src.llm.prompt_builder import PromptBuilder
from src.models.preferences import UserPreferences
from src.models.restaurant import BudgetTier, Restaurant


def test_build_includes_all_candidate_ids():
    candidates = [
        Restaurant(
            id="r_abc",
            name="Alpha",
            location="Bangalore",
            cuisine="Italian",
            budget_tier=BudgetTier.MEDIUM,
            rating=4.5,
        ),
        Restaurant(
            id="r_def",
            name="Beta",
            location="Bangalore",
            cuisine="Chinese",
            budget_tier=BudgetTier.LOW,
            rating=4.0,
        ),
    ]
    prefs = UserPreferences(
        location="Bangalore",
        budget=BudgetTier.MEDIUM,
        cuisine="Italian",
        min_rating=4.0,
        additional_preferences="family-friendly",
    )
    prompt = PromptBuilder.build(prefs, candidates, top_k=2)

    assert "r_abc" in prompt
    assert "r_def" in prompt
    assert "restaurant_id" in prompt
    assert "CANDIDATE_LIST" in prompt
    assert "family-friendly" in prompt
    assert "Do not invent" in prompt

    # Candidate list is valid JSON embedded in prompt
    marker = "[CANDIDATE_LIST]\n"
    list_start = prompt.index(marker) + len(marker)
    list_end = prompt.index("\n\n[Task]", list_start)
    candidates_json = json.loads(prompt[list_start:list_end])
    ids = {c["restaurant_id"] for c in candidates_json}
    assert ids == {"r_abc", "r_def"}
