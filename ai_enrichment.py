"""
ai_enrichment.py — AI-powered data enrichment for football predictions

Replaces broken APIs (RapidAPI injuries, Odds API) with LLM-based enrichment.
Uses Claude/OpenAI to analyze team form, injuries, and provide market insights.
"""

import os
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)

# Constants for LLM response parsing
JSON_CODE_BLOCK_START = "```json"
CODE_BLOCK_START = "```"

# Try to import anthropic, fallback to openai
try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

try:
    import openai
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False


@dataclass
class AIEnrichedData:
    """Structured output from AI enrichment"""
    form_summary: str  # "W-W-D-L-W, strong home performance"
    injury_report: List[Dict]  # List of key injuries
    key_insights: List[str]  # AI-generated insights about the matchup
    confidence_factors: Dict[str, float]  # Factors affecting confidence


class AIEnricher:
    """
    AI-powered enrichment layer for football data.
    
    Replaces:
    - RapidAPI injuries (broken)
    - Odds API market data (optional enhancement)
    
    Provides:
    - Form analysis with natural language insights
    - Injury impact assessment via web knowledge
    - Matchup-specific factors
    """

    def __init__(self):
        self.provider = os.getenv("AI_PROVIDER", "anthropic").lower()
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        
        # Model configuration
        self.anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o")
        
        # Mock mode for testing without API costs
        self.mock_mode = os.getenv("AI_MOCK_MODE", "False").lower() == "true"
        
        # Initialize clients if keys available
        self._claude_client = None
        self._openai_client = None
        
        if self.provider == "anthropic" and self.anthropic_key and _ANTHROPIC_AVAILABLE:
            self._claude_client = anthropic.Anthropic(api_key=self.anthropic_key)
            logger.info("AIEnricher: Anthropic Claude initialized")
        elif self.provider == "openai" and self.openai_key and _OPENAI_AVAILABLE:
            self._openai_client = openai.OpenAI(api_key=self.openai_key)
            logger.info("AIEnricher: OpenAI initialized")
        elif self.mock_mode:
            logger.info("AIEnricher: Mock mode (no API calls)")
        else:
            logger.warning(
                "AIEnricher: No AI provider configured. "
                "Set ANTHROPIC_API_KEY or OPENAI_API_KEY, or enable AI_MOCK_MODE"
            )

    def enrich_match_data(
        self,
        home_team: str,
        away_team: str,
        league: str,
        home_form: List[str],
        away_form: List[str],
        h2h_record: List[str],
    ) -> AIEnrichedData:
        """
        Enrich match data with AI-generated insights.
        
        Args:
            home_team: Home team name
            away_team: Away team name
            league: League code (EPL, LaLiga, etc.)
            home_form: Recent form e.g., ['W', 'W', 'D', 'L', 'W']
            away_form: Recent form e.g., ['L', 'W', 'W', 'D', 'D']
            h2h_record: Head-to-head results
            
        Returns:
            AIEnrichedData with insights, injuries, and factors
        """
        if self.mock_mode or (not self._claude_client and not self._openai_client):
            return self._mock_enrichment(home_team, away_team, home_form, away_form)

        prompt = self._build_analysis_prompt(
            home_team, away_team, league, home_form, away_form, h2h_record
        )

        try:
            response = self._call_llm(prompt)
            return self._parse_llm_response(response, home_team, away_team)
        except Exception as e:
            logger.error(f"AI enrichment failed: {e}")
            return self._mock_enrichment(home_team, away_team, home_form, away_form)

    def _build_analysis_prompt(
        self,
        home_team: str,
        away_team: str,
        league: str,
        home_form: List[str],
        away_form: List[str],
        h2h_record: List[str],
    ) -> str:
        """Build the analysis prompt for the LLM"""
        
        h2h_summary = ""
        if h2h_record:
            home_wins = h2h_record.count("HOME")
            away_wins = h2h_record.count("AWAY")
            draws = h2h_record.count("DRAW")
            h2h_summary = f"Recent H2H: Home team won {home_wins}, Away won {away_wins}, {draws} draws"

        return f"""You are a football analysis AI. Analyze this upcoming match and provide structured insights.

MATCH: {home_team} (home) vs {away_team} (away)
LEAGUE: {league}

RECENT FORM (last 5 matches):
- {home_team}: {'-'.join(home_form)}
- {away_team}: {'-'.join(away_form)}

{h2h_summary}

Provide analysis in this exact JSON format:
{{
    "form_analysis": {{
        "home_summary": "Brief analysis of home team form",
        "away_summary": "Brief analysis of away team form",
        "momentum_edge": "home" | "away" | "neutral"
    }},
    "injuries": [
        {{
            "player": "Player name (if any key injuries known)",
            "team": "home" | "away",
            "impact": "high" | "medium" | "low",
            "reason": "Why this injury matters"
        }}
    ],
    "key_factors": [
        "Factor 1 influencing the match",
        "Factor 2 influencing the match",
        "Factor 3 influencing the match"
    ],
    "confidence_weights": {{
        "home_advantage": 0.0-1.0,
        "form_momentum": 0.0-1.0,
        "h2h_history": 0.0-1.0,
        "injury_impact": 0.0-1.0
    }}
}}

If no specific injury information is available, return an empty injuries array [].
Focus on observable patterns from the form data provided.
"""

    def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM provider"""
        
        if self.provider == "anthropic" and self._claude_client:
            response = self._claude_client.messages.create(
                model=self.anthropic_model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
            
        elif self.provider == "openai" and self._openai_client:
            response = self._openai_client.chat.completions.create(
                model=self.openai_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
            )
            return response.choices[0].message.content
            
        raise RuntimeError("No LLM client available")

    def _parse_llm_response(
        self, response: str, home_team: str, away_team: str
    ) -> AIEnrichedData:
        """Parse LLM JSON response into structured data"""
        
        # Extract JSON from response (handle markdown code blocks)
        json_str = response
        if JSON_CODE_BLOCK_START in response:
            json_str = response.split(JSON_CODE_BLOCK_START)[1].split(CODE_BLOCK_START)[0].strip()
        elif CODE_BLOCK_START in response:
            json_str = response.split(CODE_BLOCK_START)[1].split(CODE_BLOCK_START)[0].strip()

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return self._mock_enrichment(home_team, away_team, [], [])

        # Build injury list
        injuries = []
        for inj in data.get("injuries", []):
            injuries.append({
                "player": inj.get("player", "Unknown"),
                "team": inj.get("team", "home"),
                "severity": inj.get("impact", "medium"),
                "reason": inj.get("reason", "Key player unavailable"),
                "position": "Unknown",
            })

        # Build confidence factors
        weights = data.get("confidence_weights", {})
        confidence_factors = {
            "home_advantage": weights.get("home_advantage", 0.15),
            "form_momentum": weights.get("form_momentum", 0.30),
            "h2h_history": weights.get("h2h_history", 0.20),
            "injury_impact": weights.get("injury_impact", 0.15),
        }

        form_analysis = data.get("form_analysis", {})
        form_summary = (
            f"{home_team}: {form_analysis.get('home_summary', 'Form data available')}. "
            f"{away_team}: {form_analysis.get('away_summary', 'Form data available')}. "
            f"Momentum: {form_analysis.get('momentum_edge', 'neutral')}"
        )

        return AIEnrichedData(
            form_summary=form_summary,
            injury_report=injuries,
            key_insights=data.get("key_factors", []),
            confidence_factors=confidence_factors,
        )

    def _mock_enrichment(
        self, home_team: str, away_team: str, home_form: List[str], away_form: List[str]
    ) -> AIEnrichedData:
        """Generate mock enrichment data when AI is unavailable"""
        
        # Calculate basic form scores for mock insights
        def form_score(form):
            if not form:
                return 0.5
            wins = form.count("W")
            draws = form.count("D")
            return (wins * 3 + draws) / (len(form) * 3)
        
        home_score = form_score(home_form)
        away_score = form_score(away_form)
        
        if home_score > away_score:
            momentum = "home"
        elif away_score > home_score:
            momentum = "away"
        else:
            momentum = "neutral"
        
        insights = [
            f"{home_team} showing {'strong' if home_score > 0.6 else 'mixed'} home form",
            f"{away_team} {'performing well' if away_score > 0.6 else 'struggling'} on the road",
            f"Momentum slightly favors {momentum} side based on recent results",
        ]

        return AIEnrichedData(
            form_summary=f"Home: {'-'.join(home_form) if home_form else 'N/A'}, Away: {'-'.join(away_form) if away_form else 'N/A'}, Momentum: {momentum}",
            injury_report=[],  # Empty in mock mode
            key_insights=insights,
            confidence_factors={
                "home_advantage": 0.15,
                "form_momentum": 0.30,
                "h2h_history": 0.20,
                "injury_impact": 0.0,  # No injury data in mock
            },
        )

    def _build_market_prompt(
        self,
        home_team: str,
        away_team: str,
        league: str,
        home_form: List[str],
        away_form: List[str],
        home_position: int,
        away_position: int,
        h2h: List[str],
    ) -> str:
        form_section = ""
        if home_form or away_form:
            n = len(home_form or away_form or [])
            home_str = '-'.join(home_form) if home_form else 'unknown'
            away_str = '-'.join(away_form) if away_form else 'unknown'
            form_section = f"\nCURRENT FORM (last {n} matches, most recent last):\n- {home_team}: {home_str}\n- {away_team}: {away_str}\n"

        position_section = ""
        if home_position and away_position:
            position_section = f"\nLEAGUE TABLE POSITION (out of 20):\n- {home_team}: {home_position}th\n- {away_team}: {away_position}th\n"

        h2h_section = ""
        if h2h:
            hw, aw, dr = h2h.count("HOME"), h2h.count("AWAY"), h2h.count("DRAW")
            h2h_section = f"\nHEAD-TO-HEAD (last {len(h2h)} meetings): {home_team} won {hw}, {away_team} won {aw}, {dr} draws\n"

        return f"""You are a football odds compiler. Estimate fair win probabilities for this match based on the data below.
