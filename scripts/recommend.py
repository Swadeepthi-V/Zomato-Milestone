"""CLI: filter + LLM recommendations (delegates to RecommendationService)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.app.main import cmd_recommend
import argparse
from src.config import TOP_K
from src.models.restaurant import BudgetTier


def main() -> int:
    parser = argparse.ArgumentParser(description="Get LLM-ranked restaurant recommendations")
    parser.add_argument("--location", "-l", required=True)
    parser.add_argument("--budget", "-b", required=True, choices=[t.value for t in BudgetTier])
    parser.add_argument("--cuisine", "-c", default="")
    parser.add_argument("--min-rating", "-r", type=float, default=None)
    parser.add_argument("--additional", default=None)
    parser.add_argument("--top-k", "-k", type=int, default=TOP_K)
    parser.add_argument("--mock", action="store_true", help="Use mock LLM (no Groq key)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--cache-path", type=Path, default=None)
    return cmd_recommend(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
