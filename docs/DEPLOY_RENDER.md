# Deploy to Render (FootyOracle Backend)

This guide deploys:
- A Render Web Service for the API
- A Render PostgreSQL database for persistence
- Hourly agent runs via GitHub Actions (free alternative to Render background workers)

---

## 1) Create Render PostgreSQL
1. Render Dashboard → New → PostgreSQL
2. Copy the **Internal Database URL**

---

## 2) Create Render Web Service
1. Render Dashboard → New → Web Service
2. Repo: `BetOracle/backend`
3. Root Directory: leave blank (repo root)
4. Build command:

```bash
pip install -r requirements.txt
```

5. Start command:

```bash
gunicorn app:app --bind 0.0.0.0:$PORT
```

---

## 3) Environment variables (Render Web Service)
Set in Render → Service → Environment:

- `DATABASE_URL` = Render Postgres internal URL
- `DEBUG` = `False`
- `MOCK_MODE` = `False`
- `FOOTBALL_API_KEY` = your football-data.org key
- `INJURIES_ENABLED` = `False`
- `REQUESTS_PER_MINUTE` = `8`
- `ALLOWED_ORIGINS` = comma-separated allowed frontend origins

Optional:
- `RAPIDAPI_KEY` only if you have a paid/subscribed plan

---

## 4) Hourly agent runs (GitHub Actions)
Render free tier may not include background workers.

Use GitHub Actions to run the agent hourly and post predictions to the API.

### 4.1 Add GitHub Secrets
GitHub → Repo → Settings → Secrets and variables → Actions:

- `BACKEND_URL` = `https://<your-render-service>.onrender.com`
- `FOOTBALL_API_KEY` = your football-data.org key

### 4.2 Run the workflow once
GitHub → Actions → "FootyOracle Agent Hourly" → Run workflow.

---

## 5) Verify deployment
- Health:
  - `GET https://<service>/health`
- Stats:
  - `GET https://<service>/api/stats`
- Predictions:
  - `GET https://<service>/api/predictions`

After an agent run, `/api/predictions` should become non-empty.
