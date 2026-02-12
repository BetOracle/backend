import random
from typing import List, Dict
from datetime import datetime, timedelta


class MockDataProvider:
    """
    Provides realistic mock data for testing
    """

    def __init__(self):
        # Team quality ratings (for realistic mock data)
        self.team_ratings = {
            # Premier League
            "Arsenal": 85,
            "Manchester City": 92,
            "Liverpool": 88,
            "Chelsea": 80,
            "Tottenham": 78,
            "Manchester United": 82,
            "Newcastle": 77,
            "Aston Villa": 75,
            # La Liga
            "Real Madrid": 90,
            "Barcelona": 88,
            "Atletico Madrid": 84,
            "Sevilla": 76,
            "Real Sociedad": 74,
            # Serie A
            "Inter Milan": 86,
            "Juventus": 83,
            "AC Milan": 81,
            "Roma": 78,
            "Napoli": 85,
            # Bundesliga
            "Bayern Munich": 91,
            "Borussia Dortmund": 84,
            "RB Leipzig": 80,
            "Bayer Leverkusen": 79,
            # Ligue 1
            "PSG": 89,
            "Marseille": 76,
            "Lyon": 75,
            "Monaco": 77,
        }

        # League teams
        self.league_teams = {
            "EPL": [
                "Arsenal",
                "Manchester City",
                "Liverpool",
                "Chelsea",
                "Tottenham",
                "Manchester United",
                "Newcastle",
                "Aston Villa",
            ],
            "LaLiga": [
                "Real Madrid",
                "Barcelona",
                "Atletico Madrid",
                "Sevilla",
                "Real Sociedad",
            ],
            "SerieA": ["Inter Milan", "Juventus", "AC Milan", "Roma", "Napoli"],
            "Bundesliga": [
                "Bayern Munich",
                "Borussia Dortmund",
                "RB Leipzig",
                "Bayer Leverkusen",
            ],
            "Ligue1": ["PSG", "Marseille", "Lyon", "Monaco"],
        }

    def get_team_rating(self, team_name: str) -> int:
        """Get team quality rating (1-100)"""
        return self.team_ratings.get(team_name, 70)

    # =========================================================================
    # TEAM FORM
    # =========================================================================

    def get_team_form(self, team_name: str, last_n: int = 5) -> List[str]:
        """
        Generate realistic team form based on team quality

        Args:
            team_name: Team name
            last_n: Number of matches

        Returns:
            List of results: ['W', 'L', 'D', 'W', 'W']
        """
        rating = self.get_team_rating(team_name)

        # Higher rating = more wins
        win_prob = (rating - 50) / 100  # 70 rating → 20% wins
        draw_prob = 0.25

        form = []
        for _ in range(last_n):
            rand = random.random()
            if rand < win_prob:
                form.append("W")
            elif rand < win_prob + draw_prob:
                form.append("D")
            else:
                form.append("L")

        return form

    # =========================================================================
    # INJURIES
    # =========================================================================

    def get_injuries(self, team_name: str) -> List[Dict]:
        """
        Generate realistic injury list

        Returns:
            [
                {
                    "player": "Player Name",
                    "position": "Forward",
                    "severity": "moderate",
                    "expectedReturn": "2026-03-15"
                },
                ...
            ]
        """
        # Random 0-4 injuries per team
        num_injuries = random.randint(0, 4)

        positions = ["Goalkeeper", "Defender", "Midfielder", "Forward"]
        severities = ["minor", "moderate", "severe"]

        injuries = []
        for i in range(num_injuries):
            severity = random.choice(severities)

            # Expected return based on severity
            if severity == "minor":
                days_out = random.randint(3, 10)
            elif severity == "moderate":
                days_out = random.randint(14, 28)
            else:  # severe
                days_out = random.randint(60, 120)

            expected_return = (datetime.now() + timedelta(days=days_out)).strftime(
                "%Y-%m-%d"
            )

            injuries.append(
                {
                    "player": f"{team_name} Player {i+1}",
                    "position": random.choice(positions),
                    "severity": severity,
                    "expectedReturn": expected_return,
                    "daysOut": days_out,
                }
            )

        return injuries

    # =========================================================================
    # HEAD-TO-HEAD
    # =========================================================================

    def get_h2h(self, home_team: str, away_team: str, last_n: int = 10) -> List[str]:
        """
        Generate realistic H2H based on team ratings

        Returns:
            ['HOME', 'AWAY', 'DRAW', ...]
        """
        home_rating = self.get_team_rating(home_team)
        away_rating = self.get_team_rating(away_team)

        # Calculate probabilities based on ratings
        rating_diff = home_rating - away_rating

        # Home advantage + rating difference
        home_win_prob = 0.40 + (rating_diff / 200)
        draw_prob = 0.25
        away_win_prob = 1 - home_win_prob - draw_prob

        results = []
        for _ in range(last_n):
            rand = random.random()
            if rand < home_win_prob:
                results.append("HOME")
            elif rand < home_win_prob + draw_prob:
                results.append("DRAW")
            else:
                results.append("AWAY")

        return results

    # =========================================================================
    # LEAGUE STANDINGS
    # =========================================================================

    def get_table_position(self, team_name: str, league: str) -> int:
        """
        Generate realistic table position based on rating

        Returns:
            Position (1-20)
        """
        rating = self.get_team_rating(team_name)

        # Higher rating = better position
        if rating >= 90:
            return random.randint(1, 3)
        elif rating >= 85:
            return random.randint(2, 6)
        elif rating >= 80:
            return random.randint(5, 10)
        elif rating >= 75:
            return random.randint(8, 14)
        else:
            return random.randint(12, 20)

    # =========================================================================
    # MATCH RESULTS
    # =========================================================================

    def get_match_result(self, match_id: str) -> str:
        """
        Generate realistic match result

        Args:
            match_id: e.g., "EPL-ARS-CHE-2026-02-12"

        Returns:
            "HOME_WIN", "DRAW", or "AWAY_WIN"
            None if match not yet played (30% chance)
        """
        # 30% chance match hasn't happened yet
        if random.random() < 0.3:
            return None

        # Parse teams from match_id (rough approximation)
        parts = match_id.split("-")
        if len(parts) >= 3:
            # Try to determine home advantage
            outcomes = ["HOME_WIN", "DRAW", "AWAY_WIN"]
            weights = [0.45, 0.25, 0.30]  # Home advantage
            return random.choices(outcomes, weights=weights)[0]

        return random.choice(["HOME_WIN", "DRAW", "AWAY_WIN"])

    # =========================================================================
    # UPCOMING MATCHES
    # =========================================================================

    def get_league_matches(self, league: str, days_ahead: int = 7) -> List[Dict]:
        """
        Generate realistic upcoming matches

        Returns:
            [
                {
                    "homeTeam": "Arsenal",
                    "awayTeam": "Chelsea",
                    "date": "2026-02-12",
                    "time": "15:00",
                    "venue": "Emirates Stadium"
                },
                ...
            ]
        """
        teams = self.league_teams.get(league, self.league_teams["EPL"])

        matches = []
        match_times = ["12:30", "15:00", "17:30", "20:00"]

        # Generate 5-10 matches
        num_matches = random.randint(5, 10)

        for i in range(num_matches):
            home = random.choice(teams)
            away = random.choice([t for t in teams if t != home])

            match_date = datetime.now() + timedelta(days=random.randint(1, days_ahead))

            matches.append(
                {
                    "homeTeam": home,
                    "awayTeam": away,
                    "date": match_date.strftime("%Y-%m-%d"),
                    "time": random.choice(match_times),
                    "venue": f"{home} Stadium",
                }
            )

        # Sort by date
        matches.sort(key=lambda x: x["date"])

        return matches

    # =========================================================================
    # PLAYER STATS
    # =========================================================================

    def get_player_stats(self, team_name: str) -> List[Dict]:
        """
        Generate mock player statistics

        Returns:
            [
                {
                    "name": "Player Name",
                    "position": "Forward",
                    "goals": 12,
                    "assists": 5,
                    "appearances": 20
                },
                ...
            ]
        """
        positions = ["Goalkeeper", "Defender", "Midfielder", "Forward"]

        players = []
        for i in range(11):  # Starting 11
            position = positions[i % len(positions)]

            # Position-based stats
            if position == "Forward":
                goals = random.randint(5, 20)
                assists = random.randint(2, 10)
            elif position == "Midfielder":
                goals = random.randint(2, 12)
                assists = random.randint(3, 15)
            elif position == "Defender":
                goals = random.randint(0, 5)
                assists = random.randint(0, 4)
            else:  # Goalkeeper
                goals = 0
                assists = 0

            players.append(
                {
                    "name": f"{team_name} Player {i+1}",
                    "position": position,
                    "goals": goals,
                    "assists": assists,
                    "appearances": random.randint(15, 25),
                    "rating": round(random.uniform(6.5, 8.5), 1),
                }
            )

        return players

    # =========================================================================
    # WEATHER (for match predictions)
    # =========================================================================

    def get_match_weather(self, venue: str, date: str) -> Dict:
        """
        Generate mock weather conditions

        Returns:
            {
                "condition": "Clear",
                "temperature": 18,
                "windSpeed": 12,
                "precipitation": 0
            }
        """
        conditions = ["Clear", "Partly Cloudy", "Cloudy", "Light Rain", "Rain"]

        return {
            "condition": random.choice(conditions),
            "temperature": random.randint(5, 25),
            "windSpeed": random.randint(5, 30),
            "precipitation": random.randint(0, 80),
            "humidity": random.randint(40, 90),
        }
