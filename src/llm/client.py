"""LLM provider adapter — Groq for production (architecture §3.7, Phase 4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.config import GROQ_API_KEY, LLM_MAX_TOKENS, LLM_MODEL, LLM_TEMPERATURE, LLM_TIMEOUT
from src.logging_config import setup_logging

logger = setup_logging(__name__)


@dataclass(frozen=True)
class LLMConfig:
    """Provider configuration for a completion request."""

    model: str
    temperature: float = 0.2
    max_tokens: int = 2048
    timeout: float = 60.0


class LLMClient(Protocol):
    """Adapter interface for LLM providers."""

    def complete(self, prompt: str, config: LLMConfig | None = None) -> str:
        """Send prompt and return raw completion text."""
        ...


@dataclass
class LLMError(Exception):
    """Raised when the LLM provider fails."""

    message: str
    retryable: bool = False

    def __str__(self) -> str:
        return self.message


class GroqLLMClient:
    """Groq Chat Completions API client (production)."""

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or GROQ_API_KEY
        if not key:
            raise LLMError(
                "GROQ_API_KEY is not set. Add it to .env or use MockLLMClient for tests.",
                retryable=False,
            )
        self._api_key = key

    def complete(self, prompt: str, config: LLMConfig | None = None) -> str:
        cfg = config or default_llm_config()
        try:
            from groq import Groq
        except ImportError as exc:
            raise LLMError("groq package not installed", retryable=False) from exc

        client = Groq(api_key=self._api_key, timeout=cfg.timeout)
        logger.info("Calling Groq model=%s", cfg.model)
        try:
            response = client.chat.completions.create(
                model=cfg.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
            )
        except Exception as exc:
            retryable = _is_retryable_error(exc)
            raise LLMError(str(exc), retryable=retryable) from exc

        content = response.choices[0].message.content
        if not content:
            raise LLMError("Empty response from Groq", retryable=True)
        return content.strip()


class MockLLMClient:
    """Deterministic LLM for tests and local dev without API keys."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = list(responses) if responses else []
        self._default = _default_mock_response()
        self.calls: list[str] = []

    def complete(self, prompt: str, config: LLMConfig | None = None) -> str:
        self.calls.append(prompt)
        if self._responses:
            return self._responses.pop(0)
        return self._default


def default_llm_config() -> LLMConfig:
    return LLMConfig(
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
        timeout=LLM_TIMEOUT,
    )


def create_llm_client(
    *,
    use_mock: bool = False,
    mock_responses: list[str] | None = None,
) -> LLMClient:
    """Factory: MockLLMClient for tests; GroqLLMClient when GROQ_API_KEY is set."""
    if use_mock:
        return MockLLMClient(mock_responses)
    if GROQ_API_KEY:
        return GroqLLMClient()
    logger.warning("No GROQ_API_KEY; using MockLLMClient")
    return MockLLMClient(mock_responses)


def _is_retryable_error(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    if "timeout" in name or "connection" in name or "rate" in name:
        return True
    status = getattr(exc, "status_code", None)
    if status is not None and int(status) >= 500:
        return True
    if getattr(exc, "status_code", None) == 429:
        return True
    return False


def mock_response_for_candidates(
    candidates: list,
    top_k: int,
    *,
    summary: str = "Top picks matching your preferences.",
) -> str:
    """Build a valid mock JSON response using real candidate IDs."""
    import json

    from src.models.restaurant import Restaurant

    items = []
    for rank, restaurant in enumerate(candidates[:top_k], start=1):
        if isinstance(restaurant, Restaurant):
            rid = restaurant.id
            location = restaurant.location
            cuisine = restaurant.cuisine
        else:
            rid = restaurant["id"]
            location = restaurant.get("location", "")
            cuisine = restaurant.get("cuisine", "")
        items.append(
            {
                "restaurant_id": rid,
                "rank": rank,
                "explanation": (
                    f"Strong match for your preferences in {location} "
                    f"with {cuisine} cuisine."
                ),
            }
        )
    return json.dumps({"summary": summary, "recommendations": items}, indent=2)


def _default_mock_response() -> str:
    return mock_response_for_candidates(
        [
            {
                "id": "r_mock1",
                "location": "Bangalore",
                "cuisine": "Italian",
            }
        ],
        top_k=1,
    )
