#!/usr/bin/env python3
"""
Data Pools for Multi-Domain QA Generation

This package contains data pools for all 9 domains:
- Historical (ExpandedHistoricalPools)
- Geographical (ExpandedGeographicalPools)
- Sports (ExpandedSportsPools)
- Business (ExpandedBusinessPools)
- Biography (ExpandedBiographyPools)
- Science (ExpandedSciencePools)
- Academia (ExpandedAcademiaPools)
- Culture & Traditions (ExpandedCultureTraditionsPools)
- Arts (ExpandedArtsPools)
- Wiki Arts Categories (ExpandedWikiCulturalCategories)

Usage:
    from pools import ExpandedHistoricalPools, ExpandedGeographicalPools, ...

    # Or import all at once
    from pools import *
"""

# Import all pool classes for easy access (relative imports within package)
from .expanded_pools import ExpandedHistoricalPools
from .expanded_geographical_pools import ExpandedGeographicalPools
from .expanded_sports_pools import ExpandedSportsPools
from .expanded_business_pools import ExpandedBusinessPools
from .expanded_biography_pools import ExpandedBiographyPools
from .expanded_science_pools import ExpandedSciencePools
from .expanded_academia_pools import ExpandedAcademiaPools
from .expanded_culture_traditions_pools import ExpandedCultureTraditionsPools
from .expanded_arts_pools import ExpandedArtsPools
from .expanded_wiki_arts_categories import ExpandedWikiCulturalCategories

__all__ = [
    'ExpandedHistoricalPools',
    'ExpandedGeographicalPools',
    'ExpandedSportsPools',
    'ExpandedBusinessPools',
    'ExpandedBiographyPools',
    'ExpandedSciencePools',
    'ExpandedAcademiaPools',
    'ExpandedCultureTraditionsPools',
    'ExpandedArtsPools',
    'ExpandedWikiCulturalCategories',
]
