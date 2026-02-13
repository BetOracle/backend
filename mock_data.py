import random
from typing import List, Dict, Optional
from datetime import datetime, timedelta


class MockDataProvider:
    """
    Provides extensive realistic mock data for testing
    Includes full league rosters, player names, historical data
    """

    def __init__(self):
        # Full league rosters (20 teams each for EPL, 18+ for others)
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
                "Brighton",
                "West Ham",
                "Crystal Palace",
                "Brentford",
                "Fulham",
                "Wolves",
                "Everton",
                "Nottingham Forest",
                "Bournemouth",
                "Luton Town",
                "Burnley",
                "Sheffield United",
            ],
            "LaLiga": [
                "Real Madrid",
                "Barcelona",
                "Atletico Madrid",
                "Athletic Bilbao",
                "Real Sociedad",
                "Real Betis",
                "Villarreal",
                "Valencia",
                "Sevilla",
                "Girona",
                "Osasuna",
                "Las Palmas",
                "Rayo Vallecano",
                "Getafe",
                "Alaves",
                "Mallorca",
                "Celta Vigo",
                "Cadiz",
                "Granada",
                "Almeria",
            ],
            "SerieA": [
                "Inter Milan",
                "AC Milan",
                "Juventus",
                "Napoli",
                "Roma",
                "Lazio",
                "Atalanta",
                "Fiorentina",
                "Bologna",
                "Torino",
                "Monza",
                "Genoa",
                "Lecce",
                "Udinese",
                "Frosinone",
                "Hellas Verona",
                "Empoli",
                "Cagliari",
                "Sassuolo",
                "Salernitana",
            ],
            "Bundesliga": [
                "Bayern Munich",
                "Borussia Dortmund",
                "RB Leipzig",
                "Union Berlin",
                "Bayer Leverkusen",
                "Eintracht Frankfurt",
                "Freiburg",
                "Wolfsburg",
                "Stuttgart",
                "Hoffenheim",
                "Borussia Monchengladbach",
                "Werder Bremen",
                "Augsburg",
                "Mainz",
                "Heidenheim",
                "Bochum",
                "Koln",
                "Darmstadt",
            ],
            "Ligue1": [
                "PSG",
                "Marseille",
                "Monaco",
                "Lyon",
                "Lille",
                "Nice",
                "Lens",
                "Rennes",
                "Toulouse",
                "Reims",
                "Montpellier",
                "Nantes",
                "Strasbourg",
                "Brest",
                "Le Havre",
                "Lorient",
                "Metz",
                "Clermont",
            ],
        }

        # Detailed team ratings
        self.team_ratings = self._generate_all_team_ratings()

        # Player names for realism
        self.first_names = [
            "Mohamed",
            "Cristiano",
            "Lionel",
            "Kylian",
            "Erling",
            "Harry",
            "Kevin",
            "Bruno",
            "Luka",
            "Antoine",
            "Robert",
            "Sadio",
            "Raheem",
            "Marcus",
            "Jack",
            "Phil",
            "Bukayo",
            "Gabriel",
            "Joao",
            "Rafael",
            "Diego",
            "Luis",
            "Carlos",
            "Juan",
            "Pierre",
            "Thomas",
            "Lucas",
            "Marco",
            "Andrea",
            "Federico",
            "Manuel",
            "Sergio",
            "David",
            "Paulo",
            "Alex",
            "James",
        ]

        self.last_names = [
            "Silva",
            "Santos",
            "Fernandez",
            "Rodriguez",
            "Martinez",
            "Garcia",
            "Lopez",
            "Gonzalez",
            "Perez",
            "Sanchez",
            "Rossi",
            "Bianchi",
            "Romano",
            "Colombo",
            "Ricci",
            "Müller",
            "Schmidt",
            "Schneider",
            "Fischer",
            "Weber",
            "Dubois",
            "Martin",
            "Bernard",
            "Thomas",
            "Robert",
            "Smith",
            "Johnson",
            "Williams",
            "Brown",
            "Jones",
            "Costa",
            "Alves",
            "Oliveira",
            "Ferreira",
            "Carvalho",
        ]

    def _generate_all_team_ratings(self) -> Dict:
        """Generate ratings for all teams in all leagues"""
        ratings = {}

        # Top teams (manually set)
        top_teams = {
            "Manchester City": {"overall": 92, "attack": 94, "defense": 90, "form": 85},
            "Real Madrid": {"overall": 91, "attack": 93, "defense": 88, "form": 89},
            "Bayern Munich": {"overall": 91, "attack": 93, "defense": 88, "form": 90},
            "PSG": {"overall": 89, "attack": 92, "defense": 85, "form": 88},
            "Arsenal": {"overall": 88, "attack": 87, "defense": 88, "form": 88},
            "Liverpool": {"overall": 88, "attack": 90, "defense": 85, "form": 87},
            "Barcelona": {"overall": 88, "attack": 90, "defense": 85, "form": 87},
            "Inter Milan": {"overall": 87, "attack": 86, "defense": 88, "form": 86},
            "Napoli": {"overall": 86, "attack": 88, "defense": 83, "form": 85},
            "Borussia Dortmund": {
                "overall": 85,
                "attack": 88,
                "defense": 81,
                "form": 84,
            },
            "Atletico Madrid": {"overall": 85, "attack": 82, "defense": 88, "form": 84},
        }

        ratings.update(top_teams)

        # Generate ratings for all other teams
        for league, teams in self.league_teams.items():
            for i, team in enumerate(teams):
                if team not in ratings:
                    # Position-based rating (higher position = lower rating)
                    base_rating = 85 - (i * 2)
                    base_rating = max(65, min(85, base_rating))

                    variation = random.randint(-3, 3)
                    overall = base_rating + variation

                    ratings[team] = {
                        "overall": overall,
                        "attack": overall + random.randint(-5, 5),
                        "defense": overall + random.randint(-5, 5),
                        "form": overall + random.randint(-10, 10),
                    }

        return ratings

    def get_team_rating(self, team_name: str, component: str = "overall") -> int:
        """Get team rating for specific component"""
        if team_name in self.team_ratings:
            return self.team_ratings[team_name].get(component, 70)
        return random.randint(65, 75)

    def get_team_form(self, team_name: str, last_n: int = 5) -> List[str]:
        """Generate realistic team form"""
        overall_rating = self.get_team_rating(team_name, "overall")
        form_rating = self.get_team_rating(team_name, "form")

        effective_rating = (overall_rating * 0.6) + (form_rating * 0.4)
        win_prob = max(0.1, min(0.8, (effective_rating - 50) / 100))
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

    def get_injuries(self, team_name: str) -> List[Dict]:
        """Generate realistic injuries with player names"""
        rating = self.get_team_rating(team_name, "overall")

        max_injuries = 3 if rating >= 85 else 4 if rating >= 75 else 5
        num_injuries = random.randint(0, max_injuries)

        positions = ["Goalkeeper", "Defender", "Midfielder", "Forward"]
        severities = ["minor", "moderate", "severe"]
        injury_types = [
            "Hamstring",
            "Ankle",
            "Knee",
            "Groin",
            "Calf",
            "Thigh",
            "Back",
            "Shoulder",
            "Foot",
            "Hip",
        ]

        injuries = []
        used_names = set()

        for _ in range(num_injuries):
            while True:
                name = f"{random.choice(self.first_names)} {random.choice(self.last_names)}"
                if name not in used_names:
                    used_names.add(name)
                    break

            severity = random.choice(severities)
            days_out = {
                "minor": random.randint(3, 10),
                "moderate": random.randint(14, 28),
                "severe": random.randint(60, 120),
            }[severity]

            injuries.append(
                {
                    "player": name,
                    "position": random.choice(positions),
                    "severity": severity,
                    "injury": f"{random.choice(injury_types)} injury",
                    "expectedReturn": (
                        datetime.now() + timedelta(days=days_out)
                    ).strftime("%Y-%m-%d"),
                    "daysOut": days_out,
                }
            )

        return injuries

    def get_h2h(self, home_team: str, away_team: str, last_n: int = 10) -> List[str]:
        """Generate H2H based on ratings"""
        home_rating = self.get_team_rating(home_team, "overall")
        away_rating = self.get_team_rating(away_team, "overall")

        rating_diff = home_rating - away_rating + 5  # Home advantage

        home_win_prob = max(0.15, min(0.65, 0.35 + (rating_diff / 150)))
        draw_prob = 0.25

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

    def get_table_position(self, team_name: str, league: str) -> int:
        """Get table position based on rating"""
        rating = self.get_team_rating(team_name, "overall")

        if rating >= 90:
            return random.randint(1, 2)
        elif rating >= 85:
            return random.randint(2, 5)
        elif rating >= 80:
            return random.randint(4, 8)
        elif rating >= 75:
            return random.randint(7, 12)
        elif rating >= 70:
            return random.randint(10, 15)
        else:
            return random.randint(14, 20)

    def get_match_result(self, match_id: str) -> Optional[str]:
        """Generate match result"""
        if random.random() < 0.3:
            return None

        outcomes = ["HOME_WIN", "DRAW", "AWAY_WIN"]
        weights = [0.46, 0.27, 0.27]
        return random.choices(outcomes, weights=weights)[0]

    def get_league_matches(self, league: str, days_ahead: int = 7) -> List[Dict]:
        """Generate realistic fixtures"""
        teams = self.league_teams.get(league, self.league_teams["EPL"])

        num_matches = random.randint(8, 12)
        matches = []
        used_teams = set()

        for _ in range(num_matches):
            for _ in range(20):  # Try up to 20 times to find valid matchup
                home = random.choice(teams)
                available = [t for t in teams if t != home and t not in used_teams]

                if not available:
                    used_teams.clear()
                    available = [t for t in teams if t != home]

                away = random.choice(available)

                if home not in used_teams:
                    break

            used_teams.add(home)
            used_teams.add(away)

            if len(used_teams) > len(teams) * 0.6:
                used_teams.clear()

            days_offset = random.randint(1, days_ahead)
            match_date = datetime.now() + timedelta(days=days_offset)

            # Weekend vs weekday times
            if match_date.weekday() in [5, 6]:
                time = random.choice(["12:30", "15:00", "17:30"])
            else:
                time = random.choice(["19:45", "20:00", "20:45"])

            matches.append(
                {
                    "homeTeam": home,
                    "awayTeam": away,
                    "date": match_date.strftime("%Y-%m-%d"),
                    "time": time,
                    "venue": f"{home} Stadium",
                }
            )

        matches.sort(key=lambda x: (x["date"], x["time"]))
        return matches

    def get_player_stats(self, team_name: str) -> List[Dict]:
        """Generate squad statistics"""
        positions = {"Goalkeeper": 2, "Defender": 7, "Midfielder": 7, "Forward": 4}

        players = []
        used_names = set()

        for position, count in positions.items():
            for _ in range(count):
                while True:
                    name = f"{random.choice(self.first_names)} {random.choice(self.last_names)}"
                    if name not in used_names:
                        used_names.add(name)
                        break

                if position == "Forward":
                    goals, assists, rating = (
                        random.randint(4, 18),
                        random.randint(2, 12),
                        round(random.uniform(6.8, 8.2), 1),
                    )
                elif position == "Midfielder":
                    goals, assists, rating = (
                        random.randint(1, 10),
                        random.randint(3, 14),
                        round(random.uniform(6.7, 8.0), 1),
                    )
                elif position == "Defender":
                    goals, assists, rating = (
                        random.randint(0, 4),
                        random.randint(0, 5),
                        round(random.uniform(6.5, 7.8), 1),
                    )
                else:
                    goals, assists, rating = 0, 0, round(random.uniform(6.4, 7.9), 1)

                appearances = random.randint(10, 28)

                players.append(
                    {
                        "name": name,
                        "position": position,
                        "number": random.randint(1, 99),
                        "goals": goals,
                        "assists": assists,
                        "appearances": appearances,
                        "minutes": appearances * random.randint(70, 90),
                        "rating": rating,
                        "yellowCards": random.randint(0, 8),
                        "redCards": random.randint(0, 1),
                    }
                )

        return players
