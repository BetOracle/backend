import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import os
import time
from dotenv import load_dotenv

from data_fetcher import DataFetcher
from prediction_engine import PredictionEngine, _NoValueBet
from resolver import MatchResolver
from models import Prediction, PredictionDatabase

# Load environment variables
load_dotenv()

# Blockchain integration — optional, only loaded when BLOCKCHAIN_ENABLED=True
_blockchain_enabled = os.getenv("BLOCKCHAIN_ENABLED", "False").lower() == "true"
BlockchainClient = None
if _blockchain_enabled:
    try:
        from blockchain_client import BlockchainClient  # type: ignore
    except ImportError:
        logging.getLogger(__name__).warning(
            "BLOCKCHAIN_ENABLED=True but blockchain_client could not be imported. "
            "On-chain recording will be skipped."
        )
        _blockchain_enabled = False

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

# Initialize blockchain client (optional - only if BLOCKCHAIN_ENABLED=True)
blockchain = BlockchainClient() if (_blockchain_enabled and BlockchainClient) else None

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


def _validate_prediction_request(data):
    """Validate the prediction request data."""
    if not isinstance(data, dict):
        raise ValueError("Invalid JSON payload")
    
    required_fields = ["homeTeam", "awayTeam", "league"]
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise ValueError(f"Missing required field: {missing_fields[0]}")


def _handle_precomputed_prediction(data):
    """Handle precomputed prediction from agent payload."""
    prediction = Prediction(
        match_id=data["matchId"],
        predicted_outcome=data["prediction"],
        confidence=data["confidence"],
        factors=data["factors"],
        timestamp=data["timestamp"],
    )
    
    prediction_id = db.add_prediction(prediction)
    
    return {
        "success": True,
        "predictionId": prediction_id,
        "matchId": prediction.match_id,
        "prediction": prediction.predicted_outcome,
        "confidence": prediction.confidence,
        "factors": prediction.factors,
        "timestamp": prediction.timestamp,
    }


def _team_code(team_name: str) -> str:
    if not team_name:
        return "UNK"

    import re

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


def _generate_match_id(data):
    """Generate match ID from fixture or match data."""
    match_id = data.get("matchId")
    if match_id:
        return match_id

    home_team = data.get("homeTeam", "")
    away_team = data.get("awayTeam", "")
    league = data.get("league", "")
    date_str = data.get("date")
    fixture_id = data.get("fixtureId")

    if not date_str:
        from datetime import datetime

        date_str = datetime.now().strftime("%Y-%m-%d")

    if home_team and away_team and league:
        home_abbr = _team_code(home_team)
        away_abbr = _team_code(away_team)
        if fixture_id is not None and str(fixture_id).isdigit():
            return f"{league}-{int(fixture_id)}-{home_abbr}-{away_abbr}-{date_str}"
        return f"{league}-{home_abbr}-{away_abbr}-{date_str}"

    return None


def _submit_to_blockchain(data, prediction_result):
    """Submit prediction to blockchain if enabled."""
    if not blockchain or not blockchain.enabled:
        return None
    
    try:
        from datetime import datetime
        match_date_ts = int(prediction_result.get("timestamp", prediction_result["timestamp"]))
        
        result = blockchain.submit_prediction(
            home_team=data["homeTeam"],
            away_team=data["awayTeam"],
            league=data["league"],
            prediction=prediction_result["prediction"],
            confidence=prediction_result["confidence"],
            match_date=match_date_ts,
        )
        
        if result.success:
            logger.info(f"Prediction recorded on-chain: {result.tx_hash}")
        else:
            logger.warning(f"Blockchain submission failed: {result.error}")
            
        return result
        
    except Exception as e:
        logger.error(f"Blockchain submission error: {e}")
        return None


