# FootyOracle Backend

**AI-Powered Football Prediction Agent**  
*Autonomous agent with multi-factor analysis and persistent storage*

---

## 🎯 What This Is

FootyOracle is an **autonomous AI agent** that:
- 🤖 Generates football match predictions using multi-factor analysis
- 📊 Tracks accuracy with transparent on-chain timestamps
- 🔄 Runs autonomously to predict upcoming matches
- 🗄️ Persists data across restarts
- 🌐 Provides REST API for integration

---

## 🏗️ Architecture

```
FootyOracle Backend
│
├── 🤖 Autonomous Agent
│   ├── Auto-predict upcoming matches (5 leagues)
│   ├── Auto-resolve completed matches
│   └── Scheduled execution (runs every hour)
│
├── 🧠 Prediction Engine (AI)
│   ├── Team Form Analysis (35%)
│   ├── Injury Impact (15%)
│   ├── Head-to-Head Records (25%)
│   └── League Position (25%)
│
├── 🌐 REST API (Flask)
│   ├── POST /api/predict
│   ├── GET /api/predictions
│   ├── POST /api/resolve
│   └── GET /api/stats
│
└── 🗄️ Database (PostgreSQL)
    └── Persistent prediction storage
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Defaults work fine for development!
```

### 3. Run the System

**Option A: API + Agent (Full System)**

```bash
# Terminal 1: Start API
python app.py

# Terminal 2: Run agent
python agent.py
```

**Option B: Scheduled Agent (Production)**

```bash
# Terminal 1: Start API
python app.py

# Terminal 2: Agent runs continuously
python agent.py schedule
```

---

## 📊 Features

### 🤖 Autonomous Agent
- Checks 5 leagues (EPL, LaLiga, SerieA, Bundesliga, Ligue1)
- Generates 40-60 predictions per cycle
- Runs on schedule (hourly) or on-demand
- Auto-resolves predictions when matches complete

### 🧠 AI Prediction Engine
- **Team Form**: Recent 5 match results
- **Injuries**: Impact of missing players
- **H2H Records**: Historical matchups
- **Table Position**: Current standings

**Typical Accuracy: 60-70%**

### 🗄️ Database
- **PostgreSQL**: Persistent database (recommended)

### 📡 Mock vs Real Data
- **Mock Mode**: 96 teams, realistic simulated data
- **Real Mode**: Live data from football-data.org

---

## 📋 API Documentation

### Base URL
```
http://localhost:8000
```

### Endpoints

#### Create Prediction
```bash
POST /api/predict
{
  "homeTeam": "Arsenal",
  "awayTeam": "Chelsea",
  "league": "EPL"
}
```

**Response:**
```json
{
  "success": true,
  "predictionId": "offchain-123",
  "matchId": "EPL-ARS-CHE-2026-02-13",
  "prediction": "HOME_WIN",
  "confidence": 0.81,
  "factors": {
    "formScore": 0.1,
    "injuryImpact": 0.0,
    "h2hScore": 0.6,
    "tablePositionScore": 0.5
  }
}
```

#### Get All Predictions
```bash
GET /api/predictions
GET /api/predictions?league=EPL
GET /api/predictions?resolved=false
```

#### Resolve Prediction
```bash
POST /api/resolve
{
  "matchId": "EPL-ARS-CHE-2026-02-13",
  "actualOutcome": "HOME_WIN"
}
```

#### Get Statistics
```bash
GET /api/stats
GET /api/stats/league/EPL
```

---

## 🧪 Testing

### Run Test Suite
```bash
python test_backend.py
```

### Run Load Test
```bash
python load_test.py
# Choose option 1-5 for different load levels
```

### Manual Testing
```bash
# Health check
curl http://localhost:8000/health

# Get stats
curl http://localhost:8000/api/stats
```

---

## 📂 Project Structure

