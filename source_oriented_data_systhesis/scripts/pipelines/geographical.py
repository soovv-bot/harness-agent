#!/usr/bin/env python3
"""
GeographicalEntryPointGenerator - Entry Point Generator for Geographical Domain

This module contains the entry point generation strategies for the Geographical domain.
"""

import random
import sys
import requests
from pathlib import Path
from typing import Dict
from loguru import logger

# Add deepforge to path (local copy)
deepforge_path = Path(__file__).parent.parent / "deepforge"
sys.path.insert(0, str(deepforge_path))

# Import shared modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from api.caller import APICaller
from pools import ExpandedGeographicalPools
from apis.historical_apis import DBpediaClient, GeoNamesClient

class GeographicalEntryPointGenerator:
    """
    地理数据入口点生成器 - 使用扩展池子

    使用多种策略生成地理相关的探索入口点
    覆盖全球所有大洲、地貌类型、气候带和生物群落
    """

    def __init__(self):
        # Use expanded pools for better diversity
        self.expanded_pools = ExpandedGeographicalPools()

        self.strategies = {
            'llm_geographical_concept': self.llm_generate_geographical_concept,
            'llm_cold_geographical_entity': self.llm_generate_cold_geographical_entity,
            'wikipedia_geographical_angle': self.wikipedia_random_with_geographical_angle,
            'wikipedia_geographical_category': self.wikipedia_random_from_category,
            'wikipedia_subcategory': self.wikipedia_random_from_subcategory,
            'random_geographical_keyword': self.random_geographical_keyword_search,
            'dbpedia_geographical_feature': self.dbpedia_random_geographical_feature,
            'dbpedia_city': self.dbpedia_random_city,
            'geonames_random_place': self.geonames_random_place,
            'cross_domain_geographical': self.cross_domain_geographical_connection,
            'regional_exploration': self.regional_geographical_exploration,
            'climate_biome_exploration': self.climate_biome_exploration,
        }

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        # Use expanded Wikipedia categories
        self.GEOGRAPHICAL_CATEGORIES = self.expanded_pools.get_all_categories()

        # Initialize API clients
        self.dbpedia_client = DBpediaClient()
        self.geonames_client = GeoNamesClient()

        logger.info(f"Initialized with {len(self.GEOGRAPHICAL_CATEGORIES)} categories and {len(self.strategies)} strategies")

    def generate_random_entry(self) -> Dict:
        """使用随机策略生成入口点"""
        strategy_name = random.choice(list(self.strategies.keys()))
        strategy_func = self.strategies[strategy_name]
        return strategy_func()

    def llm_generate_geographical_concept(self) -> Dict:
        """使用LLM生成多样化地理概念 - 强调全球覆盖"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        prompt = """Generate ONE random geographical concept from AROUND THE WORLD.

CRITICAL GLOBAL DIVERSITY REQUIREMENTS:
- Mix ALL CONTINENTS equally:
  * Africa (North, South, East, West, Central)
  * Asia (East, South, Southeast, Central, West/Middle East)
  * Europe (Western, Eastern, Northern, Southern)
  * Americas (North, South, Central)
  * Oceania (Australia, Pacific Islands, New Zealand)
  * Polar regions (Arctic, Antarctic, Subarctic, Subantarctic)

- Mix different feature types:
  * Landforms: mountains, plateaus, plains, valleys, canyons, deserts
  * Water bodies: rivers, lakes, seas, oceans, straits, deltas, wetlands
  * Coastal: islands, archipelagos, peninsulas, capes, bays, fjords
  * Ice/Snow: glaciers, ice caps, tundra, permafrost regions
  * Forest: rainforests, savannas, woodlands, taiga

- Mix different scales:
  * Major features (Himalayas, Amazon Basin)
  * Medium features (individual mountains, rivers, lakes)
  * Minor features (valleys, capes, islands)

AVOID overused examples: Mount Everest, Nile River, Amazon Rainforest, Grand Canyon, etc.

Examples (DO NOT use these, they illustrate the DIVERSITY we want):
- "Okavango Delta" (Botswana wetland)
- "Karakoram Range" (Pakistan mountain range)
- "Scandinavian Peninsula" (Northern Europe peninsula)
- "Patagonian Desert" (Argentina cold desert)
- "Malay Archipelago" (Southeast Asian island chain)
- "Lake Baikal" (Russian rift lake)
- "Serengeti Plain" (Tanzanian grassland)
- "Great Barrier Reef" (Australian coral reef system)
- "Atacama Desert" (Chilean hyper-arid desert)
- "Labrador Peninsula" (Canadian subarctic region)

