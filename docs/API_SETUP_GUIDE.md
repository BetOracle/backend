# API Setup Guide - FootyOracle

## 📊 Data Sources Overview

FootyOracle uses **multiple API sources** for comprehensive football data:

| Data Type | Primary API | Fallback |
|-----------|-------------|----------|
| Matches & Fixtures | football-data.org | Mock |
| League Standings | football-data.org | Mock |
| Team Form | football-data.org | Mock |
| H2H Records | football-data.org | Mock |
| **Injuries** | **API-Football (RapidAPI)** | **Mock** |
| Player Stats | API-Football (RapidAPI) | Mock |

---

## 🔑 Getting API Keys (Free)

### 1. football-data.org (Recommended - Start Here)

**What it provides:**
- Match fixtures and results
- League standings
- Team information
- Head-to-head records

**Free tier limits:**
- 10 requests/minute
- 5 major leagues (EPL, LaLiga, SerieA, Bundesliga, Ligue1)

**How to get:**
1. Go to https://www.football-data.org/client/register
2. Sign up (email + password)
3. Verify email
4. Copy API key from dashboard
5. Add to `.env`:
   ```bash
   FOOTBALL_API_KEY=your_key_here
   MOCK_MODE=False
   ```

---

### 2. API-Football via RapidAPI (For Injuries)

**What it provides:**
- Player injuries (real-time)
- Detailed player statistics
- Team lineups
- Match events

**Free tier limits:**
- 100 requests/day
- All major leagues

**How to get:**
1. Go to https://rapidapi.com/api-sports/api/api-football
2. Sign up for RapidAPI account
3. Subscribe to FREE plan
4. Copy your RapidAPI key
5. Add to `.env`:
   ```bash
   RAPIDAPI_KEY=your_rapidapi_key_here
   ```

---

## 🚀 Configuration Modes

### Mode 1: Mock Only (Default)
**Best for:** Development, testing, hackathon MVP

```bash
# .env
MOCK_MODE=True
FOOTBALL_API_KEY=
RAPIDAPI_KEY=
```

**Features:**
- ✅ No API keys needed
- ✅ No rate limits
- ✅ Fast responses
- ✅ Realistic simulated data
- ❌ Not real match data

---

### Mode 2: football-data.org Only
**Best for:** Basic production, budget-conscious

```bash
# .env
MOCK_MODE=False
FOOTBALL_API_KEY=your_key_here
RAPIDAPI_KEY=
```

**Features:**
- ✅ Real match data
- ✅ Real standings
- ✅ Real fixtures
- ⚠️  Mock injuries (no RapidAPI key)
- ⚠️  10 req/min limit

---

### Mode 3: Full Real Data (Recommended for Production)
**Best for:** Production with complete accuracy

```bash
# .env
MOCK_MODE=False
FOOTBALL_API_KEY=your_football_data_key
RAPIDAPI_KEY=your_rapidapi_key
```

**Features:**
- ✅ Real match data
- ✅ Real standings
- ✅ Real fixtures
- ✅ **Real injuries**
- ✅ Real player stats
- ⚠️  Combined rate limits apply

---

## 🔄 How Fallback Works

The system intelligently falls back to mock data when:

```
Try Real API
    ↓
API Key exists? → No → Use Mock Data
    ↓ Yes
Make Request
    ↓
Success? → Yes → Return Real Data
    ↓ No
Rate Limited? → Yes → Use Cached Data → No Cache? → Use Mock Data
    ↓ No
Network Error? → Yes → Use Mock Data
    ↓ No
Return Real Data
```

**You'll never see an error** - the system always returns data!

---

## 📊 API Usage Calculator

### Scenario: Agent runs every hour

**football-data.org:**
```
Per agent cycle (5 leagues):
- Get upcoming matches: 5 requests
- Get standings: 5 requests
- Get team form: ~10 requests
Total: ~20 requests/cycle

Hourly: 20 requests
Daily: 480 requests
Limit: 600 requests/hour ✅ SAFE
```