def _build_response_data(prediction_id, prediction, prediction_result, blockchain_result):
    """Build the response data for the prediction."""
    response_data = {
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
    
    if blockchain_result:
        response_data["blockchain"] = {
            "submitted": blockchain_result.success,
            "txHash": blockchain_result.tx_hash,
            "onChainId": blockchain_result.prediction_id,
            "error": blockchain_result.error,
        }
    
    return response_data


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
        _validate_prediction_request(data)

        # Accept precomputed predictions (agent payload)
        if all(k in data for k in ["matchId", "prediction", "confidence", "factors", "timestamp"]):
            response_data = _handle_precomputed_prediction(data)
            return jsonify(response_data), 201

        # Generate prediction
        match_id = _generate_match_id(data)
        prediction_result = prediction_engine.predict(
            home_team=data["homeTeam"],
            away_team=data["awayTeam"],
            league=data["league"],
            match_id=match_id,
            market_odds=data.get("marketOdds"),
        )

        factors = prediction_result["factors"]
        fixture_id = data.get("fixtureId")
        if fixture_id is not None and str(fixture_id).isdigit() and isinstance(factors, dict):
            factors = {**factors, "fixtureId": int(fixture_id)}

        # Create prediction object
        prediction = Prediction(
            match_id=prediction_result["matchId"],
            predicted_outcome=prediction_result["prediction"],
            confidence=prediction_result["confidence"],
            factors=factors,
            timestamp=prediction_result["timestamp"],
            league=data["league"],
            market_odds=prediction_result.get("marketOdds"),
            true_probabilities=prediction_result.get("trueProbabilities"),
            edge=prediction_result.get("edge"),
        )

        # Store in database
        prediction_id = db.add_prediction(prediction)

        # Submit to blockchain
        blockchain_result = _submit_to_blockchain(data, prediction_result)

        logger.info(
            "Prediction created: %s → %s (conf=%.1f%%, edge=%.1f%%)",
            prediction_result["matchId"],
            prediction_result["prediction"],
            prediction_result["confidence"] * 100,
            prediction_result.get("edge", 0) * 100,
        )

        # Build and return response
        response_data = _build_response_data(prediction_id, prediction, prediction_result, blockchain_result)
        return jsonify(response_data), 201

    except _NoValueBet as e:
        # No value edge found — return full analysis so frontend can still display it
        logger.info("No value bet: %s", e)
        return jsonify({
            "success": False,
            "code": "NO_VALUE_BET",
            "error": str(e),
            **e.analysis,
        }), 200

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


@app.route("/api/admin/purge-predictions", methods=["POST"])
def purge_predictions():
    try:
        data = request.get_json(silent=True) or {}
        dry_run = bool(data.get("dryRun", True))
        delete_unresolved = bool(data.get("deleteUnresolved", True))
        delete_test = bool(data.get("deleteTest", True))
        sample_limit = int(data.get("sample", 25))

        preds = db.get_all_predictions(page=1, limit=500)

        to_delete = []
        for p in preds:
            if delete_unresolved and not p.resolved:
                to_delete.append(p)
                continue
            if delete_test and (p.league == "TEST" or (p.match_id or "").startswith("TEST-")):
                to_delete.append(p)

        # Deduplicate by prediction_id
        seen = set()
        uniq = []
        for p in to_delete:
            if p.prediction_id in seen:
                continue
            seen.add(p.prediction_id)
            uniq.append(p)

        sample = [p.to_dict() for p in uniq[: max(0, sample_limit)]]

        if dry_run:
            return jsonify({
                "success": True,
                "dryRun": True,
                "deleteUnresolved": delete_unresolved,
                "deleteTest": delete_test,
                "wouldDelete": len(uniq),
                "sample": sample,
            }), 200

        deleted = 0
        if delete_unresolved:
            deleted += db.delete_unresolved_predictions()

        if delete_test:
            deleted += db.delete_predictions_by_match_id_prefix("TEST-")

        return jsonify({
            "success": True,
            "dryRun": False,
            "deleteUnresolved": delete_unresolved,
            "deleteTest": delete_test,
            "deleted": int(deleted),
            "sample": sample,
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/migrate-match-ids", methods=["POST"])
def migrate_match_ids():
    try:
        data = request.get_json(silent=True) or {}
        dry_run = bool(data.get("dryRun", True))
        days_ahead = int(data.get("daysAhead", 14))
        max_items = int(data.get("max", 200))

        unresolved = db.get_unresolved_predictions()

        import re

        legacy = []
        for p in unresolved:
            if re.fullmatch(r"[A-Za-z]+-\d+", p.match_id or ""):
                legacy.append(p)

        legacy = legacy[: max(0, max_items)]

        matches_by_league = {}
        fixture_index = {}
        for league in {p.league for p in legacy if p.league}:
            try:
                matches = _data_fetcher.get_league_matches(league=league, days_ahead=days_ahead)
            except Exception:
                matches = []
            matches_by_league[league] = matches
            for m in matches:
                fid = m.get("fixtureId")
                if isinstance(fid, int):
                    fixture_index[(league, fid)] = m

        updated = []
        skipped = []
        errors = []

        for p in legacy:
            try:
                league, fid_str = p.match_id.split("-", 1)
                fid = int(fid_str)
                m = fixture_index.get((league, fid))
                if not m:
                    skipped.append({"predictionId": p.prediction_id, "matchId": p.match_id, "reason": "fixture_not_found"})
                    continue

                new_match_id = f"{league}-{fid}-{_team_code(m.get('homeTeam', ''))}-{_team_code(m.get('awayTeam', ''))}-{m.get('date', '')}"
                if not m.get("date"):
                    skipped.append({"predictionId": p.prediction_id, "matchId": p.match_id, "reason": "missing_date"})
                    continue

                if dry_run:
                    updated.append({"predictionId": p.prediction_id, "from": p.match_id, "to": new_match_id, "dryRun": True})
                    continue

                ok = db.update_prediction_match_id(p.prediction_id, new_match_id)
                if ok:
                    updated.append({"predictionId": p.prediction_id, "from": p.match_id, "to": new_match_id, "dryRun": False})
                else:
                    skipped.append({"predictionId": p.prediction_id, "matchId": p.match_id, "reason": "update_failed_or_conflict"})

            except Exception as e:
                errors.append({"predictionId": getattr(p, "prediction_id", None), "matchId": getattr(p, "match_id", None), "error": str(e)})

        return jsonify({
            "success": True,
            "dryRun": dry_run,
            "daysAhead": days_ahead,
            "max": max_items,
            "foundLegacy": len(legacy),
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
        }), 200

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


def _validate_resolution_params(data):
    """Validate and extract resolution parameters."""
    try:
        max_items = int(data.get("max", 10))
    except (ValueError, TypeError):
        max_items = 10
    
    try:
        time_budget_seconds = float(data.get("timeBudgetSeconds", 20))
    except (ValueError, TypeError):
        time_budget_seconds = 20.0
    
    return max(1, max_items), time_budget_seconds


def _should_skip_resolution(force_resolution):
    """Check if resolution should be skipped due to no matches today."""
    if force_resolution:
        return None
    
    if not resolver.has_matches_today():
        return jsonify({
            "success": True,
            "message": "No matches scheduled today - skipping AI resolution",
            "resolved": 0,
            "processed": 0,
            "cost_saved": True,
            "results": [],
            "errors": []
        }), 200
    
    return None


def _process_single_prediction(prediction, resolver, db):
    """Process a single prediction and return result or error."""
    try:
        actual_outcome = resolver.get_match_result(prediction.match_id)
    except Exception as e:
        return {
            "type": "error",
            "data": {
                "matchId": prediction.match_id,
                "predictionId": prediction.prediction_id,
                "error": str(e),
            }
        }
    
    if not actual_outcome:
        return {"type": "skipped"}
    
    is_correct = prediction.predicted_outcome == actual_outcome
    db.resolve_prediction(prediction.prediction_id, actual_outcome, is_correct)
    
    return {
        "type": "success",
        "data": {
            "matchId": prediction.match_id,
            "predictionId": prediction.prediction_id,
            "correct": is_correct,
        }
    }


def _process_predictions(unresolved, max_items, time_budget_seconds, resolver, db):
    """Process all predictions within limits."""
    results = []
    errors = []
    started = time.monotonic()
    processed = 0
    
    for prediction in unresolved:
        if processed >= max_items or (time.monotonic() - started) >= time_budget_seconds:
            break
        
        result = _process_single_prediction(prediction, resolver, db)
        
        if result["type"] == "error":
            errors.append(result["data"])
        elif result["type"] == "success":
            results.append(result["data"])
        
        processed += 1
    
    return results, errors, processed


@app.route("/api/resolve/auto", methods=["POST"])
def auto_resolve():
    """
    Automatically resolve all unresolved predictions
    Smart resolution: only runs AI on match days to save costs

    Output JSON:
    {
        "success": true,
        "resolved": 5,
        "results": [...],
        "message": "AI resolution completed" or "No matches today - skipping"
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        force_resolution = data.get("force", False)
        
        # Check if we should skip resolution
        skip_response = _should_skip_resolution(force_resolution)
        if skip_response:
            return skip_response
        
        # Get unresolved predictions and validate parameters
        unresolved = db.get_unresolved_predictions()
        max_items, time_budget_seconds = _validate_resolution_params(data)
        
        # Process predictions
        results, errors, processed = _process_predictions(
            unresolved, max_items, time_budget_seconds, resolver, db
        )
        
        remaining = max(0, len(unresolved) - len(results))
        message = "AI resolution completed" if not force_resolution else "Forced AI resolution completed"
        
        return jsonify({
            "success": True,
            "message": message,
            "resolved": len(results),
            "processed": processed,
            "remaining": remaining,
            "results": results,
            "errors": errors,
        }), 200
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/resolve/schedule", methods=["GET"])
def get_resolution_schedule():
    """
    Get upcoming match schedule for resolution planning
    
    Returns:
    {
        "success": true,
        "schedule": {
            "EPL": ["2026-03-22", "2026-03-25"],
            "LaLiga": ["2026-03-23", "2026-03-26"],
            ...
        },
        "has_matches_today": true,
        "today": "2026-03-22"
    }
    """
    try:
        days_ahead = request.args.get("days", 7, type=int)
        schedule = resolver.get_match_schedule(days_ahead)
        has_matches_today = resolver.has_matches_today()
        
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        
        return jsonify({
            "success": True,
            "schedule": schedule,
            "has_matches_today": has_matches_today,
            "today": today,
            "days_ahead": days_ahead
        }), 200
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/resolve/override", methods=["POST"])
def override_resolution():
    """
    Admin endpoint to override already resolved predictions
    Use this to correct incorrect resolution data
    
    Input JSON:
    {
        "matchId": "EPL-BRI-LIV-2026-03-21",
        "actualOutcome": "HOME_WIN",
        "force": true
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        match_id = data.get("matchId")
        actual_outcome = data.get("actualOutcome")
        force = data.get("force", False)
        
        if not all([match_id, actual_outcome]):
            return jsonify({"success": False, "error": "matchId and actualOutcome required"}), 400
        
        if actual_outcome not in ["HOME_WIN", "DRAW", "AWAY_WIN"]:
            return jsonify({"success": False, "error": "actualOutcome must be HOME_WIN, DRAW, or AWAY_WIN"}), 400
        
        # Get the prediction
        prediction = db.get_prediction_by_match_id(match_id)
        if not prediction:
            return jsonify({"success": False, "error": "No predictions found for this match"}), 404
        
        # Check if already resolved and not forced
        if prediction.resolved and not force:
            return jsonify({
                "success": False, 
                "error": "Prediction already resolved. Use force=true to override."
            }), 400
        
        # Update the resolution
        is_correct = prediction.predicted_outcome == actual_outcome
        db.resolve_prediction(prediction.prediction_id, actual_outcome, is_correct)
        
        return jsonify({
            "success": True,
            "message": "Resolution updated successfully",
            "matchId": match_id,
            "predictionId": prediction.prediction_id,
            "actualOutcome": actual_outcome,
            "predictedOutcome": prediction.predicted_outcome,
            "correct": is_correct,
            "overridden": prediction.resolved and force
        }), 200
        
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
# AGENT STATUS
# ============================================================================


@app.route("/api/agent/status", methods=["GET"])
def get_agent_status():
    """
    Live agent status — consolidated view for judges / frontend.

    Output JSON:
    {
        "success": true,
        "stats": { ... },
        "lastPrediction": { ... } | null,
        "recentPredictions": [ ... ]
    }
    """
    try:
        stats = db.get_statistics()

        # Most recent prediction
        recent = db.get_all_predictions(page=1, limit=5)
        last_prediction = recent[0].to_dict() if recent else None
        recent_list = [p.to_dict() for p in recent]

        # Per-league breakdown
        leagues = ["EPL", "LaLiga", "SerieA", "Bundesliga", "Ligue1"]
        league_stats = []
        for lg in leagues:
            lg_preds = db.get_predictions_by_league(lg, page=1, limit=1000)
            if lg_preds:
                resolved = sum(1 for p in lg_preds if p.resolved)
                correct = sum(1 for p in lg_preds if p.resolved and p.correct)
                league_stats.append({
                    "league": lg,
                    "total": len(lg_preds),
                    "resolved": resolved,
                    "correct": correct,
                    "accuracy": round(correct / resolved * 100, 1) if resolved else 0,
                })

        return jsonify({
            "success": True,
            "agent": "FootyOracle AI Agent",
            "version": "1.0.0",
            "stats": stats,
            "leagueBreakdown": league_stats,
            "lastPrediction": last_prediction,
            "recentPredictions": recent_list,
        }), 200

    except Exception as e:
        logger.error("Error in get_agent_status: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# HEALTH CHECK
# ============================================================================


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    status = {
        "status": "healthy", 
        "service": "FootyOracle Backend", 
        "version": "1.0.0",
        "blockchain": blockchain.get_connection_status() if blockchain else {"enabled": False},
    }
    return jsonify(status), 200


@app.route("/", methods=["GET"])
def root():
    """Root endpoint with API documentation"""
    return (
        jsonify(
            {
                "service": "FootyOracle Backend API",
                "version": "1.0.0",
                "endpoints": {
                    "GET /api/matches": "Get upcoming matches for a league",
                    "POST /api/predict": "Create new prediction",
                    "GET /api/predictions": "Get all predictions (paginated, filterable)",
                    "GET /api/predictions/:id": "Get specific prediction",
                    "POST /api/resolve": "Resolve prediction manually",
                    "POST /api/resolve/auto": "Auto-resolve all pending predictions",
                    "GET /api/stats": "Get overall statistics",
                    "GET /api/stats/league/:league": "Get league statistics",
                    "GET /api/agent/status": "Live agent status (predictions, accuracy, league breakdown)",
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
