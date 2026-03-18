# Frontend API Guide (FootyOracle Backend)

Base URL:
- Local: `http://localhost:5000` (default; configurable via `PORT`)
- Railway (production): `https://web-production-34305.up.railway.app`

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
- `page` (optional) 1-indexed. Default `1`.
- `limit` (optional) Default `50`, max `100`.
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
  "page": 1,
  "limit": 50,
  "count": 1,
  "total": 1,
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

### Get a single prediction
`GET /api/predictions/:predictionId`

Response:

```json
{
  "success": true,
  "prediction": {
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
  "league": "EPL",
  "prediction": "HOME_WIN",
  "confidence": 0.74,
  "edge": 0.18,
  "marketOdds": {
    "home": 2.5,
    "draw": 3.2,
    "away": 2.8
  },
  "trueProbabilities": {
    "home": 0.42,
    "draw": 0.28,
    "away": 0.30
  },
  "factors": {
    "formScore": 0.7,
    "injuryImpact": -0.1,
    "h2hScore": 0.6,
    "tablePositionScore": 0.8
  },
  "timestamp": 1700000000,
  "blockchain": {
    "submitted": false,
    "txHash": null,
    "onChainId": null,
    "error": null
  }
}
```

Notes:
- If blockchain is disabled, the `blockchain` field may be omitted.
- If no value bet is found, the API returns `success=false` with `code=NO_VALUE_BET`.
- If `blockchain.submitted` is true, you can link to CeloScan:
  ```
  https://celoscan.io/tx/{blockchain.txHash}
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

Response: same shape as above (may include `blockchain` field if on-chain submission is enabled for this endpoint).

---

### Auto-resolve pending predictions
`POST /api/resolve/auto`

Optional JSON body:

```json
{
  "max": 10,
  "timeBudgetSeconds": 20
}
```

Response:

```json
{
  "success": true,
  "resolved": 0,
  "processed": 0,
  "remaining": 0,
  "results": [],
  "errors": []
}
```

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

### Agent status (frontend dashboard)
`GET /api/agent/status`

Response (shape may evolve; includes blockchain status when enabled):

```json
{
  "success": true,
  "service": "FootyOracle Backend",
  "blockchain": {
    "enabled": true,
    "agentWallet": "0x8929c7C546aF792E044326ff492439F02fD13373",
    "predictionContract": "0xd5049F6550aefC772ABDa57013fB01aB718054Ef",
    "chainId": 42220
  }
}
```

---

### Root (endpoint listing)
`GET /`

Returns an endpoint map for quick discovery.

---

## Recommended frontend polling
For a simple dashboard:
- Poll `GET /api/predictions?resolved=false` every 30–60s for “Upcoming”.
- Poll `GET /api/stats` every 30–60s for headline metrics.
- Use `GET /api/predictions` for history pagination (client-side) if needed.
