#!/usr/bin/env python3
"""
Expanded Geographical Data Pools

This module provides expanded, diverse pools for geographical data generation,
designed to minimize regional and feature bias.

Coverage:
- All continents and major regions
- All climate zones and biomes
- Diverse geographical features
- Human geography concepts
"""

from typing import List, Dict, Set
import random

# ============================================================================
# EXPANDED GEOGRAPHICAL POOLS
# ============================================================================

class ExpandedGeographicalPools:
    """
    大规模地理数据池 - 覆盖全球、全地貌、多类型
    Designed to minimize bias and maximize diversity
    """

    # ========== CONTINENTS AND REGIONS (详细地域划分) ==========

    CONTINENTS = {
        "africa": {
            "regions": [
                "North Africa", "West Africa", "East Africa", "Central Africa", "Southern Africa",
                "Sahel", "Sahara", "Congo Basin", "Kalahari", "Ethiopian Highlands", "Swahili Coast",
                "Maghreb", "Guinea Coast", "Gold Coast", "Slave Coast", "Horn of Africa", "Great Lakes"
            ],
            "countries": [
                "Egypt", "Libya", "Tunisia", "Algeria", "Morocco", "Sudan", "South Sudan",
                "Ethiopia", "Kenya", "Tanzania", "Uganda", "Rwanda", "Burundi",
                "Nigeria", "Ghana", "Mali", "Senegal", "Ivory Coast", "Benin",
                "DRC", "Congo", "Cameroon", "Gabon", "Zimbabwe", "Zambia", "South Africa",
                "Madagascar", "Mauritius", "Seychelles", "Comoros"
            ]
        },
        "asia": {
            "regions": [
                "East Asia", "Southeast Asia", "South Asia", "Central Asia", "West Asia", "North Asia",
                "Chinese Peninsula", "Indochina", "Malay Archipelago", "Indian Subcontinent",
                "Fertile Crescent", "Anatolia", "Caucasus", "Steppe", "Tibetan Plateau", "Himalayas",
                "Ganges Delta", "Mekong Delta", "Yellow River Basin", "Yangtze Basin"
            ],
            "countries": [
                "China", "Japan", "Korea", "Mongolia", "Taiwan",
                "Vietnam", "Thailand", "Cambodia", "Laos", "Myanmar", "Malaysia", "Singapore",
                "Indonesia", "Philippines", "Brunei", "East Timor",
                "India", "Pakistan", "Bangladesh", "Sri Lanka", "Nepal", "Bhutan", "Maldives",
                "Kazakhstan", "Uzbekistan", "Turkmenistan", "Kyrgyzstan", "Tajikistan",
                "Turkey", "Iran", "Iraq", "Syria", "Lebanon", "Jordan", "Israel", "Saudi Arabia",
                "UAE", "Oman", "Yemen", "Armenia", "Georgia", "Azerbaijan"
            ]
        },
        "europe": {
            "regions": [
                "Western Europe", "Eastern Europe", "Northern Europe", "Southern Europe", "Central Europe",
                "British Isles", "Scandinavia", "Iberian Peninsula", "Italian Peninsula", "Balkan Peninsula",
                "Alps", "Pyrenees", "Carpathians", "Apennines", "Dinaric Alps",
                "Mediterranean", "Baltic Region", "North Sea", "Atlantic Europe"
            ],
            "countries": [
                "Britain", "Ireland", "France", "Germany", "Netherlands", "Belgium", "Luxembourg",
                "Switzerland", "Austria", "Spain", "Portugal", "Italy", "Greece",
                "Poland", "Czech Republic", "Slovakia", "Hungary", "Romania", "Bulgaria",
                "Serbia", "Croatia", "Slovenia", "Bosnia", "Montenegro", "North Macedonia", "Albania",
                "Norway", "Sweden", "Denmark", "Finland", "Iceland",
                "Ukraine", "Belarus", "Moldova", "Russia", "Baltic States"
            ]
        },
        "north_america": {
            "regions": [
                "New England", "Mid-Atlantic", "South", "Midwest", "Great Plains", "Southwest", "West",
                "Appalachia", "Ozarks", "Rocky Mountains", "Sierra Nevada", "Cascades",
                "Great Lakes", "Great Basin", "Mojave", "Sonoran", "Chihuahuan",
                "Canadian Shield", "Canadian Prairies", "Canadian Arctic", "Maritimes"
            ],
            "countries": [
                "United States", "Canada", "Mexico",
                "Guatemala", "Belize", "El Salvador", "Honduras", "Nicaragua", "Costa Rica", "Panama"
            ]
        },
        "south_america": {
            "regions": [
                "Andes", "Amazon Basin", "Guianas", "Brazilian Highlands", "Pantanal",
                "Pampas", "Patagonia", "Atacama", "Gran Chaco", "Tierra del Fuego",
                "Caribbean South America", "Pacific Coast", "Atlantic Coast"
            ],
            "countries": [
                "Colombia", "Venezuela", "Guyana", "Suriname", "French Guiana",
                "Brazil", "Ecuador", "Peru", "Bolivia", "Paraguay", "Uruguay", "Argentina", "Chile"
            ]
        },
        "oceania": {
            "regions": [
                "Australasia", "Melanesia", "Micronesia", "Polynesia",
                "Outback", "Great Dividing Range", "New Zealand Highlands",
                "Pacific Islands", "Coral Sea", "Tasman Sea", "South Pacific"
            ],
            "countries": [
                "Australia", "New Zealand", "Papua New Guinea", "Fiji", "Solomon Islands",
                "Vanuatu", "New Caledonia", "Samoa", "Tonga", "Tahiti", "Kiribati",
                "Marshall Islands", "Micronesia", "Palau", "Nauru", "Tuvalu"
            ]
        },
        "polar": {
            "regions": [
                "Arctic", "Antarctic", "Subarctic", "Subantarctic",
                "Arctic Ocean", "Southern Ocean", "Greenland", "Svalbard", "Iceland"
            ],
            "territories": [
                "Greenland", "Iceland", "Svalbard", "Faroe Islands", "Jan Mayen",
                "Northern Canada", "Alaska", "Siberia", "Scandinavian Arctic",
                "Antarctic Peninsula", "East Antarctica", "West Antarctica", "Ross Sea", "Weddell Sea"
            ]
        }
    }

    # ========== NATURAL FEATURES (详细地貌特征) ==========

    NATURAL_FEATURES = {
        "mountainous": [
            # Mountain types
            "mountain", "mountain range", "peak", "summit", "ridge", "crest", "cliff", "crag",
            "volcano", "caldera", "crater", "lava field", "volcanic arc",
            "plateau", "mesa", "butte", "escarpment", "canyon", "gorge", "valley",
            "pass", "col", "saddle", "notch", "gap"
        ],
        "water_features": [
            # Large water bodies
            "ocean", "sea", "gulf", "bay", "strait", "channel", "sound", "fjord",
            "lake", "lagoon", "pond", "pool", "reservoir",
            "river", "stream", "creek", "tributary", "branch", "waterway",
            # Water features
            "waterfall", "cascade", "rapids", "whitewater", "spring", "geyser",
            "delta", "estuary", "marsh", "swamp", "wetland", "bog", "fen", "moor",
            # Coastal
            "beach", "coast", "shore", "shoreline", "coastline", "cliff", "bluff",
            "headland", "promontory", "peninsula", "isthmus", "cape", "point"
        ],
        "islands": [
            "island", "isle", "islet", "archipelago", "atoll", "reef",
            "barrier island", "coral island", "volcanic island", "continental island",
            "keys", "cay", "atoll", "motu"
        ],
        "plains_and_plateaus": [
            "plain", "prairie", "steppe", "savanna", "grassland", "meadow", "field",
            "plateau", "highlands", "tableland", "mesa", "butte",
            "basin", "depression", "hollow", "valley"
        ],
        "desert_and_dry": [
            "desert", "dune", "sand sea", "erg", "dry lake", "playa", "salt flat", "saltpan",
            "semiarid", "steppe", "scrub", "thorn forest", "veld"
        ],
        "forest": [
            "forest", "woodland", "jungle", "rainforest", "cloud forest", "dry forest",
            "taiga", "boreal forest", "coniferous forest", "deciduous forest",
            "mixed forest", "temperate rainforest", "mangrove", "grove", "thicket"
        ],
        "ice_and_snow": [
            "glacier", "ice sheet", "ice cap", "ice field", "ice shelf", "iceberg",
            "snowfield", "firn", "permafrost", "frozen ground", "cryosphere"
        ],
        "coastal": [
            "coast", "shore", "beach", "shoreline", "coastline", "tidal zone",
            "intertidal", "estuary", "lagoon", "harbor", "port", "anchorage",
            "maritime", "coastal plain", "continental shelf", "reef", "atoll"
        ]
    }

    # ========== CLIMATE ZONES (气候带) ==========

    CLIMATE_ZONES = [
        # Tropical
        "tropical rainforest", "tropical monsoon", "tropical savanna", "tropical wet and dry",
        # Dry
        "hot desert", "cold desert", "semiarid", "steppe",
        # Temperate
        "humid subtropical", "marine west coast", "Mediterranean", "humid continental",
        "subarctic", "dry summer", "dry winter",
        # Continental
        "warm summer continental", "hot summer continental", "subarctic continental",
        # Polar
        "tundra", "ice cap", "polar", "subpolar",
        # Highland
        "highland climate", "alpine climate", "mountain climate"
    ]

    # ========== BIOMES (生物群落) ==========

    BIOMES = [
        # Terrestrial
        "tundra", "taiga", "temperate coniferous forest", "temperate deciduous forest",
        "temperate grassland", "chaparral", "desert", "tropical rainforest",
        "tropical seasonal forest", "tropical grassland", "savanna", "flooded grassland",
        "montane grassland", "mangrove",
        # Aquatic
        "freshwater", "marine", "coral reef", "kelp forest", "estuary",
        "intertidal zone", "hydrothermal vent", "cold seep"
    ]

    # ========== HUMAN GEOGRAPHY (人文地理) ==========

    HUMAN_GEOGRAPHY = {
        "settlements": [
            "city", "metropolis", "megacity", "conurbation", "megalopolis",
            "town", "village", "hamlet", "commune",
            "capital", "county seat", "port", "harbor", "gateway city",
            "border town", "frontier town", "outpost", "settlement"
        ],
        "urban": [
            "downtown", "central business district", "suburb", "exurb", "urban area",
            "metropolitan area", "agglomeration", "urban cluster",
            "industrial district", "commercial district", "residential area"
        ],
        "economic": [
            "trade route", "trade corridor", "commercial hub", "market town",
            "port city", "naval base", "fortress", "garrison",
            "mining town", "railroad town", "company town"
        ],
        "cultural": [
            "cultural region", "cultural landscape", "heritage site", "sacred site",
            "pilgrimage site", "historical district", "old town", "medieval quarter"
        ],
        "political": [
            "border", "boundary", "frontier", "territory", "province", "region",
            "state", "nation", "country", "sovereign state", "dependency",
            "autonomous region", "special administrative region", "protectorate"
        ]
    }

    # ========== SPECIFIC GEOGRAPHICAL FEATURES (著名地标) ==========

    FAMOUS_FEATURES = {
        "mountain_ranges": [
            "Himalayas", "Karakoram", "Hindu Kush", "Pamirs", "Kunlun Mountains", "Tian Shan",
            "Altai Mountains", "Ural Mountains", "Caucasus Mountains", "Alps", "Apennines",
            "Pyrenees", "Carpathians", "Dinaric Alps", "Balkan Mountains", "Scandes",
            "Rocky Mountains", "Sierra Nevada", "Cascades", "Appalachians", "Andes",
            "Atlas Mountains", "Ethiopian Highlands", "Drakensberg", "Mount Kenya",
            "Kamchatka Peninsula", "Verkhoyansk Range", "Stanovoy Range"
        ],
        "rivers": [
            "Nile", "Amazon", "Yangtze", "Mississippi", "Yenisei", "Yellow River",
            "Ob-Irtysh", "Paraná", "Congo", "Amur", "Lena", "Mackenzie",
            "Mekong", "Volga", "Zambezi", "Niger", "Ganges", "Danube", "Orinoco",
            "Euphrates", "Tigris", "Indus", "Brahmaputra", "Salween", "Chao Phraya",
            "Irrawaddy", "Murray-Darling", "Pearl River", "Xi Jiang", "Han River"
        ],
        "lakes": [
            "Caspian Sea", "Lake Superior", "Lake Victoria", "Lake Huron", "Lake Michigan",
            "Lake Baikal", "Great Slave Lake", "Lake Malawi", "Great Bear Lake",
            "Lake Tanganyika", "Lake Nicaragua", "Lake Titicaca", "Lake Chad",
            "Lake Onega", "Lake Ladoga", "Lake Vänern", "Lake Winnipeg",
            "Lake Athabasca", "Reindeer Lake", "Lake Nipigon", "Lake Manitoba"
        ],
        "deserts": [
            "Sahara", "Arabian Desert", "Gobi Desert", "Taklamakan", "Karakum",
            "Kyzylkum", "Thar Desert", "Great Victoria Desert", "Sonoran Desert",
            "Kalahari", "Namib Desert", "Atacama", "Patagonian Desert",
            "Great Basin Desert", "Mojave Desert", "Chihuahuan Desert", "Syrian Desert"
        ],
        "islands": [
            "Greenland", "New Guinea", "Borneo", "Madagascar", "Baffin Island",
            "Sumatra", "Honshu", "Great Britain", "Victoria Island", "Ellesmere Island",
            "Celebes", "Java", "North Island", "South Island", "New Zealand",
            "Philippines", "Japan", "Malay Archipelago", "Indonesian Archipelago",
            "Caribbean Islands", "Bahamas", "Greater Antilles", "Lesser Antilles",
            "Canary Islands", "Azores", "Madeira", "Cape Verde", "Seychelles",
            "Maldives", "Fiji", "Solomon Islands", "New Caledonia", "Hawaii"
        ],
        "peninsulas": [
            "Arabian Peninsula", "Indian Peninsula", "Indochina Peninsula", "Malay Peninsula",
            "Korean Peninsula", "Kamchatka Peninsula", "Scandinavian Peninsula",
            "Iberian Peninsula", "Italian Peninsula", "Balkan Peninsula", "Jutland",
            "Crimean Peninsula", "Peloponnese", "Sinai Peninsula", "Florida Peninsula"
        ]
    }

    # ========== WIKIPEDIA GEOGRAPHICAL CATEGORIES (扩展分类) ==========

    WIKIPEDIA_CATEGORIES = {
        # By continent/region
        "africa": [
            "Category:Geography_of_Africa", "Category:Geography_of_North_Africa",
            "Category:Geography_of_West_Africa", "Category:Geography_of_East_Africa",
            "Category:Geography_of_Central_Africa", "Category:Geography_of_Southern_Africa",
            # Removed: Category:Landforms_of_Africa (0 pages)
            "Category:Mountains_of_Africa",
            "Category:Rivers_of_Africa", "Category:Lakes_of_Africa", "Category:Deserts_of_Africa"
        ],
        "asia": [
            "Category:Geography_of_Asia", "Category:Geography_of_East_Asia",
            "Category:Geography_of_Southeast_Asia", "Category:Geography_of_South_Asia",
            "Category:Geography_of_Central_Asia", "Category:Geography_of_West_Asia",
            "Category:Landforms_of_Asia", "Category:Mountains_of_Asia",
            "Category:Rivers_of_Asia", "Category:Islands_of_Asia"
        ],
        "europe": [
            "Category:Geography_of_Europe", "Category:Geography_of_the_European_Union",
            # Removed: Category:Geography_of_Western_Europe (0 pages)
            # Removed: Category:Geography_of_Eastern_Europe (0 pages)
            # Removed: Category:Geography_of_Northern_Europe (0 pages)
            # Removed: Category:Geography_of_Southern_Europe (0 pages)
            "Category:Landforms_of_Europe", "Category:Mountains_of_Europe",
            "Category:Rivers_of_Europe", "Category:Lakes_of_Europe"
        ],
        "north_america": [
            "Category:Geography_of_North_America", "Category:Geography_of_Canada",
            "Category:Geography_of_the_United_States", "Category:Geography_of_Mexico",
            "Category:Geography_of_Central_America", "Category:Geography_of_the_Caribbean",
            "Category:Landforms_of_North_America", "Category:Mountains_of_North_America"
        ],
        "south_america": [
            "Category:Geography_of_South_America", "Category:Geography_of_Brazil",
            "Category:Geography_of_Argentina", "Category:Geography_of_Chile",
            "Category:Geography_of_Peru", "Category:Geography_of_Colombia",
            "Category:Landforms_of_South_America", "Category:Andes"
        ],
        "oceania": [
            "Category:Geography_of_Oceania", "Category:Geography_of_Australia",
            "Category:Geography_of_New_Zealand",
            # Removed: Category:Geography_of_the_Pacific_Islands (0 pages)
            "Category:Geography_of_Polynesia", "Category:Geography_of_Micronesia",
            "Category:Geography_of_Melanesia"
        ],
        "polar": [
            "Category:Geography_of_the_Arctic", "Category:Geography_of_Antarctica",
            "Category:Geography_of_Greenland",
            # Removed: Category:Arctic_oceanography (0 pages)
            "Category:Glaciers", "Category:Permafrost"
        ],
        # By feature type
        "landforms": [
            "Category:Landforms", "Category:Mountains", "Category:Mountain_ranges",
            "Category:Volcanoes", "Category:Plateaus", "Category:Plains",
            "Category:Valleys", "Category:Canyons_and_gorges", "Category:Deserts"
        ],
        "water": [
            "Category:Bodies_of_water", "Category:Oceans", "Category:Seas",
            "Category:Rivers", "Category:Lakes", "Category:Waterfalls",
            "Category:Wetlands", "Category:Coastal_and_oceanic_landforms"
        ],
        "islands": [
            "Category:Islands",
            # Removed: Category:Archipelagos (0 pages)
            "Category:Atolls",
            "Category:Islands_of_Africa", "Category:Islands_of_Asia",
            "Category:Islands_of_Europe", "Category:Islands_of_North_America",
            "Category:Islands_of_South_America", "Category:Islands_of_Oceania"
        ],
        "human": [
            "Category:Human_geography", "Category:Urban_geography",
            "Category:Population_density",
            # Removed: Category:Settlements (0 pages)
            "Category:Capitals",
            # Removed: Category:Port_cities (0 pages)
            "Category:Border_crossings"
        ],
        # By climate/biome
        "climate": [
            "Category:Climate", "Category:Climate_zones", "Category:Biomes"
            # Removed: Category:Tropical_geography (0 pages)
            # Removed: Category:Desert_geography (0 pages)
            # Removed: Category:Polar_geography (0 pages)
            # Removed: Category:Mountain_geography (0 pages)
        ]
    }

    @classmethod
    def get_all_categories(cls) -> List[str]:
        """获取所有Wikipedia地理分类"""
        all_cats = []
        for category_list in cls.WIKIPEDIA_CATEGORIES.values():
            all_cats.extend(category_list)
        return all_cats

    @classmethod
    def get_all_regions(cls) -> List[str]:
        """获取所有地区"""
        all_regions = []
        for continent_data in cls.CONTINENTS.values():
            all_regions.extend(continent_data.get("regions", []))
            all_regions.extend(continent_data.get("countries", []))
        return all_regions

    @classmethod
    def get_all_features(cls) -> List[str]:
        """获取所有地理特征"""
        all_features = []
        for feature_list in cls.NATURAL_FEATURES.values():
            all_features.extend(feature_list)
        return all_features

    @classmethod
    def generate_random_combination(cls) -> Dict[str, str]:
        """
        生成随机的地理探索组合
        Returns: dict with continent, region, feature, climate, biome
        """
        # Random continent
        continent = random.choice(list(cls.CONTINENTS.keys()))
        continent_data = cls.CONTINENTS[continent]
        region = random.choice(continent_data.get("regions", []) +
                                continent_data.get("countries", []))

        # Random feature
        feature_type = random.choice(list(cls.NATURAL_FEATURES.keys()))
        feature = random.choice(cls.NATURAL_FEATURES[feature_type])

        # Random climate
        climate = random.choice(cls.CLIMATE_ZONES)

        # Random biome
        biome = random.choice(cls.BIOMES)

        return {
            "continent": continent,
            "region": region,
            "feature_type": feature_type,
            "feature": feature,
            "climate": climate,
            "biome": biome
        }

    @classmethod
    def generate_search_queries(cls) -> List[str]:
        """生成多样化的搜索查询组合"""
        combinations = []

        # 1. Region + Feature (e.g., "Alps mountains", "Nile river")
        continent = random.choice(list(cls.CONTINENTS.keys()))
        continent_data = cls.CONTINENTS[continent]
        region = random.choice(continent_data.get("regions", []))
        feature_type = random.choice(list(cls.NATURAL_FEATURES.keys()))
        feature = random.choice(cls.NATURAL_FEATURES[feature_type])
        combinations.append(f"{region} {feature}")

        # 2. Region + Climate (e.g., "Amazon tropical rainforest")
        continent = random.choice(list(cls.CONTINENTS.keys()))
        continent_data = cls.CONTINENTS[continent]
        region = random.choice(continent_data.get("regions", []) +
                                continent_data.get("countries", []) +
                                continent_data.get("territories", []))
        climate = random.choice(cls.CLIMATE_ZONES)
        combinations.append(f"{region} {climate}")

        # 3. Modifier + Feature (e.g., "Great Sahara", "Northern Himalayas")
        modifiers = ["Northern", "Southern", "Eastern", "Western", "Central",
                     "Great", "Little", "Upper", "Lower", "New", "Old"]
        feature_type = random.choice(list(cls.NATURAL_FEATURES.keys()))
        feature = random.choice(cls.NATURAL_FEATURES[feature_type])
        combinations.append(f"{random.choice(modifiers)} {feature}")

        # 4. Region + Specific Feature (e.g., "Africa Kilimanjaro")
        continent = random.choice(list(cls.CONTINENTS.keys()))
        famous = random.choice(list(cls.FAMOUS_FEATURES.keys()))
        if cls.FAMOUS_FEATURES[famous]:
            specific = random.choice(cls.FAMOUS_FEATURES[famous])
            combinations.append(specific)

        # 5. Climate + Feature (e.g., "tropical rainforest")
        climate = random.choice(["tropical", "temperate", "polar", "arid", "semi-arid"])
        feature_type = random.choice(["rainforest", "forest", "desert", "grassland", "tundra"])
        combinations.append(f"{climate} {feature_type}")

        # 6. Biome + Region (e.g., "coral reef Pacific")
        biome = random.choice(cls.BIOMES)
        continent = random.choice(list(cls.CONTINENTS.keys()))
        combinations.append(f"{biome} {continent}")

        return combinations