Weight CURRENT FORM heavily — recent results matter more than historical reputation.

MATCH: {home_team} (home) vs {away_team} (away)
LEAGUE: {league}
{form_section}{position_section}{h2h_section}
Output ONLY this JSON (probabilities must sum to 1.0):
{{
    "home_win_prob": 0.XX,
    "draw_prob": 0.XX,
    "away_win_prob": 0.XX,
    "confidence": "high" | "medium" | "low",
    "reasoning": "One sentence citing the key factor driving these probabilities"
}}
"""

    def _extract_json(self, response: str) -> str:
        if JSON_CODE_BLOCK_START in response:
            return response.split(JSON_CODE_BLOCK_START)[1].split(CODE_BLOCK_START)[0].strip()
        if CODE_BLOCK_START in response:
            return response.split(CODE_BLOCK_START)[1].split(CODE_BLOCK_START)[0].strip()
        return response

    def get_market_insights(
        self,
        home_team: str,
        away_team: str,
        league: str,
        home_form: List[str] = None,
        away_form: List[str] = None,
        home_position: int = None,
        away_position: int = None,
        h2h: List[str] = None,
    ) -> Optional[Dict]:
        """
        Get AI-generated market insights using real form and H2H data.

        Returns fair win probabilities (caller applies bookmaker margin).
        """
        if self.mock_mode or (not self._claude_client and not self._openai_client):
            return None

        prompt = self._build_market_prompt(
            home_team, away_team, league,
            home_form or [], away_form or [],
            home_position, away_position, h2h or [],
        )

        try:
            response = self._call_llm(prompt)
            return json.loads(self._extract_json(response))
        except Exception as e:
            logger.error(f"Market insights failed: {e}")
            return None
