from datetime import datetime
from typing import List, Optional, Dict
import json
import os
import threading
import psycopg

class Prediction:
    """Prediction model for football matches."""

    def __init__(self, match_id: str, predicted_outcome: str, confidence: float, factors: dict, timestamp: int, prediction_id: str = None):
        self.prediction_id = prediction_id or self.generate_prediction_id()
        self.match_id = match_id
        self.predicted_outcome = predicted_outcome
        self.confidence = confidence
        self.factors = factors
        self.timestamp = timestamp

        # Resolution fields
        self.resolved = False
        self.actual_outcome = None
        self.correct = None
        self.resolution_timestamp = None

    def to_dict(self) -> dict:
        """Convert the prediction to a dictionary."""
        return {
            "predictionId": self.prediction_id,
            "matchId": self.match_id,
            "prediction": self.predicted_outcome,
            "predictedOutcome": self.predicted_outcome,
            "confidence": self.confidence,
            "factors": self.factors,
            "timestamp": self.timestamp,
            "resolved": self.resolved,
            "actualOutcome": self.actual_outcome,
            "correct": self.correct,
            "resolutionTimestamp": self.resolution_timestamp,
            "prediction_id": self.prediction_id,
            "match_id": self.match_id,
            "predicted_outcome": self.predicted_outcome,
            "actual_outcome": self.actual_outcome,
            "resolution_timestamp": self.resolution_timestamp,
        }

    def __repr__(self):
        return f"Prediction({self.match_id}, {self.predicted_outcome}, {self.confidence:.2f})"

    @staticmethod
    def generate_prediction_id() -> str:
        """Generate a unique prediction ID."""
        return f"offchain-{int(datetime.now().timestamp())}"

    def to_json(self) -> str:
        """Serialize the predictions to JSON."""
        return json.dumps(self.to_dict(), indent=4)

