"""Recommendation engine: prompt → LLM → parse with retries (Phase 3.7)."""

from __future__ import annotations

import time

from src.config import LLM_MAX_RETRIES, TOP_K
from src.llm.client import LLMClient, LLMConfig, LLMError, default_llm_config
from src.llm.prompt_builder import PromptBuilder
from src.llm.response_parser import LLMResponseError, ResponseParser
from src.logging_config import setup_logging
from src.models.preferences import UserPreferences
from src.models.recommendation import RecommendationResponse, ResponseMeta
from src.models.restaurant import Restaurant

logger = setup_logging(__name__)


class RecommendationEngine:
    """Invoke LLM to rank and explain; parse and ground results."""

    def __init__(
        self,
        client: LLMClient,
        config: LLMConfig | None = None,
        *,
        max_llm_retries: int | None = None,
    ) -> None:
        self.client = client
        self.config = config or default_llm_config()
        self.max_llm_retries = max_llm_retries if max_llm_retries is not None else LLM_MAX_RETRIES

    def rank_and_explain(
        self,
        preferences: UserPreferences,
        candidates: list[Restaurant],
        top_k: int | None = None,
    ) -> RecommendationResponse:
        k = top_k if top_k is not None else TOP_K
        if not candidates:
            return RecommendationResponse(
                message="No candidates to rank.",
                meta=ResponseMeta(candidate_count=0, llm_called=False),
            )

        prompt = PromptBuilder.build(preferences, candidates, k)
        start = time.perf_counter()
        raw = self._complete_with_retry(prompt)
        latency_ms = int((time.perf_counter() - start) * 1000)

        parse_retries = 0
        try:
            return ResponseParser.parse(
                raw,
                candidates,
                model=self.config.model,
                latency_ms=latency_ms,
                parse_retries=parse_retries,
            )
        except LLMResponseError as first_error:
            logger.warning("Parse failed, attempting repair: %s", first_error)
            parse_retries = 1
            repair_prompt = PromptBuilder.build_repair_prompt(raw)
            repair_raw = self._complete_with_retry(repair_prompt)
            try:
                return ResponseParser.parse(
                    repair_raw,
                    candidates,
                    model=self.config.model,
                    latency_ms=latency_ms,
                    parse_retries=parse_retries,
                )
            except LLMResponseError as second_error:
                raise LLMResponseError(
                    f"Failed to parse LLM response after repair: {second_error}",
                    raw=repair_raw,
                ) from second_error

    def _complete_with_retry(self, prompt: str) -> str:
        last_error: LLMError | None = None
        attempts = max(1, self.max_llm_retries)

        for attempt in range(1, attempts + 1):
            try:
                return self.client.complete(prompt, self.config)
            except LLMError as exc:
                last_error = exc
                if not exc.retryable or attempt >= attempts:
                    raise
                logger.warning("LLM attempt %d failed (retryable): %s", attempt, exc)

        if last_error:
            raise last_error
        raise LLMError("LLM completion failed")
