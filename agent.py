import time
import logging
import schedule
from datetime import datetime, timedelta
from data_fetcher import DataFetcher
from prediction_engine import PredictionEngine
from models import PredictionDatabase, Prediction
import requests
import os
import re
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class FootyOracleAgent:
    """
    Autonomous AI agent that:
    1. Fetches upcoming matches
    2. Generates predictions automatically
    3. Records predictions on-chain (via backend API)
    4. Monitors match results
    5. Resolves predictions automatically
    """

    def __init__(self, backend_url=None):
        self.data_fetcher = DataFetcher()
        self.prediction_engine = PredictionEngine()
        self.db = None
        try:
            self.db = PredictionDatabase()
        except RuntimeError:
            self.db = None

        self.mock_mode = os.getenv("MOCK_MODE", "True").lower() == "true"

        # Backend API URL (for resolving via REST when no local DB)
        self.backend_url = backend_url or os.getenv(
            "BACKEND_URL", "http://localhost:5000"
        )

        # Load Discord bot if configured
        self._discord_bot = None
        try:
            from discord_bot import FootyOracleDiscordBot
            discord_token = os.getenv("DISCORD_TOKEN", "")
            if discord_token:
                self._discord_bot = FootyOracleDiscordBot(self.backend_url)
        except ImportError:
            pass

        # Agent configuration
        self.prediction_window_hours = 24
        self.check_interval_minutes = 60

        logger.info(
            "FootyOracle Agent initialized | backend=%s | window=%dh | interval=%dm",
            self.backend_url,
            self.prediction_window_hours,
            self.check_interval_minutes,
        )

    def run_prediction_cycle(self):
        """
        Main agent cycle:
        1. Fetch upcoming matches
        2. Generate predictions
        3. Record predictions
        """

        logger.info(
            "=== Agent Prediction Cycle Started [%s] ===",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        try:
            leagues = ["EPL", "LaLiga", "SerieA", "Bundesliga", "Ligue1"]
            total_predictions = 0

            for league in leagues:
                predictions_made = self._predict_league_matches(league)
                total_predictions += predictions_made

            logger.info("Cycle complete: %d new predictions made", total_predictions)

        except Exception as e:
            logger.error("Error in prediction cycle: %s", e, exc_info=True)

    def _predict_league_matches(self, league: str) -> int:
        """
        Generate predictions for a specific league

        Returns:
            Number of predictions made
        """

        logger.info("Checking %s matches...", league)

        matches = self.data_fetcher.get_league_matches(league)

        if not matches:
            logger.debug("No upcoming matches found for %s", league)
            return 0

        predictions_made = 0

        for match in matches:
            if not self._should_predict_match(match):
                continue

            match_id = self._generate_match_id(match, league)
            if self._already_predicted(match_id):
                continue

            try:
                prediction = self._generate_prediction(match, league, match_id)
                self._record_prediction(prediction, match, league)
                predictions_made += 1
                logger.info(
                    "Predicted: %s vs %s → %s (conf=%.1f%%, edge=%.1f%%)",
                    match["homeTeam"],
                    match["awayTeam"],
                    prediction["prediction"],
                    prediction["confidence"] * 100,
                    prediction.get("edge", 0) * 100,
                )

            except RuntimeError as e:
                # No value bet — not an error, just no pick for this match
                logger.debug(
                    "No value bet for %s vs %s: %s",
                    match.get("homeTeam"),
                    match.get("awayTeam"),
                    e,
                )

            except Exception as e:
                logger.error(
                    "Error predicting %s vs %s: %s",
                    match.get("homeTeam"),
                    match.get("awayTeam"),
                    e,
                    exc_info=True,
                )

        return predictions_made

    def _should_predict_match(self, match: dict) -> bool:
        """Check if match is within prediction window"""

        try:
            # Parse match date and time if available
            match_date_str = match["date"]
            match_time_str = match.get("time", "12:00")

            # Combine date and time
            match_datetime_str = f"{match_date_str} {match_time_str}"
            match_datetime = datetime.strptime(match_datetime_str, "%Y-%m-%d %H:%M")

            now = datetime.now()
            hours_until_match = (match_datetime - now).total_seconds() / 3600

            # Predict if match is within window (including matches happening soon)
            # Allow predictions up to 2 hours before match starts
            return -2 <= hours_until_match <= self.prediction_window_hours

        except Exception:
            # Fallback to date-only comparison
            try:
                match_date = datetime.strptime(match["date"], "%Y-%m-%d")
                now = datetime.now()
                hours_until_match = (match_date - now).total_seconds() / 3600

                return -24 <= hours_until_match <= self.prediction_window_hours
            except Exception:
                return False

    def _already_predicted(self, match_id: str) -> bool:
        """
        Check if we already have a prediction for this match.
        Uses direct DB lookup (O(1)) instead of scanning the full predictions list.
        """
        if self.db and self.db.get_prediction_by_match_id(match_id):
            return True
        return False

    def _generate_match_id(self, match: dict, league: str) -> str:
        """Generate match ID from match data"""

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

        home_abbr = team_code(match.get("homeTeam", ""))
        away_abbr = team_code(match.get("awayTeam", ""))
        date_str = match["date"]

        fixture_id = match.get("fixtureId")
        if fixture_id is not None and str(fixture_id).isdigit():
            return f"{league}-{int(fixture_id)}-{home_abbr}-{away_abbr}-{date_str}"

        return f"{league}-{home_abbr}-{away_abbr}-{date_str}"

    def _generate_prediction(self, match: dict, league: str, match_id: str) -> dict:
        """Generate prediction for a match"""

        prediction = self.prediction_engine.predict(
            home_team=match["homeTeam"],
            away_team=match["awayTeam"],
            league=league,
            match_id=match_id,
        )

        return prediction

    def _record_prediction(self, prediction_data: dict, match: dict = None, league: str = ""):
        """Record prediction in local DB and send to backend API."""

        # Derive league: use explicit param if available, fall back to matchId prefix
        resolved_league = league or (prediction_data.get("matchId", "-").split("-")[0] if prediction_data.get("matchId") else "")

        # Save locally
        if self.db:
            prediction = Prediction(
                match_id=prediction_data["matchId"],
                predicted_outcome=prediction_data["prediction"],
                confidence=prediction_data["confidence"],
                factors=prediction_data["factors"],
                timestamp=prediction_data["timestamp"],
                league=resolved_league,
            )
            self.db.add_prediction(prediction)

        # Send to backend API
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                # Build payload — include homeTeam/awayTeam/league so that
                # _validate_prediction_request passes AND so the precomputed
                # shortcut in create_prediction can also use them (e.g. blockchain).
                home_team = (match or {}).get("homeTeam", "")
                away_team = (match or {}).get("awayTeam", "")
                match_date = (match or {}).get("date")
                match_time = (match or {}).get("time")
                response = requests.post(
                    f"{self.backend_url}/api/predict",
                    json={
                        "matchId": prediction_data["matchId"],
                        "prediction": prediction_data["prediction"],
                        "confidence": prediction_data["confidence"],
                        "factors": prediction_data["factors"],
                        "timestamp": prediction_data["timestamp"],
                        "homeTeam": home_team,
                        "awayTeam": away_team,
                        "league": resolved_league,
                        "date": match_date,
                        "time": match_time,
                    },
                    timeout=10,
                )

                if response.status_code in (200, 201):
                    logger.info("Prediction recorded via backend API")
                    break
                else:
                    logger.warning(
                        "Backend recording failed (attempt %d/%d): HTTP %d",
                        attempt, max_retries, response.status_code,
                    )

            except requests.exceptions.RequestException as e:
                logger.warning(
                    "Backend unreachable (attempt %d/%d): %s",
                    attempt, max_retries, e,
                )

            if attempt < max_retries:
                time.sleep(2 ** attempt)  # Exponential backoff

        # Send Discord alert if bot is configured
        if self._discord_bot and match:
            try:
                self._discord_bot.send_prediction_alert_sync(
                    match=match,
                    prediction=prediction_data["prediction"],
                    confidence=prediction_data["confidence"],
                    edge=prediction_data.get("edge", 0),
                    factors=prediction_data.get("factors", {}),
                )
            except Exception as e:
                logger.warning("Discord alert failed: %s", e)

    def _auto_resolve_via_backend(self) -> None:
        max_loops = 30
        batch_size = 5
        time_budget_seconds = 15
        loops = 0
        total_resolved = 0

        while loops < max_loops:
            loops += 1
            try:
                response = requests.post(
                    f"{self.backend_url}/api/resolve/auto",
                    params={
                        "max": str(batch_size),
                        "timeBudgetSeconds": str(time_budget_seconds),
                    },
                    timeout=30,
                )
            except Exception as e:
                logger.error("Error in resolution cycle: %s", e)
                return

            if response.status_code != 200:
                logger.error(
                    "Backend auto-resolve failed: HTTP %d",
                    response.status_code,
                )
                return

            payload = response.json()
            batch_resolved = int(payload.get("resolved", 0))
            remaining = int(payload.get("remaining", 0))
            processed = int(payload.get("processed", 0))
            total_resolved += batch_resolved

            logger.info(
                "Auto-resolve batch: processed=%d, resolved=%d, remaining=%d",
                processed, batch_resolved, remaining,
            )

            if remaining <= 0:
                break
            if processed <= 0:
                logger.info("Auto-resolve made no progress; stopping")
                break

            time.sleep(1)

        logger.info("Auto-resolve completed: total resolved=%d", total_resolved)

    def run_resolution_cycle(self):
        """
        Resolve pending predictions:
        1. Fetch actual match results
        2. Compare with predictions
        3. Update records
        """

        logger.info(
            "=== Resolution Cycle Started [%s] ===",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        try:
            if not self.db:
                self._auto_resolve_via_backend()
                return

            unresolved = self.db.get_unresolved_predictions()

            if not unresolved:
                logger.info("No pending predictions to resolve")
                return

            logger.info("Found %d pending predictions", len(unresolved))

            resolved_count = 0

            for prediction in unresolved:
                actual_outcome = self.data_fetcher.get_match_result(prediction.match_id)

                if actual_outcome:
                    is_correct = prediction.predicted_outcome == actual_outcome
                    self.db.resolve_prediction(
                        prediction.prediction_id, actual_outcome, is_correct
                    )

                    try:
                        requests.post(
                            f"{self.backend_url}/api/resolve",
                            json={
                                "matchId": prediction.match_id,
                                "actualOutcome": actual_outcome,
                            },
                            timeout=10,
                        )
                    except Exception as e:
                        logger.warning("Backend resolve notify failed: %s", e)

                    logger.info(
                        "%s — %s (predicted=%s, actual=%s)",
                        "CORRECT" if is_correct else "INCORRECT",
                        prediction.match_id,
                        prediction.predicted_outcome,
                        actual_outcome,
                    )
                    resolved_count += 1

            logger.info("Resolved %d predictions", resolved_count)
            stats = self.db.get_statistics()
            logger.info("Current accuracy: %.1f%%", stats["accuracy"])

        except Exception as e:
            logger.error("Error in resolution cycle: %s", e, exc_info=True)

    def run_scheduled(self):
        """Run agent on a schedule (prediction every hour, resolution every 6h)."""
        logger.info("Starting FootyOracle Agent in scheduled mode. Press Ctrl+C to stop.")

        schedule.every(self.check_interval_minutes).minutes.do(self.run_prediction_cycle)
        schedule.every(6).hours.do(self.run_resolution_cycle)

        # Run immediately on start
        self.run_prediction_cycle()

        while True:
            schedule.run_pending()
            time.sleep(60)

    def run_once(self):
        """Run agent once (for testing or cron jobs)."""
        logger.info("Running FootyOracle Agent (single cycle)")
        self.run_prediction_cycle()
        self.run_resolution_cycle()
        logger.info("Agent cycle complete")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import sys

    # Parse command line arguments
    mode = sys.argv[1] if len(sys.argv) > 1 else "once"

    # Initialize agent
    agent = FootyOracleAgent()

    if mode == "schedule":
        # Run continuously on schedule
        agent.run_scheduled()

    elif mode == "predict":
        # Only run prediction cycle
        agent.run_prediction_cycle()

    elif mode == "resolve":
        # Only run resolution cycle
        agent.run_resolution_cycle()

    else:
        # Run once (default)
        agent.run_once()
