import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import os
import time
from dotenv import load_dotenv

from data_fetcher import DataFetcher
from prediction_engine import PredictionEngine
from resolver import MatchResolver
from models import Prediction, PredictionDatabase

# Load environment variables
load_dotenv()

# Logging — respects LOG_LEVEL from .env (default INFO)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Shared DataFetcher — single instance so cache is shared across all components
_data_fetcher = DataFetcher()

# Initialize components (inject shared DataFetcher to avoid duplicate caches)
prediction_engine = PredictionEngine(data_fetcher=_data_fetcher)
resolver = MatchResolver()
db = PredictionDatabase()

logger.info("FootyOracle API initialized")

# ============================================================================
# PREDICTION ENDPOINTS
# ============================================================================


@app.route("/api/matches", methods=["GET"])
def get_upcoming_matches():
    try:
        league = request.args.get("league")
        if not league:
            return (
                jsonify({"success": False, "error": "Missing required query param: league"}),
                400,
            )

        try:
            days_ahead = int(request.args.get("daysAhead", "7"))
        except ValueError:
            days_ahead = 7

        matches = _data_fetcher.get_league_matches(
            league=league, days_ahead=days_ahead
        )

        return jsonify({"success": True, "league": league, "matches": matches}), 200

    except Exception as e:
        logger.error("Error in get_upcoming_matches: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/predict", methods=["POST"])
def create_prediction():
    """
    Create a new match prediction

    Input JSON:
    {
        "homeTeam": "Arsenal",
        "awayTeam": "Chelsea",
        "league": "EPL"
    }

    Output JSON:
    {
        "success": true,
        "predictionId": "offchain-123",
        "matchId": "EPL-ARS-CHE-2026-02-12",
        "prediction": "HOME_WIN",
        "confidence": 0.74,
        "factors": {...},
        "timestamp": 1707696000
    }
    """
    try:
        data = request.get_json()

        if not isinstance(data, dict):
            return jsonify({"success": False, "error": "Invalid JSON payload"}), 400

        # Accept precomputed predictions (agent payload)
        if all(k in data for k in ["matchId", "prediction", "confidence", "factors", "timestamp"]):
            prediction = Prediction(
                match_id=data["matchId"],
                predicted_outcome=data["prediction"],
                confidence=data["confidence"],
                factors=data["factors"],
                timestamp=data["timestamp"],
            )

            prediction_id = db.add_prediction(prediction)

            return (
                jsonify(
                    {
                        "success": True,
                        "predictionId": prediction_id,
                        "matchId": prediction.match_id,
                        "prediction": prediction.predicted_outcome,
                        "confidence": prediction.confidence,
                        "factors": prediction.factors,
                        "timestamp": prediction.timestamp,
                    }
                ),
                201,
            )

        # Validate input
        required_fields = ["homeTeam", "awayTeam", "league"]
        for field in required_fields:
            if field not in data:
                return (
                    jsonify(
                        {"success": False, "error": f"Missing required field: {field}"}
                    ),
                    400,
                )

        # Generate prediction
        match_id = data.get("matchId")
        fixture_id = data.get("fixtureId")
        if not match_id and fixture_id is not None and str(fixture_id).isdigit():
            match_id = f"{data['league']}-{int(fixture_id)}"

        prediction_result = prediction_engine.predict(
            home_team=data["homeTeam"],
            away_team=data["awayTeam"],
            league=data["league"],
            match_id=match_id,
        )

        # Create prediction object
        prediction = Prediction(
            match_id=prediction_result["matchId"],
            predicted_outcome=prediction_result["prediction"],
            confidence=prediction_result["confidence"],
            factors=prediction_result["factors"],
            timestamp=prediction_result["timestamp"],
            league=data["league"],
        )

        # Store in database
        prediction_id = db.add_prediction(prediction)

        logger.info(
            "Prediction created: %s → %s (conf=%.1f%%, edge=%.1f%%)",
            prediction_result["matchId"],
            prediction_result["prediction"],
            prediction_result["confidence"] * 100,
            prediction_result.get("edge", 0) * 100,
        )

        # Return response
        return (
            jsonify(
                {
                    "success": True,
                    "predictionId": prediction_id,
                    "matchId": prediction.match_id,
                    "league": prediction.league,
                    "prediction": prediction.predicted_outcome,
                    "confidence": prediction.confidence,
                    "edge": prediction_result.get("edge"),
                    "marketOdds": prediction_result.get("marketOdds"),
                    "trueProbabilities": prediction_result.get("trueProbabilities"),
                    "factors": prediction.factors,
                    "timestamp": prediction.timestamp,
                }
            ),
            201,
        )

    except RuntimeError as e:
        # No value bet found — not an error, just no pick today
        logger.info("No value bet: %s", e)
        return jsonify({"success": False, "error": str(e), "code": "NO_VALUE_BET"}), 200

    except Exception as e:
        logger.error("Error in create_prediction: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/predictions", methods=["GET"])
