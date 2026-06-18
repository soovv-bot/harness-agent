#!/usr/bin/env python3
"""
Biography and People Data APIs Client

This module provides clients for various biography and people-related APIs.

Supported APIs:
- Wikipedia: Biographies and people categories
- Wikidata: People entities with occupations, awards, relationships
- DBpedia: Biographical data SPARQL queries
- Britannica: Biographical encyclopedia (requires API key)
- Biography.com: Famous people biographies
- Nobel Prize API: Nobel laureates information
- Library of Congress: Authorities data
- VIAF (Virtual International Authority File): Author identities

Usage:
    from biography_apis import (
        WikipediaBioClient, WikidataPeopleClient, DBpediaPeopleClient,
        NobelPrizeClient, BritannicaClient, BiographyDotComClient
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
    """Base class for biography API clients"""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; BiographyDataPipeline/1.0)'
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

        except requests.exceptions.HTTPError as e:
            logger.warning(f"{self.__class__.__name__} HTTP error: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"{self.__class__.__name__} error: {e}")
            return None


# ============================================================================
# Wikipedia Biography Client
# ============================================================================

class WikipediaBioClient(BaseClient):
    """
    Wikipedia Biography Client

    Accesses Wikipedia's biography and people-related categories.
    """

    BASE_URL = "https://en.wikipedia.org/w/api.php"

    def __init__(self):
        super().__init__()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def get_category_members(self, category: str, limit: int = 500) -> List[Dict]:
        """Get members of a Wikipedia category"""
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmlimit": limit,
            "cmtype": "page",
            "format": "json"
        }

        result = self._get(self.BASE_URL, params=params)
        if result:
            return result.get('query', {}).get('categorymembers', [])
        return []

    def get_random_from_category(self, category: str) -> Optional[Dict]:
        """Get random page from a category"""
        members = self.get_category_members(category)
        if members:
            # Filter out subcategories
            pages = [m for m in members if m.get('ns') == 0]
            if pages:
                return random.choice(pages)
        return None

    def get_page_summary(self, title: str) -> Optional[Dict]:
        """Get page summary using the REST API"""
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}"

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Wikipedia summary error for {title}: {e}")
            return None

    def search_people(self, search_term: str, limit: int = 10) -> List[Dict]:
        """Search for people on Wikipedia"""
        params = {
            "action": "query",
            "list": "search",
            "srsearch": search_term,
            "srlimit": limit,
            "srnamespace": 0,
            "format": "json"
        }

        result = self._get(self.BASE_URL, params=params)
        if result:
            return result.get('query', {}).get('search', [])
        return []


# ============================================================================
# Wikidata People Client
# ============================================================================

class WikidataPeopleClient(BaseClient):
    """
    Wikidata People Client - SPARQL queries for biographical data

    Queries Wikidata for people by occupation, nationality, era, etc.
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

        result = self._get(self.SPARQL_ENDPOINT, params=params)
        if result and 'results' in result:
            return result['results'].get('bindings', [])
        return []

    def get_people_by_occupation(self, occupation_id: str, limit: int = 50) -> List[Dict]:
        """Get people by occupation using Wikidata occupation ID"""
        sparql = f"""
        SELECT DISTINCT ?person ?personLabel ?personDescription ?countryLabel WHERE {{
          ?person wdt:P106 wd:{occupation_id}.
          ?person wdt:P31 wd:Q5.
          OPTIONAL {{ ?person wdt:P27 ?country. }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT {limit}
        """

        results = self.query_sparql(sparql)
        people = []
        for r in results:
            people.append({
                "id": r.get('person', {}).get('value', '').split('/')[-1],
                "name": r.get('personLabel', {}).get('value', ''),
                "description": r.get('personDescription', {}).get('value', ''),
                "country": r.get('countryLabel', {}).get('value', '')
            })
        return people

    def get_politicians(self, limit: int = 50) -> List[Dict]:
        """Get politicians"""
        return self.get_people_by_occupation("Q82955", limit)  # politician

    def get_scientists(self, limit: int = 50) -> List[Dict]:
        """Get scientists"""
        return self.get_people_by_occupation("Q901", limit)  # scientist

    def get_artists(self, limit: int = 50) -> List[Dict]:
        """Get artists"""
        return self.get_people_by_occupation("Q3391743", limit)  # artist

    def get_writers(self, limit: int = 50) -> List[Dict]:
        """Get writers"""
        return self.get_people_by_occupation("Q36180", limit)  # writer

    def get_musicians(self, limit: int = 50) -> List[Dict]:
        """Get musicians"""
        return self.get_people_by_occupation("Q639669", limit)  # musician

    def get_actors(self, limit: int = 50) -> List[Dict]:
        """Get actors"""
        return self.get_people_by_occupation("Q33999", limit)  # actor

    def get_athletes(self, limit: int = 50) -> List[Dict]:
        """Get athletes"""
        return self.get_people_by_occupation("Q2066131", limit)  # athlete

    def get_business_people(self, limit: int = 50) -> List[Dict]:
        """Get business people"""
        sparql = f"""
        SELECT DISTINCT ?person ?personLabel ?positionLabel ?companyLabel WHERE {{
          ?person wdt:P31 wd:Q5.
          ?person wdt:P39 ?position.
          ?position wdt:P279* wd:Q3053182.
          OPTIONAL {{ ?person wdt:P706 ?company. }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT {limit}
        """

        results = self.query_sparql(sparql)
        people = []
        for r in results:
            people.append({
                "name": r.get('personLabel', {}).get('value', ''),
                "position": r.get('positionLabel', {}).get('value', ''),
                "company": r.get('companyLabel', {}).get('value', '')
            })
        return people

    def get_nobel_laureates(self, limit: int = 50) -> List[Dict]:
        """Get Nobel Prize laureates"""
        sparql = f"""
        SELECT DISTINCT ?person ?personLabel ?prizeLabel ?year WHERE {{
          ?person wdt:P166 ?award.
          ?award wdt:P361 wd:Q7191.
          ?person wdt:P31 wd:Q5.
          ?award wdt:P31 wd:Q618779.  # instance of Nobel Prize
          OPTIONAL {{ ?award wdt:P585 ?inception. }}
          OPTIONAL {{ ?award wdt:P585|wdt:P580 ?date. }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT {limit}
        """

        results = self.query_sparql(sparql)
        people = []
        for r in results:
            people.append({
                "name": r.get('personLabel', {}).get('value', ''),
                "prize": r.get('prizeLabel', {}).get('value', '')
            })
        return people

    def get_people_by_country(self, country_id: str, limit: int = 50) -> List[Dict]:
        """Get people by nationality"""
        sparql = f"""
        SELECT DISTINCT ?person ?personLabel ?occupationLabel WHERE {{
          ?person wdt:P27 wd:{country_id}.
          ?person wdt:P31 wd:Q5.
          ?person wdt:P106 ?occupation.
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT {limit}
        """

        results = self.query_sparql(sparql)
        people = []
        for r in results:
            people.append({
                "name": r.get('personLabel', {}).get('value', ''),
                "occupation": r.get('occupationLabel', {}).get('value', '')
            })
        return people

    def get_contemporary_figures(self, limit: int = 50) -> List[Dict]:
        """Get contemporary figures (people born after 1950)"""
        sparql = f"""
        SELECT DISTINCT ?person ?personLabel ?occupationLabel ?birthDate WHERE {{
          ?person wdt:P31 wd:Q5.
          ?person wdt:P569 ?birthDate.
          ?person wdt:P106 ?occupation.
          FILTER(?birthDate > "1950-01-01"^^xsd:date)
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT {limit}
        """

        results = self.query_sparql(sparql)
        people = []
        for r in results:
            people.append({
                "name": r.get('personLabel', {}).get('value', ''),
                "occupation": r.get('occupationLabel', {}).get('value', ''),
                "birthDate": r.get('birthDate', {}).get('value', '')
            })
        return people

    def get_historical_figures(self, limit: int = 50) -> List[Dict]:
        """Get historical figures (people born before 1900)"""
        sparql = f"""
        SELECT DISTINCT ?person ?personLabel ?occupationLabel ?birthDate ?deathDate WHERE {{
          ?person wdt:P31 wd:Q5.
          ?person wdt:P569 ?birthDate.
          ?person wdt:P106 ?occupation.
          FILTER(?birthDate < "1900-01-01"^^xsd:date)
          OPTIONAL {{ ?person wdt:P570 ?deathDate. }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT {limit}
        """

        results = self.query_sparql(sparql)
        people = []
        for r in results:
            people.append({
                "name": r.get('personLabel', {}).get('value', ''),
                "occupation": r.get('occupationLabel', {}).get('value', ''),
                "birthDate": r.get('birthDate', {}).get('value', ''),
                "deathDate": r.get('deathDate', {}).get('value', '')
            })
        return people

    def get_women_figures(self, limit: int = 50) -> List[Dict]:
        """Get notable women"""
        sparql = f"""
        SELECT DISTINCT ?person ?personLabel ?occupationLabel WHERE {{
          ?person wdt:P31 wd:Q5.
          ?person wdt:P21 wd:Q6581072.
          ?person wdt:P106 ?occupation.
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT {limit}
        """

        results = self.query_sparql(sparql)
        people = []
        for r in results:
            people.append({
                "name": r.get('personLabel', {}).get('value', ''),
                "occupation": r.get('occupationLabel', {}).get('value', '')
            })
        return people


