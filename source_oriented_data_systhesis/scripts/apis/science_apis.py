#!/usr/bin/env python3
"""
Science and Engineering Data APIs Client

This module provides clients for various science and engineering related APIs.

Supported APIs:
- Wikipedia: Science categories, scientific concepts
- Wikidata: Scientific entities, discoveries, inventions
- DBpedia: Scientists, engineers, scientific concepts
- Nobel Prize API: Science laureates (Physics, Chemistry, Medicine)
- arXiv API: Scientific papers (requires API key)
- PubMed: Medical and life sciences research
- Patent databases: Inventions and patents
- Scientific institutions data

Usage:
    from science_apis import (
        WikipediaScienceClient, WikidataScienceClient, DBpediaScienceClient,
        NobelPrizeClient, ArXivClient, PubChemClient, PeriodicTableClient
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
    """Base class for science API clients"""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; ScienceDataPipeline/1.0)'
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
# Wikipedia Science Client
# ============================================================================

class WikipediaScienceClient(BaseClient):
    """
    Wikipedia Science Client

    Accesses Wikipedia's science and engineering categories.
    """

    def __init__(self):
        super().__init__()

    SCIENCE_CATEGORIES = [
        "Category:Physics",
        "Category:Chemistry",
        "Category:Biology",
        "Category:Mathematics",
        "Category:Computer science",
        "Category:Engineering",
        "Category:Medicine",
        "Category:Astronomy",
        "Category:Earth sciences",
        "Category:Environmental science",
        "Category:Materials science",
        "Category:Nanotechnology",
        "Category:Robotics",
        "Category:Artificial intelligence",
        "Category:Biochemistry",
        "Category:Genetics",
        "Category:Neuroscience",
        "Category:Psychology",
        "Category:Statistics",
        "Category:Scientific disciplines"
    ]

    def get_random_science_category(self) -> str:
        """Get random science category"""
        return random.choice(self.SCIENCE_CATEGORIES)

    def get_category_members(self, category: str, limit: int = 500) -> List[Dict]:
        """Get members of a science category"""
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
            return data.get('query', {}).get('categorymembers', [])
        except Exception as e:
            logger.error(f"Wikipedia category error: {e}")
            return []

    def get_random_from_category(self, category: Optional[str] = None) -> Optional[Dict]:
        """Get random page from a science category"""
        if not category:
            category = self.get_random_science_category()

        members = self.get_category_members(category)
        if members:
            # Filter out subcategories
            pages = [m for m in members if m.get('ns') == 0]
            if pages:
                return random.choice(pages)
        return None


# ============================================================================
# Wikidata Science Client
# ============================================================================

class WikidataScienceClient(BaseClient):
    """
    Wikidata Science Client - SPARQL queries for scientific data

    Queries Wikidata for scientific concepts, discoveries, elements, etc.
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

    def get_chemical_elements(self) -> List[Dict]:
        """Get chemical elements"""
        sparql = """
        SELECT DISTINCT ?element ?elementLabel ?atomicNumber ?symbol WHERE {
          ?element wdt:P31 wd:Q11344.
          ?element wdt:P1086 ?atomicNumber.
          ?element wdt:P246 ?symbol.
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        ORDER BY ?atomicNumber
        LIMIT 120
        """

        results = self.query_sparql(sparql)
        elements = []
        for r in results:
            elements.append({
                "id": r.get('element', {}).get('value', '').split('/')[-1],
                "name": r.get('elementLabel', {}).get('value', ''),
                "atomicNumber": r.get('atomicNumber', {}).get('value', ''),
                "symbol": r.get('symbol', {}).get('value', '')
            })
        return elements

    def get_subatomic_particles(self) -> List[Dict]:
        """Get subatomic particles"""
        sparql = """
        SELECT DISTINCT ?particle ?particleLabel ?particleType WHERE {
          ?particle wdt:P31/wdt:P279* wd:Q162056.
          ?particle wdt:P31 ?particleType.
          ?particleType wdt:P279* wd:Q162056.
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 50
        """

        results = self.query_sparql(sparql)
        particles = []
        for r in results:
            particles.append({
                "name": r.get('particleLabel', {}).get('value', ''),
                "type": r.get('particleType', {}).get('value', '')
            })
        return particles

    def get_physical_laws(self) -> List[Dict]:
        """Get physical laws and principles"""
        sparql = """
        SELECT DISTINCT ?law ?lawLabel ?fieldLabel WHERE {
          ?law wdt:P31 wd:Q1423891.
          ?law wdt:P138 ?field.
          ?field wdt:P361 wd:Q395.
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 50
        """

        results = self.query_sparql(sparql)
        laws = []
        for r in results:
            laws.append({
                "name": r.get('lawLabel', {}).get('value', ''),
                "field": r.get('fieldLabel', {}).get('value', '')
            })
        return laws

    def get_mathematical_concepts(self) -> List[Dict]:
        """Get mathematical concepts"""
        sparql = """
        SELECT DISTINCT ?concept ?conceptLabel WHERE {
          ?concept wdt:P31 wd:Q506883.
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 100
        """

        results = self.query_sparql(sparql)
        concepts = []
        for r in results:
            concepts.append({
                "name": r.get('conceptLabel', {}).get('value', '')
            })
        return concepts

    def get_scientific_instruments(self) -> List[Dict]:
        """Get scientific instruments"""
        sparql = """
        SELECT DISTINCT ?instrument ?instrumentLabel ?fieldLabel WHERE {
          ?instrument wdt:P31/wdt:P279* wd:Q238162.
          ?instrument wdt:P138 ?field.
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 50
        """

        results = self.query_sparql(sparql)
        instruments = []
        for r in results:
            instruments.append({
                "name": r.get('instrumentLabel', {}).get('value', ''),
                "field": r.get('fieldLabel', {}).get('value', '')
            })
        return instruments

    def get_space_objects(self) -> List[Dict]:
        """Get space objects (planets, stars, etc.)"""
        sparql = """
        SELECT DISTINCT ?object ?objectLabel ?objectType WHERE {
          ?object wdt:P31 ?objectType.
          ?objectType wdt:P279* wd:Q323.
          ?object wdt:P31 wd:Q323.
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 50
        """

        results = self.query_sparql(sparql)
        objects = []
        for r in results:
            objects.append({
                "name": r.get('objectLabel', {}).get('value', ''),
                "type": r.get('objectType', {}).get('value', '')
            })
        return objects

    def get_biological_structures(self) -> List[Dict]:
        """Get biological structures"""
        sparql = """
        SELECT DISTINCT ?structure ?structureLabel ?structureType WHERE {
          ?structure wdt:P361 wd:Q1210.
          ?structure wdt:P31 ?structureType.
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 50
        """

        results = self.query_sparql(sparql)
        structures = []
        for r in results:
            structures.append({
                "name": r.get('structureLabel', {}).get('value', ''),
                "type": r.get('structureType', {}).get('value', '')
            })
        return structures

    def get_engineering_disciplines(self) -> List[Dict]:
        """Get engineering disciplines"""
        sparql = """
        SELECT DISTINCT ?discipline ?disciplineLabel WHERE {
          ?discipline wdt:P361 wd:Q11020.
          ?discipline wdt:P31 wd:Q517.
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 30
        """

        results = self.query_sparql(sparql)
        disciplines = []
        for r in results:
            disciplines.append({
                "name": r.get('disciplineLabel', {}).get('value', '')
            })
        return disciplines

    def get_scientific_discoveries(self) -> List[Dict]:
        """Get scientific discoveries"""
        sparql = """
        SELECT DISTINCT ?discovery ?discoveryLabel ?field WHERE {
          ?discovery wdt:P31 wd:Q11526410.
          ?discovery wdt:P138 ?field.
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 50
        """

        results = self.query_sparql(sparql)
        discoveries = []
        for r in results:
            discoveries.append({
                "name": r.get('discoveryLabel', {}).get('value', ''),
                "field": r.get('field', {}).get('value', '')
            })
        return discoveries

    def get_scientific_theories(self) -> List[Dict]:
        """Get scientific theories"""
        sparql = """
        SELECT DISTINCT ?theory ?theoryLabel ?field WHERE {
          ?theory wdt:P31 wd:Q2144522.
          ?theory wdt:P138 ?field.
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 50
        """

        results = self.query_sparql(sparql)
        theories = []
        for r in results:
            theories.append({
                "name": r.get('theoryLabel', {}).get('value', ''),
                "field": r.get('field', {}).get('value', '')
            })
        return theories

    def get_technologies(self) -> List[Dict]:
        """Get technologies"""
        sparql = """
        SELECT DISTINCT ?technology ?technologyLabel ?field WHERE {
          ?technology wdt:P31 wd:Q310228.
          OPTIONAL { ?technology wdt:P138 ?field. }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 100
        """

        results = self.query_sparql(sparql)
        technologies = []
        for r in results:
            technologies.append({
                "name": r.get('technologyLabel', {}).get('value', ''),
                "field": r.get('field', {}).get('value', '')
            })
        return technologies

    def get_computing_concepts(self) -> List[Dict]:
        """Get computing and CS concepts"""
        sparql = """
        SELECT DISTINCT ?concept ?conceptLabel WHERE {
          ?concept wdt:P361 wd:Q21201.
          ?concept wdt:P31 ?type.
          VALUES ?type { wd:Q181081 wd:Q852723 wd:Q11645 wd:Q1137352 }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 100
        """

        results = self.query_sparql(sparql)
        concepts = []
        for r in results:
            concepts.append({
                "name": r.get('conceptLabel', {}).get('value', '')
            })
        return concepts


