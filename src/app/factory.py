"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.app.routes import router
from src.app.state import AppState
from src.config import DATA_CACHE_PATH
from src.logging_config import setup_logging
from src.services.recommendation_service import RecommendationService
from src.store.restaurant_store import RestaurantStore

logger = setup_logging(__name__)


def load_app_state(
    *,
    cache_path=None,
    use_mock_llm: bool = False,
) -> AppState:
    path = cache_path or DATA_CACHE_PATH
    try:
        store = RestaurantStore.load(path)
        service = RecommendationService(store, use_mock_llm=use_mock_llm)
        logger.info("Loaded %d restaurants from cache", store.record_count)
        return AppState(store=store, service=service)
    except FileNotFoundError:
        logger.error("Cache not found at %s", path)
        return AppState(store=None, service=None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.app_state = load_app_state()
    yield


def create_app(
    *,
    app_state: AppState | None = None,
) -> FastAPI:
    """Create FastAPI app; inject app_state in tests."""
    application = FastAPI(
        title="Zomato AI Restaurant Recommendations",
        description="Grounded restaurant recommendations powered by Groq",
        version="0.1.0",
        lifespan=lifespan if app_state is None else None,
    )

    if app_state is not None:
        application.state.app_state = app_state

    # Enable CORS
    from fastapi.middleware.cors import CORSMiddleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Serve static assets
    import os
    from fastapi.staticfiles import StaticFiles
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    os.makedirs(static_dir, exist_ok=True)
    application.mount("/static", StaticFiles(directory=static_dir), name="static")

    application.include_router(router)
    return application


# Uvicorn entry: uvicorn src.app.factory:app --reload
app = create_app()