Format: Return ONLY the geographical concept name (2-6 words), nothing else.

Now generate ONE diverse concept:"""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}])
            concept = response.strip()

            # Clean up any markdown formatting
            concept = concept.replace("**", "").replace("*", "").strip()

            if len(concept) > 100:
                concept = concept[:100]

            logger.info(f"LLM generated geographical concept: {concept}")

            return {
                "title": concept,
                "source": "llm_geographical_concept",
                "type": "geographical_feature"
            }

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            # Fallback to expanded pools
            all_regions = self.expanded_pools.get_all_regions()
            all_features = self.expanded_pools.get_all_features()
            region = random.choice(all_regions)
            feature = random.choice(all_features)
            fallback = f"{region} {feature}"
            return {
                "title": fallback,
                "source": "llm_geographical_concept",
                "type": "geographical_feature"
            }

    def wikipedia_random_with_geographical_angle(self) -> Dict:
        """
        从随机维基百科页面提取地理角度
        """
        try:
            # Get random Wikipedia page
            url = "https://en.wikipedia.org/api/rest_v1/page/random/summary"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            original_title = data.get("title", "")
            logger.info(f"Random Wikipedia page: {original_title}")

            # Extract geographical angle
            geographical_angle = self.get_geographical_angle(original_title)

            logger.info(f"  Geographical angle: {geographical_angle}")

            return {
                "title": geographical_angle,
                "source": "wikipedia_geographical_angle",
                "original_title": original_title,
                "type": "geographical_feature"
            }

        except Exception as e:
            logger.error(f"Wikipedia random error: {e}")
            # Fallback
            return {
                "title": "Geographical features",
                "source": "wikipedia_geographical_angle",
                "type": "geographical_feature"
            }

    def get_geographical_angle(self, title: str) -> str:
        """
        为任意维基百科页面提取地理角度

        任何话题都可能有其地理维度：
        - 历史事件 → 发生地点
        - 人物 → 相关地点（出生地、活动区域）
        - 物种/自然 → 地理分布
        - 文化 → 地理起源
        """
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        prompt = f"""The Wikipedia page is about "{title}".

Generate a 2-5 word phrase that connects this topic to its GEOGRAPHICAL context.

Think about:
- Where did this event happen?
- Where is this person/place/thing located?
- What is the geographical distribution?
- What region is it associated with?

Examples:
- "Aspirin" → "Bayer pharmaceutical headquarters location"
- "Napoleon" → "Napoleonic Empire territories"
- "Coffee" → "Coffee belt geographical regions"
- "Buddhism" → "Buddhist geographical spread"
- "Titanic" → "Titanic wreck location"
- "Internet" → "Global internet infrastructure"

