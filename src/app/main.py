"""CLI and API server entry point (Phase 4.10)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.config import DATA_CACHE_PATH, TOP_K
from src.logging_config import setup_logging
from src.models.preferences import UserPreferences
from src.models.restaurant import BudgetTier
from src.services.recommendation_service import RecommendationService
from src.store.restaurant_store import RestaurantStore

logger = setup_logging("main")


def _print_response(response, as_json: bool) -> None:
    if as_json:
        print(response.model_dump_json(indent=2))
        return
    if response.message and not response.recommendations:
        print(response.message)
        return
    if response.summary:
        print(f"\nSummary: {response.summary}\n")
    for rec in response.recommendations:
        r = rec.restaurant
        rating = f"{r.rating:.1f}" if r.rating is not None else "N/A"
        print(f"#{rec.rank} {r.name} ({r.cuisine}) — {rating} — {r.cost or '-'}")
        print(f"   {rec.explanation}\n")
    meta = response.meta
    print(
        f"meta: candidates={meta.candidate_count} "
        f"model={meta.model} latency_ms={meta.latency_ms} "
        f"hallucinations_dropped={meta.hallucination_count}"
    )


def cmd_recommend(args: argparse.Namespace) -> int:
    try:
        store = RestaurantStore.load(args.cache_path or DATA_CACHE_PATH)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        logger.error("Run: python -m scripts.ingest")
        return 1

    preferences = UserPreferences(
        location=args.location,
        budget=BudgetTier(args.budget),
        cuisine=args.cuisine,
        min_rating=args.min_rating,
        additional_preferences=args.additional,
    )

    service = RecommendationService(store, use_mock_llm=args.mock)

    try:
        response = service.recommend(preferences, top_k=args.top_k)
    except Exception as exc:
        logger.exception("Recommendation failed: %s", exc)
        return 1

    _print_response(response, args.json)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run(
        "src.app.factory:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Zomato recommendation service")
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("recommend", help="Get recommendations via CLI")
    rec.add_argument("--location", "-l", required=True)
    rec.add_argument(
        "--budget", "-b", required=True, choices=[t.value for t in BudgetTier]
    )
    rec.add_argument("--cuisine", "-c", default="")
    rec.add_argument("--min-rating", "-r", type=float, default=None)
    rec.add_argument("--additional", default=None)
    rec.add_argument("--top-k", "-k", type=int, default=TOP_K)
    rec.add_argument("--mock", action="store_true", help="Use mock LLM (no Groq key)")
    rec.add_argument("--json", action="store_true")
    rec.add_argument("--cache-path", type=Path, default=None)
    rec.set_defaults(func=cmd_recommend)

    srv = sub.add_parser("serve", help="Start FastAPI server")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8000)
    srv.add_argument("--reload", action="store_true")
    srv.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