**RapidAPI (for injuries):**
```
Per agent cycle (5 leagues):
- Get injuries per team: ~10 requests
Total: ~10 requests/cycle

Hourly: 10 requests
Daily: 240 requests
Limit: 100 requests/day ⚠️ EXCEEDS!

Solution: Check injuries less frequently
- Run injury check every 6 hours instead
- Daily: 40 requests ✅ SAFE
```

---

## ⚙️ Optimizing API Usage

### 1. Reduce Agent Frequency

```python
# In agent.py, modify check interval
self.check_interval_minutes = 120  # Check every 2 hours instead of 1
```

### 2. Cache Aggressively

```python
# In data_fetcher.py (already configured)
self.cache_duration = 300  # 5 minutes (increase if needed)
```

### 3. Batch Requests

The agent already batches requests by league - no changes needed!

### 4. Injury Check Frequency

```python
# In agent.py
# Only check injuries once per day instead of every cycle
if datetime.now().hour == 6:  # Check at 6 AM only
    injuries = self.data_fetcher.get_injuries(team, league)
```

---

## 🧪 Testing Your Setup

### Test Individual APIs

```bash
# Test football-data.org
curl -H "X-Auth-Token: YOUR_KEY" \
  https://api.football-data.org/v4/competitions/PL/standings

# Test RapidAPI
curl -H "X-RapidAPI-Key: YOUR_KEY" \
  -H "X-RapidAPI-Host: v3.football.api-sports.io" \
  https://v3.football.api-sports.io/injuries?team=33
```

### Test in Python

```python
from data_fetcher import DataFetcher

fetcher = DataFetcher()

# Test match data
matches = fetcher.get_league_matches("EPL")
print(f"Found {len(matches)} matches")

# Test injuries (requires RapidAPI key)
injuries = fetcher.get_injuries("Arsenal", "EPL")
print(f"Found {len(injuries)} injuries")

# Test standings
position = fetcher.get_table_position("Arsenal", "EPL")
print(f"Arsenal position: {position}")
```

---

## 📈 Upgrade Recommendations

### Free Tier Sufficient For:
- ✅ Hackathon/MVP
- ✅ Testing/Development
- ✅ Small-scale production (< 100 users)

### Consider Paid Tier When:
- ❌ Rate limits hit frequently
- ❌ Need real-time live scores
- ❌ Need all leagues worldwide
- ❌ Need advanced statistics

**Pricing:**
- football-data.org: €19/month for premium
- RapidAPI: $10-50/month depending on tier

---

## 🔒 Security Best Practices

### Never Commit API Keys

```bash
# .env is in .gitignore ✅
# Only commit .env.example ✅
```

### Use Environment Variables

```bash
# Production (Heroku/Railway)
heroku config:set FOOTBALL_API_KEY=your_key
railway variables set FOOTBALL_API_KEY=your_key
```

### Rotate Keys Regularly

Change API keys every 3-6 months or if leaked.

---

## ✅ Setup Checklist

- [ ] Signed up for football-data.org
- [ ] Got API key from football-data.org
- [ ] Added FOOTBALL_API_KEY to `.env`
- [ ] Tested football-data.org connection
- [ ] (Optional) Signed up for RapidAPI
- [ ] (Optional) Got RapidAPI key
- [ ] (Optional) Added RAPIDAPI_KEY to `.env`
- [ ] Set MOCK_MODE=False in `.env`
- [ ] Tested agent runs without errors
- [ ] Verified real data is being fetched

---

## 🚨 Troubleshooting

### "Rate limit exceeded"
```bash
# Check your usage
# Increase cache duration
# Reduce agent frequency
```

### "API key invalid"
```bash
# Verify key is correct in .env
# Check key hasn't expired
# Regenerate key if needed
```

### "No data returned"
```bash
# System falls back to mock automatically
# Check logs for specific error
# Verify API service is up
```

---

**You're all set!** The system works perfectly with or without API keys. 🚀