def get_all_predictions():
    """
    Get predictions — paginated and filterable.

    Query params:
    - page:     page number (default 1, 1-indexed)
    - limit:    results per page (default 50, max 100)
    - resolved: true/false (filter by resolution status)
    - league:   EPL / LaLiga / etc (filter by league)
    """
    try:
        try:
            page = max(1, int(request.args.get("page", 1)))
            limit = min(100, max(1, int(request.args.get("limit", 50))))
        except (TypeError, ValueError):
            page, limit = 1, 50

        resolved_param = request.args.get("resolved")
        league = request.args.get("league")

        if league:
            predictions = db.get_predictions_by_league(league, page=page, limit=limit)
        else:
            predictions = db.get_all_predictions(page=page, limit=limit)

        # Optional resolved filter (applied after DB fetch for simplicity)
        if resolved_param is not None:
            resolved_bool = resolved_param.lower() == "true"
            predictions = [p for p in predictions if p.resolved == resolved_bool]

        total = db.count_predictions()
        predictions_list = [p.to_dict() for p in predictions]

        return (
            jsonify(
                {
                    "success": True,
                    "page": page,
                    "limit": limit,
                    "count": len(predictions_list),
                    "total": total,
                    "predictions": predictions_list,
                }
            ),
            200,
        )

    except Exception as e:
        logger.error("Error in get_all_predictions: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/predictions/<prediction_id>", methods=["GET"])
