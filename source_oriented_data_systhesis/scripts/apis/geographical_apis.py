#!/usr/bin/env python3
"""
Geographical Data APIs Client

This module provides clients for various geographical data APIs
that were audited and found accessible.

Supported APIs:
- GeoNames: Place names and geographic features
- OpenStreetMap Nominatim: Geocoding
- Overpass API: OSM data queries
- Open-Meteo: Weather/climate data
- Wikidata: SPARQL queries for geographic entities
- OBIS: Marine biodiversity data
- NOAA CDO: Climate data
- UNESCO: Geoparks data
- Macrostrat: Geologic data
"""

import requests
from typing import Dict, List, Optional, Any
from loguru import logger
import json


class GeographicalAPIError(Exception):
    """Base exception for geographical API errors"""
    pass


class GeoNamesClient:
    """
    GeoNames API Client
    http://www.geonames.org/export/web-services.html

    Requires username (free registration): http://www.geonames.org/login
    """

    BASE_URL = "http://api.geonames.org"

    def __init__(self, username: Optional[str] = None):
        """
        Args:
            username: GeoNames username (optional for some endpoints)
        """
        self.username = username or "demo"  # demo has limited credits
        self.session = requests.Session()

    def search(self, query: str, max_rows: int = 10, feature_class: Optional[str] = None) -> List[Dict]:
        """
        Search for place names

        Args:
            query: Search query
            max_rows: Maximum number of results
            feature_class: Filter by feature class (A=admin, P=populated place, etc.)

        Returns:
            List of place entries
        """
        params = {
            "q": query,
            "maxRows": max_rows,
            "username": self.username,
            "type": "JSON"
        }
        if feature_class:
            params["featureClass"] = feature_class

        try:
            response = self.session.get(f"{self.BASE_URL}/searchJSON", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "geonames" in data:
                return data["geonames"]
            elif "status" in data:
                # Handle throttling or errors
                logger.warning(f"GeoNames API error: {data['status'].get('message', 'Unknown error')}")
                return []
            return []

        except Exception as e:
            logger.error(f"GeoNames search error: {e}")
            return []

    def get_place_details(self, geoname_id: int) -> Optional[Dict]:
        """Get details for a specific place by GeoNames ID"""
        params = {
            "geonameId": geoname_id,
            "username": self.username,
            "type": "JSON"
        }

        try:
            response = self.session.get(f"{self.BASE_URL}/getJSON", params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"GeoNames get_place_details error: {e}")
            return None

    def get_children(self, geoname_id: int, feature_class: Optional[str] = None) -> List[Dict]:
        """Get children (admin divisions, places) for a given location"""
        params = {
            "geonameId": geoname_id,
            "username": self.username,
            "type": "JSON"
        }
        if feature_class:
            params["featureClass"] = feature_class

        try:
            response = self.session.get(f"{self.BASE_URL}/childrenJSON", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("geonames", [])
        except Exception as e:
            logger.error(f"GeoNames get_children error: {e}")
            return []

    def get_hierarchy(self, geoname_id: int) -> List[Dict]:
        """Get administrative hierarchy for a place"""
        params = {
            "geonameId": geoname_id,
            "username": self.username,
            "type": "JSON"
        }

        try:
            response = self.session.get(f"{self.BASE_URL}/hierarchyJSON", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("geonames", [])
        except Exception as e:
            logger.error(f"GeoNames get_hierarchy error: {e}")
            return []


class NominatimClient:
    """
    OpenStreetMap Nominatim API Client
    https://nominatim.org/release-docs/latest/api/Search/

    Free geocoding service based on OpenStreetMap data.
    Requires User-Agent header and email for contact.
    """

    BASE_URL = "https://nominatim.openstreetmap.org"

    def __init__(self, email: Optional[str] = None):
        """
        Args:
            email: Contact email for API usage policy compliance
        """
        self.email = email or "audit@example.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "GeographicalDataPipeline/1.0",
            "From": self.email
        })

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search for places

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of place entries
        """
        params = {
            "q": query,
            "format": "json",
            "limit": limit,
            "addressdetails": 1,
            "namedetails": 1
        }

        try:
            response = self.session.get(f"{self.BASE_URL}/search", params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Nominatim search error: {e}")
            return []

    def reverse(self, lat: float, lon: float) -> Optional[Dict]:
        """
        Reverse geocode - get address from coordinates

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Place details or None
        """
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json",
            "addressdetails": 1
        }

        try:
            response = self.session.get(f"{self.BASE_URL}/reverse", params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Nominatim reverse error: {e}")
            return None

    def lookup(self, osm_ids: List[tuple]) -> List[Dict]:
        """
        Lookup OSM objects by ID

        Args:
            osm_ids: List of (type, id) tuples, e.g., [('N', 12345), ('W', 67890)]
                     Types: N=node, W=way, R=relation

        Returns:
            List of place entries
        """
        osm_ids_str = ",".join([f"{t}{i}" for t, i in osm_ids])
        params = {
            "osm_ids": osm_ids_str,
            "format": "json"
        }

        try:
            response = self.session.get(f"{self.BASE_URL}/lookup", params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Nominatim lookup error: {e}")
            return []


class OverpassClient:
    """
    OpenStreetMap Overpass API Client
    https://overpass-api.de/

    Query OSM data with Overpass QL.
    """

    BASE_URL = "https://overpass-api.de/api/interpreter"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "GeographicalDataPipeline/1.0"
        })

    def query(self, overpass_ql: str) -> Dict:
        """
        Execute Overpass QL query

        Args:
            overpass_ql: Overpass QL query string

        Returns:
            JSON response with OSM data
        """
        params = {"data": overpass_ql}

        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Overpass query error: {e}")
            return {}

    def get_waterways_in_bbox(self, min_lat: float, min_lon: float,
                              max_lat: float, max_lon: float) -> Dict:
        """Get waterways (rivers, canals) in a bounding box"""
        query = f"""
        [out:json][timeout:25];
        (
          way["waterway"]~"river|canal|stream"({min_lat},{min_lon},{max_lat},{max_lon});
        );
        out body;
        >;
        out skel qt;
        """
        return self.query(query)

    def get_places_in_area(self, area_name: str) -> Dict:
        """Get populated places in a named area"""
        query = f"""
        [out:json][timeout:25];
        area["name"="{area_name}"]->.searchArea;
        (
          node["place"~"city|town|village"](area.searchArea);
          way["place"~"city|town|village"](area.searchArea);
          relation["place"~"city|town|village"](area.searchArea);
        );
        out body;
        >;
        out skel qt;
        """
        return self.query(query)


class OpenMeteoClient:
    """
    Open-Meteo API Client
    https://open-meteo.com/

    Free weather API with historical data, no API key required.
    """

    BASE_URL = "https://archive-api.open-meteo.com/v1"

    def __init__(self):
        self.session = requests.Session()

    def get_historical_weather(self, lat: float, lon: float,
                               start_date: str, end_date: str,
                               variables: List[str] = None) -> Optional[Dict]:
        """
        Get historical weather data

        Args:
            lat: Latitude
            lon: Longitude
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            variables: List of weather variables (default: common ones)

        Returns:
            Weather data or None
        """
        if variables is None:
            variables = [
                "temperature_2m_mean",
                "precipitation_sum",
                "wind_speed_10m_max"
            ]

        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
            "daily": ",".join(variables),
            "timezone": "auto"
        }

        try:
            response = self.session.get(f"{self.BASE_URL}/archive", params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Open-Meteo error: {e}")
            return None


class WikidataClient:
    """
    Wikidata SPARQL Client
    https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service

    Query geographic entities from Wikidata.
    """

    SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "GeographicalDataPipeline/1.0",
            "Accept": "application/sparql-results+json"
        })

    def query(self, sparql: str) -> List[Dict]:
        """
        Execute SPARQL query

        Args:
            sparql: SPARQL query string

        Returns:
            List of result bindings
        """
        params = {
            "query": sparql,
            "format": "json"
        }

        try:
            response = self.session.get(self.SPARQL_ENDPOINT, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("results", {}).get("bindings", [])
        except Exception as e:
            logger.error(f"Wikidata SPARQL error: {e}")
            return []

    def get_place_info(self, place_name: str) -> List[Dict]:
        """Get Wikidata information for a place"""
        sparql = f"""
        SELECT ?item ?itemLabel ?coord ?country ?countryLabel WHERE {{
          ?item rdfs:label "{place_name}"@en.
          ?item wdt:P31/wdt:P279* wd:Q2221906.  # instance of geographic location
          OPTIONAL {{ ?item wdt:P625 ?coord. }}
          OPTIONAL {{ ?item wdt:P17 ?country. }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT 10
        """
        return self.query(sparql)

    def get_lakes_by_area(self, min_area_km2: float = 100) -> List[Dict]:
        """Get large lakes from Wikidata"""
        sparql = f"""
        SELECT ?lake ?lakeLabel ?area ?coord WHERE {{
          ?lake wdt:P31 wd:Q23397.  # instance of lake
          ?lake wdt:P2046 ?area.
          ?lake wdt:P625 ?coord.
          FILTER(?area >= {min_area_km2})
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        ORDER BY DESC(?area)
        LIMIT 100
        """
        return self.query(sparql)


class MacrostratClient:
    """
    Macrostrat API Client
    https://macrostrat.org/api

    Geologic and paleobiologic data.
    """

    BASE_URL = "https://macrostrat.org/api/v2"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "GeographicalDataPipeline/1.0"
        })

    def get_units(self, lat: float, lon: float, buffer: float = 0.1) -> Optional[Dict]:
        """Get geologic units at a location"""
        params = {
            "lat": lat,
            "lng": lon,
            "buffer": buffer,
            "format": "json"
        }

        try:
            response = self.session.get(f"{self.BASE_URL}/units", params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Macrostrat error: {e}")
            return None

    def get_lithologies(self) -> Optional[Dict]:
        """Get all lithology types"""
        try:
            response = self.session.get(f"{self.BASE_URL}/lithologies", timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Macrostrat lithologies error: {e}")
            return None


class UNESCOGeoparksClient:
    """
    UNESCO Global Geoparks API Client
    https://data.unesco.org/explore/dataset/eg0001/api/

    UNESCO designated geoparks with geological heritage features.
    """

    BASE_URL = "https://data.unesco.org/api/records/1.0/search/"

    def __init__(self):
        self.session = requests.Session()

    def search_geoparks(self, query: str = "", rows: int = 10) -> List[Dict]:
        """Search UNESCO geoparks"""
        params = {
            "dataset": "eg0001",
            "q": query,
            "rows": rows,
            "format": "json"
        }

        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            return data.get("records", [])
        except Exception as e:
            logger.error(f"UNESCO Geoparks error: {e}")
            return []


# Convenience functions
def get_geonames_client(username: Optional[str] = None) -> GeoNamesClient:
    """Get GeoNames client instance"""
    return GeoNamesClient(username)


def get_nominatim_client(email: Optional[str] = None) -> NominatimClient:
    """Get Nominatim client instance"""
    return NominatimClient(email)


def get_overpass_client() -> OverpassClient:
    """Get Overpass API client instance"""
    return OverpassClient()


def get_openmeteo_client() -> OpenMeteoClient:
    """Get Open-Meteo client instance"""
    return OpenMeteoClient()


def get_wikidata_client() -> WikidataClient:
    """Get Wikidata SPARQL client instance"""
    return WikidataClient()


def get_macrostrat_client() -> MacrostratClient:
    """Get Macrostrat client instance"""
    return MacrostratClient()


def get_unesco_client() -> UNESCOGeoparksClient:
    """Get UNESCO Geoparks client instance"""
    return UNESCOGeoparksClient()


if __name__ == "__main__":
    # Test clients
    logger.info("Testing Geographical API Clients...")

    # Test Nominatim
    nominatim = get_nominatim_client()
    results = nominatim.search("Mount Everest")
    logger.info(f"Nominatim search for 'Mount Everest': {len(results)} results")
    if results:
        logger.info(f"  First result: {results[0].get('display_name')}")

    # Test Overpass
    overpass = get_overpass_client()
    data = overpass.get_places_in_area("London")
    logger.info(f"Overpass query for places in London: {len(data.get('elements', []))} results")

    # Test Wikidata
    wikidata = get_wikidata_client()
    results = wikidata.get_place_info("Amazon River")
    logger.info(f"Wikidata query for 'Amazon River': {len(results)} results")

    logger.info("API client tests completed!")
