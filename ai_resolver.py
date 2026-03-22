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
    
    def lookup_fixture_id(self, match_id: str) -> Optional[Dict[str, str]]:
        """Use AI to lookup match details from fixture ID"""
        try:
            parts = match_id.split("-")
            if len(parts) != 2 or not parts[1].isdigit():
                return None
                
            league = parts[0]
            fixture_id = parts[1]
            
            league_names = {
                "EPL": "Premier League",
                "LaLiga": "La Liga", 
                "SerieA": "Serie A",
                "Bundesliga": "Bundesliga",
                "Ligue1": "Ligue 1"
            }
            
            league_full = league_names.get(league, league)
            
            prompt = f"""Search for fixture ID {fixture_id} in {league_full}. 
            
Please find the match details and return in this exact format:
home_team: [Team Name]
away_team: [Team Name]  
date: [YYYY-MM-DD]

If you cannot find this specific fixture ID, return "NOT_FOUND"."""

            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=100,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            result = response.content[0].text.strip()
            
            if "NOT_FOUND" in result:
                return None
                
            # Parse the response
            details = {}
            for line in result.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    details[key.strip().lower()] = value.strip()
            
            if all(k in details for k in ['home_team', 'away_team', 'date']):
                return {
                    "homeTeam": details['home_team'],
                    "awayTeam": details['away_team'],
                    "date": details['date'],
                    "league": league
                }
            
        except Exception as e:
            print(f"Error looking up fixture ID {match_id}: {e}")
            
        return None

    def get_match_info_from_fixture(self, league: str, fixture_id: str) -> Optional[Dict[str, str]]:
        """Get match info from fixture ID using data fetcher"""
        try:
            # Try to get fixture info from football-data.org
            fixture_info = self.data_fetcher._get_match_result_by_fixture_id(int(fixture_id))
            if fixture_info:
                # This won't give us team names directly, so we'll need to try a different approach
                pass
        except Exception as e:
            print(f"Error getting fixture info: {e}")
        
        # For now, we can't resolve fixture IDs with AI
        # These will fall back to the original data fetcher
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
            match_id: Match identifier (e.g., "EPL-ARS-CHE-2026-02-12" or "Ligue1-542641")
            
        Returns:
            "HOME_WIN", "DRAW", or "AWAY_WIN" or None
        """
        parsed = self.parse_match_id(match_id)
        if not parsed:
            return None
        
        # Format 1: Descriptive IDs (AI can handle these)
        if parsed.get("format") == "descriptive":
            home_team = parsed.get("homeTeam", "")
            away_team = parsed.get("awayTeam", "")
            match_date = parsed.get("date", "")
            
            if not all([home_team, away_team, match_date]):
                return None
            
            return self.get_ai_match_result(home_team, away_team, match_date)
        
        # Format 2: Fixture IDs (AI can now lookup and resolve these!)
        elif parsed.get("format") == "fixture":
            print(f"Fixture ID format {match_id} - attempting AI lookup")
            
            # Use AI to lookup match details from fixture ID
            match_details = self.lookup_fixture_id(match_id)
            if match_details:
                home_team = match_details.get("homeTeam", "")
                away_team = match_details.get("awayTeam", "")
                match_date = match_details.get("date", "")
                
                if all([home_team, away_team, match_date]):
                    print(f"AI lookup successful: {home_team} vs {away_team} on {match_date}")
                    return self.get_ai_match_result(home_team, away_team, match_date)
            
            print(f"AI lookup failed for {match_id} - falling back to data fetcher")
            return None  # Let resolver fall back to data fetcher
        
        return None
