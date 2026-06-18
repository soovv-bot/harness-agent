#!/usr/bin/env python3
"""
Pipeline Entry Point Generators

This package contains entry point generators for all domains.

Usage:
    from pipelines import (
        HistoricalEntryPointGenerator,
        GeographicalEntryPointGenerator,
        SportsEntryPointGenerator,
        BusinessEntryPointGenerator,
        BiographyEntryPointGenerator,
        ScienceEntryPointGenerator,
        AcademiaEntryPointGenerator,
        CultureTraditionsEntryPointGenerator,
        ArtsEntryPointGenerator,
    )

    # Or use the factory
    from pipelines import create_generator
    generator = create_generator('historical')
"""

from .historical import HistoricalEntryPointGenerator
from .geographical import GeographicalEntryPointGenerator
from .sports import SportsEntryPointGenerator
from .business import BusinessEntryPointGenerator
from .biography import BiographyEntryPointGenerator
from .science import ScienceEntryPointGenerator
from .academia import AcademiaEntryPointGenerator
from .culture_traditions import CultureTraditionsEntryPointGenerator
from .arts import ArtsEntryPointGenerator

__all__ = [
    'HistoricalEntryPointGenerator',
    'GeographicalEntryPointGenerator',
    'SportsEntryPointGenerator',
    'BusinessEntryPointGenerator',
    'BiographyEntryPointGenerator',
    'ScienceEntryPointGenerator',
    'AcademiaEntryPointGenerator',
    'CultureTraditionsEntryPointGenerator',
    'ArtsEntryPointGenerator',
    'create_generator',
]

# Domain mapping for factory
DOMAIN_GENERATORS = {
    'historical': HistoricalEntryPointGenerator,
    'geographical': GeographicalEntryPointGenerator,
    'sports': SportsEntryPointGenerator,
    'business': BusinessEntryPointGenerator,
    'biography': BiographyEntryPointGenerator,
    'science': ScienceEntryPointGenerator,
    'academia': AcademiaEntryPointGenerator,
    'culture_traditions': CultureTraditionsEntryPointGenerator,
    'arts': ArtsEntryPointGenerator,
}


def create_generator(domain: str):
    """
    Factory function to create an entry point generator for a domain.

    Args:
        domain: Domain name (historical, geographical, sports, etc.)

    Returns:
        EntryPointGenerator instance

    Raises:
        ValueError: If domain is not supported
    """
    domain = domain.lower()
    if domain not in DOMAIN_GENERATORS:
        available = ", ".join(DOMAIN_GENERATORS.keys())
        raise ValueError(f"Unsupported domain: {domain}. Available: {available}")

    generator_class = DOMAIN_GENERATORS[domain]
    return generator_class()


def list_domains():
    """List all supported domains."""
    return list(DOMAIN_GENERATORS.keys())
