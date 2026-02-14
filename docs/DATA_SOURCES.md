# Data Sources & Configuration

This document describes how FootyOracle fetches match data and how to configure mock vs real data.

---

## Environment variables

### Core
- `MOCK_MODE`
  - `True`: use mock data
  - `False`: use football-data.org as the primary source

- `REQUESTS_PER_MINUTE`
  - Throttle for external requests (approximate).

### football-data.org
- `FOOTBALL_API_KEY`
  - Required when `MOCK_MODE=False`.

### Injuries (RapidAPI)
- `INJURIES_ENABLED`
  - `False` recommended unless you are subscribed to the RapidAPI product.

- `RAPIDAPI_KEY`
  - Optional; only needed if `INJURIES_ENABLED=True` and you have access.

---

## Recommended configs

### MVP / production-friendly (recommended)
```bash
MOCK_MODE=False
FOOTBALL_API_KEY=...
INJURIES_ENABLED=False
REQUESTS_PER_MINUTE=8
```

### Development without API keys
```bash
MOCK_MODE=True
INJURIES_ENABLED=False
```

---

## Notes on fallback behavior
- When `MOCK_MODE=True`, all data comes from the mock provider.
- When `MOCK_MODE=False`, the system uses real APIs where possible.
- Injuries are optional and controlled by `INJURIES_ENABLED`.

---

## Getting the football-data.org key
1. Register: https://www.football-data.org/client/register
2. Copy API key from your dashboard
3. Set `FOOTBALL_API_KEY` in your environment
