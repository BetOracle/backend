import requests
import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import time
from dotenv import load_dotenv
from mock_data import MockDataProvider

load_dotenv()


class DataFetcher:
    """
    Fetch football data from multiple APIs

    Primary APIs:
    - football-data.org (matches, standings, teams)
    - API-Football/RapidAPI (injuries, player stats)
    - TheSportsDB (additional data)

    Features:
    - Automatic fallback to mock data
    - Response caching
    - Rate limit handling
    - Multi-source redundancy
    """

    def __init__(self):
        # API Configuration
        self.football_api_key = os.getenv("FOOTBALL_API_KEY", "")
        self.football_api_url = os.getenv(
            "FOOTBALL_API_URL", "https://api.football-data.org/v4"
        )

        self.rapidapi_key = os.getenv("RAPIDAPI_KEY", "")
        self.rapidapi_url = os.getenv(
            "RAPIDAPI_URL", "https://v3.football.api-sports.io"
        )

        # Mock mode
        self.mock_mode = os.getenv("MOCK_MODE", "True").lower() == "true"

        self.requests_per_minute = int(os.getenv("REQUESTS_PER_MINUTE", "10"))
        self.min_request_interval_seconds = (
            60.0 / self.requests_per_minute if self.requests_per_minute > 0 else 0.0
        )
        self._last_request_time = 0.0

        # Mock data provider
        self.mock = MockDataProvider()

        # League ID mappings
        self.league_ids = {
            "football_data": {
                "EPL": "PL",
                "LaLiga": "PD",
                "SerieA": "SA",
                "Bundesliga": "BL1",
                "Ligue1": "FL1",
            },
            "rapidapi": {
                "EPL": 39,
                "LaLiga": 140,
                "SerieA": 135,
                "Bundesliga": 78,
                "Ligue1": 61,
            },
        }

        # Cache
        self.cache = {}
        self.cache_duration = 300  # 5 minutes

        if self.mock_mode:
            print("⚠️  DataFetcher: MOCK MODE enabled")
        else:
            print("✅ DataFetcher: Real API mode")
            if self.football_api_key:
                print("   ✅ football-data.org connected")
            if self.rapidapi_key:
                print("   ✅ RapidAPI connected")

    def _get_cached(self, cache_key: Optional[str]) -> Optional[Dict]:
        if not cache_key:
            return None
        if cache_key not in self.cache:
            return None
        cached_time, cached_data = self.cache[cache_key]
        if (datetime.now() - cached_time).seconds < self.cache_duration:
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
                print("⚠️  Rate limit exceeded")
                time.sleep(max(0.0, self._backoff_seconds_from_response(response)))

                retry_response = self._request_once(url, headers)
                if retry_response.status_code == 200:
                    data = retry_response.json()
                    self._set_cache(cache_key, data)
                    return data

                return None

            print(f"⚠️  API error {response.status_code}")
            return None

        except Exception as e:
            print(f"❌ Request failed: {e}")
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

    def _parse_h2h_results(
        self, matches: List[Dict], home_id: int, away_id: int, last_n: int
    ) -> List[str]:
        def is_between_teams(match_home_id: int, match_away_id: int) -> bool:
            return (match_home_id == home_id and match_away_id == away_id) or (
                match_home_id == away_id and match_away_id == home_id
            )

        results: List[str] = []
        for match in matches:
            match_home_id = match["homeTeam"]["id"]
            match_away_id = match["awayTeam"]["id"]
            if not is_between_teams(match_home_id, match_away_id):
                continue

            home_score = match["score"]["fullTime"]["home"]
            away_score = match["score"]["fullTime"]["away"]

            if home_score > away_score:
                results.append("HOME")
            elif away_score > home_score:
                results.append("AWAY")
            else:
                results.append("DRAW")

            if len(results) >= last_n:
                break

        return results

    def _get_league_id(self, league: str, api_type: str = "football_data") -> str:
        """Get league ID for specific API"""
        return self.league_ids.get(api_type, {}).get(league, "PL")

    # =========================================================================
    # TEAM FORM
    # =========================================================================

    def get_team_form(self, team_name: str, league: str, last_n: int = 5) -> List[str]:
        """
        Get team's recent form

        Source: football-data.org
        Fallback: Mock data

        Returns:
            ['W', 'L', 'D', 'W', 'W']
        """
        if self.mock_mode or not self.football_api_key:
            return self.mock.get_team_form(team_name, last_n)

        try:
            league_id = self._get_league_id(league, "football_data")
            team_id = self._get_team_id_football_data(team_name, league_id)

            if not team_id:
                return self.mock.get_team_form(team_name, last_n)

            url = f"{self.football_api_url}/teams/{team_id}/matches?status=FINISHED&limit={last_n}"
            headers = {"X-Auth-Token": self.football_api_key}
            data = self._make_request(url, headers, f"form_{team_id}")

            if not data or "matches" not in data:
                return self.mock.get_team_form(team_name, last_n)

            form = []
            for match in data["matches"][:last_n]:
                home_team = match["homeTeam"]["name"]
                home_score = match["score"]["fullTime"]["home"]
                away_score = match["score"]["fullTime"]["away"]

                form.append(
                    self._outcome_from_match_score(
                        team_name, home_team, home_score, away_score
                    )
                )

            return form[:last_n]

        except Exception as e:
            print(f"Error fetching form: {e}")
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
    # INJURIES
    # =========================================================================

    def get_injuries(self, team_name: str, league: str) -> List[Dict]:
        """
        Get injury list

        Source: API-Football (RapidAPI)
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
        if self.mock_mode or not self.rapidapi_key:
            return self.mock.get_injuries(team_name)

        try:
            # Get team ID for RapidAPI
            league_id = self._get_league_id(league, "rapidapi")
            team_id = self._get_team_id_rapidapi(team_name, league_id)

            if not team_id:
                return self.mock.get_injuries(team_name)

            # Fetch injuries from RapidAPI
            url = f"{self.rapidapi_url}/injuries?team={team_id}"
            headers = {
                "X-RapidAPI-Key": self.rapidapi_key,
                "X-RapidAPI-Host": "v3.football.api-sports.io",
            }

            data = self._make_request(url, headers, f"injuries_{team_id}")

            if not data or "response" not in data:
                return self.mock.get_injuries(team_name)

            # Parse injuries
            injuries = []
            for injury in data["response"]:
                player_name = injury.get("player", {}).get("name", "Unknown")
                injury_type = injury.get("player", {}).get("type", "Unknown")
                reason = injury.get("player", {}).get("reason", "")

                # Determine severity from injury type/reason
                if any(
                    word in reason.lower() for word in ["fracture", "torn", "rupture"]
                ):
                    severity = "severe"
                elif any(
                    word in reason.lower() for word in ["strain", "sprain", "knock"]
                ):
                    severity = "moderate"
                else:
                    severity = "minor"

                injuries.append(
                    {
                        "player": player_name,
                        "position": injury.get("player", {}).get("position", "Unknown"),
                        "severity": severity,
                        "reason": reason,
                        "type": injury_type,
                    }
                )

            return injuries

        except Exception as e:
            print(f"Error fetching injuries: {e}")
            return self.mock.get_injuries(team_name)

    def _get_team_id_rapidapi(self, team_name: str, league_id: int) -> Optional[int]:
        """Get team ID from RapidAPI"""
        url = f"{self.rapidapi_url}/teams?league={league_id}&season=2024"
        headers = {
            "X-RapidAPI-Key": self.rapidapi_key,
            "X-RapidAPI-Host": "v3.football.api-sports.io",
        }

        data = self._make_request(url, headers, f"teams_rapid_{league_id}")

        if not data or "response" not in data:
            return None

        for team_data in data["response"]:
            team = team_data.get("team", {})
            if team_name.lower() in team.get("name", "").lower():
                return team.get("id")

        return None

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
        if self.mock_mode or not self.football_api_key:
            return self.mock.get_h2h(home_team, away_team, last_n)

        try:
            league_id = self._get_league_id(league, "football_data")
            home_id = self._get_team_id_football_data(home_team, league_id)
            away_id = self._get_team_id_football_data(away_team, league_id)

            if not home_id or not away_id:
                return self.mock.get_h2h(home_team, away_team, last_n)

            data = self._fetch_team_matches_football_data(home_id)

            if not data or "matches" not in data:
                return self.mock.get_h2h(home_team, away_team, last_n)

            h2h_results = self._parse_h2h_results(data["matches"], home_id, away_id, last_n)

            return (
                h2h_results[:last_n]
                if h2h_results
                else self.mock.get_h2h(home_team, away_team, last_n)
            )

        except Exception as e:
            print(f"Error fetching H2H: {e}")
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
        if self.mock_mode or not self.football_api_key:
            return self.mock.get_table_position(team_name, league)

        try:
            league_id = self._get_league_id(league, "football_data")
            url = f"{self.football_api_url}/competitions/{league_id}/standings"
            headers = {"X-Auth-Token": self.football_api_key}
            data = self._make_request(url, headers, f"standings_{league_id}")

            if not data or "standings" not in data:
                return self.mock.get_table_position(team_name, league)

            standings = data["standings"][0]["table"]

            for entry in standings:
                if team_name.lower() in entry["team"]["name"].lower():
                    return entry["position"]

            return self.mock.get_table_position(team_name, league)

        except Exception as e:
            print(f"Error fetching standings: {e}")
            return self.mock.get_table_position(team_name, league)

    # =========================================================================
    # MATCH RESULTS
    # =========================================================================

    def get_match_result(self, match_id: str) -> Optional[str]:
        """
        Get match result

        Source: football-data.org
        Fallback: Mock data

        Returns:
            "HOME_WIN", "DRAW", "AWAY_WIN" or None
        """
        if self.mock_mode or not self.football_api_key:
            return self.mock.get_match_result(match_id)

        try:
            parts = match_id.split("-")
            league = parts[0]
            date_str = "-".join(parts[3:])

            league_id = self._get_league_id(league, "football_data")

            url = f"{self.football_api_url}/competitions/{league_id}/matches?dateFrom={date_str}&dateTo={date_str}"
            headers = {"X-Auth-Token": self.football_api_key}
            data = self._make_request(url, headers, f"result_{match_id}")

            if not data or "matches" not in data:
                return self.mock.get_match_result(match_id)

            for match in data["matches"]:
                if match["status"] == "FINISHED":
                    home_score = match["score"]["fullTime"]["home"]
                    away_score = match["score"]["fullTime"]["away"]

                    if home_score > away_score:
                        return "HOME_WIN"
                    elif away_score > home_score:
                        return "AWAY_WIN"
                    else:
                        return "DRAW"

            return None

        except Exception as e:
            print(f"Error fetching result: {e}")
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
        if self.mock_mode or not self.football_api_key:
            return self.mock.get_league_matches(league, days_ahead)

        try:
            league_id = self._get_league_id(league, "football_data")

            date_from = datetime.now().strftime("%Y-%m-%d")
            date_to = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

            url = f"{self.football_api_url}/competitions/{league_id}/matches?dateFrom={date_from}&dateTo={date_to}"
            headers = {"X-Auth-Token": self.football_api_key}
            data = self._make_request(url, headers, f"matches_{league_id}")

            if not data or "matches" not in data:
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
                            "homeTeam": match["homeTeam"]["name"],
                            "awayTeam": match["awayTeam"]["name"],
                            "date": match_date.strftime("%Y-%m-%d"),
                            "time": match_date.strftime("%H:%M"),
                        }
                    )

            return matches

        except Exception as e:
            print(f"Error fetching matches: {e}")
            return self.mock.get_league_matches(league, days_ahead)