def get_prediction(prediction_id):
    """
    Get a specific prediction by ID

    Output JSON:
    {
        "success": true,
        "prediction": {...}
    }
    """
    try:
        prediction = db.get_prediction(prediction_id)

        if not prediction:
            return jsonify({"success": False, "error": "Prediction not found"}), 404

        return jsonify({"success": True, "prediction": prediction.to_dict()}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# RESOLUTION ENDPOINTS
# ============================================================================


@app.route("/api/resolve", methods=["POST"])
def resolve_prediction():
    """
    Resolve a prediction with actual match result

    Input JSON:
    {
        "matchId": "EPL-ARS-CHE-2026-02-12",
        "actualOutcome": "HOME_WIN"
    }

    Output JSON:
    {
        "success": true,
        "matchId": "...",
        "predictionId": "...",
        "actualOutcome": "HOME_WIN",
        "predictedOutcome": "HOME_WIN",
        "correct": true
    }
    """
    try:
        data = request.get_json()

        # Validate input
        if "matchId" not in data or "actualOutcome" not in data:
            return (
                jsonify(
                    {"success": False, "error": "Missing matchId or actualOutcome"}
                ),
                400,
            )

        match_id = data["matchId"]
        actual_outcome = data["actualOutcome"]

        # Find prediction
        prediction = db.get_prediction_by_match_id(match_id)

        if not prediction:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"No prediction found for match {match_id}",
                    }
                ),
                404,
            )

        if prediction.resolved:
            return (
                jsonify({"success": False, "error": "Prediction already resolved"}),
                400,
            )

        # Resolve prediction
        is_correct = prediction.predicted_outcome == actual_outcome
        db.resolve_prediction(prediction.prediction_id, actual_outcome, is_correct)

        return (
            jsonify(
                {
                    "success": True,
                    "matchId": match_id,
                    "predictionId": prediction.prediction_id,
                    "actualOutcome": actual_outcome,
                    "predictedOutcome": prediction.predicted_outcome,
                    "correct": is_correct,
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/resolve/auto", methods=["POST"])
def auto_resolve():
    """
    Automatically resolve all unresolved predictions
    Fetches actual results from external API

    Output JSON:
    {
        "success": true,
        "resolved": 5,
        "results": [...]
    }
    """
    try:
        unresolved = db.get_unresolved_predictions()
        results = []
        errors = []

        data = request.get_json(silent=True) or {}

        try:
            max_items = int(data.get("max", 10))
        except (ValueError, TypeError):
            max_items = 10

        try:
            time_budget_seconds = float(data.get("timeBudgetSeconds", 20))
        except (ValueError, TypeError):
            time_budget_seconds = 20.0

        if max_items < 1:
            max_items = 1

        started = time.monotonic()
        processed = 0

        for prediction in unresolved:
            if processed >= max_items:
                break
            if (time.monotonic() - started) >= time_budget_seconds:
                break

            try:
                actual_outcome = resolver.get_match_result(prediction.match_id)
            except Exception as e:
                errors.append(
                    {
                        "matchId": prediction.match_id,
                        "predictionId": prediction.prediction_id,
                        "error": str(e),
                    }
                )
                processed += 1
                continue

            if not actual_outcome:
                processed += 1
                continue

            is_correct = prediction.predicted_outcome == actual_outcome
            db.resolve_prediction(prediction.prediction_id, actual_outcome, is_correct)

            results.append(
                {
                    "matchId": prediction.match_id,
                    "predictionId": prediction.prediction_id,
                    "correct": is_correct,
                }
            )
            processed += 1

        remaining = max(0, len(unresolved) - processed)
        return (
            jsonify(
                {
                    "success": True,
                    "resolved": len(results),
                    "processed": processed,
                    "remaining": remaining,
                    "results": results,
                    "errors": errors,
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# STATS ENDPOINTS
# ============================================================================


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """
    Get overall prediction statistics

    Output JSON:
    {
        "success": true,
        "stats": {
            "totalPredictions": 100,
            "resolved": 80,
            "pending": 20,
            "correct": 54,
            "incorrect": 26,
            "accuracy": 67.5
        }
    }
    """
    try:
        stats = db.get_statistics()

        return jsonify({"success": True, "stats": stats}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/stats/league/<league>", methods=["GET"])
def get_league_stats(league):
    """
    Get statistics for a specific league
    """
    try:
        predictions = db.get_predictions_by_league(league)

        total = len(predictions)
        resolved = sum(1 for p in predictions if p.resolved)
        correct = sum(1 for p in predictions if p.resolved and p.correct)

        accuracy = (correct / resolved * 100) if resolved > 0 else 0

        return (
            jsonify(
                {
                    "success": True,
                    "league": league,
                    "stats": {
                        "totalPredictions": total,
                        "resolved": resolved,
                        "pending": total - resolved,
                        "correct": correct,
                        "incorrect": resolved - correct,
                        "accuracy": round(accuracy, 1),
                    },
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# HEALTH CHECK
# ============================================================================


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return (
        jsonify(
            {"status": "healthy", "service": "FootyOracle Backend", "version": "1.0.0"}
        ),
        200,
    )


@app.route("/", methods=["GET"])
def root():
    """Root endpoint with API documentation"""
    return (
        jsonify(
            {
                "service": "FootyOracle Backend API",
                "version": "1.0.0",
                "endpoints": {
                    "POST /api/predict": "Create new prediction",
                    "GET /api/predictions": "Get all predictions",
                    "GET /api/predictions/:id": "Get specific prediction",
                    "POST /api/resolve": "Resolve prediction manually",
                    "POST /api/resolve/auto": "Auto-resolve all pending",
                    "GET /api/stats": "Get overall statistics",
                    "GET /api/stats/league/:league": "Get league statistics",
                    "GET /health": "Health check",
                },
                "documentation": "See README.md for full API documentation",
            }
        ),
        200,
    )


# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "False").lower() == "true"

    print(
        f"""
    ⚽ FootyOracle Backend Starting...
    ================================
    Port: {port}
    Debug: {debug}
    Environment: {'Development' if debug else 'Production'}
    ================================
    """
    )

    app.run(host="0.0.0.0", port=port, debug=debug)
