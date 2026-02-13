# FootyOracle - Quick Start Guide

## 🚀 Complete Setup (5 Minutes)

### Step 1: Install Dependencies

```bash
# Make sure you're in the backend directory
cd backend

# Install all required packages
pip install -r requirements.txt
```

**Expected packages:**
- flask
- flask-cors
- requests
- python-dotenv
- schedule
- pytest

---

### Step 2: Configure Environment

```bash
# Create your .env file
cp .env.example .env

# Edit .env (optional - defaults work fine)
# For now, just use mock mode
```

**Your .env should contain:**
```bash
MOCK_MODE=True
PORT=5000
DEBUG=True
BACKEND_URL=http://localhost:5000
```

---

### Step 3: Test the System

#### Option A: Run Agent Only (Standalone)

```bash
# One-time prediction cycle
python agent.py

# Continuous mode (checks every hour)
python agent.py schedule
```

**What you should see:**
```
⚠️  DataFetcher: MOCK MODE enabled
🤖 FootyOracle Agent initialized
============================================================
🤖 Agent Cycle Started - 2026-02-13 07:51:30
============================================================
🔍 Checking EPL matches...
   ✅ Newcastle vs Manchester City
      Prediction: AWAY_WIN (71.0%)
      ⚠️  Backend not running (predictions saved locally)
```

The warning is **normal** - predictions are saved locally even without the API running.

---

#### Option B: Run Backend API + Agent (Full System)

**Terminal 1: Start API Server**
```bash
python app.py
```

**Expected output:**
```
⚽ FootyOracle Backend Starting...
================================
Port: 5000
Debug: True
Environment: Development
================================
 * Running on http://127.0.0.1:5000
```

**Terminal 2: Run Agent**
```bash
python agent.py
```

**Now you should see:**
```
   ✅ Newcastle vs Manchester City
      Prediction: AWAY_WIN (71.0%)
      📝 Recorded on-chain  ✅  # Success!
```

---

### Step 4: Verify Everything Works

#### Test the API (if running)

```bash
# Health check
curl http://localhost:5000/health

# Get statistics
curl http://localhost:5000/api/stats

# Get all predictions
curl http://localhost:5000/api/predictions
```

#### Check Predictions Database

The agent saves predictions locally even if the API isn't running. After running the agent, you can check:

```python
from models import PredictionDatabase

db = PredictionDatabase()
db.load_from_file('predictions.json')  # If saved

stats = db.get_statistics()
print(stats)
# Output: {'totalPredictions': 6, 'resolved': 0, 'accuracy': 0.0, ...}
```

---

## 🎯 Common Issues & Fixes

### Issue: "ModuleNotFoundError: No module named 'flask'"

**Fix:**
```bash
pip install -r requirements.txt
```

If that doesn't work:
```bash
pip install flask flask-cors requests python-dotenv schedule
```

---

### Issue: "Backend recording failed: 403"

**Cause:** API server not running or agent sending wrong format

**Fix:** 
1. Make sure API server is running in another terminal: `python app.py`
2. If you don't need the API, ignore this warning - predictions save locally

---

### Issue: "Port 5000 already in use"

**Fix:** Change port in `.env`:
```bash
PORT=8000
BACKEND_URL=http://localhost:8000
```

---

### Issue: Agent not finding any matches

**Cause:** Mock data generates random upcoming matches

**Fix:** This is normal! Run again and you'll see different matches. In production with real API, you'll get actual scheduled matches.

---

## 📊 Understanding the Output

### Agent Output Explained

```
🔍 Checking EPL matches...              # Checking Premier League
   ✅ Newcastle vs Manchester City       # Found a match to predict
      Prediction: AWAY_WIN (71.0%)      # Man City to win, 71% confidence
      📝 Recorded on-chain               # Saved to API ✅
      ⚠️  Backend not running           # API not available, saved locally ⚠️
```

### What Gets Saved

**Locally (always):**
- In-memory database during runtime
- Can save to `predictions.json` file

**Backend API (if running):**
- Persistent database
- Available via REST endpoints
- Can be queried by frontend

---

## 🧪 Testing Different Modes

### Mode 1: Agent Only (No API)
```bash
python agent.py
# Predictions saved in memory only
# Good for: Testing prediction logic
```

### Mode 2: Agent + API (Full System)
```bash
# Terminal 1
python app.py

# Terminal 2  
python agent.py
# Predictions saved in API
# Good for: Testing full integration
```

### Mode 3: Scheduled Agent (Production-like)
```bash
python agent.py schedule
# Runs continuously, checking every hour
# Good for: Simulating production
```

---

## 🎮 Next Steps

### 1. Try Manual Prediction via API

```bash
# Start API
python app.py

# In another terminal, create prediction
curl -X POST http://localhost:5000/api/predict \
  -H "Content-Type: application/json" \
  -d '{
    "homeTeam": "Arsenal",
    "awayTeam": "Chelsea",
    "league": "EPL"
  }'
```

### 2. Check Statistics

```bash
curl http://localhost:5000/api/stats
```

### 3. Resolve a Prediction

```bash
curl -X POST http://localhost:5000/api/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "matchId": "EPL-ARS-CHE-2026-02-13",
    "actualOutcome": "HOME_WIN"
  }'
```

---

## 🚀 Deploy (Optional)

### Heroku
```bash
heroku create footyoracle-backend
git push heroku main
heroku ps:scale web=1 agent=1
```

### Railway
```bash
railway init
railway up
```

---

## 📞 Need Help?

Check:
1. All dependencies installed: `pip list | grep flask`
2. `.env` file exists: `ls -la .env`
3. Python version: `python --version` (need 3.8+)
4. Virtual environment activated: `which python`

---

**You're ready to build! 🎉**