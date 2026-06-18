#!/usr/bin/env python3
"""
Shared API Clients for Multiple Domains

This module provides API clients that are used across multiple domains.
It re-exports the shared clients from historical_apis.py for convenience.

Shared Clients:
- WikidataClient - Wikidata REST API
- DBpediaClient - DBpedia SPARQL endpoint
- GeoNamesClient - GeoNames geographical API
- ArchiveClient - Internet Archive API
- OyezClient - Oyez Supreme Court API

Usage:
    from apis.shared import DBpediaClient, GeoNamesClient, WikidataClient
"""

# Import shared clients from historical_apis
# These are used by multiple domains (historical, geographical, sports, arts, etc.)
from .historical_apis import (
    APIError,
    BaseClient,
    WikidataClient,
    DBpediaClient,
    GeoNamesClient,
    ArchiveClient,
    OyezClient,
)

__all__ = [
    'APIError',
    'BaseClient',
    'WikidataClient',
    'DBpediaClient',
    'GeoNamesClient',
    'ArchiveClient',
    'OyezClient',
]
