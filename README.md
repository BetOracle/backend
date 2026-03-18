# FootyOracle Backend

**AI-Powered Football Prediction Agent**  
*Autonomous agent with multi-factor analysis and persistent storage*

---

## 🎯 What This Is

FootyOracle is an autonomous football prediction backend that:
- Generates match predictions
- Stores predictions in PostgreSQL
- Exposes a REST API for the frontend

---

## 📚 Documentation

- **Frontend API (request/response contracts)**
  - `docs/FRONTEND_API.md`
- **Deploy to Railway (recommended) or Render**
  - See deployment section below
- **Data sources & configuration (mock vs real, API keys)**
  - `docs/DATA_SOURCES.md`
- **Local quickstart**
  - `docs/QUICKSTART.md`

---

## 🚀 Quick Start (local)

See `docs/QUICKSTART.md`.

---

## 🔌 API

See `docs/FRONTEND_API.md`.

---

## 🔧 Configuration

See `docs/DATA_SOURCES.md`.

---

## 🚀 Deployment

### Railway (Recommended)

**Advantages:** No timeout limits, native cron jobs, better for persistent agents.

**1. Deploy API Service:**
```bash
# Railway CLI
railway login
railway init
railway add --database postgres

# Deploy
git push railway main
```

**2. Add Cron Job:**
- In Railway dashboard, add a new service
- Select "Cron Job"
- Command: `python railway_cron.py`
- Schedule: `0 * * * *` (hourly)
- Add same env vars as main service

**3. Environment Variables:**
```
BLOCKCHAIN_ENABLED=True
AGENT_WALLET=0x...
PREDICTION_CONTRACT=0x...
AGENT_ID=0x...
AGENT_PRIVATE_KEY=0x...
CELO_RPC_URL=https://forno.celo.org
```

### Alternative: Render

See `docs/DEPLOY_RENDER.md` for Render-specific instructions.

**Note:** GitHub Actions workflows removed (timeout limits). Use Railway Cron instead.

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

**Backend & Agent:** Pope  
**Smart Contracts:** Nnenna (ERC-8004 integration)  
**Frontend:** Lynn (Dashboard UI)

---

## 📄 License

MIT

---

**FootyOracle - Autonomous AI Football Prediction Agent** ⚽🤖