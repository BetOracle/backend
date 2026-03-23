"""
prediction_engine.py — FootyOracle Prediction Engine

Multi-factor model with:
  - Recent form (30%)
  - Head-to-head (20%)
  - Home advantage (15%)
  - Injury impact (15%)
  - League position (10%)
  - Rest days (10%)

Only surfaces predictions where the model's probability beats the market
by >= 15% (the "value edge"), ensuring we're not just predicting everything.
"""

import logging
import os
from datetime import datetime
from typing import Optional

from data_fetcher import DataFetcher

logger = logging.getLogger(__name__)


class _NoValueBet(RuntimeError):
    """Raised when no value edge is found. Carries the full analysis payload."""
    def __init__(self, message: str, analysis: dict):
        super().__init__(message)
        self.analysis = analysis


# Minimum edge over market to surface a prediction
MIN_EDGE = float(os.getenv("MIN_EDGE", "0.08"))

# Draw-specific guardrails to reduce low-quality draw picks.
MIN_EDGE_DRAW = float(os.getenv("MIN_EDGE_DRAW", "0.12"))
MIN_DRAW_PROB = float(os.getenv("MIN_DRAW_PROB", "0.28"))


class PredictionEngine:
    """
    Core prediction engine for football matches.

    Uses multi-factor analysis to calculate true win/draw/loss probabilities,
    then compares against market odds to identify value bets (edge >= 15%).

    Factors:
        form          30%  — weighted recent results (W=3, D=1, L=0)
        h2h           20%  — historical head-to-head win rate
        home_adv      15%  — fixed home advantage boost
        injury        15%  — relative injury impact
        position      10%  — normalised league table position
        rest          10%  — days since last match
    """

    def __init__(self, data_fetcher: Optional[DataFetcher] = None):
        self.data_fetcher = data_fetcher or DataFetcher()

        self.debug = os.getenv("PREDICTION_DEBUG", "False").lower() == "true"
        self.injuries_enabled = os.getenv("INJURIES_ENABLED", "True").lower() == "true"

        # Factor weights — must sum to 1.0
        self.weights = {
            "form": 0.30,
            "h2h": 0.20,
            "home_adv": 0.15,
            "injury": 0.15,
            "position": 0.10,
            "rest": 0.10,
        }

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def predict(
        self,
        home_team: str,
        away_team: str,
        league: str,
        match_id: str = None,
        market_odds: dict = None,
    ) -> dict:
        """
        Generate prediction for a match.

        Returns the full prediction payload including factors and edge.
        Raises RuntimeError if no value edge found (use find_value separately).

        Returns:
            {
                "matchId": "EPL-ARS-CHE-2026-02-12",
                "prediction": "HOME_WIN",
                "confidence": 0.74,
                "edge": 0.21,
                "marketOdds": {"home": 2.5, "draw": 3.2, "away": 2.8},
                "trueProbabilities": {"home_win": 0.65, "draw": 0.20, "away_win": 0.15},
                "factors": {...},
                "timestamp": 1707696000
            }
        """
        if not match_id:
            match_id = self._generate_match_id(home_team, away_team, league)

        # --- Step 1: Calculate true probabilities from our model ---
        true_probs, factors = self._calculate_probabilities(home_team, away_team, league)

        # --- Step 2: Use provided odds or fetch from AI ---
        if not market_odds:
            market_odds = self.data_fetcher.get_market_odds(home_team, away_team, league)

        # --- Step 3: Find value bet (if any) ---
        value_bet = None
        if market_odds:
            value_bet = self.find_value(true_probs, market_odds)

        # --- Step 4: Build base analysis (always returned) ---
        outcome_label_map = {
            "home_win": "HOME_WIN",
            "draw": "DRAW",
            "away_win": "AWAY_WIN",
        }

        result = {
            "matchId": match_id,
            "marketOdds": market_odds,
            "trueProbabilities": {k: round(v, 3) for k, v in true_probs.items()},
            "factors": factors,
            "timestamp": int(datetime.now().timestamp()),
            "hasValueBet": value_bet is not None,
        }

        if value_bet is None:
            logger.debug(
                "No value found for %s vs %s | probs=%s | odds=%s",
                home_team, away_team, true_probs, market_odds,
            )
            result.update({
                "prediction": None,
                "confidence": None,
                "edge": None,
            })
            raise _NoValueBet(
                f"No value edge >= {MIN_EDGE:.0%} found for {home_team} vs {away_team}",
                result,
            )

        prediction = outcome_label_map[value_bet["outcome"]]
        confidence = round(value_bet["our_prob"], 2)
        edge = round(value_bet["edge"], 3)

        if self.debug:
            logger.debug(
                "VALUE BET: %s vs %s → %s (conf=%.1f%%, edge=%.1f%%)",
                home_team, away_team, prediction, confidence * 100, edge * 100,
            )

        result.update({
            "prediction": prediction,
            "confidence": confidence,
            "edge": edge,
        })
        return result

    def find_value(self, true_probs: dict, market_odds: dict) -> Optional[dict]:
        """
        Find the best value bet given our model probabilities and market odds.

        Converts decimal odds to implied probabilities (with vig removed),
        then finds the outcome where our model most exceeds the market.

        Args:
            true_probs:   {"home_win": 0.65, "draw": 0.20, "away_win": 0.15}
            market_odds:  {"home": 2.50, "draw": 3.20, "away": 2.80}

        Returns:
            {"outcome": "home_win", "our_prob": 0.65, "market_prob": 0.40, "edge": 0.25}
            or None if no value bet found
        """
        # Map market odds keys → probability keys
        odds_to_prob_key = {
            "home": "home_win",
            "draw": "draw",
            "away": "away_win",
        }

        # Step 1: Raw implied probabilities (include vig)
        raw_implied = {}
        for odds_key, prob_key in odds_to_prob_key.items():
            price = market_odds.get(odds_key)
            if not price or price <= 1.0:
                return None  # Malformed odds — skip
            raw_implied[prob_key] = 1.0 / price

        # Step 2: Remove bookmaker vig (normalise to sum = 1.0)
        total_implied = sum(raw_implied.values())
        market_probs = {k: v / total_implied for k, v in raw_implied.items()}

        # Step 3: Find the outcome with the greatest edge
        best_edge = 0.0
        best_bet = None

        for outcome, our_prob in true_probs.items():
            market_prob = market_probs.get(outcome, 0)
            edge = our_prob - market_prob

            min_edge = MIN_EDGE
            if outcome == "draw":
                if our_prob < MIN_DRAW_PROB:
                    continue
                min_edge = MIN_EDGE_DRAW

            if edge >= min_edge and edge > best_edge:
                best_edge = edge
                best_bet = {
                    "outcome": outcome,
                    "our_prob": our_prob,
                    "market_prob": round(market_prob, 3),
                    "edge": edge,
                }

        return best_bet

    # =========================================================================
    # PROBABILITY CALCULATION
    # =========================================================================

    def _calculate_probabilities(
        self, home_team: str, away_team: str, league: str
    ) -> tuple[dict, dict]:
        """
        Calculate true win/draw/loss probabilities using weighted factors.

        Returns:
            (true_probs, factors)
            true_probs: {"home_win": 0.55, "draw": 0.25, "away_win": 0.20}
            factors:    {"formScore": 0.2, ...}
        """
        # --- Individual factor scores (home advantage relative to away) ---
        form_score = self._score_form(home_team, away_team, league)
        h2h_score = self._score_h2h(home_team, away_team, league)
        injury_score = (
            self._score_injuries(home_team, away_team, league)
            if self.injuries_enabled
            else 0.0
        )
        position_score = self._score_position(home_team, away_team, league)
        rest_score = self._score_rest(home_team, away_team, league)

        # Home advantage is a fixed bonus — not relative
        home_adv = self.weights["home_adv"]

        # Effective injury weight (may be 0 if disabled)
        injury_w = self.weights["injury"] if self.injuries_enabled else 0.0

        # Normalise weights if injuries disabled
        active_weights = {
            "form": self.weights["form"],
            "h2h": self.weights["h2h"],
            "injury": injury_w,
            "position": self.weights["position"],
            "rest": self.weights["rest"],
        }
        total_w = sum(active_weights.values())
        if total_w <= 0:
            total_w = 1.0

        # Weighted relative score (-1 → +1, positive = home favoured)
        relative_score = (
            form_score * (active_weights["form"] / total_w)
            + h2h_score * (active_weights["h2h"] / total_w)
            + injury_score * (active_weights["injury"] / total_w)
            + position_score * (active_weights["position"] / total_w)
            + rest_score * (active_weights["rest"] / total_w)
        )

        # Convert relative score [-1, +1] to raw home / away strengths [0, 1]
        home_raw = 0.5 + relative_score / 2.0 + home_adv
        away_raw = max(0.01, 1.0 - home_raw)
        home_raw = max(0.01, home_raw)

        # --- Draw probability: higher when teams are evenly matched ---
        balance = 1.0 - abs(relative_score)  # 1.0 when perfectly balanced
        draw_prob = max(0.18, min(0.35, 0.26 * balance + 0.08))

        # Distribute remaining probability proportionally
        remaining = 1.0 - draw_prob
        total_raw = home_raw + away_raw
        home_win_prob = (home_raw / total_raw) * remaining
        away_win_prob = (away_raw / total_raw) * remaining

        # Clamp to valid range
        total = home_win_prob + draw_prob + away_win_prob
        home_win_prob /= total
        draw_prob /= total
        away_win_prob /= total

        factors = {
            "formScore": round(form_score, 3),
            "h2hScore": round(h2h_score, 3),
            "injuryImpact": round(injury_score, 3),
            "tablePositionScore": round(position_score, 3),
            "restDaysScore": round(rest_score, 3),
            "relativeScore": round(relative_score, 3),
        }

        true_probs = {
            "home_win": round(home_win_prob, 3),
            "draw": round(draw_prob, 3),
            "away_win": round(away_win_prob, 3),
        }

        return true_probs, factors

    # =========================================================================
    # FACTOR SCORING — all return values in [-1.0, +1.0]
    # Positive = home team has the advantage
    # =========================================================================

    def _score_form(self, home_team: str, away_team: str, league: str) -> float:
        """Recent form — weighted points (W=3, D=1, L=0) over last 5 home/away games."""
        home_form = self.data_fetcher.get_team_form(home_team, league, venue="HOME")
        away_form = self.data_fetcher.get_team_form(away_team, league, venue="AWAY")

        def points(form):
            return sum(3 if r == "W" else 1 if r == "D" else 0 for r in form)

        max_pts = len(home_form) * 3 or 1
        home_norm = (points(home_form) / max_pts) * 2 - 1
        away_norm = (points(away_form) / max(len(away_form) * 3, 1)) * 2 - 1

        return float(max(-1.0, min(1.0, home_norm - away_norm)))

    def _score_h2h(self, home_team: str, away_team: str, league: str) -> float:
        """Head-to-head historical record."""
        results = self.data_fetcher.get_h2h(home_team, away_team, league)
        if not results:
            return 0.0

        home_wins = sum(1 for r in results if r == "HOME")
        away_wins = sum(1 for r in results if r == "AWAY")
        total = len(results)
        return float(max(-1.0, min(1.0, (home_wins - away_wins) / total)))

    def _score_injuries(self, home_team: str, away_team: str, league: str) -> float:
        """
        Relative injury impact.
        Each injury reduces a team's effective strength by 0.07 (moderate/minor)
        or 0.15 (severe). Positive = home team less injured.
        """
        home_injuries = self.data_fetcher.get_injuries(home_team, league)
        away_injuries = self.data_fetcher.get_injuries(away_team, league)

        severity_weights = {"severe": 0.15, "moderate": 0.07, "minor": 0.03}

        def impact(injuries):
            return sum(severity_weights.get(i.get("severity", "minor"), 0.03) for i in injuries)

        home_impact = impact(home_injuries)
        away_impact = impact(away_injuries)
        return float(max(-1.0, min(1.0, away_impact - home_impact)))

    def _score_position(self, home_team: str, away_team: str, league: str) -> float:
        """League table position — normalised to [0, 1], then differenced."""
        home_pos = self.data_fetcher.get_table_position(home_team, league)
        away_pos = self.data_fetcher.get_table_position(away_team, league)
        max_teams = 20
        home_score = 1.0 - (home_pos / max_teams)
        away_score = 1.0 - (away_pos / max_teams)
        return float(max(-1.0, min(1.0, (home_score - away_score) * 2)))

    def _score_rest(self, home_team: str, away_team: str, league: str) -> float:
        """
        Rest days advantage based on days since last match.
        Currently uses mock rest values; real implementation would look up
        last match date from the data fetcher.
        Score per team: 0.0 (<=2 days) → 1.0 (>=5 days), linear in between.
        """
        # In real mode, derive from last match date; in mock mode use team hash
        home_rest = self._estimate_rest_days(home_team, league)
        away_rest = self._estimate_rest_days(away_team, league)

        def rest_score(days: int) -> float:
            if days >= 5:
                return 1.0
            if days <= 2:
                return 0.0
            return (days - 2) / 3.0

        return float(max(-1.0, min(1.0, rest_score(home_rest) - rest_score(away_rest))))

    def _estimate_rest_days(self, team: str, league: str) -> int:
        """
        Returns estimated rest days for a team.
        In future: derive from last match timestamp via data_fetcher.
        """
        import hashlib
        seed = int(hashlib.md5(f"{team}{league}rest".encode()).hexdigest(), 16) % 7
        return 2 + seed  # 2–8 days range

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _generate_match_id(self, home_team: str, away_team: str, league: str) -> str:
        """Generate unique match ID from team names, league and current date."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        import re

        def team_code(team_name: str) -> str:
            if not team_name:
                return "UNK"

            cleaned = re.sub(r"[^A-Za-z\s]", " ", str(team_name))
            tokens = [t for t in cleaned.upper().split() if t]
            stop = {
                "FC",
                "CF",
                "SC",
                "AC",
                "AS",
                "CD",
                "CA",
                "RC",
                "UD",
                "AFC",
                "FK",
                "SK",
                "SV",
                "BV",
                "VFL",
                "VFB",
                "DE",
                "LA",
                "EL",
                "LOS",
                "LAS",
            }

            core = None
            for t in tokens:
                if t not in stop:
                    core = t
                    break
            core = core or (tokens[0] if tokens else "UNK")

            letters = re.sub(r"[^A-Z]", "", core)
            if not letters:
                return "UNK"
            return letters[:3]

        home_abbr = team_code(home_team)
        away_abbr = team_code(away_team)
        return f"{league}-{home_abbr}-{away_abbr}-{date_str}"
