#!/usr/bin/env python3
"""
API Clients for Historical Data Sources

This module provides Python clients for accessing various historical data APIs:
- Wikidata (REST API)
- DBpedia (SPARQL)
- Internet Archive (REST API)
- Oyez (REST API)

Usage:
    from historical_apis import WikidataClient, DBpediaClient, ArchiveClient

    # Get historical figure data
    client = WikidataClient()
    entity = client.get_entity("Q9519")  # Zhang Zhidong

    # Search DBpedia
    dbpedia = DBpediaClient()
    results = dbpedia.query_historical Figures(before_year=1900, limit=10)
"""

import json
import random
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime


# ============================================================================
# Base Client
# ============================================================================

@dataclass
class APIError(Exception):
    """Custom exception for API errors"""
    status_code: int
    message: str


class BaseClient:
    """Base class for API clients"""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; HistoricalDataBot/1.0)'
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


# ============================================================================
# Wikidata Client
# ============================================================================

class WikidataClient(BaseClient):
    """Client for Wikidata API

    API Documentation: https://www.wikidata.org/w/api.php
    """

    BASE_URL = "https://www.wikidata.org/w/api.php"

    def get_entity(self, entity_id: str) -> Dict:
        """Get entity data by ID

        Args:
            entity_id: Wikidata entity ID (e.g., "Q9519" for Zhang Zhidong)

        Returns:
            Entity data including labels, descriptions, and claims

        Example:
            >>> client = WikidataClient()
            >>> entity = client.get_entity("Q9519")
            >>> print(entity["entities"]["Q9519"]["labels"]["en"]["value"])
        """
        params = {
            "action": "wbgetentities",
            "ids": entity_id,
            "format": "json"
        }
        return self._get(self.BASE_URL, params)

    def search_entities(
        self,
        query: str,
        language: str = "en",
        limit: int = 10
    ) -> List[Dict]:
        """Search for entities

        Args:
            query: Search term
            language: Language code (default: "en")
            limit: Maximum results

        Returns:
            List of matching entities

        Example:
            >>> client = WikidataClient()
            >>> results = client.search_entities("Qing Dynasty", language="en")
        """
        params = {
            "action": "wbsearchentities",
            "search": query,
            "language": language,
            "limit": limit,
            "format": "json"
        }
        data = self._get(self.BASE_URL, params)
        return data.get("search", [])

    def get_label(self, entity_id: str, language: str = "en") -> str:
        """Get entity label (name) in specified language

        Args:
            entity_id: Wikidata entity ID
            language: Language code (default: "en")

        Returns:
            Entity label or entity ID if not found
        """
        try:
            entity = self.get_entity(entity_id)
            return (
                entity["entities"]
                .get(entity_id, {})
                .get("labels", {})
                .get(language, {})
                .get("value", entity_id)
            )
        except:
            return entity_id

    def get_historical_figures_by_era(
        self,
        era: str,
        limit: int = 20
    ) -> List[Dict]:
        """Search for historical figures related to an era

        Args:
            era: Era name (e.g., "Qing Dynasty", "Meiji period")
            limit: Maximum results

        Returns:
            List of historical figure entities
        """
        return self.search_entities(era, language="en", limit=limit)

    def get_property(self, entity_id: str, property_id: str) -> List[Any]:
        """Get specific property values for an entity

        Args:
            entity_id: Wikidata entity ID
            property_id: Property ID (e.g., "P569" for date of birth)

        Returns:
            List of property values
        """
        entity = self.get_entity(entity_id)
        claims = entity["entities"].get(entity_id, {}).get("claims", {})
        return claims.get(property_id, [])


# ============================================================================
# DBpedia Client
# ============================================================================