# ============================================================================
# STATISTICS AND TESTING
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("EXPANDED GEOGRAPHICAL POOLS - STATISTICS")
    print("=" * 70)

    pools = ExpandedGeographicalPools()

    print(f"\nContinents: {len(pools.CONTINENTS)}")
    for continent, data in pools.CONTINENTS.items():
        regions = len(data.get("regions", []))
        countries = len(data.get("countries", []))
        print(f"  - {continent}: {regions} regions, {countries} countries")

    print(f"\nNatural Features: {sum(len(v) for v in pools.NATURAL_FEATURES.values())}")
    for feature_type, features in pools.NATURAL_FEATURES.items():
        print(f"  - {feature_type}: {len(features)}")

    print(f"\nClimate Zones: {len(pools.CLIMATE_ZONES)}")
    print(f"Biomes: {len(pools.BIOMES)}")

    print(f"\nHuman Geography: {sum(len(v) for v in pools.HUMAN_GEOGRAPHY.values())}")
    for hg_type, items in pools.HUMAN_GEOGRAPHY.items():
        print(f"  - {hg_type}: {len(items)}")

    print(f"\nFamous Features:")
    for feature_type, features in pools.FAMOUS_FEATURES.items():
        print(f"  - {feature_type}: {len(features)}")

    print(f"\nWikipedia Categories (verified working): {len(pools.get_all_categories())}")

    print("\n" + "=" * 70)
    print("SAMPLE RANDOM COMBINATIONS")
    print("=" * 70)

    for i in range(5):
        combo = pools.generate_random_combination()
        print(f"\n[{i+1}] {combo['region']} | {combo['feature']} | "
              f"{combo['climate']} | {combo['biome']}")

    print("\n" + "=" * 70)
    print("SAMPLE SEARCH QUERIES")
    print("=" * 70)

    for i in range(5):
        queries = pools.generate_search_queries()
        for j, query in enumerate(queries):
            print(f"{j+1}. {query}")
        print()
