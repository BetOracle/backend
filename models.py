from datetime import datetime
from typing import List, Optional, Dict
import json

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
            "prediction_id": self.prediction_id,
            "match_id": self.match_id,
            "predicted_outcome": self.predicted_outcome,
            "confidence": self.confidence,
            "factors": self.factors,
            "timestamp": self.timestamp,
            "resolved": self.resolved,
            "actual_outcome": self.actual_outcome,
            "correct": self.correct,
            "resolution_timestamp": self.resolution_timestamp
        }

    def __repr__(self):
        return f"Prediction({self.match_id}, {self.predicted_outcome}, {self.confidence:.2f})"

    @staticmethod
    def generate_prediction_id() -> str:
        """Generate a unique prediction ID."""
        return f"offchain-{int(datetime.now().timestamp())}"

    def to_json(self) -> str:
        """Serialize the predictions to JSON."""
        return json.dumps(
            {pid: pred.to_dict() for pid, pred in self.predictions.items()}, indent=4
        )

class PredictionDatabase:
    """
    In-memory database for storing predictions.
    Can be replaced with SQLite or PostgreSQL later
    """

    def __init__(self):
        self.predictions: List[Prediction] = []
        self._id_counter = 1

    def add_prediction(self, prediction: Prediction) -> str:
        """
        Add new prediction to database

        Args:
            prediction: Prediction object

        Returns:
            prediction_id
        """

        # Assign ID if not set
        if not prediction.prediction_id:
            prediction.prediction_id = f"offchain-{self._id_counter}"
            self._id_counter += 1

        self.predictions.append(prediction)

        return prediction.prediction_id

    # =========================================================================
    # READ
    # =========================================================================

    def get_prediction(self, prediction_id: str) -> Optional[Prediction]:
        """Get prediction by its ID."""
        for pred in self.predictions:
            if pred.prediction_id == prediction_id:
                return pred
        return None

    def get_prediction_by_match_id(self, match_id: str) -> Optional[Prediction]:
        """Get prediction by match ID."""
        for pred in self.predictions:
            if pred.match_id == match_id:
                return pred
        return None

    def get_all_predictions(self) -> List[Prediction]:
        """Get all predictions in the database."""
        return self.predictions.copy()

    def get_unresolved_predictions(self) -> List[Prediction]:
        """Get all unresolved predictions."""
        return [p for p in self.predictions if not p.resolved]

    def get_predictions_by_league(self, league: str) -> List[Prediction]:
        """Get predictions for a specific league."""
        return [p for p in self.predictions if league in p.match_id]

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

        prediction = self.get_prediction(prediction_id)

        if not prediction:
            return False

        prediction.resolved = True
        prediction.actual_outcome = actual_outcome
        prediction.correct = correct
        prediction.resolution_timestamp = int(datetime.now().timestamp())

        return True

    # =========================================================================
    # DELETE
    # =========================================================================

    def delete_prediction(self, prediction_id: str) -> bool:
        """Delete a prediction by its ID."""
        for i, pred in enumerate(self.predictions):
            if pred.prediction_id == prediction_id:
                self.predictions.pop(i)
                return True
        return False

    def clear_all(self):
        """
        Clear all predictions (use with caution!)
        """
        self.predictions = []
        self._id_counter = 1

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

        total = len(self.predictions)
        resolved = sum(1 for p in self.predictions if p.resolved)
        pending = total - resolved
        correct = sum(1 for p in self.predictions if p.resolved and p.correct)
        incorrect = resolved - correct

        accuracy = (correct / resolved * 100) if resolved > 0 else 0.0

        return {
            "totalPredictions": total,
            "resolved": resolved,
            "pending": pending,
            "correct": correct,
            "incorrect": incorrect,
            "accuracy": round(accuracy, 1)
        }

    def get_league_statistics(self, league: str) -> dict:
        """Get statistics for specific league"""
        predictions = self.get_predictions_by_league(league)

        total = len(predictions)
        resolved = sum(1 for p in predictions if p.resolved)
        correct = sum(1 for p in predictions if p.resolved and p.correct)

        accuracy = (correct / resolved * 100) if resolved > 0 else 0.0

        return {
            "league": league,
            "totalPredictions": total,
            "resolved": resolved,
            "pending": total - resolved,
            "correct": correct,
            "incorrect": resolved - correct,
            "accuracy": round(accuracy, 1)
        }

    # =========================================================================
    # PERSISTENCE (Optional - for saving to file)
    # =========================================================================

    def save_to_file(self, filename: str = "predictions.json"):
        """Save predictions to JSON file"""
        data = {
            "predictions": [p.to_dict() for p in self.predictions],
            "id_counter": self._id_counter,
        }

        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

        print(f"✅ Saved {len(self.predictions)} predictions to {filename}")

    def load_from_file(self, filename: str = "predictions.json"):
        """Load predictions from JSON file"""
        try:
            with open(filename, "r") as f:
                data = json.load(f)

            self.predictions = []
            for pred_dict in data["predictions"]:
                pred = Prediction(
                    match_id=pred_dict["matchId"],
                    predicted_outcome=pred_dict["prediction"],
                    confidence=pred_dict["confidence"],
                    factors=pred_dict["factors"],
                    timestamp=pred_dict["timestamp"],
                    prediction_id=pred_dict["predictionId"],
                )
                pred.resolved = pred_dict["resolved"]
                pred.actual_outcome = pred_dict["actualOutcome"]
                pred.correct = pred_dict["correct"]
                pred.resolution_timestamp = pred_dict["resolutionTimestamp"]

                self.predictions.append(pred)

            self._id_counter = data.get("id_counter", len(self.predictions) + 1)

            print(f"✅ Loaded {len(self.predictions)} predictions from {filename}")

        except FileNotFoundError:
            print(f"⚠️  File {filename} not found, starting with empty database")
        except Exception as e:
            print(f"❌ Error loading file: {e}")
