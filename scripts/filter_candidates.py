"""CLI: filter restaurants by preferences without calling the LLM (Phase 2.8)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DATA_CACHE_PATH
from src.filters.preference_filter import PreferenceFilter
from src.logging_config import setup_logging
from src.models.preferences import UserPreferences
from src.models.restaurant import BudgetTier
from src.store.restaurant_store import RestaurantStore

logger = setup_logging("filter_candidates")


def _format_table(rows: list, headers: list[str]) -> str:
    if not rows:
        return "No matching restaurants."
    widths = [len(h) for h in headers]
    str_rows = []
    for row in rows:
        cells = [str(c) for c in row]
        str_rows.append(cells)
        for i, cell in enumerate(cells):
            widths[i] = max(widths[i], len(cell))
    fmt = "  ".join(f"{{:{w}}}" for w in widths)
    lines = [fmt.format(*headers), fmt.format(*["-" * w for w in widths])]
    lines.extend(fmt.format(*r) for r in str_rows)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Filter restaurants by preferences (no LLM)"
    )
    parser.add_argument("--location", "-l", required=True, help="City e.g. Bangalore")
    parser.add_argument(
        "--budget",
        "-b",
        required=True,
        choices=[t.value for t in BudgetTier],
        help="Budget tier",
    )
    parser.add_argument(
        "--cuisine",
        "-c",
        default="",
        help="Cuisine substring (empty or 'any' = no cuisine filter)",
    )
    parser.add_argument("--min-rating", "-r", type=float, default=None)
    parser.add_argument(
        "--additional",
        default=None,
        help="Additional preferences (shown only; not used in filter)",
    )
    parser.add_argument(
        "--cache-path",
        type=Path,
        default=None,
        help=f"Parquet cache (default: {DATA_CACHE_PATH})",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=None,
        help="Override MAX_CANDIDATES cap",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON array")
    args = parser.parse_args()

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

    candidates = PreferenceFilter.apply(
        store,
        preferences,
        max_candidates=args.max_candidates,
    )

    if args.json:
        payload = [
            {
                "id": r.id,
                "name": r.name,
                "location": r.location,
                "cuisine": r.cuisine,
                "rating": r.rating,
                "cost": r.cost,
                "budget_tier": r.budget_tier.value,
            }
            for r in candidates
        ]
        print(json.dumps(payload, indent=2))
    else:
        print(f"\nPreferences: {preferences.model_dump()}")
        print(f"Candidates: {len(candidates)} (cap may apply)\n")
        table_rows = [
            (
                r.name[:28],
                r.cuisine[:24],
                f"{r.rating:.1f}" if r.rating is not None else "N/A",
                r.budget_tier.value,
                r.cost or "-",
            )
            for r in candidates
        ]
        print(
            _format_table(
                table_rows,
                ["Name", "Cuisine", "Rating", "Budget", "Cost"],
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
