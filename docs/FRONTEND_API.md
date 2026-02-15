# Frontend API Guide (FootyOracle Backend)

Base URL:
- Local: `http://localhost:5000`
- Render (example): `https://backend-krxf.onrender.com`

All responses are JSON.

---

### List upcoming matches (for stable fixture ids)
`GET /api/matches`

Query params:
- `league` (required) e.g. `EPL`, `LaLiga`, `Bundesliga`, `Ligue1`
- `daysAhead` (optional) default `7`

Response:

```json
{
  "success": true,
  "league": "EPL",
  "matches": [
    {
      "fixtureId": 123456,
      "homeTeam": "Arsenal",
      "awayTeam": "Chelsea",
      "date": "2026-02-13",
      "time": "15:00"
    }
  ]
}
```

---

## Data model (Prediction)
A prediction returned by the API includes:

```json
{
  "predictionId": "offchain-1700000000",
  "matchId": "EPL-123456",
  "prediction": "HOME_WIN",
  "confidence": 0.74,
  "factors": {
    "formScore": 0.7,
    "injuryImpact": -0.1,
    "h2hScore": 0.6,
    "tablePositionScore": 0.8
  },
  "timestamp": 1700000000,
  "resolved": false,
  "actualOutcome": null,
  "correct": null,
  "resolutionTimestamp": null
}
```

Notes:
- `confidence` is a 0..1 float.
- `resolved` is boolean.
- `actualOutcome`, `correct`, `resolutionTimestamp` are present when resolved.
- `matchId` is stable when created from a fixture id: `{league}-{fixtureId}`.

---

## Endpoints

### Health
`GET /health`

Expected:
- `200 OK`

---

### List predictions
`GET /api/predictions`

Query params:
- `league` (optional) e.g. `EPL`
- `resolved` (optional) `true|false`

Examples:
- Upcoming only:
  - `GET /api/predictions?resolved=false`
- History + upcoming:
  - `GET /api/predictions`

Response:

```json
{
  "success": true,
  "predictions": [
    {
      "predictionId": "offchain-1700000000",
      "matchId": "EPL-123456",
      "prediction": "HOME_WIN",
      "confidence": 0.74,
      "factors": {},
      "timestamp": 1700000000,
      "resolved": false,
      "actualOutcome": null,
      "correct": null,
      "resolutionTimestamp": null
    }
  ]
}
```

---

### Create a prediction (frontend-triggered)
`POST /api/predict`

Request (user-driven):

```json
{
  "homeTeam": "Arsenal",
  "awayTeam": "Chelsea",
  "league": "EPL",
  "fixtureId": 123456
}
```

Response:

```json
{
  "success": true,
  "predictionId": "offchain-1700000000",
  "matchId": "EPL-123456",
  "prediction": "HOME_WIN",
  "confidence": 0.74,
  "factors": {
    "formScore": 0.7,
    "injuryImpact": -0.1,
    "h2hScore": 0.6,
    "tablePositionScore": 0.8
  },
  "timestamp": 1700000000
}
```

---

### Create a prediction (agent-triggered / precomputed)
`POST /api/predict`

Request (agent payload):

```json
{
  "matchId": "EPL-123456",
  "prediction": "HOME_WIN",
  "confidence": 0.74,
  "factors": {
    "formScore": 0.7,
    "injuryImpact": -0.1,
    "h2hScore": 0.6,
    "tablePositionScore": 0.8
  },
  "timestamp": 1700000000
}
```

Response: same shape as above.

---

### Stats
`GET /api/stats`

Response:

```json
{
  "success": true,
  "stats": {
    "totalPredictions": 0,
    "resolved": 0,
    "pending": 0,
    "correct": 0,
    "incorrect": 0,
    "accuracy": 0.0
  }
}
```

---

### Resolve a prediction
`POST /api/resolve`

Request:

```json
{
  "matchId": "EPL-123456",
  "actualOutcome": "HOME_WIN"
}
```

Response:

```json
{
  "success": true,
  "matchId": "EPL-123456",
  "actualOutcome": "HOME_WIN",
  "correct": true
}
```

---

## Recommended frontend polling
For a simple dashboard:
- Poll `GET /api/predictions?resolved=false` every 30–60s for “Upcoming”.
- Poll `GET /api/stats` every 30–60s for headline metrics.
- Use `GET /api/predictions` for history pagination (client-side) if needed.
