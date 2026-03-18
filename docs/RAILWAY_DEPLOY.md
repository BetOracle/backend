# Railway Deployment Checklist

## Prerequisites
- [ ] Railway CLI installed (`npm install -g @railway/cli`)
- [ ] Railway account connected
- [ ] Celo mainnet wallet with CELO for gas

## Step 1: Prepare Environment

### 1.1 Generate Backend Wallet
```bash
cd /Users/mac/Documents/BetOracle/backend
python generate_backend_wallet.py
# Save output to .env (DO NOT COMMIT)
```

### 1.2 Configure backend/.env
```bash
# Copy and edit
cp .env.example .env

# Required for Railway:
FOOTBALL_API_KEY=your_api_key_here
DATABASE_URL=${{Postgres.DATABASE_URL}}  # Railway will inject this
BLOCKCHAIN_ENABLED=False  # Enable AFTER contract deployment
CELO_RPC_URL=https://forno.celo.org
AGENT_WALLET=            # Fill after contract deployment
PREDICTION_CONTRACT=      # Fill after contract deployment
AGENT_ID=                 # Fill after contract deployment
AGENT_PRIVATE_KEY=        # From generate_backend_wallet.py
```

## Step 2: Deploy Backend API

### 2.1 Initialize Railway Project
```bash
cd /Users/mac/Documents/BetOracle/backend
railway login
railway init
# Select "Empty Project"
```

### 2.2 Add PostgreSQL Database
```bash
railway add --database postgres
# Or use Railway dashboard: New → Database → PostgreSQL
```

### 2.3 Deploy Service
```bash
# Push to Railway
git add .
git commit -m "Ready for Railway deployment"
railway up

# Or if you have a GitHub repo connected:
git push origin main
```

### 2.4 Configure Environment Variables in Railway Dashboard
Go to your service → Variables → Add:

| Variable | Value | Source |
|----------|-------|--------|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Reference |
| `FOOTBALL_API_KEY` | your_key | Secret |
| `AGENT_PRIVATE_KEY` | 0x... | Secret |
| `AGENT_WALLET` | 0x... | Text |
| `PREDICTION_CONTRACT` | 0x... | Text |
| `BLOCKCHAIN_ENABLED` | False | Text |

## Step 3: Verify API Works

```bash
# Get Railway URL from dashboard
curl https://your-app.railway.app/health
# Should return: {"status": "healthy", ...}
```

## Step 4: Deploy Contracts to CELO Mainnet

### 4.1 Configure contracts/.env
```bash
cd /Users/mac/Documents/BetOracle/contracts
cp .env.example .env
# Edit:
PRIVATE_KEY=your_deployer_private_key
RPC_URL=https://forno.celo.org
CELOSCAN_API_KEY=your_key
BACKEND_ADDRESS=0x...  # From Step 1.1
```

### 4.2 Deploy
```bash
forge script script/Deploy.s.sol --rpc-url $RPC_URL --broadcast
# Save output addresses!
```

### 4.3 Verify on CeloScan (optional but recommended)
```bash
forge verify-contract $AGENT_WALLET BetOracleAgentWallet --chain celo
forge verify-contract $PREDICTION_CONTRACT BetOraclePrediction --chain celo
```

## Step 5: Authorize Backend

### 5.1 From contracts folder with deployer key:
```bash
cast send $AGENT_WALLET "authorizeBackend(address,bool)" $BACKEND_ADDRESS true \
  --rpc-url https://forno.celo.org --private-key $PRIVATE_KEY
```

### 5.2 Verify authorization:
```bash
cast call $AGENT_WALLET "isAuthorized(address)" $BACKEND_ADDRESS \
  --rpc-url https://forno.celo.org
# Should return: true
```

## Step 6: Fund Backend Wallet

Send CELO to your backend wallet address (from Step 1.1).
Minimum: 0.1 CELO for gas (enough for ~100 predictions).

## Step 7: Enable Blockchain in Railway

Update Railway environment variable:
```
BLOCKCHAIN_ENABLED=True
```

## Step 8: Add Railway Cron Job

### 8.1 In Railway Dashboard:
1. Click "New" → "Cron Job"
2. Name: "agent-cron"
3. Command: `python railway_cron.py`
4. Schedule: `0 * * * *` (every hour)

### 8.2 Copy all environment variables from main service to cron job

## Step 9: Test End-to-End

```bash
# Test prediction endpoint
curl -X POST https://your-app.railway.app/api/predict \
  -H "Content-Type: application/json" \
  -d '{"homeTeam": "Arsenal", "awayTeam": "Chelsea", "league": "EPL"}'

# Check health with blockchain status
curl https://your-app.railway.app/health
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `No module named 'web3'` | `pip install web3` in requirements.txt |
| Database connection failed | Check `DATABASE_URL` is set and referenced correctly |
| Blockchain submission fails | Verify `AGENT_PRIVATE_KEY` and authorization |
| "Not authorized" error | Re-run authorization in Step 5 |
| Gas errors | Fund backend wallet with more CELO |

## Costs Estimate

- **Railway**: Free tier (500 hours/month) usually sufficient
- **PostgreSQL**: Railway free tier includes 100MB
- **CELO Gas**: ~0.001 CELO per prediction (~$0.0005 at current prices)
- **Football API**: football-data.org free tier (10 calls/minute)

## Important Files

- `Procfile` → Tells Railway to use gunicorn
- `railway_cron.py` → Cron job entry point
- `requirements.txt` → Dependencies (includes gunicorn, web3)
- `.env` → Environment variables (NEVER COMMIT)
