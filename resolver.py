from data_fetcher import DataFetcher
from typing import Optional


class MatchResolver:
    """
    Resolve predictions by fetching actual match results
    """

    def __init__(self):
        self.data_fetcher = DataFetcher()

    def get_match_result(self, match_id: str) -> Optional[str]:
        """
        Get actual match result

        Args:
            match_id: Match identifier (e.g., "EPL-ARS-CHE-2026-02-12")

        Returns:
            "HOME_WIN", "DRAW", or "AWAY_WIN"
            None if match not finished or not found
        """

        # Use data fetcher to get result
        result = self.data_fetcher.get_match_result(match_id)

        return result

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