Generate ONLY the 2-5 word geographical phrase, nothing else."""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}])
            angle = response.strip()
            angle = angle.replace("**", "").replace("*", "").strip()

            if len(angle) > 100:
                angle = angle[:100]

            return angle if angle else f"Geography of {title}"

        except Exception as e:
            logger.debug(f"Geographical angle extraction error: {e}")
            return f"Geography of {title}"

    def wikipedia_random_from_category(self) -> Dict:
        """从地理相关分类中随机选择页面"""
        category = random.choice(self.GEOGRAPHICAL_CATEGORIES)

        try:
            # Get pages from category using Wikipedia API
            api_url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": category,  # Category already includes "Category:" prefix
                "cmlimit": 100,
                "cmtype": "page",
                "format": "json"
            }

            response = requests.get(api_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            members = data.get("query", {}).get("categorymembers", [])

            # Filter out subcategories
            pages = [m for m in members if m.get("ns") == 0]

            if not pages:
                logger.warning(f"No pages found in category {category}")
                return self.wikipedia_random_from_category()

            # Select random page
            page = random.choice(pages)
            title = page.get("title", "")

            logger.info(f"Selected from category '{category}': {title}")

            return {
                "title": title,
                "source": "wikipedia_geographical_category",
                "category": category,
                "type": "geographical_feature"
            }

        except Exception as e:
            logger.error(f"Wikipedia category error: {e}")
            # Fallback to LLM generation
            return self.llm_generate_geographical_concept()

    def random_geographical_keyword_search(self) -> Dict:
        """使用扩展池子生成多样化地理关键词组合"""
        # Use expanded pools to generate diverse combinations
        queries = self.expanded_pools.generate_search_queries()
        search_term = random.choice(queries)

        logger.info(f"Geographical keyword search: {search_term}")

        return {
            "title": search_term,
            "source": "random_geographical_keyword",
            "type": "geographical_feature"
        }

    def dbpedia_random_geographical_feature(self) -> Dict:
        """
        从DBpedia随机获取地理特征

        随机选择以下类型之一:
        - 山脉 (Mountains)
        - 岛屿 (Islands)
        - 水体 (Bodies of water: lakes, seas, rivers)
        """
        # Randomly select feature type
        feature_types = ['mountains', 'islands', 'bodies_of_water']
        feature_type = random.choice(feature_types)

        try:
            if feature_type == 'mountains':
                results = self.dbpedia_client.query_mountains(limit=50)
                if results:
                    place = random.choice(results)
                    name = place.get('name', {}).get('value', '')
                    elevation = place.get('elevation', {}).get('value', '')

                    logger.info(f"DBpedia mountain: {name} (elevation: {elevation})")

                    return {
                        "title": name,
                        "source": "dbpedia_geographical_feature",
                        "feature_type": "mountain",
                        "elevation": elevation,
                        "type": "geographical_feature"
                    }

            elif feature_type == 'islands':
                results = self.dbpedia_client.query_islands(limit=50)
                if results:
                    place = random.choice(results)
                    name = place.get('name', {}).get('value', '')
                    area = place.get('area', {}).get('value', '')

                    logger.info(f"DBpedia island: {name} (area: {area})")

                    return {
                        "title": name,
                        "source": "dbpedia_geographical_feature",
                        "feature_type": "island",
                        "area": area,
                        "type": "geographical_feature"
                    }

            else:  # bodies_of_water
                results = self.dbpedia_client.query_bodies_of_water(limit=50)
                if results:
                    place = random.choice(results)
                    name = place.get('name', {}).get('value', '')

                    logger.info(f"DBpedia water body: {name}")

                    return {
                        "title": name,
                        "source": "dbpedia_geographical_feature",
                        "feature_type": "water_body",
                        "type": "geographical_feature"
                    }

        except Exception as e:
            logger.error(f"DBpedia geographical feature error: {e}")

        # Fallback to LLM generation
        return self.llm_generate_geographical_concept()

    def geonames_random_place(self) -> Dict:
        """
        从GeoNames随机获取地点

        使用多种策略:
        - 随机大陆的随机城市
        - 随机大陆的随机山脉
        - 随机大陆的随机水体
        """
        # Continent codes for GeoNames
        continents = ['AF', 'AS', 'EU', 'NA', 'OC', 'SA']
        continent = random.choice(continents)

        # Feature classes:
        # T: Mountain/Hill/Rock
        # H: Hydrographic (water bodies)
        # P: Populated place (cities, villages)
        # L: Areas (parks, reserves)
        feature_classes = ['T', 'H', 'P']
        feature_class = random.choice(feature_classes)

        try:
            place = self.geonames_client.get_random_by_continent(
                continent=continent,
                feature_class=feature_class
            )

            if place:
                name = place.get('name', '')
                country = place.get('countryCode', '')
                feature_class_name = place.get('fclName', '')
                lat = place.get('lat', '')
                lng = place.get('lng', '')

                logger.info(f"GeoNames {feature_class_name}: {name}, {country}")

                return {
                    "title": name,
                    "source": "geonames_random_place",
                    "feature_class": feature_class,
                    "country": country,
                    "lat": lat,
                    "lng": lng,
                    "type": "geographical_feature"
                }

        except Exception as e:
            logger.error(f"GeoNames error: {e}")

        # Fallback to LLM generation
        return self.llm_generate_geographical_concept()

    # ========================================================================
    # NEW STRATEGIES
    # ========================================================================

    def llm_generate_cold_geographical_entity(self) -> Dict:
        """专门生成冷门地理实体 - 难度更高"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        prompt = """Generate ONE COLD/OBSCURE geographical feature or location.

CRITICAL: This must be a LESSER-KNOWN geographical entity that requires deep research.
AVOID: Any famous mountain, major river, well-known city, major capital, or household name.

PRIORITIZE:
- Remote minor islands or archipelagos
- Obscure mountain ranges or individual peaks
- Minor rivers, tributaries, or headwaters
- Small peninsulas, capes, or bays
- Remote plateaus, valleys, or canyons
- Minor seas, straits, or gulfs
- Obscure deserts or wetlands
- Little-known geographical formations
- Remote polar locations
- Underwater features (seamounts, trenches)

Examples of COLD entities (DO NOT use):
- "Kerguelen Islands" (Indian Ocean remote islands)
- "Transylvanian Plateau" (Romanian high plateau)
- "Mackenzie Mountains" (Canadian Northwest Territories)
- "Kamchatka Peninsula" (Russian Far East peninsula)
- "Wallace Line" (Indonesian biogeographical boundary)
- "Sierra Madre Occidental" (Mexican mountain range)
- "Gulf of Tadjoura" (Djiboutian gulf)
- "Kivu Rift Valley" (East African rift section)
- "Yucatan Karst" (Mexican limestone plateau)
- "Flores Sea" (Indonesian sea)

