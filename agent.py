import time
import schedule
from datetime import datetime, timedelta
from data_fetcher import DataFetcher
from prediction_engine import PredictionEngine
from models import PredictionDatabase, Prediction
import requests
import os
from dotenv import load_dotenv

load_dotenv()


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
        self.db = PredictionDatabase()

        self.mock_mode = os.getenv("MOCK_MODE", "True").lower() == "true"

        # Backend API URL (for recording on-chain)
        self.backend_url = backend_url or os.getenv(
            "BACKEND_URL", "http://localhost:5000"
        )

        # Agent configuration
        self.prediction_window_hours = 24  # Predict matches within next 24 hours
        self.check_interval_minutes = 60  # Check for new matches every hour

        print("🤖 FootyOracle Agent initialized")
        print(f"   Backend: {self.backend_url}")
        print(f"   Prediction window: {self.prediction_window_hours}h")
        print(f"   Check interval: {self.check_interval_minutes}m")

    def run_prediction_cycle(self):
        """
        Main agent cycle:
        1. Fetch upcoming matches
        2. Generate predictions
        3. Record predictions
        """

        print("\n" + "=" * 60)
        print(
            f"🤖 Agent Cycle Started - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        print("=" * 60)

        try:
            # Get upcoming matches for all leagues
            leagues = (
                ["EPL", "LaLiga", "SerieA", "Bundesliga", "Ligue1"]
                if self.mock_mode
                else ["EPL", "LaLiga"]
            )
            total_predictions = 0

            for league in leagues:
                predictions_made = self._predict_league_matches(league)
                total_predictions += predictions_made

            print(f"\n✅ Cycle complete: {total_predictions} new predictions made")

        except Exception as e:
            print(f"❌ Error in prediction cycle: {e}")

    def _predict_league_matches(self, league: str) -> int:
        """
        Generate predictions for a specific league

        Returns:
            Number of predictions made
        """

        print(f"\n🔍 Checking {league} matches...")

        # Fetch upcoming matches
        matches = self.data_fetcher.get_league_matches(league)

        if not matches:
            print("   No upcoming matches found")
            return 0

        predictions_made = 0

        for match in matches:
            # Check if match is within prediction window
            if not self._should_predict_match(match):
                continue

            # Check if we already predicted this match
            match_id = self._generate_match_id(match, league)
            if self._already_predicted(match_id):
                continue

            # Generate prediction
            try:
                prediction = self._generate_prediction(match, league)

                # Record prediction (local + backend)
                self._record_prediction(prediction)

                predictions_made += 1

                print(f"   ✅ {match['homeTeam']} vs {match['awayTeam']}")
                print(
                    f"      Prediction: {prediction['prediction']} ({prediction['confidence']:.1%})"
                )

            except Exception as e:
                print(
                    f"   ❌ Error predicting {match['homeTeam']} vs {match['awayTeam']}: {e}"
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
        """Check if we already have a prediction for this match"""

        # Check local database
        if self.db.get_prediction_by_match_id(match_id):
            return True

        # Check backend (optional)
        try:
            response = requests.get(f"{self.backend_url}/api/predictions")
            if response.status_code == 200:
                predictions = response.json().get("predictions", [])
                return any(p["matchId"] == match_id for p in predictions)
        except Exception:
            pass

        return False

    def _generate_match_id(self, match: dict, league: str) -> str:
        """Generate match ID from match data"""

        home_abbr = match["homeTeam"][:3].upper()
        away_abbr = match["awayTeam"][:3].upper()
        date_str = match["date"]

        return f"{league}-{home_abbr}-{away_abbr}-{date_str}"

    def _generate_prediction(self, match: dict, league: str) -> dict:
        """Generate prediction for a match"""

        prediction = self.prediction_engine.predict(
            home_team=match["homeTeam"], away_team=match["awayTeam"], league=league
        )

        return prediction

    def _record_prediction(self, prediction_data: dict):
        """
        Record prediction in local DB and send to backend
        """

        # Save locally
        prediction = Prediction(
            match_id=prediction_data["matchId"],
            predicted_outcome=prediction_data["prediction"],
            confidence=prediction_data["confidence"],
            factors=prediction_data["factors"],
            timestamp=prediction_data["timestamp"],
        )

        self.db.add_prediction(prediction)

        # Send to backend API (which will record on-chain)
        try:
            response = requests.post(
                f"{self.backend_url}/api/predict",
                json={
                    "matchId": prediction_data["matchId"],
                    "prediction": prediction_data["prediction"],
                    "confidence": prediction_data["confidence"],
                    "factors": prediction_data["factors"],
                    "timestamp": prediction_data["timestamp"],
                },
            )

            if response.status_code == 201:
                print("      📝 Recorded on-chain")
            else:
                print(f"      ⚠️  Backend recording failed: {response.status_code}")

        except Exception as e:
            print(f"      ⚠️  Backend unreachable: {e}")

    def run_resolution_cycle(self):
        """
        Resolve pending predictions:
        1. Fetch actual match results
        2. Compare with predictions
        3. Update records
        """

        print("\n" + "=" * 60)
        print(
            f"🔍 Resolution Cycle Started - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        print("=" * 60)

        try:
            unresolved = self.db.get_unresolved_predictions()

            if not unresolved:
                print("   No pending predictions to resolve")
                return

            print(f"   Found {len(unresolved)} pending predictions")

            resolved_count = 0

            for prediction in unresolved:
                # Fetch actual result
                actual_outcome = self.data_fetcher.get_match_result(prediction.match_id)

                if actual_outcome:
                    # Resolve locally
                    is_correct = prediction.predicted_outcome == actual_outcome
                    self.db.resolve_prediction(
                        prediction.prediction_id, actual_outcome, is_correct
                    )

                    # Resolve on backend
                    try:
                        requests.post(
                            f"{self.backend_url}/api/resolve",
                            json={
                                "matchId": prediction.match_id,
                                "actualOutcome": actual_outcome,
                            },
                        )
                    except Exception:
                        pass

                    status = "✅ CORRECT" if is_correct else "❌ INCORRECT"
                    print(f"   {status} - {prediction.match_id}")

                    resolved_count += 1

            print(f"\n✅ Resolved {resolved_count} predictions")

            # Print accuracy stats
            stats = self.db.get_statistics()
            print(f"   Current accuracy: {stats['accuracy']:.1f}%")

        except Exception as e:
            print(f"❌ Error in resolution cycle: {e}")

    def run_scheduled(self):
        """
        Run agent on a schedule:
        - Prediction cycle every hour
        - Resolution cycle every 6 hours
        """

        print("\n🤖 Starting FootyOracle Agent in scheduled mode...")
        print("   Press Ctrl+C to stop")
        print()

        # Schedule prediction cycle
        schedule.every(self.check_interval_minutes).minutes.do(
            self.run_prediction_cycle
        )

        # Schedule resolution cycle (every 6 hours)
        schedule.every(6).hours.do(self.run_resolution_cycle)

        # Run immediately on start
        self.run_prediction_cycle()

        # Keep running
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

    def run_once(self):
        """
        Run agent once (for testing or cron jobs)
        """

        print("\n🤖 Running FootyOracle Agent (single cycle)...")

        # Run prediction cycle
        self.run_prediction_cycle()

        # Run resolution cycle
        self.run_resolution_cycle()

        print("\n✅ Agent cycle complete")


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
