"""Parse and ground LLM responses (architecture §3.8)."""

from __future__ import annotations

import json
import re
from typing import Any

from src.logging_config import setup_logging
from src.models.recommendation import (
    Recommendation,
    RecommendationResponse,
    RecommendationRestaurant,
    ResponseMeta,
)
from src.models.restaurant import Restaurant

logger = setup_logging(__name__)

_FENCE_PATTERN = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
_EXPLANATION_FALLBACK = "Recommended based on your preferences."


class LLMResponseError(Exception):
    """Raised when LLM output cannot be parsed or grounded."""

    def __init__(self, message: str, *, raw: str | None = None) -> None:
        super().__init__(message)
        self.raw = raw


class ResponseParser:
    """Convert raw LLM text into grounded RecommendationResponse."""

    @staticmethod
    def parse(
        raw: str,
        candidates: list[Restaurant],
        *,
        model: str | None = None,
        latency_ms: int | None = None,
        parse_retries: int = 0,
    ) -> RecommendationResponse:
        data = extract_json(raw)
        return ResponseParser.parse_data(
            data,
            candidates,
            model=model,
            latency_ms=latency_ms,
            parse_retries=parse_retries,
        )

    @staticmethod
    def parse_data(
        data: dict[str, Any],
        candidates: list[Restaurant],
        *,
        model: str | None = None,
        latency_ms: int | None = None,
        parse_retries: int = 0,
    ) -> RecommendationResponse:
        candidate_map = {r.id: r for r in candidates}
        raw_items = data.get("recommendations")
        if not isinstance(raw_items, list):
            raise LLMResponseError("Missing or invalid 'recommendations' array")

        recommendations: list[Recommendation] = []
        hallucination_count = 0
        seen_ids: set[str] = set()

        for item in raw_items:
            if not isinstance(item, dict):
                continue
            restaurant_id = str(item.get("restaurant_id", "")).strip()
            if not restaurant_id or restaurant_id not in candidate_map:
                hallucination_count += 1
                logger.warning("Dropped hallucinated restaurant_id=%s", restaurant_id)
                continue
            if restaurant_id in seen_ids:
                logger.warning("Duplicate restaurant_id=%s in LLM output", restaurant_id)
                continue
            seen_ids.add(restaurant_id)

            restaurant = candidate_map[restaurant_id]
            rank = _coerce_rank(item.get("rank"), len(recommendations) + 1)
            explanation = str(item.get("explanation", "")).strip() or _EXPLANATION_FALLBACK

            recommendations.append(
                Recommendation(
                    rank=rank,
                    restaurant=RecommendationRestaurant.from_restaurant(restaurant),
                    explanation=explanation,
                )
            )

        if not recommendations and raw_items:
            raise LLMResponseError(
                "All restaurant_ids were invalid (hallucination guard)",
            )

        recommendations.sort(key=lambda r: r.rank)
        for index, rec in enumerate(recommendations, start=1):
            if rec.rank != index:
                recommendations[index - 1] = rec.model_copy(update={"rank": index})

        summary = data.get("summary")
        if summary is not None:
            summary = str(summary).strip() or None

        return RecommendationResponse(
            summary=summary,
            recommendations=recommendations,
            meta=ResponseMeta(
                candidate_count=len(candidates),
                model=model,
                latency_ms=latency_ms,
                hallucination_count=hallucination_count,
                llm_called=True,
                parse_retries=parse_retries,
            ),
        )


def extract_json(raw: str) -> dict[str, Any]:
    """Strip markdown fences and parse JSON object from LLM text."""
    text = raw.strip()
    if not text:
        raise LLMResponseError("Empty LLM response", raw=raw)

    match = _FENCE_PATTERN.search(text)
    if match:
        text = match.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMResponseError(f"Invalid JSON: {exc}", raw=raw) from exc

    if not isinstance(data, dict):
        raise LLMResponseError("JSON root must be an object", raw=raw)
    return data


def _coerce_rank(value: Any, default: int) -> int:
    try:
        rank = int(value)
        return rank if rank > 0 else default
    except (TypeError, ValueError):
        return default