Return ONLY the entity name (2-6 words):"""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}], temperature=1.0)
            concept = response.strip()
            concept = concept.replace("**", "").replace("*", "").strip()

            if len(concept) > 100:
                concept = concept[:100]

            logger.info(f"LLM generated COLD geographical entity: {concept}")

            return {
                "title": concept,
                "source": "llm_cold_geographical_entity",
                "type": "geographical_feature"
            }

        except Exception as e:
            logger.error(f"Cold entity generation failed: {e}")
            return self.llm_generate_geographical_concept()

    def wikipedia_random_from_subcategory(self) -> Dict:
        """从地理相关分类及其子分类中递归随机选择页面"""
        try:
            # 随机选择主分类
            category = random.choice(self.GEOGRAPHICAL_CATEGORIES)

            # 首先尝试获取子分类
            api_url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": category,
                "cmlimit": 500,
                "cmtype": "subcat",
                "format": "json"
            }

            response = requests.get(api_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            subcategories = [m for m in data.get("query", {}).get("categorymembers", []) if m.get("ns") == 14]

            # 如果有子分类，70%概率使用子分类
            if subcategories and random.random() > 0.3:
                subcat = random.choice(subcategories)
                category = subcat["title"]
                logger.info(f"Deep dive into subcategory: {category}")

            # 然后获取页面
            params["cmtype"] = "page"
            params["cmtitle"] = category
            response = requests.get(api_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            pages = [m for m in data.get("query", {}).get("categorymembers", []) if m.get("ns") == 0]

            if not pages:
                logger.warning(f"No pages found in category {category}")
                return self.wikipedia_random_from_subcategory()

            page = random.choice(pages)
            title = page.get("title", "")

            logger.info(f"Selected from '{category}': {title}")

            return {
                "title": title,
                "source": "wikipedia_subcategory",
                "category": category,
                "type": "geographical_feature"
            }

        except Exception as e:
            logger.error(f"Wikipedia subcategory error: {e}")
            return self.llm_generate_geographical_concept()

    def dbpedia_random_city(self) -> Dict:
        """从DBpedia随机获取城市"""
        try:
            results = self.dbpedia_client.query_cities(min_population=50000, limit=50)
            if results:
                city = random.choice(results)
                name = city.get('name', {}).get('value', '')
                population = city.get('population', {}).get('value', '')
                country = city.get('country', {}).get('value', '')

                logger.info(f"DBpedia city: {name}, {country} (pop: {population})")

                return {
                    "title": name,
                    "source": "dbpedia_city",
                    "population": population,
                    "country": country,
                    "type": "geographical_feature"
                }

        except Exception as e:
            logger.error(f"DBpedia city error: {e}")

        return self.llm_generate_geographical_concept()

    def cross_domain_geographical_connection(self) -> Dict:
        """生成地理与其他领域的交叉点入口"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        cross_domains = {
            "history": ["historical sites", "battlefield locations", "ancient trade routes", "colonial boundaries"],
            "biology": ["biomes", "ecosystems", "species distribution", "biodiversity hotspots"],
            "geology": ["tectonic features", "volcanic regions", "fault lines", "mineral deposits"],
            "climate": ["climate zones", "weather patterns", "precipitation regions", "temperature gradients"],
            "anthropology": ["cultural regions", "language distribution", "indigenous territories", "migration routes"],
            "economics": ["economic zones", "trade corridors", "resource distribution", "transportation networks"],
        }

        domain = random.choice(list(cross_domains.keys()))
        topic = random.choice(cross_domains[domain])

        prompt = f"""Generate a specific, researchable geographical topic about {topic}.

Requirements:
- Must be specific enough for multi-hop geographical research
- Should require connecting multiple geographical sources
- Avoid obvious/well-known topics
- Focus on less explored geographical angles

Examples:
- "Sahel desertification patterns 1980-2020"
- "Andean altiplano agricultural zones"
- "Baltic Sea hypoxia affected areas"
- "Mekong tributary fish species distribution"

Generate ONE topic (3-8 words):"""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}], temperature=0.9)
            concept = response.strip()
            concept = concept.replace("**", "").replace("*", "").strip()

            if len(concept) > 150:
                concept = concept[:150]

            logger.info(f"Cross-domain geographical topic: {concept} ({domain})")

            return {
                "title": concept,
                "source": "cross_domain_geographical",
                "domain": domain,
                "type": "geographical_feature"
            }

        except Exception as e:
            logger.error(f"Cross-domain generation failed: {e}")
            return self.llm_generate_geographical_concept()

    def regional_geographical_exploration(self) -> Dict:
        """按特定区域深度探索地理"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        regions = [
            ("Central Asia", "Kazakhstan, Kyrgyzstan, Tajikistan, Turkmenistan, Uzbekistan steppes and mountains"),
            ("Caucasus", "Georgia, Armenia, Azerbaijan mountainous region between Black and Caspian Seas"),
            ("Horn of Africa", "Ethiopia, Somalia, Eritrea, Djibouti peninsula and rift valley"),
            ("Andean Altiplano", "Peru, Bolivia, Chile high plateau region"),
            ("Kalahari Basin", "Botswana, Namibia, South Africa semi-arid savanna"),
            ("Amazon Basin", "South American rainforest and river system across 9 countries"),
            ("Gulf of Guinea", "West African coastal islands and mangroves"),
            ("Wallacea", "Indonesian islands between Borneo and New Guinea, biogeographical boundary"),
            ("Patagonia", "Southern Argentina and Chile, steppes, glaciers, and fjords"),
            ("Scandinavia", "Norway, Sweden, Denmark, Finland mountains, fjords, and taiga"),
        ]

        region_name, region_context = random.choice(regions)

        prompt = f"""Generate a specific geographical research topic from {region_name} ({region_context}).

