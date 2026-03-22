"""
AI-based match resolution using Claude for real-time results
"""
import os
import re
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import anthropic
from data_fetcher import DataFetcher


class AIResolver:
    """
    Resolve predictions using AI to fetch real-time match results
    """

    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.leagues = ["EPL", "LaLiga", "SerieA", "Bundesliga", "Ligue1"]

    def has_matches_today(self, league: str) -> bool:
        """Check if there are matches scheduled for today in a league"""
        try:
            matches = self.data_fetcher.get_league_matches(league, days_ahead=0)
            return len(matches) > 0
        except Exception as e:
            print(f"Error checking matches for {league}: {e}")
            return False

    def any_league_has_matches_today(self) -> bool:
        """Check if any of the supported leagues have matches today"""
        for league in self.leagues:
            if self.has_matches_today(league):
                return True
        return False

    def get_match_schedule(self, days_ahead: int = 7) -> Dict[str, List[str]]:
        """Get upcoming match days for all leagues"""
        schedule = {}
        for league in self.leagues:
            try:
                matches = self.data_fetcher.get_league_matches(league, days_ahead)
                match_days = set()
                for match in matches:
                    match_days.add(match.get('date', ''))
                schedule[league] = sorted(match_days)
            except Exception as e:
                print(f"Error getting schedule for {league}: {e}")
                schedule[league] = []
        return schedule

    def parse_match_id(self, match_id: str) -> Dict[str, str]:
        """Parse match ID into components"""
        try:
            parts = match_id.split("-")

            # Format 0: League-FixtureID-HomeTeam-AwayTeam-Date (e.g., EPL-538093-TOT-NOT-2026-03-22)
            if len(parts) >= 5 and parts[1].isdigit() and parts[2].isalpha():
                return {
                    "league": parts[0],
                    "fixtureId": parts[1],
                    "homeTeam": parts[2],
                    "awayTeam": parts[3],
                    "date": "-".join(parts[4:]),
                    "format": "fixture_descriptive",
                }

            # Format 1: League-HomeTeam-AwayTeam-Date (e.g., EPL-BRI-LIV-2026-03-21)
            if len(parts) >= 4 and parts[1].isalpha():
                return {
                    "league": parts[0],
                    "homeTeam": parts[1],
                    "awayTeam": parts[2],
                    "date": "-".join(parts[3:]),
                    "format": "descriptive"
                }

            # Format 2: League-FixtureID (e.g., Ligue1-542641) - need to lookup teams
            elif len(parts) == 2 and parts[1].isdigit():
                return {
                    "league": parts[0],
                    "fixtureId": parts[1],
                    "format": "fixture"
                }

        except Exception as e:
            print(f"Error parsing match ID {match_id}: {e}")
        return {}

    def expand_team_names(self, team_code: str) -> str:
        """Expand team codes to full names"""
        team_mapping = {
            # EPL
            "ARS": "Arsenal", "CHE": "Chelsea", "MUN": "Manchester United", "MCI": "Manchester City",
            "LIV": "Liverpool", "BRI": "Brighton", "TOT": "Tottenham Hotspur", "WHU": "West Ham United",
            "NEW": "Newcastle United", "AVL": "Aston Villa", "EVE": "Everton",
            "WOL": "Wolverhampton Wanderers", "CRY": "Crystal Palace", "SOU": "Southampton",
            "FUL": "Fulham", "NOT": "Nottingham Forest", "SUN": "Sunderland",
            "BHA": "Brighton", "BRH": "Brighton", "AST": "Aston Villa", "WES": "West Ham United",
            # La Liga
            "BAR": "Barcelona", "REA": "Real Madrid", "RMA": "Real Madrid",
            "ATM": "Atletico Madrid", "ATH": "Athletic Bilbao",
            "VAL": "Valencia", "SEV": "Sevilla", "BET": "Real Betis",
            "SOC": "Real Sociedad", "CEL": "Celta Vigo", "DEP": "Deportivo Alaves",
            "CLU": "Real Valladolid", "RAY": "Rayo Vallecano", "OSA": "Osasuna",
            "VIL": "Villarreal", "GIR": "Girona", "GET": "Getafe", "MAL": "RCD Mallorca",
            "ESP": "Espanyol", "LEG": "Leganes",
            # Serie A
            "JUV": "Juventus", "INT": "Inter Milan", "MIL": "AC Milan", "NAP": "Napoli",
            "ROM": "AS Roma", "LAZ": "Lazio", "FIO": "Fiorentina", "ATA": "Atalanta",
            "ACF": "Fiorentina", "BOL": "Bologna", "TOR": "Torino",
            "HEL": "Hellas Verona", "UDI": "Udinese", "MON": "Monza",
            "EMP": "Empoli", "VEN": "Venezia", "COM": "Como", "SS": "SS Lazio",
            # Bundesliga
            "BAY": "Bayern Munich", "DOR": "Borussia Dortmund", "LEI": "RB Leipzig",
            "B04": "Bayer Leverkusen", "AUG": "FC Augsburg", "STU": "VfB Stuttgart",
            "FSV": "FSV Mainz 05", "EIN": "Eintracht Frankfurt", "FRE": "SC Freiburg",
            "ST": "VfB Stuttgart", "WER": "Werder Bremen", "HOF": "TSG Hoffenheim",
            # Ligue 1
            "PSG": "Paris Saint-Germain", "MAR": "Marseille", "LYO": "Olympique Lyon",
            "MON": "Monaco", "LIL": "Lille", "REN": "Rennes", "NAN": "Nantes",
            "STR": "RC Strasbourg", "STA": "Stade de Reims", "OLY": "Olympique Lyon",
            "PAR": "Paris Saint-Germain", "NIC": "OGC Nice", "ANG": "Angers",
            "AUX": "Auxerre", "LE": "Le Havre",
        }
        return team_mapping.get(team_code.upper(), team_code)

    def _lookup_teams_by_fixture_id(self, league: str, fixture_id: int) -> Optional[Dict[str, str]]:
        """
        Internally map a numeric fixture ID to team names using the single-fixture
        endpoint /v4/matches/{id} — permitted on the free football-data.org plan.

        Works for both upcoming (SCHEDULED) and recently played (FINISHED) matches.
        """
        try:
            info = self.data_fetcher.get_fixture_info(fixture_id)
            if info:
                return {
                    "homeTeam": info["homeTeam"],
                    "awayTeam": info["awayTeam"],
                    "date": info["date"],
                    "league": league,
                }
        except Exception as e:
            print(f"Error looking up fixture {fixture_id}: {e}")

        return None

    def get_ai_match_result(self, home_team: str, away_team: str, match_date: str) -> Optional[str]:
        """Get match result using AI to search for real-time results"""

        home_full = self.expand_team_names(home_team)
        away_full = self.expand_team_names(away_team)

        prompt = f"""Search for the final score of {home_full} vs {away_full} on {match_date}.

Please respond with ONLY one of these exact values:
- "HOME_WIN" if the home team won
- "DRAW" if the match was a draw  
- "AWAY_WIN" if the away team won
- "NOT_FOUND" if you cannot find the result or the match hasn't finished

Do not include scores, explanations, or any other text. Just return the result."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=10,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )

            result = response.content[0].text.strip().upper()

            if result in ["HOME_WIN", "DRAW", "AWAY_WIN"]:
                return result
            elif result == "NOT_FOUND":
                return None
            else:
                # Try to extract from unexpected response
                if "HOME_WIN" in result:
                    return "HOME_WIN"
                elif "DRAW" in result:
                    return "DRAW"
                elif "AWAY_WIN" in result:
                    return "AWAY_WIN"
                else:
                    print(f"Unexpected AI response: {result}")
                    return None

        except Exception as e:
            print(f"Error calling AI for result: {e}")
            return None

    def get_match_result(self, match_id: str) -> Optional[str]:
        """
        Get match result using AI
        
        Args:
            match_id: Match identifier (e.g., "EPL-ARS-CHE-2026-02-12" or "Ligue1-542641")
            
        Returns:
            "HOME_WIN", "DRAW", or "AWAY_WIN" or None
        """
        parsed = self.parse_match_id(match_id)
        if not parsed:
            return None

        # Format 1: Descriptive IDs (AI can handle these)
        if parsed.get("format") in ("descriptive", "fixture_descriptive"):
            home_team = parsed.get("homeTeam", "")
            away_team = parsed.get("awayTeam", "")
            match_date = parsed.get("date", "")

            if not all([home_team, away_team, match_date]):
                return None

            return self.get_ai_match_result(home_team, away_team, match_date)

        # Format 2: Fixture IDs — map to team names using our own schedule data
        elif parsed.get("format") == "fixture":
            league = parsed.get("league", "")
            fixture_id = int(parsed.get("fixtureId", 0))
            print(f"Fixture ID format {match_id} - looking up teams internally")

            match_details = self._lookup_teams_by_fixture_id(league, fixture_id)
            if match_details:
                home_team = match_details.get("homeTeam", "")
                away_team = match_details.get("awayTeam", "")
                match_date = match_details.get("date", "")

                if all([home_team, away_team, match_date]):
                    print(f"Internal mapping found: {home_team} vs {away_team} on {match_date}")
                    return self.get_ai_match_result(home_team, away_team, match_date)

            print(f"Internal mapping not found for {match_id} - falling back to data fetcher")
            return None  # Let resolver fall back to data_fetcher (direct fixture API call)

        return None
