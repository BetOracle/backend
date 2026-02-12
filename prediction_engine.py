import random
from datetime import datetime
from data_fetcher import DataFetcher


class PredictionEngine:
    """
    Core prediction engine for football matches

    Uses multi-factor analysis:
    - Team form (recent results)
    - Injury impact
    - Head-to-head record
    - League table position
    """

    def __init__(self):
        self.data_fetcher = DataFetcher()

        # Weight configuration (tune these for better accuracy)
        self.weights = {
            "form": 0.35,  # Recent form weight
            "injury": 0.15,  # Injury impact weight
            "h2h": 0.25,  # Head-to-head weight
            "position": 0.25,  # Table position weight
        }

    def predict(self, home_team: str, away_team: str, league: str) -> dict:
        """
        Generate prediction for a match

        Args:
            home_team: Home team name
            away_team: Away team name
            league: League code (EPL, LaLiga, etc.)

        Returns:
            {
                "matchId": "EPL-ARS-CHE-2026-02-12",
                "prediction": "HOME_WIN",
                "confidence": 0.74,
                "factors": {...},
                "timestamp": 1707696000
            }
        """

        # Generate match ID
        match_id = self._generate_match_id(home_team, away_team, league)

        # Calculate individual factors
        form_score = self._calculate_form_score(home_team, away_team, league)
        injury_impact = self._calculate_injury_impact(home_team, away_team, league)
        h2h_score = self._calculate_h2h_score(home_team, away_team, league)
        position_score = self._calculate_position_score(home_team, away_team, league)

        # Combine factors
        factors = {
            "formScore": round(form_score, 2),
            "injuryImpact": round(injury_impact, 2),
            "h2hScore": round(h2h_score, 2),
            "tablePositionScore": round(position_score, 2),
        }

        # Calculate weighted total
        total_score = (
            form_score * self.weights["form"]
            + injury_impact * self.weights["injury"]
            + h2h_score * self.weights["h2h"]
            + position_score * self.weights["position"]
        )

        # Determine prediction
        prediction, confidence = self._determine_outcome(total_score, factors)

        return {
            "matchId": match_id,
            "prediction": prediction,
            "confidence": round(confidence, 2),
            "factors": factors,
            "timestamp": int(datetime.now().timestamp()),
        }

    def _generate_match_id(self, home_team: str, away_team: str, league: str) -> str:
        """Generate unique match ID"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        home_abbr = home_team[:3].upper()
        away_abbr = away_team[:3].upper()
        return f"{league}-{home_abbr}-{away_abbr}-{date_str}"

    def _calculate_form_score(
        self, home_team: str, away_team: str, league: str
    ) -> float:
        """
        Calculate form score based on recent results

        Returns: -1.0 to 1.0
        - Positive = home team has better form
        - Negative = away team has better form
        """

        # Fetch recent results
        home_form = self.data_fetcher.get_team_form(home_team, league)
        away_form = self.data_fetcher.get_team_form(away_team, league)

        # Calculate form points (W=3, D=1, L=0)
        home_points = sum([3 if r == "W" else 1 if r == "D" else 0 for r in home_form])
        away_points = sum([3 if r == "W" else 1 if r == "D" else 0 for r in away_form])

        # Normalize to -1 to 1 scale
        max_points = len(home_form) * 3
        home_normalized = (home_points / max_points * 2) - 1
        away_normalized = (away_points / max_points * 2) - 1

        # Return difference (home advantage)
        form_diff = home_normalized - away_normalized

        # Add home advantage boost (+0.1)
        return min(1.0, max(-1.0, form_diff + 0.1))

    def _calculate_injury_impact(
        self, home_team: str, away_team: str, league: str
    ) -> float:
        """
        Calculate injury impact on match

        Returns: -1.0 to 1.0
        - Positive = home team less affected by injuries
        - Negative = away team less affected by injuries
        """

        # Fetch injury data
        home_injuries = self.data_fetcher.get_injuries(home_team, league)
        away_injuries = self.data_fetcher.get_injuries(away_team, league)

        # Count key player injuries (simple version)
        home_impact = len(home_injuries) * -0.1
        away_impact = len(away_injuries) * -0.1

        # Return relative impact
        return min(1.0, max(-1.0, away_impact - home_impact))

    def _calculate_h2h_score(
        self, home_team: str, away_team: str, league: str
    ) -> float:
        """
        Calculate head-to-head record score

        Returns: -1.0 to 1.0
        - Positive = home team historically dominates
        - Negative = away team historically dominates
        """

        # Fetch H2H history
        h2h_results = self.data_fetcher.get_h2h(home_team, away_team, league)

        if not h2h_results:
            return 0.0  # No history

        # Count wins
        home_wins = sum(1 for r in h2h_results if r == "HOME")
        away_wins = sum(1 for r in h2h_results if r == "AWAY")

        total = len(h2h_results)

        # Normalize
        h2h_score = (home_wins - away_wins) / total

        return min(1.0, max(-1.0, h2h_score))

    def _calculate_position_score(
        self, home_team: str, away_team: str, league: str
    ) -> float:
        """
        Calculate score based on league table positions

        Returns: -1.0 to 1.0
        - Positive = home team higher in table
        - Negative = away team higher in table
        """

        # Fetch standings
        home_position = self.data_fetcher.get_table_position(home_team, league)
        away_position = self.data_fetcher.get_table_position(away_team, league)

        # Lower position = better (1st place = 1)
        # Normalize to -1 to 1 scale
        max_teams = 20  # Typical league size

        home_score = 1 - (home_position / max_teams)
        away_score = 1 - (away_position / max_teams)

        position_diff = (home_score - away_score) * 2

        return min(1.0, max(-1.0, position_diff))

    def _determine_outcome(self, total_score: float, factors: dict) -> tuple:
        """
        Determine final prediction and confidence

        Args:
            total_score: Combined weighted score (-1.0 to 1.0)
            factors: Individual factor scores

        Returns:
            (prediction, confidence)
            - prediction: "HOME_WIN", "DRAW", or "AWAY_WIN"
            - confidence: 0.0 to 1.0
        """

        # Define thresholds
        STRONG_HOME_THRESHOLD = 0.3
        WEAK_HOME_THRESHOLD = 0.1
        WEAK_AWAY_THRESHOLD = -0.1
        STRONG_AWAY_THRESHOLD = -0.3

        # Determine prediction
        if total_score > STRONG_HOME_THRESHOLD:
            prediction = "HOME_WIN"
            base_confidence = 0.7
        elif total_score > WEAK_HOME_THRESHOLD:
            prediction = "HOME_WIN"
            base_confidence = 0.6
        elif total_score > WEAK_AWAY_THRESHOLD:
            prediction = "DRAW"
            base_confidence = 0.55
        elif total_score > STRONG_AWAY_THRESHOLD:
            prediction = "AWAY_WIN"
            base_confidence = 0.6
        else:
            prediction = "AWAY_WIN"
            base_confidence = 0.7

        # Adjust confidence based on factor agreement
        factor_values = list(factors.values())
        factor_std = self._calculate_std(factor_values)

        # Lower std = more agreement = higher confidence
        confidence_boost = (1 - min(factor_std, 1.0)) * 0.15

        final_confidence = min(0.95, base_confidence + confidence_boost)

        return prediction, final_confidence

    def _calculate_std(self, values: list) -> float:
        """Calculate standard deviation"""
        if not values:
            return 0.0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance**0.5