class PredictionDatabase:
    """
    In-memory database for storing predictions.
    Can be replaced with SQLite or PostgreSQL later
    """

    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL", "").strip()
        if not self.database_url:
            raise RuntimeError(
                "DATABASE_URL is required (PostgreSQL). Set DATABASE_URL in your environment."
            )

        import psycopg
        from psycopg.rows import dict_row

        self._conn = psycopg.connect(self.database_url, row_factory=dict_row)

        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self):
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS predictions (
                    prediction_id TEXT PRIMARY KEY,
                    match_id TEXT NOT NULL,
                    predicted_outcome TEXT NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL,
                    factors_json JSONB NOT NULL,
                    timestamp BIGINT NOT NULL,
                    resolved BOOLEAN NOT NULL DEFAULT FALSE,
                    actual_outcome TEXT,
                    correct BOOLEAN,
                    resolution_timestamp BIGINT
                )
                """
            )
            try:
                cur.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_predictions_match_id ON predictions(match_id)"
                )
            except psycopg.Error:
                pass
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_predictions_match_id ON predictions(match_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_predictions_resolved ON predictions(resolved)"
            )

            self._conn.commit()

    def _row_to_prediction(self, row) -> Prediction:
        pred = Prediction(
            match_id=row["match_id"],
            predicted_outcome=row["predicted_outcome"],
            confidence=row["confidence"],
            factors=row["factors_json"],
            timestamp=row["timestamp"],
            prediction_id=row["prediction_id"],
        )
        pred.resolved = bool(row["resolved"])
        pred.actual_outcome = row["actual_outcome"]
        pred.correct = None if row["correct"] is None else bool(row["correct"])
        pred.resolution_timestamp = row["resolution_timestamp"]
        return pred

    def add_prediction(self, prediction: Prediction) -> str:
        """
        Add new prediction to database

        Args:
            prediction: Prediction object

        Returns:
            prediction_id
        """

        if not prediction.prediction_id:
            prediction.prediction_id = prediction.generate_prediction_id()

        with self._lock:
            cur = self._conn.cursor()
            if prediction.correct is None:
                correct_value = None
            else:
                correct_value = bool(prediction.correct)

            cur.execute(
                """
                INSERT INTO predictions (
                    prediction_id,
                    match_id,
                    predicted_outcome,
                    confidence,
                    factors_json,
                    timestamp,
                    resolved,
                    actual_outcome,
                    correct,
                    resolution_timestamp
                ) VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
                ON CONFLICT (match_id) DO UPDATE SET
                    predicted_outcome = EXCLUDED.predicted_outcome,
                    confidence = EXCLUDED.confidence,
                    factors_json = EXCLUDED.factors_json,
                    timestamp = EXCLUDED.timestamp
                WHERE predictions.resolved = FALSE
                RETURNING prediction_id
                """,
                (
                    prediction.prediction_id,
                    prediction.match_id,
                    prediction.predicted_outcome,
                    float(prediction.confidence),
                    json.dumps(prediction.factors),
                    int(prediction.timestamp),
                    bool(prediction.resolved),
                    prediction.actual_outcome,
                    correct_value,
                    prediction.resolution_timestamp,
                ),
            )

            row = cur.fetchone()
            if row is None:
                cur.execute(
                    "SELECT prediction_id FROM predictions WHERE match_id = %s",
                    (prediction.match_id,),
                )
                row = cur.fetchone()

            self._conn.commit()

        return row["prediction_id"]

    # =========================================================================
    # READ
    # =========================================================================

    def get_prediction(self, prediction_id: str) -> Optional[Prediction]:
        """Get prediction by its ID."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT * FROM predictions WHERE prediction_id = %s", (prediction_id,)
        )
        row = cur.fetchone()
        return self._row_to_prediction(row) if row else None

    def get_prediction_by_match_id(self, match_id: str) -> Optional[Prediction]:
        """Get prediction by match ID."""
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM predictions WHERE match_id = %s", (match_id,))
        row = cur.fetchone()
        return self._row_to_prediction(row) if row else None

    def get_all_predictions(self) -> List[Prediction]:
        """Get all predictions in the database."""
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM predictions ORDER BY timestamp DESC")
        rows = cur.fetchall()
        return [self._row_to_prediction(r) for r in rows]

    def get_unresolved_predictions(self) -> List[Prediction]:
        """Get all unresolved predictions."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT * FROM predictions WHERE resolved = FALSE ORDER BY timestamp DESC"
        )
        rows = cur.fetchall()
        return [self._row_to_prediction(r) for r in rows]

    def get_predictions_by_league(self, league: str) -> List[Prediction]:
        """Get predictions for a specific league."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT * FROM predictions WHERE match_id LIKE %s ORDER BY timestamp DESC",
            (f"{league}%",),
        )
        rows = cur.fetchall()
        return [self._row_to_prediction(r) for r in rows]

    # =========================================================================
    # UPDATE
    # =========================================================================

    def resolve_prediction(
        self, prediction_id: str, actual_outcome: str, correct: bool
    ) -> bool:
        """
        Resolve a prediction with actual result

        Args:
            prediction_id: ID of prediction to resolve
            actual_outcome: Actual match outcome
            correct: Whether prediction was correct

        Returns:
            True if successful, False if not found
        """

        resolution_timestamp = int(datetime.now().timestamp())

        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                UPDATE predictions
                SET resolved = TRUE,
                    actual_outcome = %s,
                    correct = %s,
                    resolution_timestamp = %s
                WHERE prediction_id = %s
                """,
                (
                    actual_outcome,
                    bool(correct),
                    resolution_timestamp,
                    prediction_id,
                ),
            )
            self._conn.commit()

        return cur.rowcount > 0

    # =========================================================================
    # DELETE
    # =========================================================================

    def delete_prediction(self, prediction_id: str) -> bool:
        """Delete a prediction by its ID."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "DELETE FROM predictions WHERE prediction_id = %s",
                (prediction_id,),
            )
            self._conn.commit()
        return cur.rowcount > 0

    def clear_all(self):
        """
        Clear all predictions (use with caution!)
        """
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("DELETE FROM predictions")
            self._conn.commit()

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_statistics(self) -> dict:
        """
        Get overall statistics

        Returns:
            {
                "totalPredictions": 100,
                "resolved": 80,
                "pending": 20,
                "correct": 54,
                "incorrect": 26,
                "accuracy": 67.5
            }
        """

        cur = self._conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM predictions")
        total = int(cur.fetchone()["c"])

        cur.execute("SELECT COUNT(*) AS c FROM predictions WHERE resolved = TRUE")
        resolved = int(cur.fetchone()["c"])
        pending = total - resolved

        cur.execute(
            "SELECT COUNT(*) AS c FROM predictions WHERE resolved = TRUE AND correct = TRUE"
        )
        correct = int(cur.fetchone()["c"])
        incorrect = resolved - correct

        accuracy = (correct / resolved * 100) if resolved > 0 else 0.0

        return {
            "totalPredictions": total,
            "resolved": resolved,
            "pending": pending,
            "correct": correct,
            "incorrect": incorrect,
            "accuracy": round(accuracy, 1),
        }

    def get_league_statistics(self, league: str) -> dict:
        """Get statistics for specific league"""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS c FROM predictions WHERE match_id LIKE %s",
            (f"{league}%",),
        )
        total = int(cur.fetchone()["c"])

        cur.execute(
            "SELECT COUNT(*) AS c FROM predictions WHERE match_id LIKE %s AND resolved = TRUE",
            (f"{league}%",),
        )
        resolved = int(cur.fetchone()["c"])

        cur.execute(
            """
            SELECT COUNT(*) AS c
            FROM predictions
            WHERE match_id LIKE %s AND resolved = TRUE AND correct = TRUE
            """,
            (f"{league}%",),
        )
        correct = int(cur.fetchone()["c"])
        accuracy = (correct / resolved * 100) if resolved > 0 else 0.0

        return {
            "league": league,
            "totalPredictions": total,
            "resolved": resolved,
            "pending": total - resolved,
            "correct": correct,
            "incorrect": resolved - correct,
            "accuracy": round(accuracy, 1),
        }

    # =========================================================================
    # PERSISTENCE (Optional - for saving to file)
    # =========================================================================

    def save_to_file(self, filename: str = "predictions.json"):
        """Save predictions to JSON file"""
        predictions = self.get_all_predictions()
        data = {
            "predictions": [p.to_dict() for p in predictions],
        }

        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

        print(f"✅ Saved {len(predictions)} predictions to {filename}")

    def load_from_file(self, filename: str = "predictions.json"):
        """Load predictions from JSON file"""
        try:
            with open(filename, "r") as f:
                data = json.load(f)

            for pred_dict in data["predictions"]:
                match_id = pred_dict.get("matchId") or pred_dict.get("match_id")
                predicted_outcome = pred_dict.get("prediction") or pred_dict.get(
                    "predictedOutcome"
                ) or pred_dict.get("predicted_outcome")
                prediction_id = pred_dict.get("predictionId") or pred_dict.get(
                    "prediction_id"
                )
                actual_outcome = pred_dict.get("actualOutcome") or pred_dict.get(
                    "actual_outcome"
                )
                resolution_ts = pred_dict.get("resolutionTimestamp") or pred_dict.get(
                    "resolution_timestamp"
                )

                pred = Prediction(
                    match_id=match_id,
                    predicted_outcome=predicted_outcome,
                    confidence=pred_dict["confidence"],
                    factors=pred_dict["factors"],
                    timestamp=pred_dict["timestamp"],
                    prediction_id=prediction_id,
                )
                pred.resolved = pred_dict["resolved"]
                pred.actual_outcome = actual_outcome
                pred.correct = pred_dict["correct"]
                pred.resolution_timestamp = resolution_ts

                self.add_prediction(pred)

            print(
                f"✅ Loaded {len(data.get('predictions', []))} predictions from {filename}"
            )

        except FileNotFoundError:
            print(f"⚠️  File {filename} not found, starting with empty database")
        except Exception as e:
            print(f"❌ Error loading file: {e}")
