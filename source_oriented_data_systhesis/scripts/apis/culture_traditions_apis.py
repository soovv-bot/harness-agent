#!/usr/bin/env python3
"""
Culture and Traditions Data APIs Client

This module provides clients for various culture and traditions related APIs.

Supported APIs:
- UNESCO: World Heritage, Intangible Cultural Heritage
- Wikipedia: Culture, traditions, festivals categories
- Wikidata: Cultural entities, properties
- DBpedia: Structured culture data
- Holiday APIs: Global holidays and festivals
- Cuisine data: Traditional foods and cooking

Usage:
    from culture_traditions_apis import (
        UNESCOClient, WikipediaCultureClient, WikidataCultureClient,
        DBpediaCultureClient, HolidayAPIClient
    )
"""

import requests
import json
import random
from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger


# ============================================================================
# Base Client
# ============================================================================

class BaseClient:
    """Base class for culture API clients"""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; CultureDataPipeline/1.0)'
        })

    def _get(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Optional[Dict]:
        """Make GET request and return JSON response"""
        try:
            req_headers = self.session.headers.copy()
            if headers:
                req_headers.update(headers)

            response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()

            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                return response.json()
            else:
                return {'content': response.text, 'status_code': response.status_code}

        except Exception as e:
            logger.error(f"{self.__class__.__name__} error: {e}")
            return None


# ============================================================================
# UNESCO Client
# ============================================================================

class UNESCOClient(BaseClient):
    """
    UNESCO Client - World Heritage and Intangible Cultural Heritage

    UNESCO provides APIs for:
    - World Heritage Sites (cultural and natural)
    - Intangible Cultural Heritage
    - Memory of the World Register
    - Creative Cities Network

    Base URL: https://whc.unesco.org/en/

    Note: UNESCO doesn't have a public API, so we use their data feeds and Wikidata.
    """

    def __init__(self):
        super().__init__()
        # Use Wikidata for UNESCO data
        self.wikidata_sparql = "https://query.wikidata.org/sparql"

    def get_world_heritage_sites(self, limit: int = 50) -> List[Dict]:
        """
        Get UNESCO World Heritage Sites from Wikidata

        Returns list of cultural and natural heritage sites
        """
        try:
            sparql = """
            SELECT DISTINCT ?site ?siteLabel ?siteDescription ?countryLabel ?heritageTypeLabel WHERE {
              ?site wdt:P31 wd:Q9259 .  # World Heritage Site
              ?site wdt:P17 ?country .
              ?site wdt:P1435 ?heritageType .  # heritage designation

              SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
            }
            LIMIT 100
            """

            params = {
                "query": sparql,
                "format": "json"
            }

            response = self.session.get(self.wikidata_sparql, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            results = []
            bindings = data.get('results', {}).get('bindings', [])

            for binding in bindings[:limit]:
                results.append({
                    'id': binding.get('site', {}).get('value', '').split('/')[-1],
                    'name': binding.get('siteLabel', {}).get('value', ''),
                    'description': binding.get('siteDescription', {}).get('value', ''),
                    'country': binding.get('countryLabel', {}).get('value', ''),
                    'heritage_type': binding.get('heritageTypeLabel', {}).get('value', '')
                })

            return results

        except Exception as e:
            logger.error(f"UNESCO sites error: {e}")
            return []

    def get_intangible_heritage(self, limit: int = 50) -> List[Dict]:
        """
        Get UNESCO Intangible Cultural Heritage elements

        Returns list of traditions, performing arts, social practices, etc.
        """
        try:
            sparql = """
            SELECT DISTINCT ?item ?itemLabel ?countryLabel ?categoryLabel WHERE {
              ?item wdt:P31 wd:Q16617471 .  # Intangible Cultural Heritage element
              OPTIONAL { ?item wdt:P17 ?country . }
              OPTIONAL { ?item wdt:P361 ?category . }

              SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
            }
            LIMIT 100
            """

            params = {
                "query": sparql,
                "format": "json"
            }

            response = self.session.get(self.wikidata_sparql, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            results = []
            bindings = data.get('results', {}).get('bindings', [])

            for binding in bindings[:limit]:
                results.append({
                    'id': binding.get('item', {}).get('value', '').split('/')[-1],
                    'name': binding.get('itemLabel', {}).get('value', ''),
                    'country': binding.get('countryLabel', {}).get('value', ''),
                    'category': binding.get('categoryLabel', {}).get('value', '')
                })

            return results

        except Exception as e:
            logger.error(f"UNESCO intangible error: {e}")
            return []

    def get_random_heritage_site(self) -> Optional[Dict]:
        """Get random UNESCO World Heritage Site"""
        sites = self.get_world_heritage_sites(limit=100)
        if sites:
            return random.choice(sites)
        return None

    def get_random_intangible_heritage(self) -> Optional[Dict]:
        """Get random Intangible Cultural Heritage element"""
        items = self.get_intangible_heritage(limit=100)
        if items:
            return random.choice(items)
        return None


# ============================================================================
# Wikipedia Culture Client
# ============================================================================

class WikipediaCultureClient(BaseClient):
    """
    Wikipedia Culture Client - Culture, traditions, festivals

    Accesses Wikipedia's culture-related categories.
    """

    CULTURE_CATEGORIES = [
        "Category:Traditions",
        "Category:Festivals",
        "Category:Cultural heritage",
        "Category:Folklore",
        "Category:Customs",
        "Category:Rituals",
        "Category:Traditional culture",
        "Category:Cuisine",
        "Category:Traditional clothing",
        "Category:Traditional music",
        "Category:Folk art",
        "Category:Handicrafts",
        "Category:Mythology",
        "Category:Religious festivals",
        "Category:National festivals",
        "Category:Cultural landscapes",
        "Category:Ethnocultural traditions"
    ]

    def __init__(self):
        super().__init__()

    def get_random_culture_category(self) -> str:
        """Get random culture category"""
        return random.choice(self.CULTURE_CATEGORIES)

    def get_category_members(self, category: str, limit: int = 500) -> List[Dict]:
        """Get members of a culture category"""
        api_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmlimit": limit,
            "cmtype": "page",
            "format": "json"
        }

        try:
            response = self.session.get(api_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data.get("query", {}).get("categorymembers", [])
        except Exception as e:
            logger.error(f"Wikipedia culture category error: {e}")
            return []

    def get_random_from_category(self, category: Optional[str] = None) -> Optional[Dict]:
        """Get random page from a culture category"""
        if not category:
            category = self.get_random_culture_category()

        members = self.get_category_members(category)
        if members:
            pages = [m for m in members if m.get("ns") == 0]
            if pages:
                return random.choice(pages)
        return None


# ============================================================================
# Wikidata Culture Client
# ============================================================================

class WikidataCultureClient(BaseClient):
    """
    Wikidata Culture Client - SPARQL queries for cultural entities

    Queries Wikidata for cultural entities, traditions, festivals, etc.
    """

    SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

    def __init__(self):
        super().__init__()
        self.session.headers.update({
            'Accept': 'application/sparql-results+json'
        })

    def query_sparql(self, sparql: str) -> List[Dict]:
        """Execute SPARQL query"""
        params = {
            "query": sparql,
            "format": "json"
        }

        try:
            response = self.session.get(self.SPARQL_ENDPOINT, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            if data and 'results' in data:
                return data['results'].get('bindings', [])
        except Exception as e:
            logger.error(f"Wikidata SPARQL error: {e}")

        return []

    def get_traditional_festivals(self) -> List[Dict]:
        """Get traditional festivals from Wikidata"""
        sparql = """
        SELECT DISTINCT ?festival ?festivalLabel ?countryLabel ?typeLabel WHERE {
          ?festival wdt:P31/wdt:P279* wd:Q845939 .  # festival
          ?festival wdt:P495 ?country .
          OPTIONAL { ?festival wdt:P31 ?type . }

          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 100
        """

        results = self.query_sparql(sparql)
        festivals = []
        for r in results:
            festivals.append({
                'id': r.get('festival', {}).get('value', '').split('/')[-1],
                'name': r.get('festivalLabel', {}).get('value', ''),
                'country': r.get('countryLabel', {}).get('value', ''),
                'type': r.get('typeLabel', {}).get('value', '')
            })
        return festivals

    def get_traditional_clothing(self) -> List[Dict]:
        """Get traditional clothing from Wikidata"""
        sparql = """
        SELECT DISTINCT ?clothing ?clothingLabel ?originLabel ?typeLabel WHERE {
          ?clothing wdt:P31/wdt:P279* wd:Q1143600 .  # clothing
          ?clothing wdt:P361 ?origin .
          OPTIONAL { ?clothing wdt:P31 ?type . }

          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 50
        """

        results = self.query_sparql(sparql)
        clothing_items = []
        for r in results:
            clothing_items.append({
                'name': r.get('clothingLabel', {}).get('value', ''),
                'origin': r.get('originLabel', {}).get('value', ''),
                'type': r.get('typeLabel', {}).get('value', '')
            })
        return clothing_items

    def get_traditional_foods(self) -> List[Dict]:
        """Get traditional foods and dishes from Wikidata"""
        sparql = """
        SELECT DISTINCT ?dish ?dishLabel ?originLabel ?courseLabel WHERE {
          ?dish wdt:P31/wdt:P279* wd:Q746594 .  # dish
          ?dish wdt:P361 ?origin .
          OPTIONAL { ?dish wdt:P361 ?course . }

          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 100
        """

        results = self.query_sparql(sparql)
        dishes = []
        for r in results:
            dishes.append({
                'name': r.get('dishLabel', {}).get('value', ''),
                'origin': r.get('originLabel', {}).get('value', ''),
                'course': r.get('courseLabel', {}).get('value', '')
            })
        return dishes

    def get_traditional_music(self) -> List[Dict]:
        """Get traditional music genres from Wikidata"""
        sparql = """
        SELECT DISTINCT ?music ?musicLabel ?originLabel WHERE {
          ?music wdt:P31/wdt:P279* wd:Q2188189 .  # folk music
          ?music wdt:P361 ?origin .

          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 50
        """

        results = self.query_sparql(sparql)
        music_items = []
        for r in results:
            music_items.append({
                'name': r.get('musicLabel', {}).get('value', ''),
                'origin': r.get('originLabel', {}).get('value', '')
            })
        return music_items

    def get_cultural_practices(self) -> List[Dict]:
        """Get cultural practices and customs from Wikidata"""
        sparql = """
        SELECT DISTINCT ?practice ?practiceLabel ?originLabel WHERE {
          ?practice wdt:P31/wdt:P279* wd:Q852535 .  # cultural practice
          ?practice wdt:P361 ?origin .

          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 50
        """

        results = self.query_sparql(sparql)
        practices = []
        for r in results:
            practices.append({
                'name': r.get('practiceLabel', {}).get('value', ''),
                'origin': r.get('originLabel', {}).get('value', '')
            })
        return practices

    def get_folk_art(self) -> List[Dict]:
        """Get folk art forms from Wikidata"""
        sparql = """
        SELECT DISTINCT ?art ?artLabel ?originLabel ?typeLabel WHERE {
          ?art wdt:P31/wdt:P279* wd:Q161418 .  # folk art
          ?art wdt:P361 ?origin .
          OPTIONAL { ?art wdt:P31 ?type . }

          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 50
        """

        results = self.query_sparql(sparql)
        art_items = []
        for r in results:
            art_items.append({
                'name': r.get('artLabel', {}).get('value', ''),
                'origin': r.get('originLabel', {}).get('value', ''),
                'type': r.get('typeLabel', {}).get('value', '')
            })
        return art_items

    def get_mythology(self) -> List[Dict]:
        """Get mythology and mythological creatures from Wikidata"""
        sparql = """
        SELECT DISTINCT ?myth ?mythLabel ?cultureLabel WHERE {
          ?myth wdt:P31/wdt:P279* wd:Q8589 .  # mythology
          ?myth wdt:P361 ?culture .

          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 50
        """

        results = self.query_sparql(sparql)
        myths = []
        for r in results:
            myths.append({
                'name': r.get('mythLabel', {}).get('value', ''),
                'culture': r.get('cultureLabel', {}).get('value', '')
            })
        return myths


# ============================================================================
# DBpedia Culture Client
# ============================================================================

class DBpediaCultureClient(BaseClient):
    """
    DBpedia Culture Client - Structured culture data

    DBpedia provides structured data extracted from Wikipedia.
    """

    BASE_URL = "https://dbpedia.org/sparql"

    def __init__(self):
        super().__init__()
        self.session.headers.update({
            'Accept': 'application/sparql-results+json'
        })

    def query_sparql(self, sparql: str) -> List[Dict]:
        """Execute SPARQL query"""
        params = {
            "query": sparql,
            "format": "json"
        }

        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            if data and 'results' in data:
                return data['results'].get('bindings', [])
        except Exception as e:
            logger.error(f"DBpedia SPARQL error: {e}")

        return []

    def get_festivals(self) -> List[Dict]:
        """Get festivals from DBpedia"""
        sparql = """
        SELECT DISTINCT ?festival ?name ?abstract WHERE {
          ?festival a dbo:Festival .
          ?festival rdfs:label ?name .
          OPTIONAL { ?festival dbo:abstract ?abstract . }

          FILTER(lang(?name) = "en")
        }
        LIMIT 100
        """

        results = self.query_sparql(sparql)
        festivals = []
        for r in results:
            festivals.append({
                'uri': r.get('festival', {}).get('value', ''),
                'name': r.get('name', {}).get('value', ''),
                'abstract': r.get('abstract', {}).get('value', '')
            })
        return festivals

    def get_traditions(self) -> List[Dict]:
        """Get traditions from DBpedia"""
        sparql = """
        SELECT DISTINCT ?tradition ?name ?abstract WHERE {
          ?tradition a dbo:Tradition .
          ?tradition rdfs:label ?name .
          OPTIONAL { ?tradition dbo:abstract ?abstract . }

          FILTER(lang(?name) = "en")
        }
        LIMIT 50
        """

        results = self.query_sparql(sparql)
        traditions = []
        for r in results:
            traditions.append({
                'uri': r.get('tradition', {}).get('value', ''),
                'name': r.get('name', {}).get('value', ''),
                'abstract': r.get('abstract', {}).get('value', '')
            })
        return traditions


# ============================================================================
# Holiday API Client
# ============================================================================

class HolidayAPIClient(BaseClient):
    """
    Holiday API Client - Global holidays and festivals

    Uses various free holiday APIs and datasets.
    """

    def __init__(self):
        super().__init__()
        # Use a free holiday API or data source
        self.holiday_api_base = "https://date.nager.at/api/v3"

    def get_public_holidays(self, year: int, country_code: str) -> List[Dict]:
        """
        Get public holidays for a country and year

        Args:
            year: Year (e.g., 2024)
            country_code: ISO 3166-1 alpha-2 code (e.g., "US", "CN", "JP")
        """
        try:
            url = f"{self.holiday_api_base}/PublicHolidays/{year}/{country_code}"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            holidays = response.json()

            # Format the response
            results = []
            for holiday in holidays:
                results.append({
                    'date': holiday.get('date'),
                    'local_name': holiday.get('localName'),
                    'name': holiday.get('name'),
                    'country_code': country_code,
                    'global': holiday.get('global', False),
                    'type': holiday.get('type', [])
                })

            return results

        except Exception as e:
            logger.error(f"Holiday API error: {e}")
            return []

    def get_random_holiday(self, year: Optional[int] = None) -> Optional[Dict]:
        """
        Get random public holiday from various countries

        Args:
            year: Year (defaults to current year)
        """
        if year is None:
            year = datetime.now().year

        # Major countries for diversity
        countries = ['US', 'CN', 'JP', 'IN', 'BR', 'GB', 'FR', 'DE', 'RU', 'MX', 'CA', 'AU']

        all_holidays = []
        for country in countries:
            holidays = self.get_public_holidays(year, country)
            all_holidays.extend(holidays)

        if all_holidays:
            return random.choice(all_holidays)

        return None

    def get_long_weekends(self, year: int, country_code: str) -> List[Dict]:
        """
        Get long weekends for a country and year

        Args:
            year: Year (e.g., 2024)
            country_code: ISO 3166-1 alpha-2 code
        """
        try:
            url = f"{self.holiday_api_base}/LongWeekend/{year}/{country_code}"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.error(f"Long weekend API error: {e}")
            return []


# ============================================================================
# Usage Example
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("CULTURE & TRADITIONS APIS - TESTING")
    print("=" * 70)

    # Test UNESCO
    print("\n1. Testing UNESCO Client...")
    unesco = UNESCOClient()

    heritage_site = unesco.get_random_heritage_site()
    if heritage_site:
        print(f"  Heritage Site: {heritage_site.get('name')} ({heritage_site.get('country')})")

    intangible = unesco.get_random_intangible_heritage()
    if intangible:
        print(f"  Intangible Heritage: {intangible.get('name')} ({intangible.get('country')})")

    # Test Wikidata Culture
    print("\n2. Testing Wikidata Culture...")
    wikidata = WikidataCultureClient()

    festivals = wikidata.get_traditional_festivals()
    print(f"  Found {len(festivals)} traditional festivals")
    if festivals:
        print(f"  Sample: {festivals[0].get('name')} ({festivals[0].get('country')})")

    foods = wikidata.get_traditional_foods()
    print(f"  Found {len(foods)} traditional foods")
    if foods:
        print(f"  Sample: {foods[0].get('name')} ({foods[0].get('origin')})")

    # Test Holiday API
    print("\n3. Testing Holiday API...")
    holiday_api = HolidayAPIClient()

    holiday = holiday_api.get_random_holiday()
    if holiday:
        print(f"  Random Holiday: {holiday.get('name')} ({holiday.get('local_name')}) - {holiday.get('date')}")

    print("\n" + "=" * 70)
    print("API TESTS COMPLETED")
    print("=" * 70)
