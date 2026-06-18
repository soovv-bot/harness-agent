#!/usr/bin/env python3
"""
API Clients for Sports Data Sources

This module provides Python clients for accessing various sports data APIs and websites:
- Official sports organizations (FIFA, NBA, UFC, etc.)
- Sports statistics websites (BoxRec, ESPNcricinfo, etc.)
- Esports data sources (Liquipedia, HLTV, etc.)

Usage:
    from sports_apis import UFCClient, BoxRecClient, LoLClient, ESPNClient

    # Get UFC fighter data
    ufc = UFCClient()
    fighter = ufc.get_fighter("Jon Jones")

    # Get boxing records
    boxing = BoxRecClient()
    records = boxing.search_fighter("Mike Tyson")
"""

import json
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


# ============================================================================
# Base Client
# ============================================================================

@dataclass
class APIError(Exception):
    """Custom exception for API errors"""
    status_code: int
    message: str


class BaseClient:
    """Base class for sports API clients"""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; SportsDataBot/1.0)'
        })

    def _get(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Make GET request and return JSON response"""
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise APIError(401, "Authentication required")
            elif e.response.status_code == 403:
                raise APIError(403, "Access forbidden")
            elif e.response.status_code == 429:
                raise APIError(429, "Rate limit exceeded")
            else:
                raise APIError(e.response.status_code, str(e))
        except requests.exceptions.Timeout:
            raise APIError(408, "Request timeout")
        except Exception as e:
            raise APIError(500, str(e))

    def _get_html(self, url: str, params: Optional[Dict] = None) -> str:
        """Make GET request and return HTML"""
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except Exception as e:
            raise APIError(500, str(e))


# ============================================================================
# MMA/UFC Client
# ============================================================================

class UFCClient(BaseClient):
    """Client for UFC official data

    Note: UFC doesn't have a public API, but we can scrape their website
    """

    BASE_URL = "https://www.ufc.com"

    def get_fighter_stats(self, fighter_name: str) -> Optional[Dict]:
        """Get fighter statistics by scraping UFC website

        Args:
            fighter_name: Fighter name (e.g., "Jon Jones", "Khabib Nurmagomedov")

        Returns:
            Fighter statistics dict or None
        """
        # UFC URL format: https://www.ufc.com/athlete/jon-jones
        url_slug = fighter_name.lower().replace(' ', '-').replace('.', '')
        url = f"{self.BASE_URL}/athlete/{url_slug}"

        try:
            html = self._get_html(url)
            # Parse HTML to extract fighter data
            # This would require BeautifulSoup or similar
            # For now, return a placeholder
            return {
                "name": fighter_name,
                "url": url,
                "source": "ufc"
            }
        except Exception as e:
            return None

    def get_upcoming_events(self) -> List[Dict]:
        """Get upcoming UFC events"""
        url = f"{self.BASE_URL}/events/upcoming"
        try:
            html = self._get_html(url)
            # Parse HTML to extract event data
            return []
        except Exception as e:
            return []


# ============================================================================
# Boxing Records Client (BoxRec)
# ============================================================================

class BoxRecClient(BaseClient):
    """Client for BoxRec boxing records

    BoxRec URL: https://boxrec.com
    """

    BASE_URL = "https://boxrec.com"

    def search_fighter(self, name: str) -> List[Dict]:
        """Search for boxer by name

        Args:
            name: Boxer name

        Returns:
            List of matching boxers with records
        """
        # BoxRec search URL
        url = f"{self.BASE_URL}/search"
        params = {"q": name, "txt": name}

        try:
            html = self._get_html(url, params)
            # Parse HTML to extract boxer data
            return []
        except Exception as e:
            return []

    def get_fighter_record(self, boxer_id: str) -> Optional[Dict]:
        """Get detailed boxer record

        Args:
            boxer_id: BoxRec boxer ID

        Returns:
            Detailed boxer record
        """
        url = f"{self.BASE_URL}/en/box-pro/{boxer_id}"
        try:
            html = self._get_html(url)
            # Parse HTML to extract record data
            return {}
        except Exception as e:
            return None


# ============================================================================
# Esports Clients
# ============================================================================

class LiquipediaClient(BaseClient):
    """Client for Liquipedia esports data

    Liquipedia is like Wikipedia for esports
    """

    BASE_URL = "https://liquipedia.net"

    def __init__(self, game: str = "lol"):
        """Initialize Liquipedia client

        Args:
            game: Game identifier (lol, dota2, csgo, overwatch, etc.)
        """
        super().__init__()
        self.game = game

    def get_player(self, player_name: str) -> Optional[Dict]:
        """Get esports player information

        Args:
            player_name: Player in-game name

        Returns:
            Player information or None
        """
        # Liquipedia URL format
        url = f"{self.BASE_URL}/{self.game}/{player_name.replace(' ', '_')}"

        try:
            html = self._get_html(url)
            # Parse HTML to extract player data
            return {
                "name": player_name,
                "url": url,
                "game": self.game
            }
        except Exception as e:
            return None

    def get_team(self, team_name: str) -> Optional[Dict]:
        """Get esports team information

        Args:
            team_name: Team name

        Returns:
            Team information or None
        """
        url = f"{self.BASE_URL}/{self.game}/{team_name.replace(' ', '_')}"

        try:
            html = self._get_html(url)
            return {
                "name": team_name,
                "url": url,
                "game": self.game
            }
        except Exception as e:
            return None

    def get_tournament(self, tournament_name: str) -> Optional[Dict]:
        """Get tournament information

        Args:
            tournament_name: Tournament name

        Returns:
            Tournament information or None
        """
        url = f"{self.BASE_URL}/{self.game}/{tournament_name.replace(' ', '_')}"

        try:
            html = self._get_html(url)
            return {
                "name": tournament_name,
                "url": url,
                "game": self.game
            }
        except Exception as e:
            return None


class HLTVClient(BaseClient):
    """Client for HLTV CS:GO data

    HLTV: https://www.hltv.org
    """

    BASE_URL = "https://www.hltv.org"

    def get_team_rankings(self) -> List[Dict]:
        """Get current CS:GO team rankings"""
        url = f"{self.BASE_URL}/ranking"
        try:
            html = self._get_html(url)
            # Parse HTML to extract rankings
            return []
        except Exception as e:
            return []

    def get_player_stats(self, player_id: str) -> Optional[Dict]:
        """Get player statistics"""
        url = f"{self.BASE_URL}/player/{player_id}"
        try:
            html = self._get_html(url)
            return {}
        except Exception as e:
            return None


class LoLClient(BaseClient):
    """Client for League of Legends Esports

    Official LoL Esports API: https://esports-api.lolesports.com
    """

    BASE_URL = "https://esports-api.lolesports.com"

    def get_tournaments(self) -> List[Dict]:
        """Get active LoL tournaments"""
        # Note: This API may require authentication
        url = f"{self.BASE_URL}/tournaments"
        try:
            data = self._get(url)
            return data.get("data", [])
        except Exception as e:
            return []

    def get_teams(self, tournament_id: str) -> List[Dict]:
        """Get teams in a tournament"""
        url = f"{self.BASE_URL}/tournaments/{tournament_id}/teams"
        try:
            data = self._get(url)
            return data.get("data", [])
        except Exception as e:
            return []


# ============================================================================
# Sports Statistics Clients
# ============================================================================

class FootballDataClient(BaseClient):
    """Client for football-data.org API

    Free API for football data
    API: https://www.football-data.org
    """

    BASE_URL = "https://api.football-data.org/v4"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize football data client

        Args:
            api_key: API key (free at football-data.org)
        """
        super().__init__()
        if api_key:
            self.session.headers.update({'X-Auth-Token': api_key})

    def get_matches(self, league: str, season: int) -> List[Dict]:
        """Get matches for a league/season

        Args:
            league: League code (PL, BL1, SA, etc.)
            season: Season year (e.g., 2023)

        Returns:
            List of matches
        """
        url = f"{self.BASE_URL}/competitions/{league}/matches"
        params = {'season': season}
        try:
            data = self._get(url, params)
            return data.get("matches", [])
        except Exception as e:
            return []

    def get_standings(self, league: str, season: int) -> List[Dict]:
        """Get league standings"""
        url = f"{self.BASE_URL}/competitions/{league}/standings"
        params = {'season': season}
        try:
            data = self._get(url, params)
            return data.get("standings", [])
        except Exception as e:
            return []


class NBAStatsClient(BaseClient):
    """Client for NBA stats

    NBA Stats API: https://stats.nba.com
    """

    BASE_URL = "https://stats.nba.com"

    def get_player_stats(self, player_id: str) -> Optional[Dict]:
        """Get NBA player statistics"""
        url = f"{self.BASE_URL}/stats/player/{player_id}"
        try:
            # NBA stats requires specific headers
            self.session.headers.update({
                'Accept': 'application/json',
                'Accept-Language': 'en-US',
            })
            data = self._get(url)
            return data
        except Exception as e:
            return None

    def get_team_roster(self, team_id: str) -> List[Dict]:
        """Get team roster"""
        url = f"{self.BASE_URL}/team/{team_id}/roster"
        try:
            data = self._get(url)
            return data.get("players", [])
        except Exception as e:
            return []


# ============================================================================
# Utility Functions
# ============================================================================

def get_sports_client(sport: str) -> Optional[BaseClient]:
    """Factory function to get appropriate sports client

    Args:
        sport: Sport name (ufc, boxing, lol, csgo, nba, etc.)

    Returns:
        Client instance or None
    """
    clients = {
        'ufc': UFCClient,
        'mma': UFCClient,
        'boxing': BoxRecClient,
        'boxrec': BoxRecClient,
        'lol': LiquipediaClient,
        'league of legends': LiquipediaClient,
        'dota2': lambda: LiquipediaClient('dota2'),
        'csgo': HLTVClient,
        'counter-strike': HLTVClient,
        'nba': NBAStatsClient,
        'basketball': NBAStatsClient,
        'football': FootballDataClient,
        'soccer': FootballDataClient,
    }

    sport_lower = sport.lower()
    if sport_lower in clients:
        client_class = clients[sport_lower]
        if callable(client_class):
            return client_class()
        else:
            return client_class

    return None


if __name__ == "__main__":
    # Test the clients
    print("=" * 70)
    print("SPORTS API CLIENTS - TEST")
    print("=" * 70)

    # Test UFC client
    ufc = UFCClient()
    fighter = ufc.get_fighter_stats("Jon Jones")
    print(f"UFC Fighter: {fighter}")

    # Test Liquipedia client
    lol = LiquipediaClient(game="lol")
    player = lol.get_player("Faker")
    print(f"LoL Player: {player}")

    # Test factory function
    nba_client = get_sports_client("nba")
    print(f"NBA Client: {nba_client}")
