"""End-to-end recommendation orchestration (architecture §3.4, Phase 4)."""

from __future__ import annotations

import time

from src.config import TOP_K
from src.filters.preference_filter import PreferenceFilter
from src.llm.client import LLMClient, create_llm_client, mock_response_for_candidates
from src.llm.engine import RecommendationEngine
from src.llm.response_parser import LLMResponseError
from src.logging_config import setup_logging
from src.models.preferences import UserPreferences
from src.models.recommendation import RecommendationResponse, ResponseMeta
from src.store.restaurant_store import RestaurantStore

logger = setup_logging(__name__)

_EMPTY_MESSAGE = (
    "No restaurants match your filters. "
    "Try broadening location, budget, or cuisine."
)


class RecommendationService:
    """Filter → LLM rank/explain → grounded response."""

    def __init__(
        self,
        store: RestaurantStore,
        *,
        llm_client: LLMClient | None = None,
        engine: RecommendationEngine | None = None,
        use_mock_llm: bool = False,
    ) -> None:
        self.store = store
        self._use_mock_llm = use_mock_llm
        self._llm_client = llm_client
        self._engine = engine

    def _engine_for(self, candidates: list, top_k: int) -> RecommendationEngine:
        if self._engine is not None:
            return self._engine
        if self._use_mock_llm:
            mock_json = mock_response_for_candidates(candidates, top_k)
            from src.llm.client import MockLLMClient

            return RecommendationEngine(MockLLMClient([mock_json]))
        client = self._llm_client or create_llm_client()
        return RecommendationEngine(client)

    def recommend(
        self,
        preferences: UserPreferences,
        *,
        top_k: int | None = None,
    ) -> RecommendationResponse:
        """
        Run the full pipeline: filter candidates, then LLM rank and explain.

        Skips the LLM when there are zero candidates.
        """
        k = top_k if top_k is not None else TOP_K
        start = time.perf_counter()

        candidates = PreferenceFilter.apply(self.store, preferences)
        candidate_count = len(candidates)

        if not candidates:
            logger.info(
                "No candidates for location=%s budget=%s cuisine=%s",
                preferences.location,
                preferences.budget.value,
                preferences.cuisine or "any",
            )
            return RecommendationResponse(
                message=_EMPTY_MESSAGE,
                meta=ResponseMeta(candidate_count=0, llm_called=False),
            )

        try:
            engine = self._engine_for(candidates, k)
            response = engine.rank_and_explain(preferences, candidates, top_k=k)
        except LLMResponseError:
            raise
        except Exception as exc:
            logger.exception("Recommendation pipeline failed")
            raise

        total_ms = int((time.perf_counter() - start) * 1000)
        updated_meta = response.meta.model_copy(
            update={
                "candidate_count": candidate_count,
                "latency_ms": total_ms,
            }
        )
        logger.info(
            "Recommendation complete | candidates=%d returned=%d model=%s latency_ms=%d",
            candidate_count,
            len(response.recommendations),
            updated_meta.model,
            total_ms,
        )
        return response.model_copy(update={"meta": updated_meta})

    @classmethod
    def with_mock_llm_for_candidates(
        cls,
        store: RestaurantStore,
        preferences: UserPreferences,
        candidates_count_hint: int,
        *,
        top_k: int | None = None,
    ) -> RecommendationService:
        """Build service with mock LLM (used in API integration tests)."""
        from src.filters.preference_filter import PreferenceFilter

        candidates = PreferenceFilter.apply(store, preferences)
        k = top_k or TOP_K
        mock_json = mock_response_for_candidates(candidates, k)
        from src.llm.client import MockLLMClient

        client = MockLLMClient([mock_json])
        return cls(store, llm_client=client)