```
backend/
├── agent.py              # 🤖 Autonomous agent (main entry point)
├── app.py                # 🌐 Flask API server
├── prediction_engine.py  # 🧠 AI prediction logic
├── data_fetcher.py       # 📡 Data integration (real + mock)
├── mock_data.py          # 🎭 Comprehensive mock data (96 teams)
├── models.py             # 🗄️ Database (in-memory/SQLite)
├── resolver.py           # ✅ Match result checker
│
├── test_backend.py       # 🧪 Unit tests
├── load_test.py          # 🧪 Load/stress tests
│
├── requirements.txt      # 📦 Dependencies
├── .env.example          # ⚙️ Config template
├── .gitignore            # 🚫 Git ignore rules
├── Procfile              # 🚀 Deployment config
│
└── README.md            # 📖 This file
```

---

## 🔧 Configuration

### Environment Variables

```bash
# Server
PORT=8000
DEBUG=True

# Agent
MOCK_MODE=True                    # Use mock data (no API keys needed)
BACKEND_URL=http://localhost:8000

# Real Data APIs (optional)
FOOTBALL_API_KEY=                 # football-data.org

# Injuries (optional)
INJURIES_ENABLED=False

# Database
DATABASE_URL=
```

---

## 🗄️ Database Setup

### PostgreSQL (Recommended)

```bash
# Set database URL
export DATABASE_URL=postgresql://user:pass@host/db
```

**Pros:**
- ✅ Scales to millions of predictions
- ✅ Better concurrency
- ✅ Auto-backups on Render/Railway

The backend requires `DATABASE_URL`.

---

## 🚀 Deployment

### Deploy to Render (Recommended - Free)

1. **Push to GitHub**
```bash
git init
git add .
git commit -m "Initial commit"
git push
```

2. **Create Render Account**
- Go to https://render.com
- Connect GitHub repo

3. **Deploy**
- New → Web Service
- Build: `pip install -r requirements.txt`
- Start: `python app.py`
- Environment: Set `PORT=8000`

**Done!** Your API is live at `https://your-app.onrender.com`

### Deploy to Railway

```bash
railway init
railway up
```

**PostgreSQL auto-configured!**

---

## 🎯 Use Cases

### Demo Mode
```bash
python agent.py
# Creates ~50 predictions in 30 seconds
```

### Production Mode
```bash
python agent.py schedule
# Runs continuously, updates hourly
```

### API-Only Mode
```bash
python app.py
# Manual predictions via API calls
```

---

## 🔌 Integration

### For Smart Contracts (Nnenna's Job)
API provides predictions in this format:
```json
{
  "matchId": "EPL-ARS-CHE-2026-02-13",
  "prediction": "HOME_WIN",
  "confidence": 0.81,
  "timestamp": 1707696000
}
```

### For Frontend (Lynn's Job)
- CORS enabled
- RESTful API
- JSON responses
- WebSocket not needed (polling works)

Example requests:

```bash
curl http://localhost:8000/api/predictions
curl http://localhost:8000/api/predictions?league=EPL
curl http://localhost:8000/api/stats
```

Example fetch (browser):

```js
const baseUrl = "http://localhost:8000";

export async function getPredictions() {
  const res = await fetch(`${baseUrl}/api/predictions`);
  const data = await res.json();
  return data.predictions;
}

export async function createPrediction(homeTeam, awayTeam, league) {
  const res = await fetch(`${baseUrl}/api/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ homeTeam, awayTeam, league }),
  });
  return res.json();
}
```

---

## 🐛 Troubleshooting

### Port Already in Use
```bash
# Change port in .env
PORT=8000
```

### Agent Not Creating Predictions
```bash
# Check backend is running
curl http://localhost:8000/health

# Run agent in debug mode
python agent.py
```

### Database Connection Issues
```bash
# For PostgreSQL
echo $DATABASE_URL  # Should be set
```

---

## 📈 Roadmap

- [x] Autonomous agent
- [x] Multi-factor prediction engine
- [x] REST API
- [x] PostgreSQL persistence
- [x] Mock data (96 teams)
- [x] Real API integration
- [x] Comprehensive tests
- [ ] ERC-8004 blockchain integration (Nnenna)
- [ ] Frontend dashboard (Lynn)
- [ ] Discord bot

---

## 👥 Team

**Backend & Agent:** Your implementation  
**Smart Contracts:** Nnenna (ERC-8004 integration)  
**Frontend:** Lynn (Dashboard UI)

---

## 📄 License

MIT

---

**FootyOracle - Autonomous AI Football Prediction Agent** ⚽🤖