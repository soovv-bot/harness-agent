#!/usr/bin/env python3
"""
Sports Entity Pool Scrapers

This module provides scrapers for building local entity pools from sports websites.
These pools enable random access without needing to scrape on every query.

Scrapers:
1. LiquipediaScraper - Esports players/teams (LoL, Dota2, etc.)
2. UFCScraper - MMA fighters from UFC.com
3. BoxingSceneScraper - Boxers from BoxingScene.com (600-1000+ fighters)
4. NBAScraper - NBA players from NBA.com (500+ players)
5. ATPScraper - ATP tennis players from ATP Tour (100+ players)
6. TransfermarktScraper - Football/soccer players from Transfermarkt (2000+ players)
7. BoxRecScraper - Legacy scraper (deprecated, returns 403)

Usage:
    # First time: build the pool
    python apis/sports_scrapers.py --sport lol --build

    # After building: use the pool
    pool = load_local_pool('esports_lol_players.json')
    random_player = random.choice(pool)
"""

import json
import random
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import sys

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))


# ============================================================================
# Base Scraper Class
# ============================================================================

class BaseScraper:
    """Base class for sports website scrapers"""

    def __init__(self, delay: float = 1.0):
        """Initialize scraper

        Args:
            delay: Delay between requests in seconds (polite scraping)
        """
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def get_page(self, url: str) -> str:
        """Get page HTML

        Args:
            url: URL to fetch

        Returns:
            HTML content
        """
        try:
            logger.info(f"Fetching: {url}")
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            time.sleep(self.delay)  # Polite delay
            return response.text
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return ""

    def save_pool(self, entities: List[Dict], filename: str):
        """Save entity pool to file

        Args:
            entities: List of entities
            filename: Output filename
        """
        output_dir = Path(__file__).parent.parent.parent / "data" / "sports_pools"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(entities, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved {len(entities)} entities to {output_path}")

    def load_pool(self, filename: str) -> List[Dict]:
        """Load entity pool from file

        Args:
            filename: Pool filename

        Returns:
            List of entities
        """
        output_dir = Path(__file__).parent.parent.parent / "data" / "sports_pools"
        output_path = output_dir / filename

        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                entities = json.load(f)
            logger.info(f"Loaded {len(entities)} entities from {output_path}")
            return entities
        except FileNotFoundError:
            logger.warning(f"Pool file not found: {output_path}")
            return []


# ============================================================================
# Liquipedia Scraper (Esports)
# ============================================================================

class LiquipediaScraper(BaseScraper):
    """Scraper for Liquipedia.net esports data

    Liquipedia URL structure:
    - LoL: https://liquipedia.net/leagueoflegends/Player_Name
    - Dota 2: https://liquipedia.net/dota2/Player_Name
    - CS:GO: https://liquipedia.net/counterstrike/Player_Name
    - Overwatch: https://liquipedia.net/overwatch/Player_Name

    Note: Game identifiers differ from common names!
    - lol -> leagueoflegends
    - csgo -> counterstrike
    """

    BASE_URL = "https://liquipedia.net"

    # Mapping of common game names to actual Liquipedia identifiers
    GAME_IDENTIFIERS = {
        'lol': 'leagueoflegends',
        'leagueoflegends': 'leagueoflegends',
        'league of legends': 'leagueoflegends',
        'dota2': 'dota2',
        'dota 2': 'dota2',
        'csgo': 'counterstrike',
        'counterstrike': 'counterstrike',
        'counter-strike': 'counterstrike',
        'cs:go': 'counterstrike',
        'overwatch': 'overwatch',
        'valorant': 'valorant',
        'starcraft2': 'starcraft2',
        'starcraft': 'starcraft2',
        'sc2': 'starcraft2',
    }

    def scrape_players(self, game: str = "lol") -> List[Dict]:
        """Scrape all players for a game

        Args:
            game: Game identifier (lol, dota2, csgo, overwatch, etc.)

        Returns:
            List of players with name, url, team
        """
        # Map common game name to Liquipedia identifier
        liquipedia_game = self.GAME_IDENTIFIERS.get(game.lower(), game.lower())
        logger.info(f"Scraping {game} (liquipedia: {liquipedia_game}) players from Liquipedia...")

        players = []

        # Regional pages for games that use tab-based portals
        # Note: Use Portal:Players prefix for regional subpages
        regional_pages = {
            'dota2': ['Americas', 'Europe', 'China', 'SoutheastAsia'],
            'counterstrike': ['Americas', 'Europe', 'Asia'],
        }

        # For games with regional portals, scrape each region
        if liquipedia_game in regional_pages:
            logger.info(f"Using regional pages for {liquipedia_game}")
            for region in regional_pages[liquipedia_game]:
                region_url = f"{self.BASE_URL}/{liquipedia_game}/Portal:Players/{region}"
                logger.info(f"Scraping {region}: {region_url}")
                html = self.get_page(region_url)

                if html:
                    region_players = self._parse_player_links(html, liquipedia_game, game, region)
                    players.extend(region_players)
                    logger.info(f"  Found {len(region_players)} players in {region}")

            # Also try the main Players page for any additional players
            main_url = f"{self.BASE_URL}/{liquipedia_game}/Players"
            logger.info(f"Trying main page: {main_url}")
            html = self.get_page(main_url)
            if html:
                main_players = self._parse_player_links(html, liquipedia_game, game, 'main')
                players.extend(main_players)
        else:
            # For games without regional portals (LoL), use the original approach
            # Approach 1: Direct players category
            category_url = f"{self.BASE_URL}/{liquipedia_game}/Players"
            logger.info(f"Trying: {category_url}")
            html = self.get_page(category_url)

            # Approach 2: Portal pages
            if not html:
                category_url = f"{self.BASE_URL}/{liquipedia_game}/Portal:Players"
                logger.info(f"Trying: {category_url}")
                html = self.get_page(category_url)

            if html:
                players = self._parse_player_links(html, liquipedia_game, game, 'main')

        if not players:
            logger.warning(f"Could not access any page for {game} (tried: {liquipedia_game})")
            return self.get_fallback_players(game)

        # Remove duplicates
        seen = set()
        unique_players = []
        for p in players:
            key = (p['name'].lower(), p['game'])
            if key not in seen:
                seen.add(key)
                unique_players.append(p)

        logger.info(f"Found {len(unique_players)} {game} players (from {liquipedia_game})")

        if len(unique_players) < 50:
            logger.warning("Low player count, using fallback")
            return self.get_fallback_players(game)

        return unique_players

    def _parse_player_links(self, html: str, liquipedia_game: str, original_game: str, source_region: str) -> List[Dict]:
        """Parse player links from HTML content

        Args:
            html: HTML content to parse
            liquipedia_game: Game identifier on Liquipedia
            original_game: Original game name requested by user
            source_region: Region identifier for logging

        Returns:
            List of players found in the HTML
        """
        players = []
        soup = BeautifulSoup(html, 'html.parser')

        # Liquipedia uses div/div with specific classes
        # Look for links to player pages
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            # Filter player pages (exclude special pages)
            if (f'/{liquipedia_game}/' in href and
                not any(excl in href for excl in ['Category:', 'Portal:', 'Template:', 'File:', 'Match:', 'Liquipedia:', 'Special:', 'index.php', 'action=edit'])):

                # Extract player name from URL
                # URL format: /leagueoflegends/Player_Name or /leagueoflegends/Player_Name_(Team)
                player_name = href.split(f'/{liquipedia_game}/')[-1]

                # Clean up URL fragments
                player_name = player_name.split('(')[0].strip()
                player_name = player_name.split('#')[0].strip()
                player_name = player_name.split('?')[0].strip()
                player_name = player_name.replace('_', ' ')

                # Filter out short names and special pages
                if player_name and len(player_name) > 2 and not player_name.startswith('Category:'):
                    players.append({
                        'name': player_name,
                        'url': urljoin(self.BASE_URL, href),
                        'game': liquipedia_game,
                        'original_game': original_game,
                        'source': f'liquipedia_{source_region}'
                    })

        return players

    def get_fallback_players(self, game: str) -> List[Dict]:
        """Get fallback players for games that can't be scraped

        Args:
            game: Game identifier

        Returns:
            List of known players
        """
        liquipedia_game = self.GAME_IDENTIFIERS.get(game.lower(), game.lower())

        fallback_pools = {
            'lol': [
                {'name': 'Faker', 'url': f'https://liquipedia.net/leagueoflegends/Faker', 'game': 'leagueoflegends', 'source': 'liquipedia_fallback'},
                {'name': 'Rookie', 'url': f'https://liquipedia.net/leagueoflegends/Rookie', 'game': 'leagueoflegends', 'source': 'liquipedia_fallback'},
                {'name': 'ShowMaker', 'url': f'https://liquipedia.net/leagueoflegends/ShowMaker', 'game': 'leagueoflegends', 'source': 'liquipedia_fallback'},
                {'name': 'Chovy', 'url': f'https://liquipedia.net/leagueoflegends/Chovy', 'game': 'leagueoflegends', 'source': 'liquipedia_fallback'},
                {'name': 'Caps', 'url': f'https://liquipedia.net/leagueoflegends/Caps', 'game': 'leagueoflegends', 'source': 'liquipedia_fallback'},
                {'name': 'Doublelift', 'url': f'https://liquipedia.net/leagueoflegends/Doublelift', 'game': 'leagueoflegends', 'source': 'liquipedia_fallback'},
                {'name': 'Uzi', 'url': f'https://liquipedia.net/leagueoflegends/Uzi', 'game': 'leagueoflegends', 'source': 'liquipedia_fallback'},
                {'name': 'TheShy', 'url': f'https://liquipedia.net/leagueoflegends/TheShy', 'game': 'leagueoflegends', 'source': 'liquipedia_fallback'},
                {'name': 'Doinb', 'url': f'https://liquipedia.net/leagueoflegends/Doinb', 'game': 'leagueoflegends', 'source': 'liquipedia_fallback'},
                {'name': 'Viper', 'url': f'https://liquipedia.net/leagueoflegends/Viper', 'game': 'leagueoflegends', 'source': 'liquipedia_fallback'},
            ],
            'dota2': [
                {'name': 'Puppey', 'url': 'https://liquipedia.net/dota2/Puppey', 'game': 'dota2', 'source': 'liquipedia_fallback'},
                {'name': 'Arteezy', 'url': 'https://liquipedia.net/dota2/Arteezy', 'game': 'dota2', 'source': 'liquipedia_fallback'},
                {'name': 'Miracle-', 'url': 'https://liquipedia.net/dota2/Miracle-', 'game': 'dota2', 'source': 'liquipedia_fallback'},
                {'name': 'KuroKy', 'url': 'https://liquipedia.net/dota2/KuroKy', 'game': 'dota2', 'source': 'liquipedia_fallback'},
                {'name': 'SumaiL', 'url': 'https://liquipedia.net/dota2/SumaiL', 'game': 'dota2', 'source': 'liquipedia_fallback'},
            ],
            'csgo': [
                {'name': 's1mple', 'url': 'https://liquipedia.net/counterstrike/S1mple', 'game': 'counterstrike', 'source': 'liquipedia_fallback'},
                {'name': 'ZywOo', 'url': 'https://liquipedia.net/counterstrike/ZywOo', 'game': 'counterstrike', 'source': 'liquipedia_fallback'},
                {'name': 'dev1ce', 'url': 'https://liquipedia.net/counterstrike/Dev1ce', 'game': 'counterstrike', 'source': 'liquipedia_fallback'},
                {'name': 'NiKo', 'url': 'https://liquipedia.net/counterstrike/NiKo', 'game': 'counterstrike', 'source': 'liquipedia_fallback'},
                {'name': 'M0NESY', 'url': 'https://liquipedia.net/counterstrike/M0NESY', 'game': 'counterstrike', 'source': 'liquipedia_fallback'},
            ]
        }

        return fallback_pools.get(game.lower(), [])


# ============================================================================
# UFC Scraper (MMA)
# ============================================================================

class UFCScraper(BaseScraper):
    """Scraper for UFC.com MMA fighters

    UFC URL structure:
    - Rankings page: https://www.ufc.com/rankings (has all ranked fighters)
    - Fighter pages: https://www.ufc.com/athlete/jon-jones
    """

    BASE_URL = "https://www.ufc.com"

    def scrape_fighters(self) -> List[Dict]:
        """Scrape all UFC fighters from the rankings page

        The UFC rankings page contains ~195 fighters across 13 weight classes.
        Each class has 15 ranked fighters plus champions.

        Returns:
            List of fighters with name, nickname, url
        """
        logger.info("Scraping UFC fighters from rankings page...")

        fighters = []

        # Use the rankings page which has all fighters
        url = f"{self.BASE_URL}/rankings"
        html = self.get_page(url)

        if not html:
            logger.warning("Could not access rankings page")
            return self.get_fallback_fighters()

        # Parse HTML to find fighter names
        soup = BeautifulSoup(html, 'html.parser')

        # Method 1: Try to find table rows with fighter info
        # UFC rankings are often in table format
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    # First cell is rank, second cell is fighter name
                    rank_text = cells[0].get_text(strip=True)

                    # Skip headers and non-numeric ranks
                    if not rank_text.isdigit():
                        continue

                    name_text = cells[1].get_text(strip=True)

                    # Clean up name - remove rank change indicators
                    name = name_text.split('\n')[0].strip()
                    name = name.split('Rank increased')[0].strip()
                    name = name.split('Rank decreased')[0].strip()
                    name = name.split('(NR)')[0].strip()

                    # Filter out non-fighter entries
                    if (name and len(name) > 2 and
                        name not in ['Rank increased', 'Rank decreased', 'NR', 'Champion', 'Interim'] and
                        not name.startswith('####')):
                        # Generate URL slug
                        slug = self._slugify_name(name)
                        fighters.append({
                            'name': name,
                            'slug': slug,
                            'url': f"{self.BASE_URL}/athlete/{slug}",
                            'source': 'ufc_rankings',
                            'rank': rank_text
                        })

        # Method 2: Look for fighter links in the page
        # UFC pages often have direct links to athlete pages
        if not fighters or len(fighters) < 100:
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                # Look for athlete page links
                if '/athlete/' in href:
                    name = link.get_text(strip=True)
                    # Filter out short names and navigation elements
                    if (name and len(name) > 2 and
                        not any(excl in name.lower() for excl in ['all athletes', 'rankings', 'champion'])):
                        slug = href.split('/athlete/')[-1].split('?')[0].split('#')[0]
                        fighters.append({
                            'name': name,
                            'slug': slug,
                            'url': urljoin(self.BASE_URL, href),
                            'source': 'ufc_athlete_link'
                        })

        # Method 3: Text-based parsing for markdown-style tables
        # Some UFC pages use markdown-style formatting
        if not fighters or len(fighters) < 100:
            text = soup.get_text()
            lines = text.split('\n')

            for line in lines:
                # Look for lines that look like: | 1 | Jon Jones |  |
                if line.strip().startswith('|') and '|' in line[1:]:
                    parts = [p.strip() for p in line.split('|')[1:-1]]  # Remove empty first/last
                    if len(parts) >= 2:
                        rank_part = parts[0]
                        name_part = parts[1]

                        # Check if rank is numeric
                        if rank_part.isdigit():
                            # Clean up name
                            name = name_part.split('\n')[0].strip()
                            name = name.split('Rank')[0].strip()

                            if name and len(name) > 2 and name not in ['NR', 'Champion']:
                                slug = self._slugify_name(name)
                                fighters.append({
                                    'name': name,
                                    'slug': slug,
                                    'url': f"{self.BASE_URL}/athlete/{slug}",
                                    'source': 'ufc_text_parse',
                                    'rank': rank_part
                                })

        # Remove duplicates based on name
        seen = set()
        unique_fighters = []
        for f in fighters:
            # Normalize name for comparison
            name_key = f['name'].lower().strip()
            if name_key not in seen:
                seen.add(name_key)
                unique_fighters.append(f)

        logger.info(f"Found {len(unique_fighters)} unique fighters from rankings page")

        if len(unique_fighters) < 50:
            logger.warning(f"Low fighter count ({len(unique_fighters)}), using fallback")
            return self.get_fallback_fighters()

        return unique_fighters

    def _slugify_name(self, name: str) -> str:
        """Convert fighter name to URL slug format

        Examples:
            Jon Jones -> jon-jones
            José Aldo -> jose-aldo
            Conor McGregor -> conor-mcgregor

        Args:
            name: Fighter name

        Returns:
            URL-friendly slug
        """
        slug = name.lower()
        # Remove apostrophes and periods
        slug = slug.replace("'", '').replace('.', '')
        # Replace spaces and special chars with hyphens
        slug = slug.replace(' ', '-').replace('_', '-')
        # Remove consecutive hyphens
        while '--' in slug:
            slug = slug.replace('--', '-')
        # Strip leading/trailing hyphens
        slug = slug.strip('-')
        return slug

    def get_fallback_fighters(self) -> List[Dict]:
        """Get fallback UFC fighters

        Returns:
            List of known UFC fighters
        """
        return [
            {'name': 'Jon Jones', 'slug': 'jon-jones', 'url': 'https://www.ufc.com/athlete/jon-jones', 'source': 'ufc_fallback'},
            {'name': 'Khabib Nurmagomedov', 'slug': 'khabib-nurmagomedov', 'url': 'https://www.ufc.com/athlete/khabib-nuragomedov', 'source': 'ufc_fallback'},
            {'name': 'Conor McGregor', 'slug': 'conor-mcgregor', 'url': 'https://www.ufc.com/athlete/conor-mcgregor', 'source': 'ufc_fallback'},
            {'name': 'Israel Adesanya', 'slug': 'israel-adesanya', 'url': 'https://www.ufc.com/athlete/israel-adesanya', 'source': 'ufc_fallback'},
            {'name': 'Francis Ngannou', 'slug': 'francis-ngannou', 'url': 'https://www.ufc.com/athlete/francis-ngannou', 'source': 'ufc_fallback'},
            {'name': 'Stipe Miocic', 'slug': 'stipe-miocic', 'url': 'https://www.ufc.com/athlete/stipe-miocic', 'source': 'ufc_fallback'},
            {'name': 'Dustin Poirier', 'slug': 'dustin-poirier', 'url': 'https://www.ufc.com/athlete/dustin-poirier', 'source': 'ufc_fallback'},
            {'name': 'Amanda Nunes', 'slug': 'amanda-nunes', 'url': 'https://www.ufc.com/athlete/amanda-nunes', 'source': 'ufc_fallback'},
            {'name': 'Valentina Shevchenko', 'slug': 'valentina-shevchenko', 'url': 'https://www.ufc.com/athlete/valentina-shevchenko', 'source': 'ufc_fallback'},
            {'name': 'Weili Zhang', 'slug': 'weili-zhang', 'url': 'https://www.ufc.com/athlete/weili-zhang', 'source': 'ufc_fallback'},
            {'name': 'Islam Makhachev', 'slug': 'islam-makhachev', 'url': 'https://www.ufc.com/athlete/islam-makhachev', 'source': 'ufc_fallback'},
            {'name': 'Leon Edwards', 'slug': 'leon-edwards', 'url': 'https://www.ufc.com/athlete/leon-edwards', 'source': 'ufc_fallback'},
        ]


# ============================================================================
# BoxingScene Scraper (Boxing)
# ============================================================================

class BoxingSceneScraper(BaseScraper):
    """Scraper for BoxingScene.com rankings

    BoxingScene URL structure:
    - Rankings: https://boxingscene.com/rankings/
    - Fighter pages: https://boxingscene.com/fighter-name/

    Data structure:
    - 17 weight classes (Heavyweight to Strawweight)
    - 4 organizations per class (IBF, WBA, WBC, WBO)
    - ~15 ranked fighters per organization
    - Estimated total: ~600-1000+ unique fighters
    """

    BASE_URL = "https://boxingscene.com"
    RANKINGS_URL = f"{BASE_URL}/rankings/"

    # Weight classes in order
    # Note: BoxingScene uses "Junior" instead of "Super" for some classes
    WEIGHT_CLASSES = [
        "Heavyweight", "Cruiserweight", "Light Heavyweight", "Super Middleweight",
        "Middleweight", "Junior Middleweight", "Junior Welterweight", "Welterweight",
        "Junior Lightweight", "Lightweight", "Junior Featherweight", "Featherweight",
        "Junior Bantamweight", "Bantamweight", "Junior Flyweight", "Flyweight",
        "Strawweight", "Minimumweight"
    ]

    # Organizations to track
    ORGANIZATIONS = ["IBF", "WBA", "WBC", "WBO"]

    def scrape_boxers(self, limit: int = 1500) -> List[Dict]:
        """Scrape boxers from BoxingScene rankings

        The rankings page contains 17 weight classes × 4 organizations
        with ~15 ranked fighters each = ~1000+ fighters total.

        Args:
            limit: Maximum number of boxers to scrape (default: 1500)

        Returns:
            List of boxers with name, weight_class, organization, url
        """
        logger.info("Scraping BoxingScene boxers from rankings page...")

        boxers = []

        # Fetch the rankings page
        html = self.get_page(self.RANKINGS_URL)

        if not html:
            logger.warning("Could not access rankings page")
            return self.get_fallback_boxers()

        # Parse the page
        soup = BeautifulSoup(html, 'html.parser')

        # Get the page text for markdown-style parsing
        # BoxingScene uses markdown format with ### for weight classes
        # and ##### for organizations
        text = soup.get_text()

        # Parse using text-based approach for markdown format
        boxers = self._parse_rankings_text(text)

        # Also try HTML-based parsing as backup
        if not boxers or len(boxers) < 100:
            logger.info("Trying HTML-based parsing...")
            boxers = self._parse_rankings_html(soup)

        # Remove duplicates based on name
        seen = set()
        unique_boxers = []
        for b in boxers:
            name_key = b['name'].lower().strip()
            if name_key not in seen:
                seen.add(name_key)
                unique_boxers.append(b)

        logger.info(f"Found {len(unique_boxers)} unique boxers")

        if len(unique_boxers) < 50:
            logger.warning("Low boxer count, using fallback")
            return self.get_fallback_boxers()

        return unique_boxers[:limit]

    def _parse_rankings_text(self, text: str) -> List[Dict]:
        """Parse rankings from text content

        The page uses a concatenated format like:
        HeavyweightunlimitedIBFOleksandr Usyk1NOT RATED2Derek Chisora3Frank Sanchez...

        We need to extract fighter names from this using regex patterns.

        Args:
            text: Page text content

        Returns:
            List of boxers found
        """
        import re

        boxers = []
        current_weight_class = None

        # Find the start of the rankings (after "updated on" messages)
        rankings_start = text.find('Heavyweight')
        if rankings_start == -1:
            logger.warning("Could not find start of rankings")
            return boxers

        # Work with just the rankings section
        rankings_text = text[rankings_start:]

        # Tokenize the text by finding weight classes, organizations, and other known markers
        # Don't use word boundaries since text is concatenated
        tokens = []

        # Find all weight classes - sort by length descending to match longer names first
        # This ensures "Light Heavyweight" is matched before "Heavyweight"
        weight_classes_sorted = sorted(self.WEIGHT_CLASSES, key=len, reverse=True)

        # Use a greedy matching approach to find non-overlapping tokens
        covered_ranges = []

        for wc in weight_classes_sorted:
            pattern = re.escape(wc)
            for match in re.finditer(pattern, rankings_text):
                start, end = match.span()

                # Check if this match overlaps with any already covered range
                overlaps = False
                for covered_start, covered_end in covered_ranges:
                    if not (end <= covered_start or start >= covered_end):
                        overlaps = True
                        break

                # Only add if it doesn't overlap
                if not overlaps:
                    tokens.append((start, 'weight_class', wc))
                    covered_ranges.append((start, end))

        # Find all organizations (these are short and won't overlap)
        for org in self.ORGANIZATIONS:
            pattern = re.escape(org)
            for match in re.finditer(pattern, rankings_text):
                start, end = match.span()
                tokens.append((start, 'organization', org))

        # Sort tokens by position
        tokens.sort()

        # Process tokens in order
        for i, (pos, token_type, value) in enumerate(tokens):
            if token_type == 'weight_class':
                current_weight_class = value
            elif token_type == 'organization':
                if current_weight_class:
                    # Extract fighters between this org and the next token
                    # Find the next token position
                    next_pos = None
                    for next_token in tokens[i+1:]:
                        if next_token[0] > pos:
                            next_pos = next_token[0]
                            break

                    # Get the text segment for this organization
                    if next_pos:
                        segment = rankings_text[pos:next_pos]
                    else:
                        segment = rankings_text[pos:]

                    # Extract fighter names from this segment
                    fighters = self._extract_fighters_from_segment(segment, value)
                    for fighter in fighters:
                        boxers.append({
                            'name': fighter,
                            'weight_class': current_weight_class,
                            'organization': value,
                            'slug': self._slugify_name(fighter),
                            'url': f"{self.BASE_URL}/{self._slugify_name(fighter)}/",
                            'source': 'boxingscene_rankings'
                        })

        return boxers

    def _extract_fighters_from_segment(self, segment: str, organization: str) -> List[str]:
        """Extract fighter names from a segment of text

        Segment format: "IBFOleksandr Usyk1NOT RATED2Derek Chisora3..."
        We need to find names that are:
        1. Not numbers
        2. Not "NOT RATED" or "VACANT"
        3. Not the org name itself
        4. Have at least 2 letters

        Args:
            segment: Text segment for one organization
            organization: Organization name (to filter out)

        Returns:
            List of fighter names
        """
        import re

        fighters = []

        # Remove the org name from the start
        if segment.startswith(organization):
            segment = segment[len(organization):]

        # Split on digit boundaries to separate names from ranks
        # This gives us tokens like: "Oleksandr Usyk", "NOT RATED", "Derek Chisora"
        parts = re.split(r'\d+', segment)

        for part in parts:
            # Clean up the part
            name = part.strip()

            # Remove anything in parentheses
            name = re.sub(r'\([^)]*\)', '', name).strip()

            # Skip common non-fighter entries
            if name in ['NOT RATED', 'VACANT', 'unlimited', 'lbs', '']:
                continue

            # Skip if too short or doesn't look like a name
            if len(name) < 3:
                continue

            # Skip if it's just a number or special characters
            if not any(c.isalpha() for c in name):
                continue

            # Skip if it's the org name again
            if name == organization:
                continue

            # Skip status/rank indicators
            if any(indicator in name.lower() for indicator in ['champion', 'interim', 'regular', 'recess']):
                continue

            # Skip weight indicators
            if name.endswith('lbs') or name == 'unlimited':
                continue

            # Should be a fighter name - validate it has at least 2 letters
            if sum(c.isalpha() for c in name) >= 2:
                # Clean up any remaining artifacts
                name = ' '.join(name.split())
                if name:
                    fighters.append(name)

        return fighters

    def _parse_rankings_html(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse rankings from HTML structure

        Args:
            soup: BeautifulSoup object

        Returns:
            List of boxers found
        """
        boxers = []

        # Look for tables with rankings
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    # First cell might be rank, second might be name
                    for cell in cells:
                        text = cell.get_text(strip=True)
                        if text and len(text) > 2 and not text.isdigit():
                            # Check if it looks like a fighter name
                            if text not in ['Champion', 'Interim', 'Regular', 'VACANT']:
                                slug = self._slugify_name(text)
                                boxers.append({
                                    'name': text,
                                    'slug': slug,
                                    'url': f"{self.BASE_URL}/{slug}/",
                                    'source': 'boxingscene_html'
                                })

        return boxers

    def _slugify_name(self, name: str) -> str:
        """Convert fighter name to URL slug format

        Examples:
            Oleksandr Usyk -> oleksandr-usyk
            Canelo Alvarez -> canelo-alvarez
            Tyson Fury -> tyson-fury

        Args:
            name: Fighter name

        Returns:
            URL-friendly slug
        """
        slug = name.lower()
        # Remove apostrophes and periods
        slug = slug.replace("'", '').replace('.', '')
        # Replace spaces and special chars with hyphens
        slug = slug.replace(' ', '-').replace('_', '-')
        # Remove consecutive hyphens
        while '--' in slug:
            slug = slug.replace('--', '-')
        # Strip leading/trailing hyphens
        slug = slug.strip('-')
        return slug

    def get_fallback_boxers(self) -> List[Dict]:
        """Get fallback boxers

        Returns:
            List of known boxers
        """
        return [
            {'name': 'Mike Tyson', 'slug': 'mike-tyson', 'url': 'https://boxingscene.com/mike-tyson/', 'source': 'boxingscene_fallback'},
            {'name': 'Muhammad Ali', 'slug': 'muhammad-ali', 'url': 'https://boxingscene.com/muhammad-ali/', 'source': 'boxingscene_fallback'},
            {'name': 'Floyd Mayweather', 'slug': 'floyd-mayweather', 'url': 'https://boxingscene.com/floyd-mayweather/', 'source': 'boxingscene_fallback'},
            {'name': 'Manny Pacquiao', 'slug': 'manny-pacquiao', 'url': 'https://boxingscene.com/manny-pacquiao/', 'source': 'boxingscene_fallback'},
            {'name': 'Sugar Ray Robinson', 'slug': 'sugar-ray-robinson', 'url': 'https://boxingscene.com/sugar-ray-robinson/', 'source': 'boxingscene_fallback'},
            {'name': 'Joe Louis', 'slug': 'joe-louis', 'url': 'https://boxingscene.com/joe-louis/', 'source': 'boxingscene_fallback'},
            {'name': 'Rocky Marciano', 'slug': 'rocky-marciano', 'url': 'https://boxingscene.com/rocky-marciano/', 'source': 'boxingscene_fallback'},
            {'name': 'Oscar De La Hoya', 'slug': 'oscar-de-la-hoya', 'url': 'https://boxingscene.com/oscar-de-la-hoya/', 'source': 'boxingscene_fallback'},
            {'name': 'Oleksandr Usyk', 'slug': 'oleksandr-usyk', 'url': 'https://boxingscene.com/oleksandr-usyk/', 'source': 'boxingscene_fallback'},
            {'name': 'Tyson Fury', 'slug': 'tyson-fury', 'url': 'https://boxingscene.com/tyson-fury/', 'source': 'boxingscene_fallback'},
            {'name': 'Canelo Alvarez', 'slug': 'canelo-alvarez', 'url': 'https://boxingscene.com/canelo-alvarez/', 'source': 'boxingscene_fallback'},
            {'name': 'Anthony Joshua', 'slug': 'anthony-joshua', 'url': 'https://boxingscene.com/anthony-joshua/', 'source': 'boxingscene_fallback'},
            {'name': 'Deontay Wilder', 'slug': 'deontay-wilder', 'url': 'https://boxingscene.com/deontay-wilder/', 'source': 'boxingscene_fallback'},
            {'name': 'Gennady Golovkin', 'slug': 'gennady-golovkin', 'url': 'https://boxingscene.com/gennady-golovkin/', 'source': 'boxingscene_fallback'},
            {'name': 'Vasiliy Lomachenko', 'slug': 'vasiliy-lomachenko', 'url': 'https://boxingscene.com/vasiliy-lomachenko/', 'source': 'boxingscene_fallback'},
        ]


# ============================================================================
# NBA Scraper (Basketball)
# ============================================================================

class NBAScraper(BaseScraper):
    """Scraper for NBA.com players

    NBA URL structure:
    - Players list: https://www.nba.com/players
    - Player pages: https://www.nba.com/player/firstname-lastname/123456

    Data structure:
    - 546 NBA players across all teams
    - 11 pages with ~50 players each
    - Player info: name, team, number, position, height, weight, country
    """

    BASE_URL = "https://www.nba.com"
    PLAYERS_URL = f"{BASE_URL}/players"

    def scrape_players(self) -> List[Dict]:
        """Scrape all NBA players from the players list

        The NBA players page contains 546 players across 11 pages.
        Each player has: name, team, number, position, height, weight, country.

        Returns:
            List of players with name, team, position, country, url
        """
        logger.info("Scraping NBA players from NBA.com...")

        players = []

        # Fetch the main players page
        html = self.get_page(self.PLAYERS_URL)

        if not html:
            logger.warning("Could not access players page")
            return self.get_fallback_players()

        # Parse HTML to find player info
        soup = BeautifulSoup(html, 'html.parser')

        # Method 1: Look for table rows with player info
        # NBA uses a table format with columns: Player, Team, Number, Position, Height, Weight, Last Attended, Country
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    # First cell should have player info
                    player_cell = cells[0]
                    player_text = player_cell.get_text(strip=True)

                    # Skip header rows and empty cells
                    if (not player_text or
                        player_text.lower() in ['player', 'team', 'number', 'position',
                                               'height', 'weight', 'last attended', 'country'] or
                        player_text.startswith('Image')):
                        continue

                    # Clean up player name (remove "Headshot" text and image references)
                    player_name = player_text.replace('Headshot', '').strip()
                    # Remove "Image X:" prefix if present
                    if player_name.startswith('Image'):
                        player_name = player_name.split(':', 1)[-1].strip()

                    # Fix concatenated names (e.g., "PreciousAchiuwa" -> "Precious Achiuwa")
                    # This happens when names are split across lines: "First\nLast" -> "FirstLast"
                    if player_name and any(c.isupper() for c in player_name[1:]):
                        # Look for patterns where lowercase is followed by uppercase (no space)
                        # Example: "PreciousAchiuwa" -> "Precious Achiuwa"
                        import re
                        # Split when lowercase letter is followed by uppercase letter
                        fixed_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', player_name)
                        # Also split when multiple uppercase letters are followed by lowercase (e.g., "BAM Adebayo")
                        fixed_name = re.sub(r'([A-Z]{2,})([A-Z][a-z])', r'\1 \2', fixed_name)
                        player_name = fixed_name

                    # Skip if too short or doesn't look like a name
                    if len(player_name) < 3 or not any(c.isalpha() for c in player_name):
                        continue

                    # Get team from second cell if available
                    team = cells[1].get_text(strip=True) if len(cells) > 1 else ''
                    position = cells[3].get_text(strip=True) if len(cells) > 3 else ''
                    country = cells[7].get_text(strip=True) if len(cells) > 7 else ''

                    # Skip invalid entries
                    if team in ['Team', ''] or position in ['Position', '']:
                        # Try to find team, position, country from other cells
                        for cell in cells[1:]:
                            cell_text = cell.get_text(strip=True)
                            if cell_text and cell_text not in ['Team', 'Number', 'Position',
                                                              'Height', 'Weight',
                                                              'Last Attended', 'Country']:
                                if len(cell_text) <= 3 and cell_text.isupper():
                                    team = cell_text
                                elif cell_text in ['G', 'F', 'C', 'G-F', 'F-C', 'C-F']:
                                    position = cell_text
                                elif len(cell_text) > 3:
                                    country = cell_text

                    # Only add if we have a valid player name
                    if player_name and len(player_name) >= 3:
                        # Generate URL slug
                        slug = self._slugify_name(player_name)
                        players.append({
                            'name': player_name,
                            'team': team,
                            'position': position,
                            'country': country,
                            'slug': slug,
                            'url': f"{self.BASE_URL}/player/{slug}/123456",
                            'source': 'nba_players_list'
                        })

        # Method 2: Look for player links in the page
        if not players or len(players) < 100:
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                # Look for player page links
                if '/player/' in href and href.count('/') >= 3:
                    name = link.get_text(strip=True)
                    # Filter out short names and navigation elements
                    if (name and len(name) > 2 and
                        not any(excl in name.lower() for excl in ['all players', 'rosters', 'teams'])):
                        slug = href.split('/player/')[-1].split('/')[0] if '/player/' in href else self._slugify_name(name)
                        players.append({
                            'name': name,
                            'team': '',
                            'position': '',
                            'country': '',
                            'slug': slug,
                            'url': urljoin(self.BASE_URL, href),
                            'source': 'nba_player_link'
                        })

        # Remove duplicates based on name
        seen = set()
        unique_players = []
        for p in players:
            name_key = p['name'].lower().strip()
            if name_key not in seen:
                seen.add(name_key)
                unique_players.append(p)

        logger.info(f"Found {len(unique_players)} unique NBA players")

        if len(unique_players) < 50:
            logger.warning(f"Low player count ({len(unique_players)}), using fallback")
            return self.get_fallback_players()

        return unique_players

    def _slugify_name(self, name: str) -> str:
        """Convert player name to URL slug format

        Examples:
            LeBron James -> lebron-james
            Stephen Curry -> stephen-curry
            Giannis Antetokounmpo -> giannis-antetokounmpo

        Args:
            name: Player name

        Returns:
            URL-friendly slug
        """
        slug = name.lower()
        # Remove apostrophes and periods
        slug = slug.replace("'", '').replace('.', '')
        # Replace spaces and special chars with hyphens
        slug = slug.replace(' ', '-').replace('_', '-')
        # Remove consecutive hyphens
        while '--' in slug:
            slug = slug.replace('--', '-')
        # Strip leading/trailing hyphens
        slug = slug.strip('-')
        return slug

    def get_fallback_players(self) -> List[Dict]:
        """Get fallback NBA players

        Returns:
            List of known NBA players
        """
        return [
            {'name': 'LeBron James', 'team': 'LAL', 'position': 'F', 'country': 'USA',
             'slug': 'lebron-james', 'url': 'https://www.nba.com/player/lebron-james/123456', 'source': 'nba_fallback'},
            {'name': 'Stephen Curry', 'team': 'GSW', 'position': 'G', 'country': 'USA',
             'slug': 'stephen-curry', 'url': 'https://www.nba.com/player/stephen-curry/123456', 'source': 'nba_fallback'},
            {'name': 'Kevin Durant', 'team': 'PHX', 'position': 'F', 'country': 'USA',
             'slug': 'kevin-durant', 'url': 'https://www.nba.com/player/kevin-durant/123456', 'source': 'nba_fallback'},
            {'name': 'Giannis Antetokounmpo', 'team': 'MIL', 'position': 'F', 'country': 'Greece',
             'slug': 'giannis-antetokounmpo', 'url': 'https://www.nba.com/player/giannis-antetokounmpo/123456', 'source': 'nba_fallback'},
            {'name': 'Luka Doncic', 'team': 'DAL', 'position': 'G', 'country': 'Slovenia',
             'slug': 'luka-doncic', 'url': 'https://www.nba.com/player/luka-doncic/123456', 'source': 'nba_fallback'},
            {'name': 'Joel Embiid', 'team': 'PHI', 'position': 'C', 'country': 'Cameroon',
             'slug': 'joel-embid', 'url': 'https://www.nba.com/player/joel-embid/123456', 'source': 'nba_fallback'},
            {'name': 'Nikola Jokic', 'team': 'DEN', 'position': 'C', 'country': 'Serbia',
             'slug': 'nikola-jokic', 'url': 'https://www.nba.com/player/nikola-jokic/123456', 'source': 'nba_fallback'},
            {'name': 'Jayson Tatum', 'team': 'BOS', 'position': 'F', 'country': 'USA',
             'slug': 'jayson-tatum', 'url': 'https://www.nba.com/player/jayson-tatum/123456', 'source': 'nba_fallback'},
            {'name': 'Anthony Davis', 'team': 'LAL', 'position': 'F-C', 'country': 'USA',
             'slug': 'anthony-davis', 'url': 'https://www.nba.com/player/anthony-davis/123456', 'source': 'nba_fallback'},
            {'name': 'Damian Lillard', 'team': 'MIL', 'position': 'G', 'country': 'USA',
             'slug': 'damian-lillard', 'url': 'https://www.nba.com/player/damian-lillard/123456', 'source': 'nba_fallback'},
            {'name': 'Kyrie Irving', 'team': 'DAL', 'position': 'G', 'country': 'USA',
             'slug': 'kyrie-irving', 'url': 'https://www.nba.com/player/kyrie-irving/123456', 'source': 'nba_fallback'},
            {'name': 'Jimmy Butler', 'team': 'MIA', 'position': 'F', 'country': 'USA',
             'slug': 'jimmy-butler', 'url': 'https://www.nba.com/player/jimmy-butler/123456', 'source': 'nba_fallback'},
        ]


# ============================================================================
# ATP Tour Scraper (Tennis)
# ============================================================================

class ATPScraper(BaseScraper):
    """Scraper for ATP Tour tennis rankings

    ATP Tour URL structure:
    - Singles rankings: https://www.atptour.com/en/rankings/singles
    - Doubles rankings: https://www.atptour.com/en/rankings/doubles
    - Player pages: https://www.atptour.com/en/players/player-name/abc123/overview

    Data structure:
    - Top 100 singles players
    - Top 100 doubles players
    - Player info: rank, name, points, age, country
    """

    BASE_URL = "https://www.atptour.com"
    SINGLES_RANKINGS_URL = f"{BASE_URL}/en/rankings/singles"
    DOUBLES_RANKINGS_URL = f"{BASE_URL}/en/rankings/doubles"

    def scrape_players(self, rankings_type: str = "singles") -> List[Dict]:
        """Scrape ATP tennis players from the rankings page

        The ATP rankings page contains the top 100 players.
        Each player has: rank, name, points, age, country.

        Args:
            rankings_type: Type of rankings ('singles' or 'doubles')

        Returns:
            List of players with name, rank, points, age, url
        """
        logger.info(f"Scraping ATP {rankings_type} players from ATP Tour...")

        players = []

        # Select URL based on rankings type
        url = self.SINGLES_RANKINGS_URL if rankings_type == "singles" else self.DOUBLES_RANKINGS_URL

        # Fetch the rankings page
        html = self.get_page(url)

        if not html:
            logger.warning(f"Could not access {rankings_type} rankings page")
            return self.get_fallback_players(rankings_type)

        # Parse HTML to find player info
        soup = BeautifulSoup(html, 'html.parser')

        # Method 1: Look for table rows with player rankings
        # ATP rankings are in table format with columns: Rank, Player, Points, Age, etc.
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:
                    # First cell is rank, second cell is player name
                    rank_text = cells[0].get_text(strip=True)

                    # Skip headers and non-numeric ranks
                    if not rank_text.isdigit() and rank_text != '1':
                        continue

                    # Player name is in second cell
                    player_text = cells[1].get_text(strip=True)

                    # Clean up name - remove rank change indicators (*, +1, -1, etc.)
                    # Format examples: "* C. Alcaraz", "* 1 * N. Djokovic", "* -2 * A. Zverev"
                    name = player_text

                    # Remove all * characters first
                    name = name.replace('*', '').strip()

                    # Remove rank change indicators at the start (numbers followed by name)
                    # Examples: "3Cristian Garin" -> "Cristian Garin", "-2B. Nakashima" -> "B. Nakashima"
                    import re
                    # Remove leading digits, +/- followed by digits, etc.
                    name = re.sub(r'^[\d+\-]+', '', name)
                    # Remove leading whitespace after removal
                    name = name.strip()

                    # Skip if too short or doesn't look like a name
                    if len(name) < 2 or not any(c.isalpha() for c in name):
                        continue

                    # Get points from third cell if available
                    points = cells[2].get_text(strip=True) if len(cells) > 2 else ''

                    # Get age from fourth cell if available
                    age = cells[3].get_text(strip=True) if len(cells) > 3 else ''

                    # Only add if we have a valid player name
                    if name and len(name) >= 2:
                        # Generate URL slug
                        slug = self._slugify_name(name)
                        players.append({
                            'name': name,
                            'rank': rank_text,
                            'points': points,
                            'age': age,
                            'rankings_type': rankings_type,
                            'slug': slug,
                            'url': f"{self.BASE_URL}/en/players/{slug}/abc123/overview",
                            'source': f'atp_{rankings_type}_rankings'
                        })

        # Method 2: Text-based parsing for markdown-style tables
        # ATP rankings pages sometimes use markdown-style formatting
        if not players or len(players) < 50:
            text = soup.get_text()
            lines = text.split('\n')

            for line in lines:
                # Look for lines that look like: | 1 | C. Alcaraz | 13,650 | 22 |
                if line.strip().startswith('|') and '|' in line[1:]:
                    parts = [p.strip() for p in line.split('|')[1:-1]]  # Remove empty first/last
                    if len(parts) >= 3:
                        rank_part = parts[0]
                        name_part = parts[1]

                        # Clean up rank
                        rank = rank_part.split('*')[0].strip()

                        # Clean up name - remove indicators
                        name = name_part

                        # Remove all * characters first
                        name = name.replace('*', '').strip()

                        # Remove rank change indicators at the start (numbers followed by name)
                        import re
                        name = re.sub(r'^[\d+\-]+', '', name)
                        name = name.strip()

                        # Check if rank is numeric (or 1)
                        if (rank.isdigit() or rank == '1') and name and len(name) >= 2:
                            points = parts[2] if len(parts) > 2 else ''
                            age = parts[3] if len(parts) > 3 else ''

                            players.append({
                                'name': name,
                                'rank': rank,
                                'points': points,
                                'age': age,
                                'rankings_type': rankings_type,
                                'slug': self._slugify_name(name),
                                'url': f"{self.BASE_URL}/en/players/{self._slugify_name(name)}/abc123/overview",
                                'source': f'atp_{rankings_type}_text'
                            })

        # Remove duplicates based on name
        seen = set()
        unique_players = []
        for p in players:
            name_key = p['name'].lower().strip()
            if name_key not in seen:
                seen.add(name_key)
                unique_players.append(p)

        logger.info(f"Found {len(unique_players)} unique ATP {rankings_type} players")

        if len(unique_players) < 20:
            logger.warning(f"Low player count ({len(unique_players)}), using fallback")
            return self.get_fallback_players(rankings_type)

        return unique_players

    def _slugify_name(self, name: str) -> str:
        """Convert player name to URL slug format

        Examples:
            Carlos Alcaraz -> carlos-alcaraz
            Jannik Sinner -> jannik-sinner
            Novak Djokovic -> novak-djokovic

        Args:
            name: Player name

        Returns:
            URL-friendly slug
        """
        slug = name.lower()
        # Remove apostrophes and periods
        slug = slug.replace("'", '').replace('.', '')
        # Replace spaces and special chars with hyphens
        slug = slug.replace(' ', '-').replace('_', '-')
        # Remove consecutive hyphens
        while '--' in slug:
            slug = slug.replace('--', '-')
        # Strip leading/trailing hyphens
        slug = slug.strip('-')
        return slug

    def get_fallback_players(self, rankings_type: str = "singles") -> List[Dict]:
        """Get fallback ATP players

        Args:
            rankings_type: Type of rankings ('singles' or 'doubles')

        Returns:
            List of known ATP players
        """
        fallback_pools = {
            'singles': [
                {'name': 'Carlos Alcaraz', 'rank': '1', 'points': '13650', 'age': '22',
                 'slug': 'carlos-alcaraz', 'url': 'https://www.atptour.com/en/players/carlos-alcaraz/abc123/overview', 'source': 'atp_fallback'},
                {'name': 'Jannik Sinner', 'rank': '2', 'points': '10300', 'age': '24',
                 'slug': 'jannik-sinner', 'url': 'https://www.atptour.com/en/players/jannik-sinner/abc123/overview', 'source': 'atp_fallback'},
                {'name': 'Novak Djokovic', 'rank': '3', 'points': '5280', 'age': '38',
                 'slug': 'novak-djokovic', 'url': 'https://www.atptour.com/en/players/novak-djokovic/abc123/overview', 'source': 'atp_fallback'},
                {'name': 'Alexander Zverev', 'rank': '4', 'points': '4605', 'age': '28',
                 'slug': 'alexander-zverev', 'url': 'https://www.atptour.com/en/players/alexander-zverev/abc123/overview', 'source': 'atp_fallback'},
                {'name': 'Daniil Medvedev', 'rank': '11', 'points': '3060', 'age': '29',
                 'slug': 'daniil-medvedev', 'url': 'https://www.atptour.com/en/players/daniil-medvedev/abc123/overview', 'source': 'atp_fallback'},
                {'name': 'Andrey Rublev', 'rank': '14', 'points': '2600', 'age': '28',
                 'slug': 'andrey-rublev', 'url': 'https://www.atptour.com/en/players/andrey-rublev/abc123/overview', 'source': 'atp_fallback'},
                {'name': 'Stefanos Tsitsipas', 'rank': '33', 'points': '1495', 'age': '27',
                 'slug': 'stefanos-tsitsipas', 'url': 'https://www.atptour.com/en/players/stefanos-tsitsipas/abc123/overview', 'source': 'atp_fallback'},
                {'name': 'Grigor Dimitrov', 'rank': '43', 'points': '1105', 'age': '34',
                 'slug': 'grigor-dimitrov', 'url': 'https://www.atptour.com/en/players/grigor-dimitrov/abc123/overview', 'source': 'atp_fallback'},
                {'name': 'Hubert Hurkacz', 'rank': '52', 'points': '965', 'age': '28',
                 'slug': 'hubert-hurkacz', 'url': 'https://www.atptour.com/en/players/hubert-hurkacz/abc123/overview', 'source': 'atp_fallback'},
                {'name': 'Tommy Paul', 'rank': '22', 'points': '1850', 'age': '28',
                 'slug': 'tommy-paul', 'url': 'https://www.atptour.com/en/players/tommy-paul/abc123/overview', 'source': 'atp_fallback'},
            ],
            'doubles': [
                {'name': 'Neal Skupski', 'rank': '1', 'points': '8000', 'age': '35',
                 'slug': 'neal-skupski', 'url': 'https://www.atptour.com/en/players/neal-skupski/abc123/overview', 'source': 'atp_fallback'},
                {'name': 'Wesley Koolhof', 'rank': '2', 'points': '7500', 'age': '36',
                 'slug': 'wesley-koolhof', 'url': 'https://www.atptour.com/en/players/wesley-koolhof/abc123/overview', 'source': 'atp_fallback'},
                {'name': 'Marcel Granollers', 'rank': '3', 'points': '7000', 'age': '39',
                 'slug': 'marcel-granollers', 'url': 'https://www.atptour.com/en/players/marcel-granollers/abc123/overview', 'source': 'atp_fallback'},
            ]
        }

        return fallback_pools.get(rankings_type, fallback_pools['singles'])


# ============================================================================
# Transfermarkt Scraper (Football/Soccer)
# ============================================================================

class TransfermarktScraper(BaseScraper):
    """Scraper for Transfermarkt.com football/soccer players

    Transfermarkt URL structure:
    - League overview: https://www.transfermarkt.com/premier-league/startseite/wettbewerb/GB1
    - Club squad: https://www.transfermarkt.com/manchester-city/startseite/verein/281/saison_id/2025
    - Player profile: https://www.transfermarkt.com/erling-haaland/profil/spieler/418560

    Data structure:
    - Multiple leagues (Premier League, La Liga, Serie A, Bundesliga, Ligue 1)
    - ~20 clubs per league × ~25 players per club = ~500 players per league
    - 5 major leagues = ~2500+ players total
    - Player info: name, club, position, age, nationality, market value
    """

    BASE_URL = "https://www.transfermarkt.com"

    # Major leagues to scrape
    LEAGUES = {
        'premier-league': {
            'name': 'Premier League',
            'url_path': 'premier-league/startseite/wettbewerb/GB1',
            'code': 'GB1'
        },
        'laliga': {
            'name': 'LaLiga',
            'url_path': 'laliga/startseite/wettbewerb/ES1',
            'code': 'ES1'
        },
        'serie-a': {
            'name': 'Serie A',
            'url_path': 'serie-a/startseite/wettbewerb/IT1',
            'code': 'IT1'
        },
        'bundesliga': {
            'name': 'Bundesliga',
            'url_path': 'bundesliga/startseite/wettbewerb/L1',
            'code': 'L1'
        },
        'ligue-1': {
            'name': 'Ligue 1',
            'url_path': 'ligue-1/startseite/wettbewerb/FR1',
            'code': 'FR1'
        }
    }

    def scrape_players(self, leagues: list = None, limit: int = 3000) -> List[Dict]:
        """Scrape football players from Transfermarkt

        This method:
        1. Gets club links from league pages
        2. Visits each club's squad page
        3. Extracts player data from squad tables

        Args:
            leagues: List of league keys to scrape (default: all major leagues)
            limit: Maximum number of players to scrape (default: 3000)

        Returns:
            List of players with name, club, position, nationality, url
        """
        if leagues is None:
            leagues = list(self.LEAGUES.keys())

        logger.info(f"Scraping football players from Transfermarkt for leagues: {leagues}")

        all_players = []

        # First, get all club links from league pages
        club_links = self._get_club_links_from_leagues(leagues)
        logger.info(f"Found {len(club_links)} club links")

        # Then, visit each club's squad page to get players
        for i, (club_name, club_url, league_name) in enumerate(club_links, 1):
            logger.info(f"[{i}/{len(club_links)}] Scraping {club_name} ({league_name})...")

            try:
                players = self._scrape_club_squad(club_url, club_name, league_name)
                all_players.extend(players)
                logger.info(f"  Found {len(players)} players")

                # Stop if we've reached the limit
                if len(all_players) >= limit:
                    logger.info(f"Reached limit of {limit} players")
                    break

                # Polite delay between requests
                time.sleep(self.delay)

            except Exception as e:
                logger.error(f"Error scraping {club_name}: {e}")
                continue

        # Remove duplicates based on name
        seen = set()
        unique_players = []
        for p in all_players:
            name_key = p['name'].lower().strip()
            if name_key not in seen:
                seen.add(name_key)
                unique_players.append(p)

        logger.info(f"Found {len(unique_players)} unique football players")

        if len(unique_players) < 50:
            logger.warning("Low player count, using fallback")
            return self.get_fallback_players()

        return unique_players[:limit]

    def _get_club_links_from_leagues(self, leagues: list) -> List[tuple]:
        """Get club links from league pages

        Args:
            leagues: List of league keys to scrape

        Returns:
            List of tuples (club_name, club_url, league_name)
        """
        club_links = []

        # Max clubs per league (top division only)
        MAX_CLUBS_PER_LEAGUE = 22

        for league_key in leagues:
            if league_key not in self.LEAGUES:
                logger.warning(f"Unknown league: {league_key}")
                continue

            league_info = self.LEAGUES[league_key]
            league_url = f"{self.BASE_URL}/{league_info['url_path']}"

            logger.info(f"Fetching clubs from {league_info['name']}...")

            html = self.get_page(league_url)
            if not html:
                logger.warning(f"Could not access {league_info['name']} page")
                continue

            # Parse HTML to find club links
            soup = BeautifulSoup(html, 'html.parser')

            # Track clubs found for this league
            league_clubs = []
            seen_urls = set()

            # Look for club links in the league table
            # Transfermarkt uses specific classes for club items
            # The league table shows clubs in order of standing
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')

                # Look for links that match the club URL pattern
                # Club URLs are like: /manchester-city/startseite/verein/281
                if '/startseite/verein/' in href:
                    # Extract club name and ID from URL
                    parts = href.split('/')
                    if len(parts) >= 3 and parts[1] != 'startseite':
                        club_slug = parts[1]

                        # Skip if this looks like a player or other page
                        if any(x in href for x in ['profil/spieler', 'transfers', 'leistungsspielplan']):
                            continue

                        # Skip if already found this club
                        if href in seen_urls:
                            continue

                        # Build full URL
                        club_url = urljoin(self.BASE_URL, href)
                        club_name = link.get_text(strip=True)

                        # Clean up club name
                        if club_name and len(club_name) > 2 and not club_name.isdigit():
                            league_clubs.append((club_name, club_url, league_info['name']))
                            seen_urls.add(href)

                            # Stop if we've reached max clubs per league
                            if len(league_clubs) >= MAX_CLUBS_PER_LEAGUE:
                                break

            club_links.extend(league_clubs)
            logger.info(f"  Found {len(league_clubs)} clubs in {league_info['name']} (top division only)")

        return club_links

    def _scrape_club_squad(self, club_url: str, club_name: str, league_name: str) -> List[Dict]:
        """Scrape players from a club's squad page

        Args:
            club_url: URL of the club's squad page
            club_name: Name of the club
            league_name: Name of the league

        Returns:
            List of players from this club
        """
        players = []

        # Add season parameter to get current squad
        squad_url = club_url.rstrip('/') + '/saison_id/2025'

        html = self.get_page(squad_url)
        if not html:
            return players

        soup = BeautifulSoup(html, 'html.parser')

        # Look for the squad table
        # Transfermarkt uses table with class 'items' or similar
        for table in soup.find_all('table'):
            # Check if this looks like a squad table
            headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]

            # Squad tables have specific column headers
            if any(keyword in ' '.join(headers) for keyword in ['player', 'name', '#', 'position']):
                for row in table.find_all('tr'):
                    cells = row.find_all(['td', 'th'])

                    if len(cells) >= 2:
                        # First cell is usually shirt number or player link
                        player_cell = cells[0] if cells[0].find('a') else (cells[1] if len(cells) > 1 else None)

                        if not player_cell:
                            continue

                        # Look for player link
                        player_link = player_cell.find('a')
                        if not player_link:
                            # Try second cell
                            if len(cells) > 1:
                                player_link = cells[1].find('a')

                        if player_link:
                            player_name = player_link.get_text(strip=True)
                            player_href = player_link.get('href', '')

                            # Skip if not a valid player name
                            if not player_name or len(player_name) < 2:
                                continue

                            # Skip headers and non-player entries
                            if any(excl in player_name.lower() for excl in ['player', 'name', 'club', 'total']):
                                continue

                            # Get position from row if available
                            position = ''
                            for cell in cells:
                                cell_text = cell.get_text(strip=True)
                                # Common position abbreviations
                                if cell_text in ['GK', 'RB', 'CB', 'LB', 'RWB', 'LWB',
                                                 'CDM', 'CM', 'CAM', 'RM', 'LM',
                                                 'RW', 'LW', 'RF', 'LF', 'CF', 'ST']:
                                    position = cell_text
                                    break

                            # Get additional info from other cells if available
                            age = ''
                            nationality = ''
                            for cell in cells:
                                cell_text = cell.get_text(strip=True)
                                # Look for age (usually a number under 50)
                                if cell_text.isdigit() and int(cell_text) < 50:
                                    age = cell_text
                                # Look for nationality (might be in title or data attribute)
                                if len(cell_text) == 2 or len(cell_text) == 3:
                                    if cell_text.isalpha() and cell_text[0].isupper():
                                        nationality = cell_text

                            players.append({
                                'name': player_name,
                                'club': club_name,
                                'league': league_name,
                                'position': position,
                                'age': age,
                                'nationality': nationality,
                                'slug': self._slugify_name(player_name),
                                'url': urljoin(self.BASE_URL, player_href),
                                'source': 'transfermarkt_squad'
                            })

        # Also try to find players using link-based parsing
        if not players:
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')

                # Look for player profile links
                if '/profil/spieler/' in href:
                    player_name = link.get_text(strip=True)

                    if player_name and len(player_name) >= 2:
                        players.append({
                            'name': player_name,
                            'club': club_name,
                            'league': league_name,
                            'position': '',
                            'age': '',
                            'nationality': '',
                            'slug': self._slugify_name(player_name),
                            'url': urljoin(self.BASE_URL, href),
                            'source': 'transfermarkt_player_link'
                        })

        return players

    def _slugify_name(self, name: str) -> str:
        """Convert player name to URL slug format

        Examples:
            Erling Haaland -> erling-haaland
            Kylian Mbappé -> kylian-mbappe

        Args:
            name: Player name

        Returns:
            URL-friendly slug
        """
        slug = name.lower()
        # Remove apostrophes and periods
        slug = slug.replace("'", '').replace('.', '')
        # Replace spaces and special chars with hyphens
        slug = slug.replace(' ', '-').replace('_', '-')
        # Remove consecutive hyphens
        while '--' in slug:
            slug = slug.replace('--', '-')
        # Strip leading/trailing hyphens
        slug = slug.strip('-')
        return slug

    def get_fallback_players(self) -> List[Dict]:
        """Get fallback football players

        Returns:
            List of known football players
        """
        return [
            {'name': 'Erling Haaland', 'club': 'Manchester City', 'league': 'Premier League',
             'position': 'ST', 'age': '24', 'nationality': 'NO',
             'slug': 'erling-haaland', 'url': 'https://www.transfermarkt.com/erling-haaland/profil/spieler/418560', 'source': 'transfermarkt_fallback'},
            {'name': 'Kevin De Bruyne', 'club': 'Manchester City', 'league': 'Premier League',
             'position': 'CM', 'age': '33', 'nationality': 'BE',
             'slug': 'kevin-de-bruyne', 'url': 'https://www.transfermarkt.com/kevin-de-bruyne/profil/spieler/48550', 'source': 'transfermarkt_fallback'},
            {'name': 'Mohamed Salah', 'club': 'Liverpool FC', 'league': 'Premier League',
             'position': 'RW', 'age': '32', 'nationality': 'EG',
             'slug': 'mohamed-salah', 'url': 'https://www.transfermarkt.com/mohamed-salah/profil/spieler/148455', 'source': 'transfermarkt_fallback'},
            {'name': 'Virgil van Dijk', 'club': 'Liverpool FC', 'league': 'Premier League',
             'position': 'CB', 'age': '32', 'nationality': 'NL',
             'slug': 'virgil-van-dijk', 'url': 'https://www.transfermarkt.com/virgil-van-dijk/profil/spieler/199200', 'source': 'transfermarkt_fallback'},
            {'name': 'Bukayo Saka', 'club': 'Arsenal FC', 'league': 'Premier League',
             'position': 'RW', 'age': '23', 'nationality': 'EN',
             'slug': 'bukayo-saka', 'url': 'https://www.transfermarkt.com/bukayo-saka/profil/spieler/401923', 'source': 'transfermarkt_fallback'},
            {'name': 'Martin Ødegaard', 'club': 'Arsenal FC', 'league': 'Premier League',
             'position': 'CM', 'age': '26', 'nationality': 'NO',
             'slug': 'martin-odegaard', 'url': 'https://www.transfermarkt.com/martin-odegaard/profil/spieler/345565', 'source': 'transfermarkt_fallback'},
            {'name': 'Bruno Fernandes', 'club': 'Manchester United', 'league': 'Premier League',
             'position': 'CM', 'age': '30', 'nationality': 'PT',
             'slug': 'bruno-fernandes', 'url': 'https://www.transfermarkt.com/bruno-fernandes/profil/spieler/355559', 'source': 'transfermarkt_fallback'},
            {'name': 'Vinícius Júnior', 'club': 'Real Madrid', 'league': 'LaLiga',
             'position': 'LW', 'age': '24', 'nationality': 'BR',
             'slug': 'vinicius-junior', 'url': 'https://www.transfermarkt.com/vinicius-junior/profil/spieler/371998', 'source': 'transfermarkt_fallback'},
            {'name': 'Jude Bellingham', 'club': 'Real Madrid', 'league': 'LaLiga',
             'position': 'CM', 'age': '21', 'nationality': 'EN',
             'slug': 'jude-bellingham', 'url': 'https://www.transfermarkt.com/jude-bellingham/profil/spieler/581678', 'source': 'transfermarkt_fallback'},
            {'name': 'Lautaro Martínez', 'club': 'Inter Milan', 'league': 'Serie A',
             'position': 'ST', 'age': '27', 'nationality': 'AR',
             'slug': 'lautaro-martinez', 'url': 'https://www.transfermarkt.com/lautaro-martinez/profil/spieler/344875', 'source': 'transfermarkt_fallback'},
            {'name': 'Khvicha Kvaratskhelia', 'club': 'Napoli', 'league': 'Serie A',
             'position': 'LW', 'age': '24', 'nationality': 'GE',
             'slug': 'khvicha-kvaratskhelia', 'url': 'https://www.transfermarkt.com/khvicha-kvaratskhelia/profil/spieler/505531', 'source': 'transfermarkt_fallback'},
            {'name': 'Jamal Musiala', 'club': 'Bayern Munich', 'league': 'Bundesliga',
             'position': 'CM', 'age': '21', 'nationality': 'DE',
             'slug': 'jamal-musiala', 'url': 'https://www.transfermarkt.com/jamal-musiala/profil/spieler/580195', 'source': 'transfermarkt_fallback'},
            {'name': 'Florian Wirtz', 'club': 'Bayer Leverkusen', 'league': 'Bundesliga',
             'position': 'CM', 'age': '21', 'nationality': 'DE',
             'slug': 'florian-wirtz', 'url': 'https://www.transfermarkt.com/florian-wirtz/profil/spieler/580185', 'source': 'transfermarkt_fallback'},
            {'name': 'Kylian Mbappé', 'club': 'Real Madrid', 'league': 'LaLiga',
             'position': 'ST', 'age': '26', 'nationality': 'FR',
             'slug': 'kylian-mbappe', 'url': 'https://www.transfermarkt.com/kylian-mbappe/profil/spieler/342229', 'source': 'transfermarkt_fallback'},
            {'name': 'Pedri', 'club': 'FC Barcelona', 'league': 'LaLiga',
             'position': 'CM', 'age': '22', 'nationality': 'ES',
             'slug': 'pedri', 'url': 'https://www.transfermarkt.com/pedri/profil/spieler/416122', 'source': 'transfermarkt_fallback'},
        ]


# ============================================================================
# Legacy BoxRec Scraper (Deprecated - returns 403)
# ============================================================================

class BoxRecScraper(BaseScraper):
    """Scraper for BoxRec.com boxing records (DEPRECATED - returns 403 Forbidden)

    BoxRec has anti-scraping protection. Use BoxingSceneScraper instead.

    BoxRec URL structure:
    - Alphabet: https://boxrec.com/en/box-pro?sex=M&first_name=&last_name=&country=&stance=&p=position
    - Boxer by ID: https://boxrec.com/en/box-pro/123456
    """

    BASE_URL = "https://boxrec.com"

    def scrape_boxers(self, limit: int = 500) -> List[Dict]:
        """Scrape boxers from BoxRec (DEPRECATED - will use fallback)

        Note: BoxRec returns 403 Forbidden. This method now directly
        returns the fallback pool.

        Args:
            limit: Maximum number of boxers to scrape (ignored)

        Returns:
            List of fallback boxers
        """
        logger.warning("BoxRecScraper is deprecated due to 403 Forbidden errors. Using fallback pool.")
        return self.get_fallback_boxers()

    def get_fallback_boxers(self) -> List[Dict]:
        """Get fallback boxers

        Returns:
            List of known boxers
        """
        return [
            {'name': 'Mike Tyson', 'id': '025806', 'url': 'https://boxrec.com/en/box-pro/025806', 'source': 'boxrec_fallback'},
            {'name': 'Muhammad Ali', 'id': '018122', 'url': 'https://boxrec.com/en/box-pro/018122', 'source': 'boxrec_fallback'},
            {'name': 'Floyd Mayweather', 'id': '000300', 'url': 'https://boxrec.com/en/box-pro/000300', 'source': 'boxrec_fallback'},
            {'name': 'Manny Pacquiao', 'id': '012707', 'url': 'https://boxrec.com/en/box-pro/012707', 'source': 'boxrec_fallback'},
            {'name': 'Sugar Ray Robinson', 'id': '007457', 'url': 'https://boxrec.com/en/box-pro/007457', 'source': 'boxrec_fallback'},
            {'name': 'Joe Louis', 'id': '009234', 'url': 'https://boxrec.com/en/box-pro/009234', 'source': 'boxrec_fallback'},
            {'name': 'Rocky Marciano', 'id': '017391', 'url': 'https://boxrec.com/en/box-pro/017391', 'source': 'boxrec_fallback'},
            {'name': 'Oscar De La Hoya', 'id': '014232', 'url': 'https://boxrec.com/en/box-pro/014232', 'source': 'boxrec_fallback'},
        ]


# ============================================================================
# NFL Scraper - American Football
# ============================================================================

class NFLScraper(BaseScraper):
    """Scraper for NFL Players (using fallback data)

    Pro-Football-Reference has anti-scraping protection.
    This scraper uses a curated list of notable NFL players.
    """

    def scrape_players(self, limit: int = 1000) -> List[Dict]:
        """Scrape NFL players (uses fallback pool)

        Args:
            limit: Maximum number of players (ignored, uses fallback)

        Returns:
            List of notable NFL players
        """
        logger.info("Using fallback NFL players pool (Pro-Football-Reference has anti-scraping)")
        return self.get_fallback_players()

    def get_fallback_players(self) -> List[Dict]:
        """Get fallback NFL players

        Returns:
            List of known NFL players
        """
        return [
            # Current/Recent Stars
            {'name': 'Patrick Mahomes', 'id': 'MahoPa00', 'url': 'https://www.pro-football-reference.com/players/M/MahoPa00.htm', 'source': 'nfl_fallback', 'team': 'Kansas City Chiefs', 'position': 'QB'},
            {'name': 'Josh Allen', 'id': 'AlleJo02', 'url': 'https://www.pro-football-reference.com/players/A/AlleJo02.htm', 'source': 'nfl_fallback', 'team': 'Buffalo Bills', 'position': 'QB'},
            {'name': 'Justin Herbert', 'id': 'HerbJu00', 'url': 'https://www.pro-football-reference.com/players/H/HerbJu00.htm', 'source': 'nfl_fallback', 'team': 'Los Angeles Chargers', 'position': 'QB'},
            {'name': 'Lamar Jackson', 'id': 'JackLa00', 'url': 'https://www.pro-football-reference.com/players/J/JackLa00.htm', 'source': 'nfl_fallback', 'team': 'Baltimore Ravens', 'position': 'QB'},
            {'name': 'Joe Burrow', 'id': 'BurroJo00', 'url': 'https://www.pro-football-reference.com/players/B/BurroJo00.htm', 'source': 'nfl_fallback', 'team': 'Cincinnati Bengals', 'position': 'QB'},
            {'name': 'Trevor Lawrence', 'id': 'LawrTr00', 'url': 'https://www.pro-football-reference.com/players/L/LawrTr00.htm', 'source': 'nfl_fallback', 'team': 'Jacksonville Jaguars', 'position': 'QB'},
            {'name': 'Dak Prescott', 'id': 'PresDa00', 'url': 'https://www.pro-football-reference.com/players/P/PresDa00.htm', 'source': 'nfl_fallback', 'team': 'Dallas Cowboys', 'position': 'QB'},
            # Legendary Quarterbacks
            {'name': 'Tom Brady', 'id': 'BradTo00', 'url': 'https://www.pro-football-reference.com/players/B/BradTo00.htm', 'source': 'nfl_fallback', 'team': 'Tampa Bay Buccaneers', 'position': 'QB'},
            {'name': 'Peyton Manning', 'id': 'MannPe00', 'url': 'https://www.pro-football-reference.com/players/M/MannPe00.htm', 'source': 'nfl_fallback', 'team': 'Denver Broncos', 'position': 'QB'},
            {'name': 'Aaron Rodgers', 'id': 'RodgAa00', 'url': 'https://www.pro-football-reference.com/players/R/RodgAa00.htm', 'source': 'nfl_fallback', 'team': 'Green Bay Packers', 'position': 'QB'},
            {'name': 'Brett Favre', 'id': 'FavrBr00', 'url': 'https://www.pro-football-reference.com/players/F/FavrBr00.htm', 'source': 'nfl_fallback', 'team': 'Green Bay Packers', 'position': 'QB'},
            {'name': 'Dan Marino', 'id': 'MariDa00', 'url': 'https://www.pro-football-reference.com/players/M/MariDa00.htm', 'source': 'nfl_fallback', 'team': 'Miami Dolphins', 'position': 'QB'},
            {'name': 'John Elway', 'id': 'ElwaJo00', 'url': 'https://www.pro-football-reference.com/players/E/ElwaJo00.htm', 'source': 'nfl_fallback', 'team': 'Denver Broncos', 'position': 'QB'},
            {'name': 'Joe Montana', 'id': 'MontJo00', 'url': 'https://www.pro-football-reference.com/players/M/MontJo00.htm', 'source': 'nfl_fallback', 'team': 'San Francisco 49ers', 'position': 'QB'},
            # Other Legends
            {'name': 'Jerry Rice', 'id': 'RiceJe00', 'url': 'https://www.pro-football-reference.com/players/R/RiceJe00.htm', 'source': 'nfl_fallback', 'team': 'San Francisco 49ers', 'position': 'WR'},
            {'name': 'Emmitt Smith', 'id': 'SmitEm00', 'url': 'https://www.pro-football-reference.com/players/S/SmitEm00.htm', 'source': 'nfl_fallback', 'team': 'Dallas Cowboys', 'position': 'RB'},
            {'name': 'Lawrence Taylor', 'id': 'TaylLa00', 'url': 'https://www.pro-football-reference.com/players/T/TaylLa00.htm', 'source': 'nfl_fallback', 'team': 'New York Giants', 'position': 'LB'},
            {'name': 'Reggie White', 'id': 'WhitRe00', 'url': 'https://www.pro-football-reference.com/players/W/WhitRe00.htm', 'source': 'nfl_fallback', 'team': 'Green Bay Packers', 'position': 'DE'},
            {'name': 'Walter Payton', 'id': 'PaytWa00', 'url': 'https://www.pro-football-reference.com/players/P/PaytWa00.htm', 'source': 'nfl_fallback', 'team': 'Chicago Bears', 'position': 'RB'},
            # Recent Defensive Stars
            {'name': 'T.J. Watt', 'id': 'WattTJ00', 'url': 'https://www.pro-football-reference.com/players/W/WattTJ00.htm', 'source': 'nfl_fallback', 'team': 'Pittsburgh Steelers', 'position': 'LB'},
            {'name': 'Aaron Donald', 'id': 'DonaAa00', 'url': 'https://www.pro-football-reference.com/players/D/DonaAa00.htm', 'source': 'nfl_fallback', 'team': 'Los Angeles Rams', 'position': 'DT'},
            {'name': 'Myles Garrett', 'id': 'GarrMy00', 'url': 'https://www.pro-football-reference.com/players/G/GarrMy00.htm', 'source': 'nfl_fallback', 'team': 'Cleveland Browns', 'position': 'DE'},
            # More Current Players
            {'name': 'Travis Kelce', 'id': 'KelcTr00', 'url': 'https://www.pro-football-reference.com/players/K/KelcTr00.htm', 'source': 'nfl_fallback', 'team': 'Kansas City Chiefs', 'position': 'TE'},
            {'name': 'Tyreek Hill', 'id': 'HillTy00', 'url': 'https://www.pro-football-reference.com/players/H/HillTy00.htm', 'source': 'nfl_fallback', 'team': 'Miami Dolphins', 'position': 'WR'},
            {'name': 'Davante Adams', 'id': 'AdamDa00', 'url': 'https://www.pro-football-reference.com/players/A/AdamDa00.htm', 'source': 'nfl_fallback', 'team': 'Las Vegas Raiders', 'position': 'WR'},
            {'name': 'Nick Bosa', 'id': 'BosaNi00', 'url': 'https://www.pro-football-reference.com/players/B/BosaNi00.htm', 'source': 'nfl_fallback', 'team': 'San Francisco 49ers', 'position': 'DE'},
        ]


# ============================================================================
# MLB Scraper - Baseball
# ============================================================================

class MLBScraper(BaseScraper):
    """Scraper for MLB Players (using fallback data)

    Baseball-Reference has anti-scraping protection.
    This scraper uses a curated list of notable MLB players.
    """

    def scrape_players(self, limit: int = 1000) -> List[Dict]:
        """Scrape MLB players (uses fallback pool)

        Args:
            limit: Maximum number of players (ignored, uses fallback)

        Returns:
            List of notable MLB players
        """
        logger.info("Using fallback MLB players pool (Baseball-Reference has anti-scraping)")
        return self.get_fallback_players()

    def get_fallback_players(self) -> List[Dict]:
        """Get fallback MLB players

        Returns:
            List of known MLB players
        """
        return [
            # Current Stars
            {'name': 'Shohei Ohtani', 'id': 'ohtansh01', 'url': 'https://www.baseball-reference.com/players/o/ohtansh01.shtml', 'source': 'mlb_fallback', 'team': 'Los Angeles Dodgers', 'position': 'DH/SP'},
            {'name': 'Aaron Judge', 'id': 'judgeaa01', 'url': 'https://www.baseball-reference.com/players/j/judgeaa01.shtml', 'source': 'mlb_fallback', 'team': 'New York Yankees', 'position': 'RF'},
            {'name': 'Mookie Betts', 'id': 'bettmm01', 'url': 'https://www.baseball-reference.com/players/b/bettmm01.shtml', 'source': 'mlb_fallback', 'team': 'Los Angeles Dodgers', 'position': 'SS/2B'},
            {'name': 'Ronald Acuña Jr.', 'id': 'acunaro01', 'url': 'https://www.baseball-reference.com/players/a/acunaro01.shtml', 'source': 'mlb_fallback', 'team': 'Atlanta Braves', 'position': 'RF'},
            {'name': 'Juan Soto', 'id': 'sotoju01', 'url': 'https://www.baseball-reference.com/players/s/sotoju01.shtml', 'source': 'mlb_fallback', 'team': 'New York Yankees', 'position': 'RF'},
            {'name': 'Freddie Freeman', 'id': 'freemfr01', 'url': 'https://www.baseball-reference.com/players/f/freemfr01.shtml', 'source': 'mlb_fallback', 'team': 'Los Angeles Dodgers', 'position': '1B'},
            # Legends
            {'name': 'Babe Ruth', 'id': 'ruthba01', 'url': 'https://www.baseball-reference.com/players/r/ruthba01.shtml', 'source': 'mlb_fallback', 'team': 'New York Yankees', 'position': 'RF/P'},
            {'name': 'Hank Aaron', 'id': 'aaronha01', 'url': 'https://www.baseball-reference.com/players/a/aaronha01.shtml', 'source': 'mlb_fallback', 'team': 'Atlanta Braves', 'position': 'RF'},
            {'name': 'Barry Bonds', 'id': 'bondsba01', 'url': 'https://www.baseball-reference.com/players/b/bondsba01.shtml', 'source': 'mlb_fallback', 'team': 'San Francisco Giants', 'position': 'LF'},
            {'name': 'Ted Williams', 'id': 'willite01', 'url': 'https://www.baseball-reference.com/players/w/willite01.shtml', 'source': 'mlb_fallback', 'team': 'Boston Red Sox', 'position': 'LF'},
            {'name': 'Mickey Mantle', 'id': 'mantlmi01', 'url': 'https://www.baseball-reference.com/players/m/mantlmi01.shtml', 'source': 'mlb_fallback', 'team': 'New York Yankees', 'position': 'CF'},
            {'name': 'Willie Mays', 'id': 'mayswi01', 'url': 'https://www.baseball-reference.com/players/m/mayswi01.shtml', 'source': 'mlb_fallback', 'team': 'San Francisco Giants', 'position': 'CF'},
            {'name': 'Jackie Robinson', 'id': 'robinja01', 'url': 'https://www.baseball-reference.com/players/r/robinja01.shtml', 'source': 'mlb_fallback', 'team': 'Brooklyn Dodgers', 'position': '2B'},
            {'name': 'Derek Jeter', 'id': 'jeterde01', 'url': 'https://www.baseball-reference.com/players/j/jeterde01.shtml', 'source': 'mlb_fallback', 'team': 'New York Yankees', 'position': 'SS'},
            {'name': 'Ken Griffey Jr.', 'id': 'griffke02', 'url': 'https://www.baseball-reference.com/players/g/griffke02.shtml', 'source': 'mlb_fallback', 'team': 'Seattle Mariners', 'position': 'CF'},
            # Pitchers
            {'name': 'Clayton Kershaw', 'id': 'kershcl01', 'url': 'https://www.baseball-reference.com/players/k/kershcl01.shtml', 'source': 'mlb_fallback', 'team': 'Los Angeles Dodgers', 'position': 'SP'},
            {'name': 'Max Scherzer', 'id': 'scherma01', 'url': 'https://www.baseball-reference.com/players/s/scherma01.shtml', 'source': 'mlb_fallback', 'team': 'Texas Rangers', 'position': 'SP'},
            {'name': 'Jacob deGrom', 'id': 'degroja01', 'url': 'https://www.baseball-reference.com/players/d/degroja01.shtml', 'source': 'mlb_fallback', 'team': 'Texas Rangers', 'position': 'SP'},
            {'name': 'Mariano Rivera', 'id': 'riverma01', 'url': 'https://www.baseball-reference.com/players/r/riverma01.shtml', 'source': 'mlb_fallback', 'team': 'New York Yankees', 'position': 'RP'},
            {'name': 'Nolan Ryan', 'id': 'ryanno01', 'url': 'https://www.baseball-reference.com/players/r/ryanno01.shtml', 'source': 'mlb_fallback', 'team': 'California Angels', 'position': 'SP'},
            {'name': 'Greg Maddux', 'id': 'maddugr01', 'url': 'https://www.baseball-reference.com/players/m/maddugr01.shtml', 'source': 'mlb_fallback', 'team': 'Atlanta Braves', 'position': 'SP'},
            {'name': 'Randy Johnson', 'id': 'johnsra05', 'url': 'https://www.baseball-reference.com/players/j/johnsra05.shtml', 'source': 'mlb_fallback', 'team': 'Arizona Diamondbacks', 'position': 'SP'},
        ]


# ============================================================================
# NHL Scraper - Ice Hockey
# ============================================================================

class NHLScraper(BaseScraper):
    """Scraper for NHL Players (using fallback data)

    Hockey-Reference has anti-scraping protection.
    This scraper uses a curated list of notable NHL players.
    """

    def scrape_players(self, limit: int = 1000) -> List[Dict]:
        """Scrape NHL players (uses fallback pool)

        Args:
            limit: Maximum number of players (ignored, uses fallback)

        Returns:
            List of notable NHL players
        """
        logger.info("Using fallback NHL players pool (Hockey-Reference has anti-scraping)")
        return self.get_fallback_players()

    def get_fallback_players(self) -> List[Dict]:
        """Get fallback NHL players

        Returns:
            List of known NHL players
        """
        return [
            # Current Stars
            {'name': 'Connor McDavid', 'id': 'mcdavco01', 'url': 'https://www.hockey-reference.com/players/m/mcdavco01.html', 'source': 'nhl_fallback', 'team': 'Edmonton Oilers', 'position': 'C'},
            {'name': 'Nathan MacKinnon', 'id': 'mackina01', 'url': 'https://www.hockey-reference.com/players/m/mackina01.html', 'source': 'nhl_fallback', 'team': 'Colorado Avalanche', 'position': 'C'},
            {'name': 'Auston Matthews', 'id': 'matthau01', 'url': 'https://www.hockey-reference.com/players/m/matthau01.html', 'source': 'nhl_fallback', 'team': 'Toronto Maple Leafs', 'position': 'C'},
            {'name': 'Leon Draisaitl', 'id': 'draisle01', 'url': 'https://www.hockey-reference.com/players/d/draisle01.html', 'source': 'nhl_fallback', 'team': 'Edmonton Oilers', 'position': 'C'},
            {'name': 'Artemi Panarin', 'id': 'panarar01', 'url': 'https://www.hockey-reference.com/players/p/panarar01.html', 'source': 'nhl_fallback', 'team': 'New York Rangers', 'position': 'LW'},
            {'name': 'Cale Makar', 'id': 'makarca01', 'url': 'https://www.hockey-reference.com/players/m/makarca01.html', 'source': 'nhl_fallback', 'team': 'Colorado Avalanche', 'position': 'D'},
            # Legends
            {'name': 'Wayne Gretzky', 'id': 'greetwa01', 'url': 'https://www.hockey-reference.com/players/g/greetwa01.html', 'source': 'nhl_fallback', 'team': 'Edmonton Oilers', 'position': 'C'},
            {'name': 'Mario Lemieux', 'id': 'lemieuma01', 'url': 'https://www.hockey-reference.com/players/l/lemieuma01.html', 'source': 'nhl_fallback', 'team': 'Pittsburgh Penguins', 'position': 'C'},
            {'name': 'Bobby Orr', 'id': 'orrbo01', 'url': 'https://www.hockey-reference.com/players/o/orrbo01.html', 'source': 'nhl_fallback', 'team': 'Boston Bruins', 'position': 'D'},
            {'name': 'Gordie Howe', 'id': 'howego01', 'url': 'https://www.hockey-reference.com/players/h/howego01.html', 'source': 'nhl_fallback', 'team': 'Detroit Red Wings', 'position': 'RW'},
            {'name': 'Sidney Crosby', 'id': 'crosbsi01', 'url': 'https://www.hockey-reference.com/players/c/crosbsi01.html', 'source': 'nhl_fallback', 'team': 'Pittsburgh Penguins', 'position': 'C'},
            {'name': 'Alex Ovechkin', 'id': 'ovechal01', 'url': 'https://www.hockey-reference.com/players/o/ovechal01.html', 'source': 'nhl_fallback', 'team': 'Washington Capitals', 'position': 'LW'},
            {'name': 'Patrick Kane', 'id': 'kanepa01', 'url': 'https://www.hockey-reference.com/players/k/kanepa01.html', 'source': 'nhl_fallback', 'team': 'Chicago Blackhawks', 'position': 'RW'},
            {'name': 'Steven Stamkos', 'id': 'stamste01', 'url': 'https://www.hockey-reference.com/players/s/stamste01.html', 'source': 'nhl_fallback', 'team': 'Tampa Bay Lightning', 'position': 'C'},
            {'name': 'Mikhail Sergachev', 'id': 'sergemm01', 'url': 'https://www.hockey-reference.com/players/s/sergemm01.html', 'source': 'nhl_fallback', 'team': 'Tampa Bay Lightning', 'position': 'D'},
            # Defensemen
            {'name': 'Victor Hedman', 'id': 'hedmavi01', 'url': 'https://www.hockey-reference.com/players/h/hedmavi01.html', 'source': 'nhl_fallback', 'team': 'Tampa Bay Lightning', 'position': 'D'},
            {'name': 'Drew Doughty', 'id': 'doughdr01', 'url': 'https://www.hockey-reference.com/players/d/doughdr01.html', 'source': 'nhl_fallback', 'team': 'Los Angeles Kings', 'position': 'D'},
            {'name': 'Erik Karlsson', 'id': 'karler01', 'url': 'https://www.hockey-reference.com/players/k/karler01.html', 'source': 'nhl_fallback', 'team': 'Pittsburgh Penguins', 'position': 'D'},
            {'name': 'Nicklas Lidström', 'id': 'lidstni01', 'url': 'https://www.hockey-reference.com/players/l/lidstni01.html', 'source': 'nhl_fallback', 'team': 'Detroit Red Wings', 'position': 'D'},
            {'name': 'Ray Bourque', 'id': 'bourara01', 'url': 'https://www.hockey-reference.com/players/b/bourara01.html', 'source': 'nhl_fallback', 'team': 'Boston Bruins', 'position': 'D'},
            # Goalies
            {'name': 'Martin Brodeur', 'id': 'brodemr01', 'url': 'https://www.hockey-reference.com/players/b/brodemr01.html', 'source': 'nhl_fallback', 'team': 'New Jersey Devils', 'position': 'G'},
            {'name': 'Patrick Roy', 'id': 'roypa01', 'url': 'https://www.hockey-reference.com/players/r/roypa01.html', 'source': 'nhl_fallback', 'team': 'Montreal Canadiens', 'position': 'G'},
            {'name': 'Dominik Hašek', 'id': 'hasedo01', 'url': 'https://www.hockey-reference.com/players/h/hasedo01.html', 'source': 'nhl_fallback', 'team': 'Buffalo Sabres', 'position': 'G'},
        ]


# ============================================================================
# F1 Scraper - Formula 1 Racing
# ============================================================================

class F1Scraper(BaseScraper):
    """Scraper for Formula1.com - F1 Drivers

    Formula1.com has a drivers listing page with historical data.

    Coverage: All F1 drivers (current and historical)
    """

    BASE_URL = "https://www.formula1.com"

    def scrape_drivers(self, limit: int = 500) -> List[Dict]:
        """Scrape F1 drivers from Formula1.com

        Args:
            limit: Maximum number of drivers to scrape

        Returns:
            List of F1 drivers
        """
        # Formula1.com uses JavaScript for content loading
        # We'll use a fallback list of known F1 drivers
        logger.info("Using fallback F1 drivers pool (Formula1.com requires JS)")
        return self.get_fallback_drivers()

    def get_fallback_drivers(self) -> List[Dict]:
        """Get fallback F1 drivers

        Returns:
            List of known F1 drivers
        """
        return [
            # Current/Recent Drivers
            {'name': 'Max Verstappen', 'id': 'max_verstappen', 'url': 'https://www.formula1.com/en/drivers/max-verstappen.html', 'source': 'f1_fallback', 'team': 'Red Bull Racing'},
            {'name': 'Lewis Hamilton', 'id': 'lewis_hamilton', 'url': 'https://www.formula1.com/en/drivers/lewis-hamilton.html', 'source': 'f1_fallback', 'team': 'Mercedes'},
            {'name': 'Charles Leclerc', 'id': 'charles_leclerc', 'url': 'https://www.formula1.com/en/drivers/charles-leclerc.html', 'source': 'f1_fallback', 'team': 'Ferrari'},
            {'name': 'Carlos Sainz', 'id': 'carlos_sainz', 'url': 'https://www.formula1.com/en/drivers/carlos-sainz.html', 'source': 'f1_fallback', 'team': 'Ferrari'},
            {'name': 'Lando Norris', 'id': 'lando_norris', 'url': 'https://www.formula1.com/en/drivers/lando-norris.html', 'source': 'f1_fallback', 'team': 'McLaren'},
            {'name': 'Daniel Ricciardo', 'id': 'daniel_ricciardo', 'url': 'https://www.formula1.com/en/drivers/daniel-ricciardo.html', 'source': 'f1_fallback', 'team': 'RB'},
            {'name': 'Fernando Alonso', 'id': 'fernando_alonso', 'url': 'https://www.formula1.com/en/drivers/fernando-alonso.html', 'source': 'f1_fallback', 'team': 'Aston Martin'},
            {'name': 'Sebastian Vettel', 'id': 'sebastian_vettel', 'url': 'https://www.formula1.com/en/drivers/sebastian-vettel.html', 'source': 'f1_fallback', 'team': 'Retired'},
            {'name': 'Kimi Räikkönen', 'id': 'kimi_raikkonen', 'url': 'https://www.formula1.com/en/drivers/kimi-raikkonen.html', 'source': 'f1_fallback', 'team': 'Retired'},
            # Legendary Drivers
            {'name': 'Michael Schumacher', 'id': 'michael_schumacher', 'url': 'https://www.formula1.com/en/drivers/michael-schumacher.html', 'source': 'f1_fallback', 'team': 'Ferrari'},
            {'name': 'Ayrton Senna', 'id': 'ayrton_senna', 'url': 'https://www.formula1.com/en/drivers/ayrton-senna.html', 'source': 'f1_fallback', 'team': 'McLaren'},
            {'name': 'Alain Prost', 'id': 'alain_prost', 'url': 'https://www.formula1.com/en/drivers/alain-prost.html', 'source': 'f1_fallback', 'team': 'Ferrari'},
            {'name': 'Niki Lauda', 'id': 'niki_lauda', 'url': 'https://www.formula1.com/en/drivers/niki-lauda.html', 'source': 'f1_fallback', 'team': 'Ferrari'},
            {'name': 'Juan Manuel Fangio', 'id': 'juan_manuel_fangio', 'url': 'https://www.formula1.com/en/drivers/juan-manuel-fangio.html', 'source': 'f1_fallback', 'team': 'Mercedes'},
            {'name': 'Jackie Stewart', 'id': 'jackie_stewart', 'url': 'https://www.formula1.com/en/drivers/jackie-stewart.html', 'source': 'f1_fallback', 'team': 'Matra'},
            {'name': 'Nelson Piquet', 'id': 'nelson_piquet', 'url': 'https://www.formula1.com/en/drivers/nelson-piquet.html', 'source': 'f1_fallback', 'team': 'Williams'},
            {'name': 'Nico Rosberg', 'id': 'nico_rosberg', 'url': 'https://www.formula1.com/en/drivers/nico-rosberg.html', 'source': 'f1_fallback', 'team': 'Mercedes'},
            {'name': 'Jenson Button', 'id': 'jenson_button', 'url': 'https://www.formula1.com/en/drivers/jenson-button.html', 'source': 'f1_fallback', 'team': 'McLaren'},
            # More recent champions
            {'name': 'Damon Hill', 'id': 'damon_hill', 'url': 'https://www.formula1.com/en/drivers/damon-hill.html', 'source': 'f1_fallback', 'team': 'Williams'},
            {'name': 'Jacques Villeneuve', 'id': 'jacques_villeneuve', 'url': 'https://www.formula1.com/en/drivers/jacques-villeneuve.html', 'source': 'f1_fallback', 'team': 'Williams'},
            {'name': 'Mika Häkkinen', 'id': 'mika_hakkinen', 'url': 'https://www.formula1.com/en/drivers/mika-hakkinen.html', 'source': 'f1_fallback', 'team': 'McLaren'},
        ]


# ============================================================================
# Cricket Scraper
# ============================================================================

class CricketScraper(BaseScraper):
    """Scraper for Cricket Players (using fallback data)

    Cricket has many international players across Test, ODI, and T20 formats.
    This scraper uses a curated list of notable cricketers.
    """

    def scrape_players(self, limit: int = 500) -> List[Dict]:
        """Scrape cricket players (uses fallback pool)

        Args:
            limit: Maximum number of players (ignored, uses fallback)

        Returns:
            List of notable cricket players
        """
        logger.info("Using fallback cricket players pool")
        return self.get_fallback_players()

    def get_fallback_players(self) -> List[Dict]:
        """Get fallback cricket players

        Returns:
            List of known cricket players
        """
        return [
            # Modern Greats
            {'name': 'Virat Kohli', 'id': 'kohli', 'url': 'https://www.espncricinfo.com/cricketers/virat-kohli-253798', 'source': 'cricket_fallback', 'country': 'India', 'role': 'Batsman'},
            {'name': 'Steve Smith', 'id': 'smith', 'url': 'https://www.espncricinfo.com/cricketers/steve-smith-270725', 'source': 'cricket_fallback', 'country': 'Australia', 'role': 'Batsman'},
            {'name': 'Kane Williamson', 'id': 'williamson', 'url': 'https://www.espncricinfo.com/cricketers/kane-williamson-277907', 'source': 'cricket_fallback', 'country': 'New Zealand', 'role': 'Batsman'},
            {'name': 'Joe Root', 'id': 'root', 'url': 'https://www.espncricinfo.com/cricketers/joe-root-303669', 'source': 'cricket_fallback', 'country': 'England', 'role': 'Batsman'},
            {'name': 'Babar Azam', 'id': 'azam', 'url': 'https://www.espncricinfo.com/cricketers/babar-azam-1185654', 'source': 'cricket_fallback', 'country': 'Pakistan', 'role': 'Batsman'},
            # Legends - Batsmen
            {'name': 'Sachin Tendulkar', 'id': 'tendulkar', 'url': 'https://www.espncricinfo.com/cricketers/sachin-tendulkar-35320', 'source': 'cricket_fallback', 'country': 'India', 'role': 'Batsman'},
            {'name': 'Brian Lara', 'id': 'lara', 'url': 'https://www.espncricinfo.com/cricketers/brian-lara-51780', 'source': 'cricket_fallback', 'country': 'West Indies', 'role': 'Batsman'},
            {'name': 'Ricky Ponting', 'id': 'ponting', 'url': 'https://www.espncricinfo.com/cricketers/ricky-ponting-7113', 'source': 'cricket_fallback', 'country': 'Australia', 'role': 'Batsman'},
            {'name': 'Jacques Kallis', 'id': 'kallis', 'url': 'https://www.espncricinfo.com/cricketers/jacques-kallis-45778', 'source': 'cricket_fallback', 'country': 'South Africa', 'role': 'All-rounder'},
            {'name': 'Sir Don Bradman', 'id': 'bradman', 'url': 'https://www.espncricinfo.com/cricketers/don-bradman-4188', 'source': 'cricket_fallback', 'country': 'Australia', 'role': 'Batsman'},
            {'name': 'Rahul Dravid', 'id': 'dravid', 'url': 'https://www.espncricinfo.com/cricketers/rahul-dravid-28114', 'source': 'cricket_fallback', 'country': 'India', 'role': 'Batsman'},
            {'name': 'Sourav Ganguly', 'id': 'ganguly', 'url': 'https://www.espncricinfo.com/cricketers/sourav-ganguly-28775', 'source': 'cricket_fallback', 'country': 'India', 'role': 'Batsman'},
            {'name': 'VVS Laxman', 'id': 'laxman', 'url': 'https://www.espncricinfo.com/cricketers/vvs-laxman-28780', 'source': 'cricket_fallback', 'country': 'India', 'role': 'Batsman'},
            {'name': 'Inzamam-ul-Haq', 'id': 'inzamam', 'url': 'https://www.espncricinfo.com/cricketers/inzamam-ul-haq-26066', 'source': 'cricket_fallback', 'country': 'Pakistan', 'role': 'Batsman'},
            {'name': 'Mahela Jayawardene', 'id': 'jayawardene', 'url': 'https://www.espncricinfo.com/cricketers/mahela-jayawardene-49649', 'source': 'cricket_fallback', 'country': 'Sri Lanka', 'role': 'Batsman'},
            {'name': 'Kumar Sangakkara', 'id': 'sangakkara', 'url': 'https://www.espncricinfo.com/cricketers/kumar-sangakkara-50710', 'source': 'cricket_fallback', 'country': 'Sri Lanka', 'role': 'Batsman/Wicketkeeper'},
            # Bowlers
            {'name': 'Muttiah Muralitharan', 'id': 'muralitharan', 'url': 'https://www.espncricinfo.com/cricketers/muttiah-muralitharan-49364', 'source': 'cricket_fallback', 'country': 'Sri Lanka', 'role': 'Bowler'},
            {'name': 'Shane Warne', 'id': 'warne', 'url': 'https://www.espncricinfo.com/cricketers/shane-warne-8551', 'source': 'cricket_fallback', 'country': 'Australia', 'role': 'Bowler'},
            {'name': 'Glenn McGrath', 'id': 'mcgrath', 'url': 'https://www.espncricinfo.com/cricketers/glenn-mcgrath-8552', 'source': 'cricket_fallback', 'country': 'Australia', 'role': 'Bowler'},
            {'name': 'Wasim Akram', 'id': 'akram', 'url': 'https://www.espncricinfo.com/cricketers/wasim-akram-25779', 'source': 'cricket_fallback', 'country': 'Pakistan', 'role': 'Bowler'},
            {'name': 'James Anderson', 'id': 'anderson', 'url': 'https://www.espncricinfo.com/cricketers/james-anderson-11272', 'source': 'cricket_fallback', 'country': 'England', 'role': 'Bowler'},
            {'name': 'Dale Steyn', 'id': 'steyn', 'url': 'https://www.espncricinfo.com/cricketers/dale-steyn-45794', 'source': 'cricket_fallback', 'country': 'South Africa', 'role': 'Bowler'},
            # All-rounders
            {'name': 'Ben Stokes', 'id': 'stokes', 'url': 'https://www.espncricinfo.com/cricketers/ben-stokes-328263', 'source': 'cricket_fallback', 'country': 'England', 'role': 'All-rounder'},
            {'name': 'Ravindra Jadeja', 'id': 'jadeja', 'url': 'https://www.espncricinfo.com/cricketers/ravindra-jadeja-423882', 'source': 'cricket_fallback', 'country': 'India', 'role': 'All-rounder'},
            # Wicketkeepers
            {'name': 'MS Dhoni', 'id': 'dhoni', 'url': 'https://www.espncricinfo.com/cricketers/ms-dhoni-28114', 'source': 'cricket_fallback', 'country': 'India', 'role': 'Wicketkeeper-Batsman'},
            {'name': 'Adam Gilchrist', 'id': 'gilchrist', 'url': 'https://www.espncricinfo.com/cricketers/adam-gilchrist-8708', 'source': 'cricket_fallback', 'country': 'Australia', 'role': 'Wicketkeeper-Batsman'},
            {'name': 'Mark Boucher', 'id': 'boucher', 'url': 'https://www.espncricinfo.com/cricketers/mark-boucher-44904', 'source': 'cricket_fallback', 'country': 'South Africa', 'role': 'Wicketkeeper'},
        ]


# ============================================================================
# Rugby Scraper
# ============================================================================

class RugbyScraper(BaseScraper):
    """Scraper for Rugby Players (using fallback data)

    Rugby Union has international players from various countries.
    This scraper uses a curated list of notable rugby players.
    """

    def scrape_players(self, limit: int = 500) -> List[Dict]:
        """Scrape rugby players (uses fallback pool)

        Args:
            limit: Maximum number of players (ignored, uses fallback)

        Returns:
            List of notable rugby players
        """
        logger.info("Using fallback rugby players pool")
        return self.get_fallback_players()

    def get_fallback_players(self) -> List[Dict]:
        """Get fallback rugby players

        Returns:
            List of known rugby players
        """
        return [
            # New Zealand (All Blacks) Legends
            {'name': 'Richie McCaw', 'id': 'mccaw', 'url': 'https://www.espnscrum.com/player/13543/Richie-McCaw', 'source': 'rugby_fallback', 'country': 'New Zealand', 'position': 'Flanker'},
            {'name': 'Dan Carter', 'id': 'carter', 'url': 'https://www.espnscrum.com/player/13585/Dan-Carter', 'source': 'rugby_fallback', 'country': 'New Zealand', 'position': 'Fly-half'},
            {'name': 'Jonah Lomu', 'id': 'lomu', 'url': 'https://www.espnscrum.com/player/9162/Jonah-Lomu', 'source': 'rugby_fallback', 'country': 'New Zealand', 'position': 'Winger'},
            {'name': 'Colin Meads', 'id': 'meads', 'url': 'https://www.espnscrum.com/player/10416/Colin-Meads', 'source': 'rugby_fallback', 'country': 'New Zealand', 'position': 'Lock'},
            # South Africa (Springboks)
            {'name': 'Siya Kolisi', 'id': 'kolisi', 'url': 'https://www.espnscrum.com/player/185103/Siya-Kolisi', 'source': 'rugby_fallback', 'country': 'South Africa', 'position': 'Flanker'},
            {'name': 'Francois Pienaar', 'id': 'pienaar', 'url': 'https://www.espnscrum.com/player/9093/Francois-Pienaar', 'source': 'rugby_fallback', 'country': 'South Africa', 'position': 'Flanker'},
            {'name': 'Faf de Klerk', 'id': 'deklerk', 'url': 'https://www.espnscrum.com/player/167383/Faf-de-Klerk', 'source': 'rugby_fallback', 'country': 'South Africa', 'position': 'Scrum-half'},
            {'name': 'Handre Pollard', 'id': 'pollard', 'url': 'https://www.espnscrum.com/player/177479/Handre-Pollard', 'source': 'rugby_fallback', 'country': 'South Africa', 'position': 'Fly-half'},
            # England
            {'name': 'Johnny Wilkinson', 'id': 'wilkinson', 'url': 'https://www.espnscrum.com/player/9238/Jonny-Wilkinson', 'source': 'rugby_fallback', 'country': 'England', 'position': 'Fly-half'},
            {'name': 'Martin Johnson', 'id': 'johnson', 'url': 'https://www.espnscrum.com/player/8730/Martin-Johnson', 'source': 'rugby_fallback', 'country': 'England', 'position': 'Lock'},
            {'name': 'Owen Farrell', 'id': 'farrell', 'url': 'https://www.espnscrum.com/player/146126/Owen-Farrell', 'source': 'rugby_fallback', 'country': 'England', 'position': 'Fly-half'},
            # Ireland
            {'name': 'Brian O\'Driscoll', 'id': 'odriscoll', 'url': 'https://www.espnscrum.com/player/9393/Brian-ODriscoll', 'source': 'rugby_fallback', 'country': 'Ireland', 'position': 'Centre'},
            {'name': 'Ronan O\'Gara', 'id': 'ogara', 'url': 'https://www.espnscrum.com/player/9408/Ronan-OGara', 'source': 'rugby_fallback', 'country': 'Ireland', 'position': 'Fly-half'},
            {'name': 'Johnny Sexton', 'id': 'sexton', 'url': 'https://www.espnscrum.com/player/123578/Johnny-Sexton', 'source': 'rugby_fallback', 'country': 'Ireland', 'position': 'Fly-half'},
            # Australia (Wallabies)
            {'name': 'David Pocock', 'id': 'pocock', 'url': 'https://www.espnscrum.com/player/8973/David-Pocock', 'source': 'rugby_fallback', 'country': 'Australia', 'position': 'Flanker'},
            {'name': 'Michael Hooper', 'id': 'hooper', 'url': 'https://www.espnscrum.com/player/157882/Michael-Hooper', 'source': 'rugby_fallback', 'country': 'Australia', 'position': 'Flanker'},
            {'name': 'Israel Folau', 'id': 'folau', 'url': 'https://www.espnscrum.com/player/162556/Israel-Folau', 'source': 'rugby_fallback', 'country': 'Australia', 'position': 'Full-back'},
            # Wales
            {'name': 'Shane Williams', 'id': 'williams', 'url': 'https://www.espnscrum.com/player/10018/Shane-Williams', 'source': 'rugby_fallback', 'country': 'Wales', 'position': 'Winger'},
            {'name': 'Alun Wyn Jones', 'id': 'jones', 'url': 'https://www.espnscrum.com/player/128562/Alun-Wyn-Jones', 'source': 'rugby_fallback', 'country': 'Wales', 'position': 'Lock'},
            # France
            {'name': 'Serge Blanco', 'id': 'blanco', 'url': 'https://www.espnscrum.com/player/8755/Serge-Blanco', 'source': 'rugby_fallback', 'country': 'France', 'position': 'Full-back'},
            {'name': 'Antoine Dupont', 'id': 'dupont', 'url': 'https://www.espnscrum.com/player/224016/Antoine-Dupont', 'source': 'rugby_fallback', 'country': 'France', 'position': 'Scrum-half'},
        ]


# ============================================================================
# Golf Scraper
# ============================================================================

class GolfScraper(BaseScraper):
    """Scraper for Golf Players (using fallback data)

    Golf has PGA Tour, European Tour, and OWGR rankings.
    This scraper uses a curated list of notable golfers.
    """

    def scrape_players(self, limit: int = 500) -> List[Dict]:
        """Scrape golf players (uses fallback pool)

        Args:
            limit: Maximum number of players (ignored, uses fallback)

        Returns:
            List of notable golfers
        """
        logger.info("Using fallback golf players pool")
        return self.get_fallback_players()

    def get_fallback_players(self) -> List[Dict]:
        """Get fallback golf players

        Returns:
            List of known golfers
        """
        return [
            # Current Stars
            {'name': 'Scottie Scheffler', 'id': 'scheffler', 'url': 'https://www.pgatour.com/players/player.scottie-scheffler.html', 'source': 'golf_fallback', 'country': 'USA', 'rankings': 'OWGR #1'},
            {'name': 'Rory McIlroy', 'id': 'mcilroy', 'url': 'https://www.pgatour.com/players/player.rory-mcilroy.html', 'source': 'golf_fallback', 'country': 'Northern Ireland', 'rankings': 'OWGR Top 10'},
            {'name': 'Jon Rahm', 'id': 'rahm', 'url': 'https://www.pgatour.com/players/player.jon-rahm.html', 'source': 'golf_fallback', 'country': 'Spain', 'rankings': 'OWGR Top 10'},
            {'name': 'Viktor Hovland', 'id': 'hovland', 'url': 'https://www.pgatour.com/players/player.viktor-hovland.html', 'source': 'golf_fallback', 'country': 'Norway', 'rankings': 'OWGR Top 10'},
            {'name': 'Xander Schauffele', 'id': 'schauffele', 'url': 'https://www.pgatour.com/players/player.xander-schauffele.html', 'source': 'golf_fallback', 'country': 'USA', 'rankings': 'OWGR Top 10'},
            {'name': 'Patrick Cantlay', 'id': 'cantlay', 'url': 'https://www.pgatour.com/players/player.patrick-cantlay.html', 'source': 'golf_fallback', 'country': 'USA', 'rankings': 'OWGR Top 10'},
            {'name': 'Dustin Johnson', 'id': 'johnson', 'url': 'https://www.pgatour.com/players/player.dustin-johnson.html', 'source': 'golf_fallback', 'country': 'USA', 'rankings': 'Major Winner'},
            {'name': 'Brooks Koepka', 'id': 'koepka', 'url': 'https://www.pgatour.com/players/player.brooks-koepka.html', 'source': 'golf_fallback', 'country': 'USA', 'rankings': 'Major Winner'},
            {'name': 'Bryson DeChambeau', 'id': 'dechambeau', 'url': 'https://www.pgatour.com/players/player.bryson-dechambeau.html', 'source': 'golf_fallback', 'country': 'USA', 'rankings': 'Major Winner'},
            {'name': 'Jordan Spieth', 'id': 'spieth', 'url': 'https://www.pgatour.com/players/player.jordan-spieth.html', 'source': 'golf_fallback', 'country': 'USA', 'rankings': 'Major Winner'},
            # Legends
            {'name': 'Tiger Woods', 'id': 'woods', 'url': 'https://www.pgatour.com/players/player.tiger-woods.html', 'source': 'golf_fallback', 'country': 'USA', 'rankings': '15 Major Wins'},
            {'name': 'Jack Nicklaus', 'id': 'nicklaus', 'url': 'https://www.pgatour.com/players/player.jack-nicklaus.html', 'source': 'golf_fallback', 'country': 'USA', 'rankings': '18 Major Wins'},
            {'name': 'Arnold Palmer', 'id': 'palmer', 'url': 'https://www.pgatour.com/players/player.arnold-palmer.html', 'source': 'golf_fallback', 'country': 'USA', 'rankings': '7 Major Wins'},
            {'name': 'Gary Player', 'id': 'player', 'url': 'https://www.pgatour.com/players/player.gary-player.html', 'source': 'golf_fallback', 'country': 'South Africa', 'rankings': '9 Major Wins'},
            {'name': 'Ben Hogan', 'id': 'hogan', 'url': 'https://www.pgatour.com/players/player.ben-hogan.html', 'source': 'golf_fallback', 'country': 'USA', 'rankings': '9 Major Wins'},
            {'name': 'Tom Watson', 'id': 'watson', 'url': 'https://www.pgatour.com/players/player.tom-watson.html', 'source': 'golf_fallback', 'country': 'USA', 'rankings': '8 Major Wins'},
            {'name': 'Seve Ballesteros', 'id': 'ballesteros', 'url': 'https://www.pgatour.com/players/player.seve-ballesteros.html', 'source': 'golf_fallback', 'country': 'Spain', 'rankings': '5 Major Wins'},
            {'name': 'Nick Faldo', 'id': 'faldo', 'url': 'https://www.pgatour.com/players/player.nick-faldo.html', 'source': 'golf_fallback', 'country': 'England', 'rankings': '6 Major Wins'},
            {'name': 'Greg Norman', 'id': 'norman', 'url': 'https://www.pgatour.com/players/player.greg-norman.html', 'source': 'golf_fallback', 'country': 'Australia', 'rankings': '2 Major Wins'},
            {'name': 'Phil Mickelson', 'id': 'mickelson', 'url': 'https://www.pgatour.com/players/player.phil-mickelson.html', 'source': 'golf_fallback', 'country': 'USA', 'rankings': '6 Major Wins'},
            # International Stars
            {'name': 'Hideki Matsuyama', 'id': 'matsuyama', 'url': 'https://www.pgatour.com/players/player.hideki-matsuyama.html', 'source': 'golf_fallback', 'country': 'Japan', 'rankings': 'Masters Winner'},
            {'name': 'Jason Day', 'id': 'day', 'url': 'https://www.pgatour.com/players/player.jason-day.html', 'source': 'golf_fallback', 'country': 'Australia', 'rankings': 'PGA Winner'},
            {'name': 'Adam Scott', 'id': 'scott', 'url': 'https://www.pgatour.com/players/player.adam-scott.html', 'source': 'golf_fallback', 'country': 'Australia', 'rankings': 'Masters Winner'},
            {'name': 'Louis Oosthuizen', 'id': 'oosthuizen', 'url': 'https://www.pgatour.com/players/player.louis-oosthuizen.html', 'source': 'golf_fallback', 'country': 'South Africa', 'rankings': 'Open Champion'},
            {'name': 'Cam Smith', 'id': 'smith', 'url': 'https://www.pgatour.com/players/player.cam-smith.html', 'source': 'golf_fallback', 'country': 'Australia', 'rankings': 'Open Champion'},
        ]


# ============================================================================
# WTA Tennis Scraper (Women's Tennis)
# ============================================================================

class WTAScraper(BaseScraper):
    """Scraper for WTA Tennis Players (using fallback data)

    WTA is the women's professional tennis tour.
    This scraper uses a curated list of notable WTA players.
    """

    def scrape_players(self, limit: int = 500) -> List[Dict]:
        """Scrape WTA tennis players (uses fallback pool)

        Args:
            limit: Maximum number of players (ignored, uses fallback)

        Returns:
            List of notable WTA players
        """
        logger.info("Using fallback WTA players pool")
        return self.get_fallback_players()

    def get_fallback_players(self) -> List[Dict]:
        """Get fallback WTA players

        Returns:
            List of known WTA players
        """
        return [
            # Current Stars
            {'name': 'Iga Świątek', 'id': 'swiatek', 'url': 'https://www.wtatennis.com/players/player/iga-swiatek/318732', 'source': 'wta_fallback', 'country': 'Poland', 'rankings': 'WTA #1'},
            {'name': 'Aryna Sabalenka', 'id': 'sabalenka', 'url': 'https://www.wtatennis.com/players/player/aryna-sabalenka/321760', 'source': 'wta_fallback', 'country': 'Belarus', 'rankings': 'WTA Top 5'},
            {'name': 'Elena Rybakina', 'id': 'rybakina', 'url': 'https://www.wtatennis.com/players/player/elena-rybakina/321788', 'source': 'wta_fallback', 'country': 'Kazakhstan', 'rankings': 'WTA Top 5'},
            {'name': 'Jessica Pegula', 'id': 'pegula', 'url': 'https://www.wtatennis.com/players/player/jessica-pegula/319233', 'source': 'wta_fallback', 'country': 'USA', 'rankings': 'WTA Top 10'},
            {'name': 'Coco Gauff', 'id': 'gauff', 'url': 'https://www.wtatennis.com/players/player/coco-gauff/326254', 'source': 'wta_fallback', 'country': 'USA', 'rankings': 'WTA Top 10'},
            {'name': 'Maria Sakkari', 'id': 'sakkari', 'url': 'https://www.wtatennis.com/players/player/maria-sakkari/314088', 'source': 'wta_fallback', 'country': 'Greece', 'rankings': 'WTA Top 10'},
            {'name': 'Ons Jabeur', 'id': 'jabeur', 'url': 'https://www.wtatennis.com/players/player/ons-jabeur/315099', 'source': 'wta_fallback', 'country': 'Tunisia', 'rankings': 'WTA Top 10'},
            {'name': 'Caroline Garcia', 'id': 'garcia', 'url': 'https://www.wtatennis.com/players/player/caroline-garcia/313839', 'source': 'wta_fallback', 'country': 'France', 'rankings': 'WTA Top 20'},
            # Legends
            {'name': 'Serena Williams', 'id': 'williams', 'url': 'https://www.wtatennis.com/players/player/serena-williams/224000', 'source': 'wta_fallback', 'country': 'USA', 'rankings': '23 Grand Slams'},
            {'name': 'Venus Williams', 'id': 'williams_venus', 'url': 'https://www.wtatennis.com/players/player/venus-williams/223999', 'source': 'wta_fallback', 'country': 'USA', 'rankings': '7 Grand Slams'},
            {'name': 'Steffi Graf', 'id': 'graf', 'url': 'https://www.wtatennis.com/players/player/steffi-graf/224001', 'source': 'wta_fallback', 'country': 'Germany', 'rankings': '22 Grand Slams'},
            {'name': 'Martina Navratilova', 'id': 'navratilova', 'url': 'https://www.wtatennis.com/players/player/martina-navratilova/224002', 'source': 'wta_fallback', 'country': 'USA', 'rankings': '18 Grand Slams'},
            {'name': 'Chris Evert', 'id': 'evert', 'url': 'https://www.wtatennis.com/players/player/chris-evert/224003', 'source': 'wta_fallback', 'country': 'USA', 'rankings': '18 Grand Slams'},
            {'name': 'Margaret Court', 'id': 'court', 'url': 'https://www.wtatennis.com/players/player/margaret-court/224004', 'source': 'wta_fallback', 'country': 'Australia', 'rankings': '24 Grand Slams'},
            {'name': 'Monica Seles', 'id': 'seles', 'url': 'https://www.wtatennis.com/players/player/monica-seles/224005', 'source': 'wta_fallback', 'country': 'USA', 'rankings': '9 Grand Slams'},
            {'name': 'Justine Henin', 'id': 'henin', 'url': 'https://www.wtatennis.com/players/player/justine-henin/224006', 'source': 'wta_fallback', 'country': 'Belgium', 'rankings': '7 Grand Slams'},
            {'name': 'Kim Clijsters', 'id': 'clijsters', 'url': 'https://www.wtatennis.com/players/player/kim-clijsters/224007', 'source': 'wta_fallback', 'country': 'Belgium', 'rankings': '4 Grand Slams'},
            {'name': 'Martina Hingis', 'id': 'hingis', 'url': 'https://www.wtatennis.com/players/player/martina-hingis/224008', 'source': 'wta_fallback', 'country': 'Switzerland', 'rankings': '5 Grand Slams'},
            {'name': 'Lindsay Davenport', 'id': 'davenport', 'url': 'https://www.wtatennis.com/players/player/lindsay-davenport/224009', 'source': 'wta_fallback', 'country': 'USA', 'rankings': '3 Grand Slams'},
            # Recent Champions
            {'name': 'Naomi Osaka', 'id': 'osaka', 'url': 'https://www.wtatennis.com/players/player/naomi-osaka/319770', 'source': 'wta_fallback', 'country': 'Japan', 'rankings': '4 Grand Slams'},
            {'name': 'Simona Halep', 'id': 'halep', 'url': 'https://www.wtatennis.com/players/player/simona-halep/314590', 'source': 'wta_fallback', 'country': 'Romania', 'rankings': '2 Grand Slams'},
            {'name': 'Ashleigh Barty', 'id': 'barty', 'url': 'https://www.wtatennis.com/players/player/ashleigh-barty/313880', 'source': 'wta_fallback', 'country': 'Australia', 'rankings': '3 Grand Slams'},
            {'name': 'Angelique Kerber', 'id': 'kerber', 'url': 'https://www.wtatennis.com/players/player/angelique-kerber/223975', 'source': 'wta_fallback', 'country': 'Germany', 'rankings': '3 Grand Slams'},
            {'name': 'Petra Kvitová', 'id': 'kvitova', 'url': 'https://www.wtatennis.com/players/player/petra-kvitova/224054', 'source': 'wta_fallback', 'country': 'Czech Republic', 'rankings': '2 Grand Slams'},
        ]


# ============================================================================
# Table Tennis Scraper
# ============================================================================

class TableTennisScraper(BaseScraper):
    """Scraper for Table Tennis Players (using fallback data)

    Table Tennis has strong Chinese and international presence.
    This scraper uses a curated list of notable table tennis players.
    """

    def scrape_players(self, limit: int = 500) -> List[Dict]:
        """Scrape table tennis players (uses fallback pool)

        Args:
            limit: Maximum number of players (ignored, uses fallback)

        Returns:
            List of notable table tennis players
        """
        logger.info("Using fallback table tennis players pool")
        return self.get_fallback_players()

    def get_fallback_players(self) -> List[Dict]:
        """Get fallback table tennis players

        Returns:
            List of known table tennis players
        """
        return [
            # Chinese Legends
            {'name': 'Ma Long', 'id': 'malong', 'url': 'https://www.ittf.com/players/long-ma', 'source': 'tabletennis_fallback', 'country': 'China', 'rankings': 'Former World #1'},
            {'name': 'Zhang Jike', 'id': 'zhangjike', 'url': 'https://www.ittf.com/players/jike-zhang', 'source': 'tabletennis_fallback', 'country': 'China', 'rankings': 'Grand Slam Winner'},
            {'name': 'Fan Zhendong', 'id': 'fanzhendong', 'url': 'https://www.ittf.com/players/zhendong-fan', 'source': 'tabletennis_fallback', 'country': 'China', 'rankings': 'World #1'},
            {'name': 'Wang Hao', 'id': 'wanghao', 'url': 'https://www.ittf.com/players/hao-wang', 'source': 'tabletennis_fallback', 'country': 'China', 'rankings': 'Former World #1'},
            {'name': 'Liu Guoliang', 'id': 'liuguoliang', 'url': 'https://www.ittf.com/players/guoliang-liu', 'source': 'tabletennis_fallback', 'country': 'China', 'rankings': 'Hall of Famer'},
            {'name': 'Deng Yaping', 'id': 'dengyaping', 'url': 'https://www.ittf.com/players/yaping-deng', 'source': 'tabletennis_fallback', 'country': 'China', 'rankings': '4-time Olympic Champion'},
            # International Stars
            {'name': 'Jan-Ove Waldner', 'id': 'waldner', 'url': 'https://www.ittf.com/players/jan-ove-waldner', 'source': 'tabletennis_fallback', 'country': 'Sweden', 'rankings': 'Mozart of Table Tennis'},
            {'name': 'Timo Boll', 'id': 'boll', 'url': 'https://www.ittf.com/players/timo-boll', 'source': 'tabletennis_fallback', 'country': 'Germany', 'rankings': 'European Legend'},
            {'name': 'Vladimir Samsonov', 'id': 'samsonov', 'url': 'https://www.ittf.com/players/vladimir-samsonov', 'source': 'tabletennis_fallback', 'country': 'Belarus', 'rankings': 'European Legend'},
            {'name': 'Jörgen Persson', 'id': 'persson', 'url': 'https://www.ittf.com/players/jorgen-persson', 'source': 'tabletennis_fallback', 'country': 'Sweden', 'rankings': 'European Legend'},
            # Japanese Stars
            {'name': 'Jun Mizutani', 'id': 'mizutani', 'url': 'https://www.ittf.com/players/jun-mizutani', 'source': 'tabletennis_fallback', 'country': 'Japan', 'rankings': 'Olympic Medalist'},
            {'name': 'Tomokazu Harimoto', 'id': 'harimoto', 'url': 'https://www.ittf.com/players/tomokazu-harimoto', 'source': 'tabletennis_fallback', 'country': 'Japan', 'rankings': 'Rising Star'},
            {'name': 'Mima Ito', 'id': 'ito', 'url': 'https://www.ittf.com/players/mima-ito', 'source': 'tabletennis_fallback', 'country': 'Japan', 'rankings': 'Women\'s Star'},
            # Korean Stars
            {'name': 'Lee Sang-su', 'id': 'leesangsu', 'url': 'https://www.ittf.com/players/sang-su-lee', 'source': 'tabletennis_fallback', 'country': 'South Korea', 'rankings': 'Olympic Medalist'},
            {'name': 'Joo Sae-hyuk', 'id': 'joosaehyuk', 'url': 'https://www.ittf.com/players/sae-hyuk-joo', 'source': 'tabletennis_fallback', 'country': 'South Korea', 'rankings': 'Defensive Master'},
            # Other Notables
            {'name': 'Ariel Hsing', 'id': 'hsing', 'url': 'https://www.ittf.com/players/ariel-hsing', 'source': 'tabletennis_fallback', 'country': 'USA', 'rankings': 'US Champion'},
            {'name': 'Lily Zhang', 'id': 'zhang', 'url': 'https://www.ittf.com/players/lily-zhang', 'source': 'tabletennis_fallback', 'country': 'USA', 'rankings': 'US Champion'},
        ]


# ============================================================================
# Badminton Scraper
# ============================================================================

class BadmintonScraper(BaseScraper):
    """Scraper for Badminton Players (using fallback data)

    Badminton has strong Asian and European presence.
    This scraper uses a curated list of notable badminton players.
    """

    def scrape_players(self, limit: int = 500) -> List[Dict]:
        """Scrape badminton players (uses fallback pool)

        Args:
            limit: Maximum number of players (ignored, uses fallback)

        Returns:
            List of notable badminton players
        """
        logger.info("Using fallback badminton players pool")
        return self.get_fallback_players()

    def get_fallback_players(self) -> List[Dict]:
        """Get fallback badminton players

        Returns:
            List of known badminton players
        """
        return [
            # Chinese Legends
            {'name': 'Lin Dan', 'id': 'lindan', 'url': 'https://www.bwfbadminton.com/player/67919/lin-dan', 'source': 'badminton_fallback', 'country': 'China', 'rankings': 'Super Dan - 2-time Olympic Champion'},
            {'name': 'Lee Chong Wei', 'id': 'leechongwei', 'url': 'https://www.bwfbadminton.com/player/61417/lee-chong-wei', 'source': 'badminton_fallback', 'country': 'Malaysia', 'rankings': '3-time Olympic Silver'},
            {'name': 'Chen Long', 'id': 'chenlong', 'url': 'https://www.bwfbadminton.com/player/74715/chen-long', 'source': 'badminton_fallback', 'country': 'China', 'rankings': 'Olympic Champion'},
            {'name': 'Viktor Axelsen', 'id': 'axelsen', 'url': 'https://www.bwfbadminton.com/player/72196/viktor-axelsen', 'source': 'badminton_fallback', 'country': 'Denmark', 'rankings': 'Olympic Champion'},
            {'name': 'Kento Momota', 'id': 'momota', 'url': 'https://www.bwfbadminton.com/player/76550/kento-momota', 'source': 'badminton_fallback', 'country': 'Japan', 'rankings': 'Former World #1'},
            {'name': 'Tai Tzu-ying', 'id': 'taitzuying', 'url': 'https://www.bwfbadminton.com/player/64577/tai-tzu-ying', 'source': 'badminton_fallback', 'country': 'Taiwan', 'rankings': 'Women\'s Legend'},
            {'name': 'Carolina Marín', 'id': 'marin', 'url': 'https://www.bwfbadminton.com/player/71192/carolina-marin', 'source': 'badminton_fallback', 'country': 'Spain', 'rankings': 'Olympic Champion'},
            # Men's Singles
            {'name': 'Shi Yuqi', 'id': 'shiyuqi', 'url': 'https://www.bwfbadminton.com/player/105674/shi-yu-qi', 'source': 'badminton_fallback', 'country': 'China', 'rankings': 'Top 10'},
            {'name': 'Anthony Ginting', 'id': 'ginting', 'url': 'https://www.bwfbadminton.com/player/99173/anthony-sinisuka-ginting', 'source': 'badminton_fallback', 'country': 'Indonesia', 'rankings': 'Top 10'},
            {'name': 'Anders Antonsen', 'id': 'antonsen', 'url': 'https://www.bwfbadminton.com/player/80272/anders-antonsen', 'source': 'badminton_fallback', 'country': 'Denmark', 'rankings': 'Top 10'},
            {'name': 'Lee Zii Jia', 'id': 'leeziiia', 'url': 'https://www.bwfbadminton.com/player/113932/lee-zii-jia', 'source': 'badminton_fallback', 'country': 'Malaysia', 'rankings': 'Top 10'},
            # Women's Singles
            {'name': 'Chen Yufei', 'id': 'chenyufei', 'url': 'https://www.bwfbadminton.com/player/107980/chen-yu-fei', 'source': 'badminton_fallback', 'country': 'China', 'rankings': 'World #1'},
            {'name': 'Akane Yamaguchi', 'id': 'yamaguchi', 'url': 'https://www.bwfbadminton.com/player/77979/akane-yamaguchi', 'source': 'badminton_fallback', 'country': 'Japan', 'rankings': 'Former World #1'},
            {'name': 'Ratchanok Intanon', 'id': 'intanon', 'url': 'https://www.bwfbadminton.com/player/68956/ratchanok-intanon', 'source': 'badminton_fallback', 'country': 'Thailand', 'rankings': 'World Champion'},
            {'name': 'Pusarla V. Sindhu', 'id': 'sindhu', 'url': 'https://www.bwfbadminton.com/player/70222/pusarla-v-sindhu', 'source': 'badminton_fallback', 'country': 'India', 'rankings': 'Olympic Medalist'},
            {'name': 'He Bingjiao', 'id': 'hebingjiao', 'url': 'https://www.bwfbadminton.com/player/107981/he-bing-jiao', 'source': 'badminton_fallback', 'country': 'China', 'rankings': 'Top 10'},
            # Doubles Specialists
            {'name': 'Mohammad Ahsan', 'id': 'ahsan', 'url': 'https://www.bwfbadminton.com/player/66044/mohammad-ahsan', 'source': 'badminton_fallback', 'country': 'Indonesia', 'rankings': 'World Champion (Doubles)'},
            {'name': 'Hendra Setiawan', 'id': 'setiawan', 'url': 'https://www.bwfbadminton.com/player/66043/hendra-setiawan', 'source': 'badminton_fallback', 'country': 'Indonesia', 'rankings': 'World Champion (Doubles)'},
            {'name': 'Marcus Ellis', 'id': 'ellis', 'url': 'https://www.bwfbadminton.com/player/63642/marcus-ellis', 'source': 'badminton_fallback', 'country': 'England', 'rankings': 'Olympic Champion (Doubles)'},
            {'name': 'Chris Adcock', 'id': 'adcock', 'url': 'https://www.bwfbadminton.com/player/63256/chris-adcock', 'source': 'badminton_fallback', 'country': 'England', 'rankings': 'European Champion'},
            # Mixed Doubles
            {'name': 'Zheng Siwei', 'id': 'zhengsiwei', 'url': 'https://www.bwfbadminton.com/player/107050/zheng-si-wei', 'source': 'badminton_fallback', 'country': 'China', 'rankings': 'World #1 (Mixed)'},
            {'name': 'Huang Yaqiong', 'id': 'huangyaqiong', 'url': 'https://www.bwfbadminton.com/player/92627/huang-ya-qiong', 'source': 'badminton_fallback', 'country': 'China', 'rankings': 'World #1 (Mixed)'},
        ]


# ============================================================================
# Utility Functions
# ============================================================================

def build_pool(sport: str, scraper_class: type, filename: str, game: str = None, rankings_type: str = None, leagues: list = None, limit: int = 3000):
    """Build a sports entity pool

    Args:
        sport: Sport name for logging
        scraper_class: Scraper class to use
        filename: Output filename
        game: Game identifier (for LiquipediaScraper)
        rankings_type: Rankings type (for ATPScraper: 'singles' or 'doubles')
        leagues: List of leagues (for TransfermarktScraper)
        limit: Maximum number of entities to scrape (for TransfermarktScraper)
    """
    logger.info(f"Building {sport} pool...")

    scraper = scraper_class()

    if scraper_class == LiquipediaScraper:
        game = game or 'lol'
        entities = scraper.scrape_players(game)
    elif scraper_class == UFCScraper:
        entities = scraper.scrape_fighters()
    elif scraper_class == BoxingSceneScraper:
        entities = scraper.scrape_boxers()
    elif scraper_class == NBAScraper:
        entities = scraper.scrape_players()
    elif scraper_class == ATPScraper:
        rankings_type = rankings_type or 'singles'
        entities = scraper.scrape_players(rankings_type)
    elif scraper_class == TransfermarktScraper:
        entities = scraper.scrape_players(leagues=leagues, limit=limit)
    elif scraper_class == NFLScraper:
        entities = scraper.scrape_players()
    elif scraper_class == MLBScraper:
        entities = scraper.scrape_players()
    elif scraper_class == NHLScraper:
        entities = scraper.scrape_players()
    elif scraper_class == F1Scraper:
        entities = scraper.scrape_drivers()
    elif scraper_class == CricketScraper:
        entities = scraper.scrape_players()
    elif scraper_class == RugbyScraper:
        entities = scraper.scrape_players()
    elif scraper_class == GolfScraper:
        entities = scraper.scrape_players()
    elif scraper_class == WTAScraper:
        entities = scraper.scrape_players()
    elif scraper_class == TableTennisScraper:
        entities = scraper.scrape_players()
    elif scraper_class == BadmintonScraper:
        entities = scraper.scrape_players()
    else:
        logger.error(f"Unknown scraper class: {scraper_class}")
        return

    if entities:
        scraper.save_pool(entities, filename)
        logger.info(f"✓ Successfully saved {len(entities)} entities")
    else:
        logger.error("✗ No entities scraped")


def load_and_use_pool(filename: str):
    """Load and demonstrate using a pool

    Args:
        filename: Pool filename
    """
    scraper = BaseScraper()
    entities = scraper.load_pool(filename)

    if entities:
        logger.info(f"Loaded {len(entities)} entities from pool")

        # Show 5 random examples
        for i in range(5):
            entity = random.choice(entities)
            logger.info(f"[{i+1}] {entity.get('name')} - {entity.get('url')}")
    else:
        logger.error(f"Could not load pool: {filename}")


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Build sports entity pools from official websites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Build League of Legends player pool
    python apis/sports_scrapers.py --sport lol --build

    # Build UFC fighter pool
    python apis/sports_scrapers.py --sport ufc --build

    # Build BoxingScene boxer pool (600-1000+ fighters)
    python apis/sports_scrapers.py --sport boxing --build

    # Build NBA player pool (500+ players)
    python apis/sports_scrapers.py --sport nba --build

    # Build ATP singles tennis player pool (100+ players)
    python apis/sports_scrapers.py --sport atp --build

    # Build football/soccer player pool from Transfermarkt (2000+ players)
    python apis/sports_scrapers.py --sport football --build

    # Build NFL player pool (American Football)
    python apis/sports_scrapers.py --sport nfl --build

    # Build MLB player pool (Baseball)
    python apis/sports_scrapers.py --sport mlb --build

    # Build NHL player pool (Ice Hockey)
    python apis/sports_scrapers.py --sport nhl --build

    # Build F1 driver pool
    python apis/sports_scrapers.py --sport f1 --build

    # Build Cricket player pool
    python apis/sports_scrapers.py --sport cricket --build

    # Build Rugby player pool
    python apis/sports_scrapers.py --sport rugby --build

    # Build Golf player pool
    python apis/sports_scrapers.py --sport golf --build

    # Build WTA (women's tennis) player pool
    python apis/sports_scrapers.py --sport wta --build

    # Build Table Tennis player pool
    python apis/sports_scrapers.py --sport tabletennis --build

    # Build Badminton player pool
    python apis/sports_scrapers.py --sport badminton --build

    # Test a pool
    python apis/sports_scrapers.py --sport lol --test
        """
    )

    parser.add_argument(
        '--sport',
        type=str,
        choices=['lol', 'dota2', 'csgo', 'ufc', 'boxing', 'nba', 'atp', 'football', 'nfl', 'mlb', 'nhl', 'f1', 'cricket', 'rugby', 'golf', 'wta', 'tabletennis', 'badminton'],
        help='Sport to scrape'
    )

    parser.add_argument(
        '--build',
        action='store_true',
        help='Build the pool for this sport'
    )

    parser.add_argument(
        '--test',
        action='store_true',
        help='Test loading a pool'
    )

    args = parser.parse_args()

    if not args.build and not args.test:
        parser.print_help()
        return

    if args.build:
        if args.sport == 'lol':
            build_pool('LoL (Liquipedia)', LiquipediaScraper, 'esports_lol_players.json', game='lol')
        elif args.sport == 'dota2':
            build_pool('Dota 2 (Liquipedia)', LiquipediaScraper, 'esports_dota2_players.json', game='dota2')
        elif args.sport == 'csgo':
            build_pool('CS:GO (Liquipedia)', LiquipediaScraper, 'esports_csgo_players.json', game='csgo')
        elif args.sport == 'ufc':
            build_pool('UFC (MMA)', UFCScraper, 'mma_ufc_fighters.json')
        elif args.sport == 'boxing':
            build_pool('BoxingScene (Boxing)', BoxingSceneScraper, 'boxing_boxrec_boxers.json')
        elif args.sport == 'nba':
            build_pool('NBA (Basketball)', NBAScraper, 'basketball_nba_players.json')
        elif args.sport == 'atp':
            build_pool('ATP Tour (Tennis)', ATPScraper, 'tennis_atp_players.json', rankings_type='singles')
        elif args.sport == 'football':
            # Scrape from all 5 major leagues for full coverage
            all_leagues = ['premier-league', 'laliga', 'serie-a', 'bundesliga', 'ligue-1']
            build_pool('Transfermarkt (Football)', TransfermarktScraper, 'football_transfermarkt_players.json', leagues=all_leagues, limit=5000)
        elif args.sport == 'nfl':
            build_pool('NFL (American Football)', NFLScraper, 'american_football_nfl_players.json')
        elif args.sport == 'mlb':
            build_pool('MLB (Baseball)', MLBScraper, 'baseball_mlb_players.json')
        elif args.sport == 'nhl':
            build_pool('NHL (Ice Hockey)', NHLScraper, 'ice_hockey_nhl_players.json')
        elif args.sport == 'f1':
            build_pool('Formula 1 (Racing)', F1Scraper, 'racing_f1_drivers.json')
        elif args.sport == 'cricket':
            build_pool('Cricket', CricketScraper, 'cricket_players.json')
        elif args.sport == 'rugby':
            build_pool('Rugby Union', RugbyScraper, 'rugby_players.json')
        elif args.sport == 'golf':
            build_pool('Golf (PGA)', GolfScraper, 'golf_players.json')
        elif args.sport == 'wta':
            build_pool('WTA Tour (Women\'s Tennis)', WTAScraper, 'tennis_wta_players.json')
        elif args.sport == 'tabletennis':
            build_pool('Table Tennis', TableTennisScraper, 'tabletennis_players.json')
        elif args.sport == 'badminton':
            build_pool('Badminton', BadmintonScraper, 'badminton_players.json')

    if args.test:
        if args.sport == 'lol':
            load_and_use_pool('esports_lol_players.json')
        elif args.sport == 'dota2':
            load_and_use_pool('esports_dota2_players.json')
        elif args.sport == 'csgo':
            load_and_use_pool('esports_csgo_players.json')
        elif args.sport == 'ufc':
            load_and_use_pool('mma_ufc_fighters.json')
        elif args.sport == 'boxing':
            load_and_use_pool('boxing_boxrec_boxers.json')
        elif args.sport == 'nba':
            load_and_use_pool('basketball_nba_players.json')
        elif args.sport == 'atp':
            load_and_use_pool('tennis_atp_players.json')
        elif args.sport == 'football':
            load_and_use_pool('football_transfermarkt_players.json')
        elif args.sport == 'nfl':
            load_and_use_pool('american_football_nfl_players.json')
        elif args.sport == 'mlb':
            load_and_use_pool('baseball_mlb_players.json')
        elif args.sport == 'nhl':
            load_and_use_pool('ice_hockey_nhl_players.json')
        elif args.sport == 'f1':
            load_and_use_pool('racing_f1_drivers.json')
        elif args.sport == 'cricket':
            load_and_use_pool('cricket_players.json')
        elif args.sport == 'rugby':
            load_and_use_pool('rugby_players.json')
        elif args.sport == 'golf':
            load_and_use_pool('golf_players.json')
        elif args.sport == 'wta':
            load_and_use_pool('tennis_wta_players.json')
        elif args.sport == 'tabletennis':
            load_and_use_pool('tabletennis_players.json')
        elif args.sport == 'badminton':
            load_and_use_pool('badminton_players.json')


if __name__ == "__main__":
    main()
