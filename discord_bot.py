"""
discord_bot.py — FootyOracle Discord Bot

Commands:
    !predict  — List today's pending predictions
    !results  — Last 5 resolved predictions with W/L
    !stats    — Overall win rate and accuracy

Automated alerts:
    send_prediction_alert_sync() — Called by the agent after each value bet is found.
    Posts to #predictions channel with match details, confidence, edge, and factors.
"""

import os
import logging
import asyncio
import threading
import aiohttp
import requests as http_requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

try:
    import discord
    from discord.ext import commands
    _DISCORD_AVAILABLE = True
except ImportError:
    _DISCORD_AVAILABLE = False
    logger.warning("discord.py not installed — Discord bot will be disabled. Run: pip install discord.py")


# =====================================================================================
# BOT
# =====================================================================================

class FootyOracleDiscordBot:
    """
    Discord bot with prediction alert broadcasting and slash commands.

    Usage (from agent):
        bot = FootyOracleDiscordBot(backend_url="http://localhost:5000")
        bot.start_in_background()
        ...
        bot.send_prediction_alert_sync(match, prediction, confidence, edge, factors)
    """

    def __init__(self, backend_url: str = None):
        self.backend_url = backend_url or os.getenv("BACKEND_URL", "http://localhost:5000")
        self.token = os.getenv("DISCORD_TOKEN", "")
        self.channel_id = int(os.getenv("DISCORD_CHANNEL_ID", "0") or "0")

        if not _DISCORD_AVAILABLE:
            raise ImportError("discord.py is required. Run: pip install 'discord.py>=2.3.0'")

        intents = discord.Intents.default()
        intents.message_content = True

        self.bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
        self._loop: asyncio.AbstractEventLoop = None
        self._thread: threading.Thread = None

        self._register_commands()

    # =========================================================================
    # COMMANDS
    # =========================================================================

    def _register_commands(self):
        """Register all Discord bot commands."""
        self._register_on_ready()
        self._register_predict_command()
        self._register_results_command()
        self._register_stats_command()
        self._register_help_command()

    def _register_on_ready(self):
        """Register the on_ready event handler."""
        @self.bot.event
        async def on_ready():
            logger.info("FootyOracle Discord bot connected as %s", self.bot.user)

    def _register_predict_command(self):
        """Register the predict command."""
        @self.bot.command(name="predict")
        async def predict_cmd(ctx):
            """Show today's pending predictions."""
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self.backend_url}/api/predictions",
                        params={"resolved": "false", "limit": "10"},
                        timeout=10,
                    ) as resp:
                        data = await resp.json()
                        predictions = data.get("predictions", [])

                if not predictions:
                    await ctx.send("🔮 No pending predictions today.")
                    return

                lines = ["**🔮 Today's Pending Predictions**\n"]
                for p in predictions[:10]:
                    lines.append(
                        f"• **{p['matchId']}** — {p['prediction']} "
                        f"(conf: {p['confidence']:.0%})"
                    )
                await ctx.send("\n".join(lines))

            except Exception as e:
                logger.error("Discord !predict error: %s", e)
                await ctx.send("⚠️ Could not fetch predictions.")

    def _register_results_command(self):
        """Register the results command."""
        @self.bot.command(name="results")
        async def results_cmd(ctx):
            """Show the last 5 resolved predictions."""
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self.backend_url}/api/predictions",
                        params={"resolved": "true", "limit": "5"},
                        timeout=10,
                    ) as resp:
                        data = await resp.json()
                        predictions = data.get("predictions", [])

                if not predictions:
                    await ctx.send("📊 No resolved predictions yet.")
                    return

                lines = ["**📊 Last 5 Results**\n"]
                for p in predictions[:5]:
                    icon = "✅" if p.get("correct") else "❌"
                    lines.append(
                        f"{icon} **{p['matchId']}** — Predicted: {p['prediction']} | "
                        f"Actual: {p.get('actualOutcome', 'N/A')}"
                    )
                await ctx.send("\n".join(lines))

            except Exception as e:
                logger.error("Discord !results error: %s", e)
                await ctx.send("⚠️ Could not fetch results.")

    def _register_stats_command(self):
        """Register the stats command."""
        @self.bot.command(name="stats")
        async def stats_cmd(ctx):
            """Show overall accuracy stats."""
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self.backend_url}/api/stats", timeout=10
                    ) as resp:
                        data = await resp.json()
                stats = data.get("statistics", data)

                total = stats.get("totalPredictions", 0)
                resolved = stats.get("resolved", 0)
                correct = stats.get("correct", 0)
                accuracy = stats.get("accuracy", 0.0)

                lines = [
                    "**📈 FootyOracle Stats**\n",
                    f"• Total predictions: **{total}**",
                    f"• Resolved: **{resolved}** | Pending: **{total - resolved}**",
                    f"• Correct: **{correct}** | Accuracy: **{accuracy:.1f}%**",
                ]
                await ctx.send("\n".join(lines))

            except Exception as e:
                logger.error("Discord !stats error: %s", e)
                await ctx.send("⚠️ Could not fetch stats.")

    def _register_help_command(self):
        """Register the help command."""
        @self.bot.command(name="help")
        async def help_cmd(ctx):
            await ctx.send(
                "**🤖 FootyOracle Commands**\n\n"
                "`!predict` — Today's pending predictions\n"
                "`!results` — Last 5 resolved predictions\n"
                "`!stats`   — Overall win rate and accuracy"
            )

    # =========================================================================
    # ALERT BROADCASTING
    # =========================================================================

    def _build_alert_message(
        self,
        match: dict,
        prediction: str,
        confidence: float,
        edge: float,
        factors: dict,
    ) -> str:
        """Build a human-readable prediction alert message."""
        home = match.get("homeTeam", "Home")
        away = match.get("awayTeam", "Away")
        date = match.get("date", datetime.now().strftime("%Y-%m-%d"))

        outcome_label = {
            "HOME_WIN": f"{home} to win",
            "AWAY_WIN": f"{away} to win",
            "DRAW": "Draw",
        }.get(prediction, prediction)

        form_score = factors.get("formScore", 0)
        h2h_score = factors.get("h2hScore", 0)
        injury = factors.get("injuryImpact", 0)
        rest = factors.get("restDaysScore", 0)

        factor_lines = []
        if abs(form_score) >= 0.2:
            side = home if form_score > 0 else away
            factor_lines.append(f"• {'Strong' if abs(form_score) > 0.4 else 'Good'} {side} recent form")
        if abs(h2h_score) >= 0.2:
            h2h_fav = home if h2h_score > 0 else away
            factor_lines.append(f"• {h2h_fav} H2H advantage")
        if abs(injury) >= 0.1:
            inj_side = away if injury > 0 else home
            factor_lines.append(f"• {inj_side} injury issues")
        if abs(rest) >= 0.2:
            rest_side = home if rest > 0 else away
            factor_lines.append(f"• {rest_side} better rested")

        factor_text = "\n".join(factor_lines) if factor_lines else "• Model probability edge"

        return (
            f"🔮 **New Prediction Alert** — {date}\n\n"
            f"**Match:** {home} vs {away}\n"
            f"**Pick:** {outcome_label}\n"
            f"**Confidence:** {confidence:.0%}\n"
            f"**Edge vs Market:** {edge:.0%}\n\n"
            f"**Factors:**\n{factor_text}"
        )

    async def _send_alert_async(self, message: str):
        """Send message to the configured Discord channel."""
        if not self.channel_id:
            logger.warning("DISCORD_CHANNEL_ID not set — skipping alert")
            return

        channel = self.bot.get_channel(self.channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(self.channel_id)
            except Exception as e:
                logger.error("Could not find Discord channel %d: %s", self.channel_id, e)
                return

        await channel.send(message)

    def send_prediction_alert_sync(
        self,
        match: dict,
        prediction: str,
        confidence: float,
        edge: float,
        factors: dict,
    ):
        """
        Thread-safe synchronous call to post a prediction alert.
        Called from the agent loop (not an async context).
        """
        if not self._loop or not self._loop.is_running():
            logger.warning("Discord event loop not running — alert not sent")
            return

        message = self._build_alert_message(match, prediction, confidence, edge, factors)
        asyncio.run_coroutine_threadsafe(self._send_alert_async(message), self._loop)

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    def start_in_background(self):
        """Start the discord bot in a background thread (non-blocking)."""
        if not self.token:
            logger.warning("DISCORD_TOKEN not set — bot will not start")
            return

        def _run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self.bot.start(self.token))

        self._thread = threading.Thread(target=_run, daemon=True, name="discord-bot")
        self._thread.start()
        logger.info("Discord bot started in background thread")

    def stop(self):
        """Gracefully stop the bot."""
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.bot.close(), self._loop)


# =====================================================================================
# STANDALONE ENTRY POINT (run bot without the full agent)
# =====================================================================================

if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    backend_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    discord_bot = FootyOracleDiscordBot(backend_url=backend_url)
    discord_bot.start_in_background()

    # Block main thread
    try:
        import time
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        discord_bot.stop()
        logger.info("Bot stopped")