# ============================================================================
# DBpedia People Client
# ============================================================================

class DBpediaPeopleClient(BaseClient):
    """
    DBpedia People Client - SPARQL queries for biographical data

    Queries DBpedia for people, biographies, and relationships.
    """

    SPARQL_ENDPOINT = "http://dbpedia.org/sparql"

    def __init__(self):
        super().__init__()
        self.session.headers.update({
            'Accept': 'application/sparql-results+json'
        })

    def query_sparql(self, sparql: str) -> Dict:
        """Execute SPARQL query"""
        params = {
            "query": sparql,
            "format": "json"
        }

        result = self._get(self.SPARQL_ENDPOINT, params=params)
        if result:
            return result
        return {'results': {'bindings': []}}

    def get_random_person(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get random people from DBpedia"""
        sparql = f"""
        SELECT DISTINCT ?person ?name ?birthDate ?abstract WHERE {{
          ?person a dbo:Person .
          ?person foaf:name ?name .
          ?person dbo:birthDate ?birthDate .
          OPTIONAL {{ ?person dbo:abstract ?abstract .
            FILTER(LANG(?abstract) = "en")
          }}
          FILTER(?birthDate > "1800-01-01"^^xsd:date)
        }}
        LIMIT {limit}
        OFFSET {offset}
        """

        result = self.query_sparql(sparql)
        bindings = result.get('results', {}).get('bindings', [])

        people = []
        for b in bindings:
            people.append({
                "name": b.get('name', {}).get('value', ''),
                "birthDate": b.get('birthDate', {}).get('value', ''),
                "abstract": b.get('abstract', {}).get('value', '')[:300]
            })
        return people

    def get_people_by_profession(self, profession: str, limit: int = 50) -> List[Dict]:
        """Get people by profession"""
        sparql = f"""
        SELECT DISTINCT ?person ?name ?birthDate WHERE {{
          ?person a dbo:Person .
          ?person foaf:name ?name .
          ?person dbo:profession ?profession .
          FILTER(?profession = "{profession}"@en)
        }}
        LIMIT {limit}
        """

        result = self.query_sparql(sparql)
        bindings = result.get('results', {}).get('bindings', [])

        people = []
        for b in bindings:
            people.append({
                "name": b.get('name', {}).get('value', ''),
                "birthDate": b.get('birthDate', {}).get('value', '')
            })
        return people


# ============================================================================
# Nobel Prize API Client
# ============================================================================

class NobelPrizeClient(BaseClient):
    """
    Nobel Prize API Client - https://www.nobelprize.org/about/developer-info-zone/

    Access to Nobel Prize laureates data.
    """

    BASE_URL = "https://api.nobelprize.org/2.1"

    def __init__(self):
        super().__init__()

    def get_laureates(self, limit: int = 50) -> List[Dict]:
        """Get Nobel Prize laureates"""
        url = f"{self.BASE_URL}/nobelPrizes"
        params = {"nobelPrizeYear": "1901-2024", "format": "json"}

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            laureates = []
            if 'nobelPrizes' in data:
                for prize in data['nobelPrizes'][:limit]:
                    for laureate in prize.get('laureates', []):
                        full_name = laureate.get('knownName', {}).get('en', '')
                        if not full_name:
                            org_name = laureate.get('orgName', {}).get('en', '')
                            full_name = org_name

                        laureates.append({
                            "name": full_name,
                            "category": prize.get('category', {}).get('en', ''),
                            "year": prize.get('awardYear', ''),
                            "motivation": laureate.get('motivation', {}).get('en', '')
                        })

            return laureates

        except Exception as e:
            logger.error(f"Nobel Prize API error: {e}")
            return []

    def get_laureates_by_category(self, category: str = 'phy') -> List[Dict]:
        """Get laureates by category"""
        url = f"{self.BASE_URL}/nobelPrizes"
        params = {
            "nobelPrizeCategory": category,
            "format": "json"
        }

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            laureates = []
            if 'nobelPrizes' in data:
                for prize in data['nobelPrizes']:
                    for laureate in prize.get('laureates', []):
                        full_name = laureate.get('knownName', {}).get('en', '')
                        if not full_name:
                            full_name = laureate.get('orgName', {}).get('en', '')

                        laureates.append({
                            "name": full_name,
                            "category": prize.get('category', {}).get('en', ''),
                            "year": prize.get('awardYear', '')
                        })

            return laureates

        except Exception as e:
            logger.error(f"Nobel Prize API error: {e}")
            return []

    def get_random_laureate(self) -> Optional[Dict]:
        """Get random Nobel laureate"""
        laureates = self.get_laureates(limit=200)
        if laureates:
            return random.choice(laureates)
        return None


# ============================================================================
# Biography.com Client
# ============================================================================

class BiographyDotComClient(BaseClient):
    """
    Biography.com Client - https://www.biography.com/

    Famous people biographies and life stories.
    """

    BASE_URL = "https://www.biography.com"

    def get_categories(self) -> List[str]:
        """Get available categories"""
        return [
            "political-leaders",
            "artists",
            "athletes",
            "scientists",
            "musicians",
            "actors",
            "entrepreneurs",
            "activists",
            "writers",
            "infamous"
        ]

    def search_person(self, name: str) -> Optional[Dict]:
        """Search for a person"""
        url = f"{self.BASE_URL}/search/"
        params = {"q": name}

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return {'url': response.url}
        except Exception as e:
            logger.error(f"Biography.com search error: {e}")
            return None

    def get_random_person(self) -> Dict:
        """Get random famous person concept"""
        categories = self.get_categories()
        category = random.choice(categories)

        # Famous people by category
        people_by_category = {
            "political-leaders": ["Barack Obama", "Winston Churchill", "Nelson Mandela", "Abraham Lincoln"],
            "artists": ["Pablo Picasso", "Vincent van Gogh", "Frida Kahlo", "Andy Warhol"],
            "athletes": ["Michael Jordan", "Serena Williams", "Muhammad Ali", "Usain Bolt"],
            "scientists": ["Albert Einstein", "Marie Curie", "Charles Darwin", "Stephen Hawking"],
            "musicians": ["Bob Dylan", "Aretha Franklin", "Freddie Mercury", "Taylor Swift"],
            "actors": ["Marilyn Monroe", "Tom Hanks", "Meryl Streep", "Denzel Washington"],
            "entrepreneurs": ["Steve Jobs", "Oprah Winfrey", "Elon Musk", "Walt Disney"],
            "activists": ["Martin Luther King Jr.", "Rosa Parks", "Gandhi", "Malala Yousafzai"],
            "writers": ["William Shakespeare", "Maya Angelou", "Ernest Hemingway", "Virginia Woolf"],
            "infamous": ["Al Capone", "Jesse James", "Bonnie & Clyde"]
        }

        people = people_by_category.get(category, people_by_category["political-leaders"])
        person = random.choice(people)

        return {
            "name": person,
            "category": category,
            "source": "biography_dot_com"
        }


# ============================================================================
# Convenience Functions
# ============================================================================

def get_wikipedia_bio_client() -> WikipediaBioClient:
    return WikipediaBioClient()


def get_wikidata_people_client() -> WikidataPeopleClient:
    return WikidataPeopleClient()


def get_dbpedia_people_client() -> DBpediaPeopleClient:
    return DBpediaPeopleClient()


def get_nobel_prize_client() -> NobelPrizeClient:
    return NobelPrizeClient()


def get_biography_dot_com_client() -> BiographyDotComClient:
    return BiographyDotComClient()


if __name__ == "__main__":
    # Test clients
    logger.info("Testing Biography API Clients...")

    # Test Wikidata
    wikidata = get_wikidata_people_client()
    politicians = wikidata.get_politicians(limit=3)
    logger.info(f"Wikidata politicians: {len(politicians)}")

    scientists = wikidata.get_scientists(limit=3)
    logger.info(f"Wikidata scientists: {len(scientists)}")

    # Test Nobel Prize
    nobel = get_nobel_prize_client()
    laureates = nobel.get_laureates(limit=5)
    logger.info(f"Nobel laureates: {len(laureates)}")

    # Test Biography.com
    bio_dot_com = get_biography_dot_com_client()
    person = bio_dot_com.get_random_person()
    logger.info(f"Biography.com person: {person}")

    logger.info("API client tests completed!")