Requirements:
- Must be a specific geographical feature or phenomenon from this region
- Should require regional geographical research
- Avoid well-documented famous topics
- Focus on lesser-known aspects

Examples:
- "Central Asia endorheic basin lakes"
- "Caucasus alpine meadows elevation zones"
- "Horn of Africa rift valley lakes"
- "Andean altiplano salt flats"

Generate ONE topic (3-7 words):"""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}], temperature=0.9)
            concept = response.strip()
            concept = concept.replace("**", "").replace("*", "").strip()

            if len(concept) > 150:
                concept = concept[:150]

            logger.info(f"Regional geographical topic: {concept} ({region_name})")

            return {
                "title": concept,
                "source": "regional_geographical",
                "region": region_name,
                "type": "geographical_feature"
            }

        except Exception as e:
            logger.error(f"Regional exploration failed: {e}")
            return self.llm_generate_geographical_concept()

    def climate_biome_exploration(self) -> Dict:
        """探索气候和生物群落"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        climate_zones = [
            ("Tropical Rainforest", "equatorial constant heat and rainfall, Amazon, Congo, Indonesia"),
            ("Savanna", "tropical wet-dry seasonal, African Serengeti, Brazilian Cerrado"),
            ("Desert", "arid <250mm annual rainfall, Sahara, Arabian, Gobi, Atacama"),
            ("Mediterranean", "wet winter dry summer, California, Chile, South Africa, Australia"),
            ("Temperate Forest", "deciduous/coniferous四季分明, Europe, Eastern North America, East Asia"),
            ("Grassland/Steppe", "semi-arid temperate, Eurasian Steppe, North American Prairies, Pampas"),
            ("Taiga/Boreal Forest", "subarctic coniferous, Canada, Russia, Scandinavia"),
            ("Tundra", "arctic treeless permafrost, Northern Canada, Siberia, Greenland"),
            ("Mediterranean California", "chaparral shrubland coastal California"),
            ("Monsoon Asia", "seasonal rainfall South/Southeast Asia"),
        ]

        zone_name, zone_context = random.choice(climate_zones)

        prompt = f"""Generate a specific geographical research topic about {zone_name} climate/biome ({zone_context}).

Requirements:
- Must be a specific feature or phenomenon of this climate zone
- Should require climatological or ecological research
- Avoid well-documented famous topics
- Focus on lesser-known aspects

Examples:
- "Amazon rainforest dry season canopy changes"
- "Saharan desert oasis distribution patterns"
- "Mediterranean chaparral fire adaptation"
- "Boreal forest permafrost thaw impacts"

Generate ONE topic (3-7 words):"""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}], temperature=0.9)
            concept = response.strip()
            concept = concept.replace("**", "").replace("*", "").strip()

            if len(concept) > 150:
                concept = concept[:150]

            logger.info(f"Climate/biome topic: {concept} ({zone_name})")

            return {
                "title": concept,
                "source": "climate_biome",
                "climate_zone": zone_name,
                "type": "geographical_feature"
            }

        except Exception as e:
            logger.error(f"Climate/biome exploration failed: {e}")
            return self.llm_generate_geographical_concept()

