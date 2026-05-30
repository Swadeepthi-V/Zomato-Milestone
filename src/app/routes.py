"""HTTP routes (architecture §7)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from src.llm.response_parser import LLMResponseError
from src.models.api import HealthResponse, RecommendRequest
from src.models.recommendation import RecommendationResponse

import os
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def read_index() -> HTMLResponse:
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    index_path = os.path.join(static_dir, "index.html")
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Frontend index.html not found. Make sure it is created in src/static.</h1>",
            status_code=404,
        )


def _get_state(request: Request):
    return request.app.state.app_state


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    state = _get_state(request)
    if not state.is_ready:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unavailable",
                "dataset_loaded": False,
                "message": "Restaurant data not loaded. Run: python -m scripts.ingest",
            },
        )
    store = state.store
    assert store is not None
    return HealthResponse(
        status="ok",
        dataset_loaded=True,
        record_count=store.record_count,
        ingested_at=store.ingested_at.isoformat(),
    )


@router.get("/locations", response_model=list[str])
def get_locations(request: Request) -> list[str]:
    state = _get_state(request)
    if not state.is_ready or state.store is None:
        raise HTTPException(
            status_code=503,
            detail="Service unavailable: dataset not loaded",
        )
    return state.store.unique_locations


@router.post("/recommend", response_model=RecommendationResponse)
def recommend(request: Request, body: RecommendRequest) -> RecommendationResponse:
    state = _get_state(request)
    if not state.is_ready or state.service is None:
        raise HTTPException(
            status_code=503,
            detail="Service unavailable: dataset not loaded",
        )

    preferences = body.to_preferences()
    try:
        return state.service.recommend(preferences, top_k=body.top_k)
    except LLMResponseError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "llm_parse_failed", "message": str(exc)},
        ) from exc
