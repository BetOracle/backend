from data_fetcher import DataFetcher
from ai_resolver import AIResolver
from typing import Optional


class MatchResolver:
    """
    Resolve predictions by fetching actual match results using AI
    """

    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.ai_resolver = AIResolver()

    def get_match_result(self, match_id: str) -> Optional[str]:
        """
        Get actual match result using AI

        Args:
            match_id: Match identifier (e.g., "EPL-ARS-CHE-2026-02-12")

        Returns:
            "HOME_WIN", "DRAW", or "AWAY_WIN"
            None if match not finished or not found
        """

        # Try AI resolution first (for current/future matches)
        try:
            result = self.ai_resolver.get_match_result(match_id)
            if result:
                return result
        except Exception as e:
            print(f"AI resolution failed: {e}")

        # Fallback to data fetcher for historical matches
        try:
            result = self.data_fetcher.get_match_result(match_id)
            return result
        except Exception as e:
            print(f"Data fetcher resolution failed: {e}")
            return None

    def has_matches_today(self) -> bool:
        """Check if any leagues have matches scheduled today"""
        return self.ai_resolver.any_league_has_matches_today()

    def get_match_schedule(self, days_ahead: int = 7) -> dict:
        """Get upcoming match schedule"""
        return self.ai_resolver.get_match_schedule(days_ahead)

    def parse_match_id(self, match_id: str) -> dict:
        """
        Parse match ID into components

        Args:
            match_id: e.g., "EPL-ARS-CHE-2026-02-12"

        Returns:
            {
                "league": "EPL",
                "homeTeam": "ARS",
                "awayTeam": "CHE",
                "date": "2026-02-12"
            }
        """

        try:
            parts = match_id.split("-")

            return {
                "league": parts[0],
                "homeTeam": parts[1],
                "awayTeam": parts[2],
                "date": "-".join(parts[3:]),
            }
        except Exception as e:
            print(f"Error parsing match ID: {e}")
            return {}
