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
            if len(parts) >= 4:
                return {
                    "league": parts[0],
                    "homeTeam": parts[1],
                    "awayTeam": parts[2],
                    "date": "-".join(parts[3:])
                }
        except Exception as e:
            print(f"Error parsing match ID {match_id}: {e}")
        return {}
    
    def expand_team_names(self, team_code: str) -> str:
        """Expand team codes to full names"""
        team_mapping = {
            "ARS": "Arsenal", "CHE": "Chelsea", "MUN": "Manchester United", "MCI": "Manchester City",
            "LIV": "Liverpool", "BRI": "Brighton", "TOT": "Tottenham", "WHU": "West Ham",
            "NEW": "Newcastle", "LEI": "Leicester", "AVL": "Aston Villa", "EVE": "Everton",
            "WOL": "Wolves", "CRY": "Crystal Palace", "SOU": "Southampton", "FUL": "Fulham",
            "LEE": "Leeds United", "BUR": "Burnley", "NOT": "Nottingham Forest", 
            "BHA": "Brighton", "BRH": "Brighton",
            # La Liga
            "BAR": "Barcelona", "RMA": "Real Madrid", "ATM": "Atletico Madrid", "VAL": "Valencia",
            "SEV": "Sevilla", "BET": "Real Betis", "SOC": "Real Sociedad", "ATH": "Athletic Bilbao",
            # Serie A
            "JUV": "Juventus", "INT": "Inter Milan", "MIL": "AC Milan", "NAP": "Napoli",
            "ROM": "Roma", "LAZ": "Lazio", "FIO": "Fiorentina", "ATA": "Atalanta",
            # Bundesliga
            "BAY": "Bayern Munich", "DOR": "Borussia Dortmund", "LEB": "RB Leipzig", 
            "B04": "Bayer Leverkusen",
            # Ligue 1
            "PSG": "Paris Saint-Germain", "MAR": "Marseille", "LYO": "Lyon", "MON": "Monaco",
            "LIL": "Lille", "REN": "Rennes"
        }
        return team_mapping.get(team_code.upper(), team_code)
    
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
                model="claude-3-sonnet-20240229",
                max_tokens=10,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
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
            match_id: Match identifier (e.g., "EPL-ARS-CHE-2026-02-12")
            
        Returns:
            "HOME_WIN", "DRAW", or "AWAY_WIN" or None
        """
        parsed = self.parse_match_id(match_id)
        if not parsed:
            return None
        
        home_team = parsed.get("homeTeam", "")
        away_team = parsed.get("awayTeam", "")
        match_date = parsed.get("date", "")
        
        if not all([home_team, away_team, match_date]):
            return None
        
        return self.get_ai_match_result(home_team, away_team, match_date)
