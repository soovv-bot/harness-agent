#!/usr/bin/env python3
"""
API Clients for Multi-Domain QA Generation

This package contains API clients for all 9 domains.

Usage:
    # Import shared APIs directly
    from apis.shared import DBpediaClient, GeoNamesClient, WikidataClient

    # Import domain-specific APIs
    from apis.historical_apis import ArchiveClient
    from apis.geographical_apis import NominatimClient

    # Or use the package as namespace
    from apis import historical_apis, geographical_apis
"""

# ============================================================================
# Shared APIs (used by multiple domains)
# ============================================================================

from .shared import (
    APIError,
    BaseClient,
    WikidataClient,
    DBpediaClient,
    GeoNamesClient,
    ArchiveClient,
    OyezClient,
)

# ============================================================================
# Export all shared APIs at package level
# ============================================================================

__all__ = [
    # Shared classes
    'APIError',
    'BaseClient',
    'WikidataClient',
    'DBpediaClient',
    'GeoNamesClient',
    'ArchiveClient',
    'OyezClient',
    # Domain API modules
    'historical_apis',
    'geographical_apis',
    'sports_apis',
    'business_apis',
    'biography_apis',
    'science_apis',
    'academia_apis',
    'culture_traditions_apis',
    'arts_apis',
    # Scraper modules
    'sports_scrapers',
    'business_websites',
    'arts_websites',
]