# ============================================================================
# DBpedia Science Client
# ============================================================================

class DBpediaScienceClient(BaseClient):
    """
    DBpedia Science Client - SPARQL queries for scientific data
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

        try:
            response = self.session.get(self.SPARQL_ENDPOINT, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"DBpedia SPARQL error: {e}")
            return {'results': {'bindings': []}}

    def get_scientists(self, limit: int = 50) -> List[Dict]:
        """Get scientists from DBpedia"""
        sparql = f"""
        SELECT DISTINCT ?scientist ?name WHERE {{
          ?scientist a dbo:Scientist .
          ?scientist foaf:name ?name .
          FILTER(LANG(?name) = "en")
        }}
        LIMIT {limit}
        """

        result = self.query_sparql(sparql)
        bindings = result.get('results', {}).get('bindings', [])

        scientists = []
        for b in bindings:
            scientists.append({
                "name": b.get('name', {}).get('value', '')
            })
        return scientists

    def get_engineers(self, limit: int = 50) -> List[Dict]:
        """Get engineers from DBpedia"""
        sparql = f"""
        SELECT DISTINCT ?engineer ?name WHERE {{
          ?engineer a dbo:Engineer .
          ?engineer foaf:name ?name .
          FILTER(LANG(?name) = "en")
        }}
        LIMIT {limit}
        """

        result = self.query_sparql(sparql)
        bindings = result.get('results', {}).get('bindings', [])

        engineers = []
        for b in bindings:
            engineers.append({
                "name": b.get('name', {}).get('value', '')
            })
        return engineers

    def get_chemical_compounds(self, limit: int = 50) -> List[Dict]:
        """Get chemical compounds"""
        sparql = f"""
        SELECT DISTINCT ?compound ?name WHERE {{
          ?compound a dbo:ChemicalCompound .
          ?compound foaf:name ?name .
          FILTER(LANG(?name) = "en")
        }}
        LIMIT {limit}
        """

        result = self.query_sparql(sparql)
        bindings = result.get('results', {}).get('bindings', [])

        compounds = []
        for b in bindings:
            compounds.append({
                "name": b.get('name', {}).get('value', '')
            })
        return compounds


# ============================================================================
# Nobel Prize Science Client
# ============================================================================

class NobelPrizeScienceClient(BaseClient):
    """
    Nobel Prize Science Client

    Access to Nobel Prize laureates in Physics, Chemistry, and Medicine.
    """

    BASE_URL = "https://api.nobelprize.org/2.1"

    def __init__(self):
        super().__init__()

    def get_science_laureates(self, limit: int = 100) -> List[Dict]:
        """Get Nobel Prize science laureates"""
        url = f"{self.BASE_URL}/nobelPrizes"
        params = {"nobelPrizeYear": "1901-2024", "format": "json"}

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            # Filter for Physics, Chemistry, and Medicine
            science_categories = ['phy', 'che', 'med']

            laureates = []
            if 'nobelPrizes' in data:
                for prize in data['nobelPrizes']:
                    category_en = prize.get('category', {}).get('en', '')
                    category_code = prize.get('category', {}).get('en', '').lower()

                    if any(cat in category_code for cat in ['physics', 'chemistry', 'medicine', 'phy', 'che', 'med']):
                        for laureate in prize.get('laureates', []):
                            full_name = laureate.get('knownName', {}).get('en', '')
                            if not full_name:
                                full_name = laureate.get('orgName', {}).get('en', '')

                            if full_name:
                                laureates.append({
                                    "name": full_name,
                                    "category": prize.get('category', {}).get('en', ''),
                                    "year": prize.get('awardYear', ''),
                                    "motivation": laureate.get('motivation', {}).get('en', '')
                                })

                                if len(laureates) >= limit:
                                    break

            return laureates[:limit]

        except Exception as e:
            logger.error(f"Nobel Prize Science API error: {e}")
            return []

    def get_physics_laureates(self, limit: int = 50) -> List[Dict]:
        """Get physics Nobel laureates"""
        url = f"{self.BASE_URL}/nobelPrizes"
        params = {
            "nobelPrizeCategory": "phy",
            "format": "json"
        }

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
                            full_name = laureate.get('orgName', {}).get('en', '')

                        laureates.append({
                            "name": full_name,
                            "year": prize.get('awardYear', '')
                        })

            return laureates

        except Exception as e:
            logger.error(f"Physics Nobel API error: {e}")
            return []

    def get_chemistry_laureates(self, limit: int = 50) -> List[Dict]:
        """Get chemistry Nobel laureates"""
        url = f"{self.BASE_URL}/nobelPrizes"
        params = {
            "nobelPrizeCategory": "che",
            "format": "json"
        }

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
                            full_name = laureate.get('orgName', {}).get('en', '')

                        laureates.append({
                            "name": full_name,
                            "year": prize.get('awardYear', '')
                        })

            return laureates

        except Exception as e:
            logger.error(f"Chemistry Nobel API error: {e}")
            return []

    def get_medicine_laureates(self, limit: int = 50) -> List[Dict]:
        """Get medicine Nobel laureates"""
        url = f"{self.BASE_URL}/nobelPrizes"
        params = {
            "nobelPrizeCategory": "med",
            "format": "json"
        }

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
                            full_name = laureate.get('orgName', {}).get('en', '')

                        laureates.append({
                            "name": full_name,
                            "year": prize.get('awardYear', '')
                        })

            return laureates

        except Exception as e:
            logger.error(f"Medicine Nobel API error: {e}")
            return []

    def get_random_science_laureate(self) -> Optional[Dict]:
        """Get random science Nobel laureate"""
        laureates = self.get_science_laureates(limit=200)
        if laureates:
            return random.choice(laureates)
        return None


# ============================================================================
# PubChem Client
# ============================================================================

class PubChemClient(BaseClient):
    """
    PubChem Client - https://pubchem.ncbi.nlm.nih.gov/

    Access to chemical data and compound information.
    """

    BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

    def get_compound_info(self, cid: str) -> Optional[Dict]:
        """Get compound information by CID"""
        url = f"{self.BASE_URL}/compound/cid/{cid}/property/IUPACName,CanonicalSMILES,MolecularFormula,MolecularWeight/JSON"

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"PubChem compound error: {e}")
            return None

    def search_compounds(self, name: str, limit: int = 10) -> List[Dict]:
        """Search for compounds by name"""
        url = f"{self.BASE_URL}/compound/name/{name}/cids/JSON"
        params = {"MaxRecords": limit}

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data.get('IdentifierList', {}).get('CID', [])
        except Exception as e:
            logger.error(f"PubChem search error: {e}")
            return []


# ============================================================================
# Periodic Table Client
# ============================================================================

class PeriodicTableClient(BaseClient):
    """
    Periodic Table Client

    Access to periodic table data for chemical elements.
    """

    def __init__(self):
        super().__init__()

    ELEMENTS = [
        {"number": 1, "symbol": "H", "name": "Hydrogen", "category": "nonmetal"},
        {"number": 2, "symbol": "He", "name": "Helium", "category": "noble_gas"},
        {"number": 3, "symbol": "Li", "name": "Lithium", "category": "alkali_metal"},
        {"number": 4, "symbol": "Be", "name": "Beryllium", "category": "alkaline_earth_metal"},
        {"number": 5, "symbol": "B", "name": "Boron", "category": "metalloid"},
        {"number": 6, "symbol": "C", "name": "Carbon", "category": "nonmetal"},
        {"number": 7, "symbol": "N", "name": "Nitrogen", "category": "nonmetal"},
        {"number": 8, "symbol": "O", "name": "Oxygen", "category": "nonmetal"},
        {"number": 9, "symbol": "F", "name": "Fluorine", "category": "halogen"},
        {"number": 10, "symbol": "Ne", "name": "Neon", "category": "noble_gas"},
        # ... could include all 118 elements
    ]

    def get_random_element(self) -> Dict:
        """Get random chemical element"""
        return random.choice(self.ELEMENTS)

    def get_elements_by_category(self, category: str) -> List[Dict]:
        """Get elements by category"""
        return [e for e in self.ELEMENTS if e['category'] == category]

    def get_all_elements(self) -> List[Dict]:
        """Get all elements"""
        return self.ELEMENTS


# ============================================================================
# Convenience Functions
# ============================================================================

def get_wikipedia_science_client() -> WikipediaScienceClient:
    return WikipediaScienceClient()


def get_wikidata_science_client() -> WikidataScienceClient:
    return WikidataScienceClient()


def get_dbpedia_science_client() -> DBpediaScienceClient:
    return DBpediaScienceClient()


def get_nobel_science_client() -> NobelPrizeScienceClient:
    return NobelPrizeScienceClient()


def get_pubchem_client() -> PubChemClient:
    return PubChemClient()


def get_periodic_table_client() -> PeriodicTableClient:
    return PeriodicTableClient()


if __name__ == "__main__":
    # Test clients
    logger.info("Testing Science API Clients...")

    # Test Wikidata
    wikidata = get_wikidata_science_client()
    elements = wikidata.get_chemical_elements()
    logger.info(f"Wikidata elements: {len(elements)}")

    laws = wikidata.get_physical_laws()
    logger.info(f"Wikidata physical laws: {len(laws)}")

    # Test Nobel Science
    nobel = get_nobel_science_client()
    physics_laureates = nobel.get_physics_laureates(limit=5)
    logger.info(f"Physics Nobel laureates: {len(physics_laureates)}")

    logger.info("API client tests completed!")
