"""
railway_cron.py - Single-run agent for Railway Cron Jobs

Railway Cron Jobs run this script on a schedule (e.g., every hour).
Unlike GitHub Actions, Railway has no timeout limits.

Setup in Railway:
1. Deploy your backend as a service
2. Add a Cron Job service pointing to: python railway_cron.py
3. Set schedule: 0 * * * * (hourly)
4. Add required env vars to the cron service
"""

import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_agent_cycle():
    """Run one agent cycle - fetch matches, generate predictions, submit to API"""
    from agent import FootyOracleAgent
    
    backend_url = os.getenv("BACKEND_URL", "http://localhost:5000")
    agent = FootyOracleAgent(backend_url=backend_url)
    
    logger.info("=" * 60)
    logger.info("Starting Railway Agent Cycle")
    logger.info("=" * 60)
    
    try:
        # Run predictions for all leagues
        agent.run_predictions()
        logger.info("Predictions completed")
    except Exception as e:
        logger.error(f"Prediction cycle failed: {e}")
        return False
    
    try:
        # Auto-resolve completed matches
        agent.auto_resolve()
        logger.info("Auto-resolve completed")
    except Exception as e:
        logger.error(f"Auto-resolve failed: {e}")
        # Don't fail the whole cycle if resolve fails
    
    logger.info("=" * 60)
    logger.info("Agent Cycle Complete")
    logger.info("=" * 60)
    return True


if __name__ == "__main__":
    success = run_agent_cycle()
    sys.exit(0 if success else 1)
