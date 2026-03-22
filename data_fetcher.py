import logging
import requests
import os
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import time
import re
import unicodedata
from urllib.parse import urlparse
from dotenv import load_dotenv
from mock_data import MockDataProvider
from ai_enrichment import AIEnricher, AIEnrichedData

load_dotenv()

logger = logging.getLogger(__name__)

_MISSING_FOOTBALL_API_KEY = "Missing FOOTBALL_API_KEY"


class DataFetcher:
    """
    Fetch football data from football-data.org with AI enrichment.

    Primary API:
    - football-data.org (matches, standings, teams, form)

    AI Enrichment (replaces broken APIs):
    - AI-powered injury analysis
    - AI-generated form insights
    - AI market insights (replaces odds API)

    Features:
    - Automatic fallback to mock data
    - Response caching
    - Rate limit handling
    - AI-powered data enrichment
    """

    def __init__(self):
        # API Configuration
        self.football_api_key = os.getenv("FOOTBALL_API_KEY", "")
        self.football_api_url = os.getenv(
            "FOOTBALL_API_URL", "https://api.football-data.org/v4"
        )

        # AI Enrichment (replaces broken RapidAPI and Odds API)
        self.ai_enricher = AIEnricher()
        self.ai_enrichment_enabled = os.getenv("AI_ENRICHMENT_ENABLED", "True").lower() == "true"

        self.agent_id = os.getenv("AGENT_ID", "")

        # Mock mode
        self.mock_mode = os.getenv("MOCK_MODE", "True").lower() == "true"

        self.strict_real_data = os.getenv("STRICT_REAL_DATA", "False").lower() == "true"
        if not self.mock_mode:
            self.strict_real_data = True

        self.requests_per_minute = int(os.getenv("REQUESTS_PER_MINUTE", "10"))
        self.min_request_interval_seconds = (
            60.0 / self.requests_per_minute if self.requests_per_minute > 0 else 0.0
        )
        self._last_request_time = 0.0
        self._last_response: Optional[requests.Response] = None

        # Mock data provider
        self.mock = MockDataProvider()

        # League ID mappings (football-data.org only)
        self.league_ids = {
            "football_data": {
                "EPL": "PL",
                "LaLiga": "PD",
                "SerieA": "SA",
                "Bundesliga": "BL1",
                "Ligue1": "FL1",
            },
        }

        # Cache
        self.cache = {}
        self.cache_duration = 300  # 5 minutes

        if self.mock_mode:
            logger.info("DataFetcher: MOCK MODE enabled")
        else:
            logger.info("DataFetcher: Real API mode")
            if self.football_api_key:
                logger.info("  football-data.org connected")
            if self.ai_enrichment_enabled:
                logger.info("  AI enrichment enabled")

    def _strict_fail(self, reason: str):
        if self.strict_real_data and not self.mock_mode:
            raise RuntimeError(reason)

    def _normalize_team_name(self, name: str) -> str:
        name = unicodedata.normalize("NFKD", name)
        name = "".join(ch for ch in name if not unicodedata.combining(ch))
        name = name.lower()
        name = re.sub(r"\b(cf|fc|sc|ac|rcd|cd|ud|de|la|el|the)\b", " ", name)
        name = re.sub(r"[^a-z0-9]+", " ", name)
        name = re.sub(r"\s+", " ", name).strip()
        return name

    def _string_token_score(self, a: str, b: str) -> int:
        a_tokens = set(a.split())
        b_tokens = set(b.split())
        if not a_tokens or not b_tokens:
            return 0
        return len(a_tokens & b_tokens)

    # TTLs for data that changes at different rates
    CACHE_TTL_LIVE = 300          # 5 min  — form, standings (changes match-to-match)
    CACHE_TTL_DAILY = 86400       # 24 hr  — H2H history, AI odds (stable within a day)

    def _get_cached(self, cache_key: Optional[str], ttl: int = None) -> Optional[Dict]:
        if not cache_key or cache_key not in self.cache:
            return None
        cached_time, cached_data = self.cache[cache_key]
        effective_ttl = ttl if ttl is not None else self.cache_duration
        if (datetime.now() - cached_time).total_seconds() < effective_ttl:
            return cached_data
        return None

    def _set_cache(self, cache_key: Optional[str], data: Dict) -> None:
        if cache_key:
            self.cache[cache_key] = (datetime.now(), data)

    def _throttle_if_needed(self) -> None:
        if self.mock_mode or self.min_request_interval_seconds <= 0:
            return

        now = time.monotonic()
        sleep_for = self._last_request_time + self.min_request_interval_seconds - now
        if sleep_for > 0:
            time.sleep(sleep_for)

    def _request_once(self, url: str, headers: Dict) -> requests.Response:
        self._throttle_if_needed()
        self._last_request_time = time.monotonic()
        return requests.get(url, headers=headers, timeout=10)

    def _backoff_seconds_from_response(self, response: requests.Response) -> float:
        retry_after = response.headers.get("Retry-After")
        if not retry_after:
            return 6.0
        try:
            return float(retry_after)
        except ValueError:
            return 6.0

    def _should_raise_on_real_api_failure(self) -> bool:
        return self.strict_real_data and not self.mock_mode

    def _handle_rate_limit(self, url: str, headers: Dict, cache_key: Optional[str]) -> Optional[Dict]:
        logger.warning("Rate limit exceeded — retrying after backoff")
        backoff = self._backoff_seconds_from_response(self._last_response) if self._last_response else 6.0
        time.sleep(max(0.0, backoff))

        retry_response = self._request_once(url, headers)
        if retry_response.status_code == 200:
            data = retry_response.json()
            self._set_cache(cache_key, data)
            return data

        if self._should_raise_on_real_api_failure():
            raise RuntimeError(
                f"API rate limit exceeded (429). Last response: {retry_response.text}"
            )
        return None

    def _handle_non_200(self, response: requests.Response) -> Optional[Dict]:
        if response.status_code in (401, 403):
            if self._should_raise_on_real_api_failure():
                raise RuntimeError(
                    f"API auth error ({response.status_code}). Response: {response.text}"
                )
            logger.warning("API auth error %d: %s", response.status_code, response.text[:200])
            return None

        if response.status_code == 404:
            return None

        if self._should_raise_on_real_api_failure():
            raise RuntimeError(
                f"API error ({response.status_code}). Response: {response.text}"
            )

        logger.warning("API error %d: %s", response.status_code, response.text[:200])
        return None

    def _make_request(
        self, url: str, headers: Dict, cache_key: str = None
    ) -> Optional[Dict]:
        """
        Make API request with caching

        Args:
            url: Full API URL
            headers: Request headers
            cache_key: Optional cache key

        Returns:
            JSON response or None
        """
        cached_data = self._get_cached(cache_key)
        if cached_data is not None:
            return cached_data

        try:
            response = self._request_once(url, headers)
            if response.status_code == 200:
                data = response.json()
                self._set_cache(cache_key, data)
                return data

            if response.status_code == 429:
                self._last_response = response
                return self._handle_rate_limit(url, headers, cache_key)

            return self._handle_non_200(response)

        except Exception as e:
            logger.error("Request failed: %s", e)
            return None

    def _outcome_from_match_score(
        self, team_name: str, home_team: str, home_score: int, away_score: int
    ) -> str:
        if home_team == team_name:
            if home_score > away_score:
                return "W"
            if home_score < away_score:
                return "L"
            return "D"

        if away_score > home_score:
            return "W"
        if away_score < home_score:
            return "L"
        return "D"

    def _fetch_team_matches_football_data(self, team_id: int) -> Optional[Dict]:
        url = f"{self.football_api_url}/teams/{team_id}/matches?status=FINISHED&limit=50"
        headers = {"X-Auth-Token": self.football_api_key}
        return self._make_request(url, headers, f"team_matches_{team_id}")

    def _is_between_teams(self, match_home_id: int, match_away_id: int, home_id: int, away_id: int) -> bool:
        return (match_home_id == home_id and match_away_id == away_id) or (
            match_home_id == away_id and match_away_id == home_id
        )

    def _determine_venue_winner(self, match_home_id: int, match_away_id: int, home_score: int, away_score: int) -> Optional[int]:
        if home_score > away_score:
            return match_home_id
        elif away_score > home_score:
            return match_away_id
        return None

    def _map_to_home_away_perspective(self, venue_winner: int, home_id: int) -> str:
        return "HOME" if venue_winner == home_id else "AWAY"

    def _parse_h2h_results(
        self, matches: List[Dict], home_id: int, away_id: int, last_n: int
    ) -> List[str]:
        """
        Returns results from the perspective of home_id (the designated home team).
        HOME = home_id won, AWAY = away_id won, DRAW = draw.
        """
        results: List[str] = []
        for match in matches:
            match_home_id = match["homeTeam"]["id"]
            match_away_id = match["awayTeam"]["id"]
            
            if not self._is_between_teams(match_home_id, match_away_id, home_id, away_id):
                continue

            home_score = match["score"]["fullTime"]["home"]
            away_score = match["score"]["fullTime"]["away"]

            venue_winner = self._determine_venue_winner(match_home_id, match_away_id, home_score, away_score)
            
            if venue_winner is None:
                results.append("DRAW")
            else:
                results.append(self._map_to_home_away_perspective(venue_winner, home_id))

            if len(results) >= last_n:
                break

        return results

    def _get_league_id(self, league: str, api_type: str = "football_data") -> str:
        """Get league ID for specific API"""
        return self.league_ids.get(api_type, {}).get(league, "PL")

    # =========================================================================
    # TEAM FORM
    # =========================================================================

    def _matches_venue_filter(self, team_name: str, home_team_name: str, venue: str) -> bool:
        """Return True if the match should be included given the venue filter."""
        if venue is None:
            return True
        is_home = (home_team_name == team_name)
        return is_home if venue == "HOME" else not is_home

    def _parse_form_from_matches(self, matches: List[Dict], team_name: str, venue: str, last_n: int) -> List[str]:
        form = []
        for match in matches:
            home_team = match["homeTeam"]["name"]
            if not self._matches_venue_filter(team_name, home_team, venue):
                continue
            home_score = match["score"]["fullTime"]["home"]
            away_score = match["score"]["fullTime"]["away"]
            form.append(self._outcome_from_match_score(team_name, home_team, home_score, away_score))
            if len(form) >= last_n:
                break
        return form

    def get_team_form(self, team_name: str, league: str, last_n: int = 5, venue: str = None) -> List[str]:
        """
        Get team's recent form, optionally filtered by venue.

        Args:
            venue: "HOME" for home matches only, "AWAY" for away only, None for all.

        Returns:
            ['W', 'L', 'D', 'W', 'W']
        """
        if self.mock_mode:
            return self.mock.get_team_form(team_name, last_n)
        if not self.football_api_key:
            self._strict_fail(_MISSING_FOOTBALL_API_KEY)
            return self.mock.get_team_form(team_name, last_n)

        try:
            league_id = self._get_league_id(league, "football_data")
            team_id = self._get_team_id_football_data(team_name, league_id)

            if not team_id:
                self._strict_fail(f"Could not resolve team id for '{team_name}'")
                return self.mock.get_team_form(team_name, last_n)

            fetch_limit = last_n * 3 if venue else last_n
            cache_key = f"form_{team_id}_{venue or 'all'}"
            url = f"{self.football_api_url}/teams/{team_id}/matches?status=FINISHED&limit={fetch_limit}"
            headers = {"X-Auth-Token": self.football_api_key}
            data = self._make_request(url, headers, cache_key)

            if not data or "matches" not in data:
                self._strict_fail("No matches returned for team form")
                return self.mock.get_team_form(team_name, last_n)

            return self._parse_form_from_matches(data["matches"], team_name, venue, last_n)

        except Exception as e:
            if not self.strict_real_data:
                print(f"Error fetching form: {e}")
            self._strict_fail(f"Error fetching form: {e}")
            return self.mock.get_team_form(team_name, last_n)

    def _get_team_id_football_data(
        self, team_name: str, league_id: str
    ) -> Optional[int]:
        """Get team ID from football-data.org"""
        url = f"{self.football_api_url}/competitions/{league_id}/teams"
        headers = {"X-Auth-Token": self.football_api_key}
        data = self._make_request(url, headers, f"teams_{league_id}")

        if not data or "teams" not in data:
            return None

        for team in data["teams"]:
            if team_name.lower() in team["name"].lower():
                return team["id"]

        return None

    # =========================================================================
    # INJURIES (AI-Powered)
    # =========================================================================

    def get_injuries(self, team_name: str, league: str) -> List[Dict]:
        """
        Get injury list via AI enrichment.

        Source: AI analysis (replaces broken RapidAPI)
        Fallback: Mock data

        Returns:
            [
                {
                    "player": "Name",
                    "position": "Forward",
                    "severity": "moderate",
                    "expectedReturn": "2026-03-15"
                },
                ...
            ]
        """
        if self.mock_mode:
            return self.mock.get_injuries(team_name)

        # Use AI enrichment for injury data
        if self.ai_enrichment_enabled and self.ai_enricher:
            try:
                # Get enriched data with empty form (injuries only)
                enriched = self.ai_enricher.enrich_match_data(
                    home_team=team_name,
                    away_team="",
                    league=league,
                    home_form=[],
                    away_form=[],
                    h2h_record=[],
                )
                
                # Filter injuries for this team
                team_injuries = [
                    inj for inj in enriched.injury_report
                    if inj.get("team") == "home" or not inj.get("team")
                ]
                
                # Format to expected structure
                injuries = []
                for inj in team_injuries:
                    injuries.append({
                        "player": inj.get("player", "Unknown"),
                        "position": inj.get("position", "Unknown"),
                        "severity": inj.get("severity", "medium"),
                        "reason": inj.get("reason", "Unavailable"),
                    })
                
                if injuries:
                    logger.info(f"AI enrichment found {len(injuries)} injuries for {team_name}")
                    return injuries
                    
            except Exception as e:
                logger.warning(f"AI injury enrichment failed: {e}")

        # Fallback to mock
        return self.mock.get_injuries(team_name)


    # =========================================================================
    # HEAD-TO-HEAD
    # =========================================================================

    def get_h2h(
        self, home_team: str, away_team: str, league: str, last_n: int = 10
    ) -> List[str]:
        """
        Get head-to-head record

        Source: football-data.org
        Fallback: Mock data

        Returns:
            ['HOME', 'AWAY', 'DRAW', ...]
        """
        if self.mock_mode:
            return self.mock.get_h2h(home_team, away_team, last_n)
        if not self.football_api_key:
            self._strict_fail(_MISSING_FOOTBALL_API_KEY)
            return self.mock.get_h2h(home_team, away_team, last_n)

        try:
            # H2H history is stable within a day — use daily cache
            h2h_cache_key = f"h2h_{home_team}_{away_team}_{league}"
            cached_h2h = self._get_cached(h2h_cache_key, ttl=self.CACHE_TTL_DAILY)
            if cached_h2h:
                return cached_h2h

            league_id = self._get_league_id(league, "football_data")
            home_id = self._get_team_id_football_data(home_team, league_id)
            away_id = self._get_team_id_football_data(away_team, league_id)

            if not home_id or not away_id:
                self._strict_fail("Could not resolve team ids for H2H")
                return self.mock.get_h2h(home_team, away_team, last_n)

            data = self._fetch_team_matches_football_data(home_id)

            if not data or "matches" not in data:
                self._strict_fail("No matches returned for H2H")
                return self.mock.get_h2h(home_team, away_team, last_n)

            h2h_results = self._parse_h2h_results(data["matches"], home_id, away_id, last_n)

            if h2h_results:
                self._set_cache(h2h_cache_key, h2h_results[:last_n])
                return h2h_results[:last_n]
            return self.mock.get_h2h(home_team, away_team, last_n)

        except Exception as e:
            if not self.strict_real_data:
                print(f"Error fetching H2H: {e}")
            self._strict_fail(f"Error fetching H2H: {e}")
            return self.mock.get_h2h(home_team, away_team, last_n)

    # =========================================================================
    # LEAGUE STANDINGS
    # =========================================================================

    def get_table_position(self, team_name: str, league: str) -> int:
        """
        Get league position

        Source: football-data.org
        Fallback: Mock data

        Returns:
            Position (1-20)
        """
        if self.mock_mode:
            return self.mock.get_table_position(team_name, league)
        if not self.football_api_key:
            self._strict_fail(_MISSING_FOOTBALL_API_KEY)
            return self.mock.get_table_position(team_name, league)

        try:
            league_id = self._get_league_id(league, "football_data")
            url = f"{self.football_api_url}/competitions/{league_id}/standings"
            headers = {"X-Auth-Token": self.football_api_key}
            data = self._make_request(url, headers, f"standings_{league_id}")

            if not data or "standings" not in data:
                self._strict_fail("No standings returned")
                return self.mock.get_table_position(team_name, league)

            standings = data["standings"][0]["table"]

            for entry in standings:
                if team_name.lower() in entry["team"]["name"].lower():
                    return entry["position"]

            self._strict_fail(f"Team '{team_name}' not found in standings")
            return self.mock.get_table_position(team_name, league)

        except Exception as e:
            if not self.strict_real_data:
                print(f"Error fetching standings: {e}")
            self._strict_fail(f"Error fetching standings: {e}")
            return self.mock.get_table_position(team_name, league)

    # =========================================================================
    # MATCH RESULTS
    # =========================================================================

    def _outcome_from_score(self, home_score: int, away_score: int) -> str:
        if home_score > away_score:
            return "HOME_WIN"
        if away_score > home_score:
            return "AWAY_WIN"
        return "DRAW"

    def _try_parse_fixture_match_id(self, match_id: str) -> Optional[int]:
        parts = match_id.split("-")
        # Format A: League-FixtureID (e.g. "EPL-538093")
        # Format B: League-FixtureID-HomeCode-AwayCode-YYYY-MM-DD (e.g. "EPL-538093-TOT-NOT-2026-03-22")
        if len(parts) < 2:
            return None
        fixture_part = parts[1]
        if not fixture_part.isdigit():
            return None
        return int(fixture_part)

    def _get_match_result_by_fixture_id(self, fixture_id: int) -> Optional[str]:
        headers = {"X-Auth-Token": self.football_api_key}
        url = f"{self.football_api_url}/matches/{fixture_id}"
        data = self._make_request(url, headers, f"match_{fixture_id}")

        if not data:
            if self.strict_real_data and not self.mock_mode:
                raise RuntimeError("Fixture lookup failed (no data returned)")
            return None

        match = data.get("match") if isinstance(data, dict) else None
        if match is None:
            match = data

        if not isinstance(match, dict) or "status" not in match or "score" not in match:
            if self.strict_real_data and not self.mock_mode:
                keys = list(data.keys()) if isinstance(data, dict) else type(data)
                raise RuntimeError(
                    f"Fixture lookup returned unexpected payload: {keys}"
                )
            return None

        if match.get("status") != "FINISHED":
            return None

        home_score = match["score"]["fullTime"]["home"]
        away_score = match["score"]["fullTime"]["away"]
        return self._outcome_from_score(home_score, away_score)

    def _get_match_result_by_legacy_id(self, match_id: str) -> Optional[str]:
        parts = match_id.split("-")
        if len(parts) < 4:
            self._strict_fail("Invalid match_id format")
            return self.mock.get_match_result(match_id)

        league = parts[0]
        home_abbr = parts[1].strip().upper()
        away_abbr = parts[2].strip().upper()
        date_str = "-".join(parts[3:])

        league_id = self._get_league_id(league, "football_data")
        headers = {"X-Auth-Token": self.football_api_key}
        url = f"{self.football_api_url}/competitions/{league_id}/matches?dateFrom={date_str}&dateTo={date_str}"
        data = self._make_request(url, headers, f"result_{match_id}")

        if not data or "matches" not in data:
            self._strict_fail("No matches returned for result lookup")
            return self.mock.get_match_result(match_id)

        for match in data["matches"]:
            if match.get("status") != "FINISHED":
                continue

            match_home = match["homeTeam"]["name"]
            match_away = match["awayTeam"]["name"]
            match_home_abbr = match_home[:3].strip().upper()
            match_away_abbr = match_away[:3].strip().upper()

            if match_home_abbr != home_abbr or match_away_abbr != away_abbr:
                continue

            home_score = match["score"]["fullTime"]["home"]
            away_score = match["score"]["fullTime"]["away"]
            return self._outcome_from_score(home_score, away_score)

        return None

    def get_match_result(self, match_id: str) -> Optional[str]:
        """
        Get match result

        Source: football-data.org
        Fallback: Mock data

        Returns:
            "HOME_WIN", "DRAW", "AWAY_WIN" or None
        """
        if self.mock_mode:
            return self.mock.get_match_result(match_id)
        if not self.football_api_key:
            self._strict_fail(_MISSING_FOOTBALL_API_KEY)
            return self.mock.get_match_result(match_id)

        try:
            fixture_id = self._try_parse_fixture_match_id(match_id)
            if fixture_id is not None:
                return self._get_match_result_by_fixture_id(fixture_id)

            return self._get_match_result_by_legacy_id(match_id)

        except Exception as e:
            if not self.strict_real_data:
                print(f"Error fetching result: {e}")
            self._strict_fail(f"Error fetching result: {e}")
            return self.mock.get_match_result(match_id)

    # =========================================================================
    # UPCOMING MATCHES
    # =========================================================================

    def get_league_matches(self, league: str, days_ahead: int = 7) -> List[Dict]:
        """
        Get upcoming matches

        Source: football-data.org
        Fallback: Mock data

        Returns:
            [
                {
                    "homeTeam": "Arsenal",
                    "awayTeam": "Chelsea",
                    "date": "2026-02-12",
                    "time": "15:00"
                },
                ...
            ]
        """
        if self.mock_mode:
            return self.mock.get_league_matches(league, days_ahead)
        if not self.football_api_key:
            self._strict_fail(_MISSING_FOOTBALL_API_KEY)
            return self.mock.get_league_matches(league, days_ahead)

        try:
            league_id = self._get_league_id(league, "football_data")

            date_from = datetime.now().strftime("%Y-%m-%d")
            date_to = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

            url = f"{self.football_api_url}/competitions/{league_id}/matches?dateFrom={date_from}&dateTo={date_to}"
            headers = {"X-Auth-Token": self.football_api_key}
            data = self._make_request(url, headers, f"matches_{league_id}")

            if not data or "matches" not in data:
                self._strict_fail("No matches returned for league matches")
                return self.mock.get_league_matches(league, days_ahead)

            matches = []
            for match in data["matches"]:
                # Include both SCHEDULED and TIMED matches
                if match["status"] in ["SCHEDULED", "TIMED"]:
                    match_date = datetime.fromisoformat(
                        match["utcDate"].replace("Z", "+00:00")
                    )

                    matches.append(
                        {
                            "fixtureId": match.get("id"),
                            "homeTeam": match["homeTeam"]["name"],
                            "awayTeam": match["awayTeam"]["name"],
                            "date": match_date.strftime("%Y-%m-%d"),
                            "time": match_date.strftime("%H:%M"),
                        }
                    )

            return matches

        except Exception as e:
            if not self.strict_real_data:
                print(f"Error fetching matches: {e}")
            self._strict_fail(f"Error fetching matches: {e}")
            return self.mock.get_league_matches(league, days_ahead)

    def get_fixture_info(self, fixture_id: int) -> Optional[Dict]:
        """
        Fetch team names and date for a single fixture using the permitted
        /v4/matches/{id} endpoint (no date-range restriction on free plan).

        Works for both scheduled and finished matches.

        Returns:
            {"homeTeam": "Newcastle United FC", "awayTeam": "Sunderland AFC",
             "date": "2026-03-22", "status": "SCHEDULED"} or None
        """
        if self.mock_mode:
            return None  # Mock mode doesn't map fixture IDs

        if not self.football_api_key:
            return None

        try:
            url = f"{self.football_api_url}/matches/{fixture_id}"
            headers = {"X-Auth-Token": self.football_api_key}
            # Reuse the same cache key as _get_match_result_by_fixture_id so we
            # don't make a duplicate request if both methods are called for the same fixture.
            data = self._make_request(url, headers, f"match_{fixture_id}")

            if not data:
                return None

            match = data.get("match") if isinstance(data, dict) else None
            if match is None:
                match = data

            if not isinstance(match, dict) or "homeTeam" not in match:
                return None

            match_date = datetime.fromisoformat(
                match["utcDate"].replace("Z", "+00:00")
            )
            return {
                "homeTeam": match["homeTeam"]["name"],
                "awayTeam": match["awayTeam"]["name"],
                "date": match_date.strftime("%Y-%m-%d"),
                "status": match.get("status"),
            }

        except Exception as e:
            logger.warning("Error fetching fixture info for %d: %s", fixture_id, e)
            return None

    # =========================================================================
    # MARKET ODDS (AI-Powered)
    # =========================================================================

    def get_market_odds(self, home_team: str, away_team: str, league: str) -> Optional[Dict]:
        """
        Get market odds via AI enrichment (replaces the-odds-api.com).

        Source: AI probability estimates converted to odds
        Fallback: calibrated mock odds

        Returns:
            {
                "home": 2.50,   # decimal odds — home win
                "draw": 3.20,   # decimal odds — draw
                "away": 2.80    # decimal odds — away win
            }
            or None if odds cannot be generated
        """
        if self.mock_mode:
            return self.mock.get_market_odds(home_team, away_team, league)

        # AI odds are stable within a day — check cache first
        odds_cache_key = f"market_odds_{home_team}_{away_team}_{league}"
        cached = self._get_cached(odds_cache_key, ttl=self.CACHE_TTL_DAILY)
        if cached:
            return cached

        # Try AI enrichment
        if self.ai_enrichment_enabled and self.ai_enricher:
            try:
                home_form = self.get_team_form(home_team, league)
                away_form = self.get_team_form(away_team, league)
                home_pos = self.get_table_position(home_team, league)
                away_pos = self.get_table_position(away_team, league)
                h2h = self.get_h2h(home_team, away_team, league)

                insights = self.ai_enricher.get_market_insights(
                    home_team, away_team, league,
                    home_form=home_form,
                    away_form=away_form,
                    home_position=home_pos,
                    away_position=away_pos,
                    h2h=h2h,
                )

                if insights:
                    home_prob = max(insights.get("home_win_prob", 0.33), 0.05)
                    draw_prob = max(insights.get("draw_prob", 0.33), 0.05)
                    away_prob = max(insights.get("away_win_prob", 0.33), 0.05)

                    total_fair = home_prob + draw_prob + away_prob
                    margin = 1.05
                    home_prob = (home_prob / total_fair) * margin
                    draw_prob = (draw_prob / total_fair) * margin
                    away_prob = (away_prob / total_fair) * margin

                    odds = {
                        "home": round(1.0 / home_prob, 2),
                        "draw": round(1.0 / draw_prob, 2),
                        "away": round(1.0 / away_prob, 2),
                        "source": "ai",
                        "confidence": insights.get("confidence", "medium"),
                    }

                    self._set_cache(odds_cache_key, odds)
                    logger.info(f"AI market odds for {home_team} vs {away_team}: {odds}")
                    return odds

            except Exception as e:
                logger.warning(f"AI market odds failed: {e}")

        # Fallback to mock
        return self.mock.get_market_odds(home_team, away_team, league)