class DBpediaClient(BaseClient):
    """Client for DBpedia SPARQL endpoint

    SPARQL Endpoint: https://dbpedia.org/sparql
    """

    SPARQL_URL = "https://dbpedia.org/sparql"

    def query(self, sparql: str) -> Dict:
        """Execute SPARQL query

        Args:
            sparql: SPARQL query string

        Returns:
            Query results as JSON

        Example:
            >>> client = DBpediaClient()
            >>> results = client.query("SELECT * WHERE { ?s a dbo:Person } LIMIT 10")
        """
        params = {
            "query": sparql,
            "format": "json"
        }
        return self._get(self.SPARQL_URL, params)

    def query_historical_figures(
        self,
        before_year: int = 1900,
        after_year: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Query for historical figures born within a date range

        Args:
            before_year: Birth year must be before this
            after_year: Optional, birth year must be after this
            limit: Maximum results

        Returns:
            List of historical figures with metadata
        """
        filter_clause = f"FILTER(?birthDate < \"{before_year}-01-01\"^^xsd:date)"
        if after_year:
            filter_clause += f"\n  FILTER(?birthDate > \"{after_year}-01-01\"^^xsd:date)"

        sparql = f"""
        SELECT DISTINCT ?person ?name ?birthDate ?deathDate ?abstract WHERE {{
          ?person a dbo:Person .
          ?person foaf:name ?name .
          ?person dbp:birthDate ?birthDate .
          OPTIONAL {{ ?person dbp:deathDate ?deathDate }}
          OPTIONAL {{ ?person dbo:abstract ?abstract }}
          {filter_clause}
        }}
        LIMIT {limit}
        """

        results = self.query(sparql)
        return results.get("results", {}).get("bindings", [])

    def query_events_by_period(
        self,
        start_year: int,
        end_year: int,
        limit: int = 50
    ) -> List[Dict]:
        """Query for historical events within a date range

        Args:
            start_year: Event start date must be after this
            end_year: Event start date must be before this
            limit: Maximum results

        Returns:
            List of events with metadata
        """
        sparql = f"""
        SELECT DISTINCT ?event ?label ?date WHERE {{
          ?event a dbo:Event .
          ?event rdfs:label ?label .
          ?event dbo:date ?date .
          FILTER(?date > "{start_year}-01-01"^^xsd:date)
          FILTER(?date < "{end_year}-01-01"^^xsd:date)
          FILTER(LANG(?label) = "en")
        }}
        LIMIT {limit}
        """

        results = self.query(sparql)
        return results.get("results", {}).get("bindings", [])

    def query_person_by_occupation(
        self,
        occupation: str,
        limit: int = 50
    ) -> List[Dict]:
        """Query for people by occupation

        Args:
            occupation: Occupation name (e.g., "politician", "writer")
            limit: Maximum results

        Returns:
            List of people with the specified occupation
        """
        sparql = f"""
        SELECT DISTINCT ?person ?name ?occupation WHERE {{
          ?person a dbo:Person .
          ?person foaf:name ?name .
          ?person dbo:occupation ?occupationEntity .
          ?occupationEntity rdfs:label ?occupation .
          FILTER(LCASE(STR(?occupation)) = "{occupation.lower()}")
          FILTER(LANG(?name) = "en")
        }}
        LIMIT {limit}
        """

        results = self.query(sparql)
        return results.get("results", {}).get("bindings", [])

    # ========================================================================
    # Geographical Query Methods
    # ========================================================================

    def query_geographical_places(
        self,
        place_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Query for geographical places

        Args:
            place_type: Optional type filter (e.g., "dbo:Mountain", "dbo:Island", "dbo:BodyOfWater")
            limit: Maximum results

        Returns:
            List of geographical places with metadata
        """
        if place_type:
            type_filter = f"?place a {place_type} ."
        else:
            type_filter = "?place a dbo:Place ."

        sparql = f"""
        SELECT DISTINCT ?place ?name ?abstract ?lat ?long WHERE {{
          {type_filter}
          ?place foaf:name ?name .
          OPTIONAL {{ ?place dbo:abstract ?abstract }}
          OPTIONAL {{ ?place geo:lat ?lat }}
          OPTIONAL {{ ?place geo:long ?long }}
          FILTER(LANG(?name) = "en")
        }}
        LIMIT {limit}
        OFFSET 1000
        """

        results = self.query(sparql)
        return results.get("results", {}).get("bindings", [])

    def query_mountains(
        self,
        limit: int = 50
    ) -> List[Dict]:
        """Query for mountains

        Args:
            limit: Maximum results

        Returns:
            List of mountains with elevation and location
        """
        sparql = f"""
        SELECT DISTINCT ?mountain ?name ?elevation ?abstract WHERE {{
          ?mountain a dbo:Mountain .
          ?mountain foaf:name ?name .
          OPTIONAL {{ ?mountain dbo:elevation ?elevation }}
          OPTIONAL {{ ?mountain dbo:abstract ?abstract }}
          FILTER(LANG(?name) = "en")
        }}
        LIMIT {limit}
        OFFSET 500
        """

        results = self.query(sparql)
        return results.get("results", {}).get("bindings", [])

    def query_islands(
        self,
        limit: int = 50
    ) -> List[Dict]:
        """Query for islands

        Args:
            limit: Maximum results

        Returns:
            List of islands with area and location
        """
        sparql = f"""
        SELECT DISTINCT ?island ?name ?area ?abstract WHERE {{
          ?island a dbo:Island .
          ?island foaf:name ?name .
          OPTIONAL {{ ?island dbo:area ?area }}
          OPTIONAL {{ ?island dbo:abstract ?abstract }}
          FILTER(LANG(?name) = "en")
        }}
        LIMIT {limit}
        OFFSET 200
        """

        results = self.query(sparql)
        return results.get("results", {}).get("bindings", [])

    def query_bodies_of_water(
        self,
        limit: int = 50
    ) -> List[Dict]:
        """Query for bodies of water (lakes, seas, rivers)

        Args:
            limit: Maximum results

        Returns:
            List of water bodies with type and location
        """
        sparql = f"""
        SELECT DISTINCT ?water ?name ?abstract WHERE {{
          {{
            ?water a dbo:BodyOfWater .
          }} UNION {{
            ?water a dbo:Lake .
          }} UNION {{
            ?water a dbo:Sea .
          }} UNION {{
            ?water a dbo:River .
          }}
          ?water foaf:name ?name .
          OPTIONAL {{ ?water dbo:abstract ?abstract }}
          FILTER(LANG(?name) = "en")
        }}
        LIMIT {limit}
        OFFSET 500
        """

        results = self.query(sparql)
        return results.get("results", {}).get("bindings", [])

    def query_cities(
        self,
        min_population: int = 100000,
        limit: int = 50
    ) -> List[Dict]:
        """Query for cities

        Args:
            min_population: Minimum population threshold
            limit: Maximum results

        Returns:
            List of cities with population and location
        """
        sparql = f"""
        SELECT DISTINCT ?city ?name ?population ?country WHERE {{
          ?city a dbo:City .
          ?city foaf:name ?name .
          ?city dbo:populationTotal ?population .
          ?city dbo:country ?country .
          FILTER(?population > {min_population})
          FILTER(LANG(?name) = "en")
        }}
        LIMIT {limit}
        OFFSET 1000
        """

        results = self.query(sparql)
        return results.get("results", {}).get("bindings", [])

    # ========================================================================
    # Sports Query Methods
    # ========================================================================

    def query_athletes(
        self,
        sport: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Query for athletes

        Args:
            sport: Optional sport name filter
            limit: Maximum results

        Returns:
            List of athletes with their sport
        """
        if sport:
            sport_filter = f'?athlete dbo:occupation|dbp:sport|dbo:sport ?sportEntity . ?sportEntity rdfs:label "{sport}"@en .'
        else:
            sport_filter = ''

        sparql = f"""
        SELECT DISTINCT ?athlete ?name ?sport ?abstract WHERE {{
          ?athlete a dbo:Athlete .
          ?athlete foaf:name ?name .
          OPTIONAL {{ ?athlete dbo:sport|dbp:sport ?sport }}
          OPTIONAL {{ ?athlete dbo:abstract ?abstract }}
          {sport_filter}
          FILTER(LANG(?name) = "en")
        }}
        LIMIT {limit}
        OFFSET {random.randint(0, 5000)}
        """

        results = self.query(sparql)
        return results.get("results", {}).get("bindings", [])

    def query_sports_teams(
        self,
        sport: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Query for sports teams/clubs

        Args:
            sport: Optional sport name filter
            limit: Maximum results

        Returns:
            List of teams with league and sport
        """
        if sport:
            sport_filter = f'?team dbo:sport|dbp:sport ?sportEntity . ?sportEntity rdfs:label "{sport}"@en .'
        else:
            sport_filter = ''

        sparql = f"""
        SELECT DISTINCT ?team ?name ?league ?sport ?abstract WHERE {{
          {{
            ?team a dbo:SportsTeam .
          }} UNION {{
            ?team a dbo:Organisation .
            ?team dbo:industry ?industry .
            ?industry rdfs:label "Sports"@en .
          }}
          ?team foaf:name ?name .
          OPTIONAL {{ ?team dbo:league|dbp:league ?league }}
          OPTIONAL {{ ?team dbo:sport|dbp:sport ?sport }}
          OPTIONAL {{ ?team dbo:abstract ?abstract }}
          {sport_filter}
          FILTER(LANG(?name) = "en")
        }}
        LIMIT {limit}
        OFFSET {random.randint(0, 1000)}
        """

        results = self.query(sparql)
        return results.get("results", {}).get("bindings", [])

    def query_competitions(
        self,
        sport: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Query for sports competitions/events

        Args:
            sport: Optional sport name filter
            limit: Maximum results

        Returns:
            List of competitions with sport
        """
        if sport:
            sport_filter = f'?competition dbo:sport|dbp:sport ?sportEntity . ?sportEntity rdfs:label "{sport}"@en .'
        else:
            sport_filter = ''

        sparql = f"""
        SELECT DISTINCT ?competition ?name ?sport ?abstract WHERE {{
          {{
            ?competition a dbo:SportsEvent .
          }} UNION {{
            ?competition a dbo:Competition .
          }}
          ?competition foaf:name ?name .
          OPTIONAL {{ ?competition dbo:sport|dbp:sport ?sport }}
          OPTIONAL {{ ?competition dbo:abstract ?abstract }}
          {sport_filter}
          FILTER(LANG(?name) = "en")
        }}
        LIMIT {limit}
        OFFSET {random.randint(0, 500)}
        """

        results = self.query(sparql)
        return results.get("results", {}).get("bindings", [])

    def query_sports_coaches(
        self,
        sport: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Query for sports coaches/managers

        Args:
            sport: Optional sport name filter
            limit: Maximum results

        Returns:
            List of coaches with their team and sport
        """
        if sport:
            sport_filter = f'?coach dbo:occupation|dbp:sport ?sportEntity . ?sportEntity rdfs:label "{sport}"@en .'
        else:
            sport_filter = ''

        sparql = f"""
        SELECT DISTINCT ?coach ?name ?team ?sport ?abstract WHERE {{
          ?coach a dbo:Person .
          ?coach foaf:name ?name .
          ?coach dbo:occupation ?occupation .
          ?occupation rdfs:label "Coach"@en .
          OPTIONAL {{ ?coach dbo:team|dbp:team ?team }}
          OPTIONAL {{ ?coach dbo:sport|dbp:sport ?sport }}
          OPTIONAL {{ ?coach dbo:abstract ?abstract }}
          {sport_filter}
          FILTER(LANG(?name) = "en")
        }}
        LIMIT {limit}
        OFFSET {random.randint(0, 1000)}
        """

        results = self.query(sparql)
        return results.get("results", {}).get("bindings", [])

    def query_sports_venues(
        self,
        venue_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Query for sports venues/stadiums

        Args:
            venue_type: Optional venue type filter (e.g., "Stadium", "Arena")
            limit: Maximum results

        Returns:
            List of venues with location and capacity
        """
        if venue_type:
            type_filter = f'?venue a dbo:{venue_type} .'
        else:
            type_filter = '''
          { ?venue a dbo:Stadium . }
          UNION { ?venue a dbo:Arena . }
          UNION { ?venue a dbo:SportsVenue . }'''

        sparql = f"""
        SELECT DISTINCT ?venue ?name ?location ?capacity ?abstract WHERE {{
          {type_filter}
          ?venue foaf:name ?name .
          OPTIONAL {{ ?venue dbo:location|dbp:location ?location }}
          OPTIONAL {{ ?venue dbo:capacity|dbp:seatingCapacity ?capacity }}
          OPTIONAL {{ ?venue dbo:abstract ?abstract }}
          FILTER(LANG(?name) = "en")
        }}
        LIMIT {limit}
        OFFSET {random.randint(0, 2000)}
        """

        results = self.query(sparql)
        return results.get("results", {}).get("bindings", [])

    def query_sports_federations(
        self,
        sport: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Query for sports federations/governing bodies

        Args:
            sport: Optional sport name filter
            limit: Maximum results

        Returns:
            List of sports organizations
        """
        if sport:
            sport_filter = f'?org dbo:sport|dbp:sport ?sportEntity . ?sportEntity rdfs:label "{sport}"@en .'
        else:
            sport_filter = ''

        sparql = f"""
        SELECT DISTINCT ?org ?name ?sport ?abstract WHERE {{
          ?org a dbo:Organisation .
          ?org foaf:name ?name .
          ?org dbo:industry|dbo:activity ?activity .
          ?activity rdfs:label ?activityLabel .
          FILTER(CONTAINS(LCASE(STR(?activityLabel)), "sport"))
          OPTIONAL {{ ?org dbo:sport|dbp:sport ?sport }}
          OPTIONAL {{ ?org dbo:abstract ?abstract }}
          {sport_filter}
          FILTER(LANG(?name) = "en")
        }}
        LIMIT {limit}
        OFFSET {random.randint(0, 500)}
        """

        results = self.query(sparql)
        return results.get("results", {}).get("bindings", [])


# ============================================================================
# GeoNames Client
# ============================================================================

class GeoNamesClient(BaseClient):
    """Client for GeoNames API

    GeoNames API Documentation: http://www.geonames.org/export/web-services.html
    Free API allows up to 2000 requests per hour
    """

    BASE_URL = "http://api.geonames.org"

    def __init__(self, username: str = "demo"):
        """Initialize GeoNames client

        Args:
            username: GeoNames username (default: "demo" for testing)
                     Get a free account at: http://www.geonames.org/login
        """
        super().__init__(timeout=15)
        self.username = username

    def _get(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Make GET request with username parameter"""
        if params is None:
            params = {}
        params["username"] = self.username
        return super()._get(url, params)

    def search_places(
        self,
        query: str,
        feature_class: Optional[str] = None,
        feature_code: Optional[str] = None,
        max_rows: int = 10
    ) -> List[Dict]:
        """Search for places by name

        Args:
            query: Search query (place name)
            feature_class: Optional feature class filter
                A: Administrative country codes
                H: Hydrographic (water bodies)
                L: Areas (parks, reserves)
                P: Populated places (cities, villages)
                R: Roads, streets
                S: Spot, building, farm
                T: Mountain, hill, rock
                U: Undersea
                V: Vegetation (forest, heath)
            feature_code: Optional feature code for more specific filtering
            max_rows: Maximum results (default: 10)

        Returns:
            List of matching places

        Example:
            >>> client = GeoNamesClient()
            >>> results = client.search_places("Mount Everest", feature_class="T")
        """
        url = f"{self.BASE_URL}/searchJSON"
        params = {
            "q": query,
            "maxRows": max_rows
        }

        if feature_class:
            params["featureClass"] = feature_class
        if feature_code:
            params["featureCode"] = feature_code

        results = self._get(url, params)
        return results.get("geonames", [])

    def get_random_place(
        self,
        feature_class: Optional[str] = None,
        north: float = 90.0,
        south: float = -90.0,
        east: float = 180.0,
        west: float = -180.0,
        max_rows: int = 500
    ) -> Optional[Dict]:
        """Get a random place within bounding box

        Args:
            feature_class: Optional feature class filter
            north: North latitude (default: 90.0)
            south: South latitude (default: -90.0)
            east: East longitude (default: 180.0)
            west: West longitude (default: -180.0)
            max_rows: Maximum places to select from

        Returns:
            Random place dict or None
        """
        url = f"{self.BASE_URL}/searchJSON"
        params = {
            "north": north,
            "south": south,
            "east": east,
            "west": west,
            "maxRows": max_rows
        }

        if feature_class:
            params["featureClass"] = feature_class

        try:
            results = self._get(url, params)
            places = results.get("geonames", [])

            if places:
                import random
                return random.choice(places)
        except Exception as e:
            pass

        return None

    def get_cities(
        self,
        country: Optional[str] = None,
        min_population: int = 10000,
        max_rows: int = 100
    ) -> List[Dict]:
        """Get cities with population threshold

        Args:
            country: Optional country code (e.g., "US", "CN", "BR")
            min_population: Minimum population (default: 10000)
            max_rows: Maximum results

        Returns:
            List of cities
        """
        url = f"{self.BASE_URL}/searchJSON"
        params = {
            "featureClass": "P",  # Populated place
            "minPopulation": min_population,
            "maxRows": max_rows,
            "orderby": "population"
        }

        if country:
            params["country"] = country

        results = self._get(url, params)
        return results.get("geonames", [])

    def get_mountains(
        self,
        country: Optional[str] = None,
        max_rows: int = 100
    ) -> List[Dict]:
        """Get mountains and peaks

        Args:
            country: Optional country code
            max_rows: Maximum results

        Returns:
            List of mountains
        """
        url = f"{self.BASE_URL}/searchJSON"
        params = {
            "featureClass": "T",  # Mountain, hill, rock
            "featureCode": "MT",  # Mountain
            "maxRows": max_rows
        }

        if country:
            params["country"] = country

        results = self._get(url, params)
        return results.get("geonames", [])

    def get_bodies_of_water(
        self,
        water_type: Optional[str] = None,
        max_rows: int = 100
    ) -> List[Dict]:
        """Get bodies of water

        Args:
            water_type: Optional type filter
                LAKE: Lake
                RIVER: River
                STRM: Stream
                CANAL: Canal
                BAY: Bay
                SEA: Sea
                OCN: Ocean
            max_rows: Maximum results

        Returns:
            List of water bodies
        """
        url = f"{self.BASE_URL}/searchJSON"
        params = {
            "featureClass": "H",  # Hydrographic
            "maxRows": max_rows
        }

        if water_type:
            params["featureCode"] = water_type

        results = self._get(url, params)
        return results.get("geonames", [])

    def get_random_by_continent(
        self,
        continent: str,
        feature_class: Optional[str] = None
    ) -> Optional[Dict]:
        """Get random place from a continent

        Args:
            continent: Continent name or code
                AF: Africa
                AS: Asia
                EU: Europe
                NA: North America
                OC: Oceania
                SA: South America
            feature_class: Optional feature class filter

        Returns:
            Random place dict or None
        """
        # Bounding boxes for continents
        bbox = {
            "AF": {"north": 37, "south": -35, "east": 52, "west": -18},
            "AS": {"north": 77, "south": -10, "east": 145, "west": 26},
            "EU": {"north": 72, "south": 34, "east": 45, "west": -25},
            "NA": {"north": 72, "south": 7, "east": -52, "west": -168},
            "OC": {"north": 0, "south": -47, "east": 180, "west": 110},
            "SA": {"north": 13, "south": -56, "east": -34, "west": -81}
        }

        if continent.upper() in bbox:
            bounds = bbox[continent.upper()]
            return self.get_random_place(
                feature_class=feature_class,
                **bounds
            )

        return None


# ============================================================================
# Internet Archive Client
# ============================================================================

class ArchiveClient(BaseClient):
    """Client for Internet Archive APIs

    Search API: https://archive.org/advancedsearch.php
    Metadata API: https://archive.org/metadata/{identifier}
    """

    SEARCH_URL = "https://archive.org/advancedsearch.php"
    METADATA_URL = "https://archive.org/metadata"

    def search(
        self,
        query: str,
        fields: Optional[List[str]] = None,
        rows: int = 50,
        page: int = 1
    ) -> Dict:
        """Search for documents

        Args:
            query: Search query
            fields: Fields to return (default: identifier, title, year)
            rows: Number of results per page
            page: Page number

        Returns:
            Search results with metadata

        Example:
            >>> client = ArchiveClient()
            >>> results = client.search("Qing Dynasty", rows=10)
            >>> print(f"Found {results['response']['numFound']} documents")
        """
        if fields is None:
            fields = ["identifier", "title", "year", "collection", "format"]

        params = {
            "q": query,
            "output": "json",
            "rows": rows,
            "page": page
        }

        for field in fields:
            params.setdefault("fl[]", field)

        return self._get(self.SEARCH_URL, params)

    def get_metadata(self, identifier: str) -> Dict:
        """Get metadata for a specific item

        Args:
            identifier: Archive identifier

        Returns:
            Item metadata

        Example:
            >>> client = ArchiveClient()
            >>> metadata = client.get_metadata("qingdynasty00humm")
        """
        return self._get(f"{self.METADATA_URL}/{identifier}", {})

    def search_by_year(
        self,
        query: str,
        start_year: int,
        end_year: int,
        rows: int = 50
    ) -> List[Dict]:
        """Search for documents within a year range

        Args:
            query: Search query
            start_year: Start year (inclusive)
            end_year: End year (inclusive)
            rows: Maximum results

        Returns:
            List of matching documents
        """
        year_query = f"{query} year:[{start_year} TO {end_year}]"
        results = self.search(year_query, rows=rows)
        return results.get("response", {}).get("docs", [])

    def get_download_url(self, identifier: str, filename: Optional[str] = None) -> str:
        """Get download URL for an item

        Args:
            identifier: Archive identifier
            filename: Optional specific file

        Returns:
            Download URL
        """
        if filename:
            return f"https://archive.org/download/{identifier}/{filename}"
        else:
            metadata = self.get_metadata(identifier)
            # Try to find the first readable file
            for file in metadata.get("files", []):
                if file.get("format") in ["Text", "PDF", "DjVu"]:
                    return f"https://archive.org/download/{identifier}/{file['name']}"
            return f"https://archive.org/details/{identifier}"


# ============================================================================
# Oyez Client
# ============================================================================

class OyezClient(BaseClient):
    """Client for Oyez Supreme Court API

    API Base: https://api.oyez.org/
    """

    BASE_URL = "https://api.oyez.org"

    def get_cases(self, limit: int = 50) -> List[Dict]:
        """Get list of Supreme Court cases

        Args:
            limit: Maximum number of cases

        Returns:
            List of case summaries
        """
        return self._get(f"{self.BASE_URL}/cases", {})

    def get_case(self, year: int, docket_number: str) -> Dict:
        """Get details for a specific case

        Args:
            year: Case year
            docket_number: Docket number

        Returns:
            Case details
        """
        return self._get(f"{self.BASE_URL}/cases/{year}/{docket_number}", {})

    def search_cases(self, term: str) -> List[Dict]:
        """Search for cases by term

        Note: The Oyez API doesn't have a direct search endpoint.
        This method fetches all cases and filters client-side.

        Args:
            term: Search term

        Returns:
            Matching cases
        """
        cases = self.get_cases()
        term_lower = term.lower()

        matching = []
        for case in cases:
            # Search in case name, citation, or description
            if (
                term_lower in case.get("name", "").lower() or
                term_lower in case.get("citation", {}).get("volume", "").lower() or
                term_lower in case.get("question", "").lower()
            ):
                matching.append(case)

        return matching


# ============================================================================
# Utility Functions
# ============================================================================

def create_historical_seed_entities(
    era: str,
    num_figures: int = 10,
    num_events: int = 5
) -> List[Dict]:
    """Create seed entities for historical QA generation

    Args:
        era: Historical era name (e.g., "Qing Dynasty")
        num_figures: Number of historical figures to fetch
        num_events: Number of events to fetch

    Returns:
        List of seed entities for OffSeeker pipeline
    """
    entities = []

    # Get historical figures from Wikidata
    wikidata = WikidataClient()
    figures = wikidata.search_entities(era, limit=num_figures)

    for fig in figures:
        entities.append({
            "name": fig.get("display", {}).get("label", {}).get("value", ""),
            "id": fig.get("id", ""),
            "type": "person",
            "source": "wikidata"
        })

    # Get events from DBpedia (extract years from era)
    # This is a simplified approach
    dbpedia = DBpediaClient()

    return entities


# ============================================================================
# CLI Interface
# ============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python historical_apis.py wikidata search <query>")
        print("  python historical_apis.py wikidata entity <id>")
        print("  python historical_apis.py dbpedia query <sparql>")
        print("  python historical_apis.py archive search <query>")
        print("  python historical_apis.py oyez cases")
        sys.exit(1)

    client_type = sys.argv[1].lower()
    command = sys.argv[2].lower()

    if client_type == "wikidata" and command == "search":
        query = sys.argv[3] if len(sys.argv) > 3 else "Qing Dynasty"
        client = WikidataClient()
        results = client.search_entities(query)
        for r in results[:5]:
            print(f"  {r['id']}: {r.get('display', {}).get('label', {}).get('value', 'N/A')}")

    elif client_type == "wikidata" and command == "entity":
        entity_id = sys.argv[3] if len(sys.argv) > 3 else "Q9519"
        client = WikidataClient()
        entity = client.get_entity(entity_id)
        data = entity["entities"].get(entity_id, {})
        print(f"ID: {entity_id}")
        print(f"Label: {data.get('labels', {}).get('en', {}).get('value', 'N/A')}")
        print(f"Description: {data.get('descriptions', {}).get('en', {}).get('value', 'N/A')}")

    elif client_type == "dbpedia" and command == "query":
        client = DBpediaClient()
        results = client.query_historical_figures(before_year=1900, limit=10)
        print(f"Found {len(results)} historical figures:")
        for r in results[:5]:
            print(f"  - {r['name']['value']}: {r.get('birthDate', {}).get('value', 'N/A')}")

    elif client_type == "archive" and command == "search":
        query = sys.argv[3] if len(sys.argv) > 3 else "Qing Dynasty"
        client = ArchiveClient()
        results = client.search(query, rows=10)
        total = results.get("response", {}).get("numFound", 0)
        docs = results.get("response", {}).get("docs", [])
        print(f"Found {total} documents:")
        for d in docs[:5]:
            print(f"  - {d.get('title', 'N/A')} ({d.get('year', 'N/A')})")

    elif client_type == "oyez" and command == "cases":
        client = OyezClient()
        cases = client.get_cases()
        print(f"Found {len(cases)} Supreme Court cases:")
        for c in cases[:5]:
            print(f"  - {c.get('name', 'N/A')} ({c.get('citation', {}).get('year', 'N/A')})")

    else:
        print(f"Unknown command: {client_type} {command}")
        sys.exit(1)
