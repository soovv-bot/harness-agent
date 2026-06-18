#!/usr/bin/env python3
"""
RandomEntryPointGenerator - Entry Point Generator for Random Domain

This module contains the entry point generation strategies for the Historical domain.
"""

import random
import sys
import requests
import json
from pathlib import Path
from typing import Dict
from loguru import logger

# Add deepforge to path (local copy)
deepforge_path = Path(__file__).parent.parent / "deepforge"
sys.path.insert(0, str(deepforge_path))

# Import shared modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from api.caller import APICaller
from pools import ExpandedHistoricalPools
from apis.historical_apis import DBpediaClient

class HistoricalEntryPointGenerator:
    """混合随机入口点生成器 - 使用多种策略获取历史探索起点"""

    def __init__(self):
        self.strategies = {
            'llm_historical_concept': self.llm_generate_historical_concept,
            'llm_cold_historical_entity': self.llm_generate_cold_historical_entity,
            'wikipedia_history_angle': self.wikipedia_random_with_history_angle,
            'wikipedia_category': self.wikipedia_random_from_category,
            'wikipedia_subcategory': self.wikipedia_random_from_subcategory,
            'dbpedia_person': self.dbpedia_random_person,
            'dbpedia_event': self.dbpedia_random_event,
            'dbpedia_entity': self.dbpedia_random_historical_entity,
            'keyword_search': self.random_keyword_search,
            'cross_domain_historical': self.cross_domain_historical_connection,
            'temporal_exploration': self.temporal_historical_exploration,
        }

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        # Use expanded pools for better diversity
        self.expanded_pools = ExpandedHistoricalPools()

        # Wikipedia historical categories - using expanded pools
        self.history_categories = self.expanded_pools.get_all_categories()

        # Random keyword pools - using expanded pools
        # Flatten all time periods for keyword generation
        all_time_periods = []
        for era_list in self.expanded_pools.TIME_PERIODS.values():
            all_time_periods.extend(era_list)

        # Flatten all roles
        all_roles = []
        for role_list in self.expanded_pools.ROLES.values():
            all_roles.extend(role_list)

        # Flatten all events
        all_events = self.expanded_pools.EVENTS

        self.keyword_pools = {
            "eras": all_time_periods,
            "roles": all_roles,
            "actions": all_events
        }

        logger.info(f"Initialized with {len(self.history_categories)} categories, "
                   f"{len(all_time_periods)} time periods, {len(all_roles)} roles")

    def get_random_entry(self) -> Dict:
        """随机选择一种策略获取入口点"""
        strategy_name = random.choice(list(self.strategies.keys()))
        logger.info(f"Selected strategy: {strategy_name}")

        strategy_func = self.strategies[strategy_name]
        return strategy_func()

    # ========================================================================
    # Strategy 1: LLM generates random historical concept
    # ========================================================================

    def llm_generate_historical_concept(self) -> Dict:
        """用LLM随机生成历史概念作为起点 - 强调全球多样性"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        prompt = """Generate ONE random historical concept from WORLD HISTORY (3000 BC - 1950 AD).

CRITICAL DIVERSITY REQUIREMENTS:
- Mix ALL GLOBAL REGIONS equally:
  * Africa (North, South, East, West, Central)
  * Americas (North, South, Pre-Columbian, Colonial)
  * Asia (East, South, Southeast, Central, West/Middle East)
  * Europe (Western, Eastern, Northern, Southern, Balkans)
  * Oceania (Australia, Pacific Islands, Polynesia)

- Mix different time periods:
  * Ancient (3000 BC - 500 AD)
  * Medieval (500 - 1500 AD)
  * Early Modern (1500 - 1800 AD)
  * Modern (1800 - 1950 AD)

- Mix different domains:
  * Political: empires, kingdoms, treaties, revolutions
  * Military: wars, battles, rebellions, conquests
  * Cultural: art, literature, philosophy, religion
  * Economic: trade, commerce, industry, agriculture
  * Scientific: discoveries, inventions, innovations
  * Social: movements, reforms, migrations, daily life

Can be: people, events, places, movements, treaties, inventions, organizations, cultures.

AVOID overused examples: Napoleon, George Washington, Lincoln, Caesar, etc.

Examples (DO NOT use these, they illustrate the DIVERSITY we want):
- Treaty of Tordesillas (colonial Africa/Americas)
- Great Zimbabwe (medieval African kingdom)
- Majapahit Empire (Southeast Asian thalassocracy)
- Battle of Adwa (Ethiopian-Italian War)
- Haitian Revolution (Caribbean independence)
- Meiji Constitution (Japanese modernization)
- Sikh Confederacy (Punjab region)
- Ashanti Empire (West African kingdom)
- Qing Dynasty's Self-Strengthening Movement
- Songhai Empire (West African trading state)

Format: Return ONLY the concept name (2-6 words), nothing else.

Now generate ONE diverse concept:"""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}])
            concept = response.strip()

            # Clean up common LLM artifacts
            for prefix in ["The ", "A ", "An "]:
                if concept.startswith(prefix):
                    concept = concept[len(prefix):]
            concept = concept.strip('"\'.')

            if len(concept) > 100:
                concept = concept[:100]

            logger.info(f"LLM generated concept: {concept}")

            return {
                "source": "llm_historical_concept",
                "title": concept,
                "url": f"https://en.wikipedia.org/wiki/{concept.replace(' ', '_')}"
            }
        except Exception as e:
            logger.error(f"LLM generation failed: {e}, falling back to category")
            return self.wikipedia_random_from_category()

    # ========================================================================
    # Strategy 2: Wikipedia random + historical angle
    # ========================================================================

    def wikipedia_random_with_history_angle(self) -> Dict:
        """随机Wikipedia页面 + 从历史角度探索"""

        try:
            # Get random Wikipedia page
            url = "https://en.wikipedia.org/api/rest_v1/page/random/html"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            page_title = response.url.split('/')[-1].replace('_', ' ')
            logger.info(f"Random Wikipedia page: {page_title}")

            # Generate historical angle
            historical_angle = self.get_historical_angle(page_title)

            return {
                "source": "wikipedia_history_angle",
                "original_title": page_title,
                "historical_angle": historical_angle,
                "url": response.url
            }
        except Exception as e:
            logger.error(f"Wikipedia random failed: {e}, falling back to category")
            return self.wikipedia_random_from_category()

    def get_historical_angle(self, title: str) -> str:
        """为任意词条生成历史相关的探索角度"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        prompt = f"""The Wikipedia page is about "{title}".

Generate a 2-4 word phrase that connects this topic to its HISTORICAL context.

Guidelines for different types:
- For people: their era, movement, or major career event
- For things/medicines/technologies: development history, discovery, or invention
- For places: historical events, founding, or changes over time
- For organizations: founding history, key members, or evolution
- For concepts: historical development or key historical figures

Format: Return ONLY the phrase, nothing else.

Examples:
- "Aspirin" → "Aspirin discovery history"
- "Tokyo" → "Edo period Tokyo"
- "Suez Canal" → "Suez Canal construction"
- "Railways" → "Qing dynasty railways"
- "Penicillin" → "Penicillin discovery"

For "{title}", return:"""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}])
            angle = response.strip()
            angle = angle.strip('"\'')

            logger.info(f"Historical angle for '{title}': {angle}")
            return angle
        except Exception as e:
            logger.error(f"Historical angle generation failed: {e}")
            # Fallback: just use "X history"
            return f"{title} history"

    # ========================================================================
    # Strategy 3: DBpedia random person
    # ========================================================================

    def dbpedia_random_person(self) -> Dict:
        """从DBpedia随机获取历史人物"""
        client = DBpediaClient()

        # Use random offset to get different people
        offset = random.randint(0, 50000)

        sparql = f"""
        SELECT DISTINCT ?person ?name ?birthDate ?deathDate ?abstract WHERE {{
          ?person a dbo:Person .
          ?person foaf:name ?name .
          ?person dbp:birthDate ?birthDate .
          OPTIONAL {{ ?person dbp:deathDate ?deathDate }}
          OPTIONAL {{
            ?person dbo:abstract ?abstract .
            FILTER(LANG(?abstract) = "en")
          }}
          FILTER(?birthDate > "1600-01-01"^^xsd:date)
          FILTER(?birthDate < "1900-01-01"^^xsd:date)
        }}
        LIMIT 1
        OFFSET {offset}
        """

        try:
            result = client.query(sparql)
            bindings = result.get('results', {}).get('bindings', [])

            if bindings:
                person = bindings[0]
                name = person.get('name', {}).get('value', '')
                birth = person.get('birthDate', {}).get('value', '')
                death = person.get('deathDate', {}).get('value', '')
                abstract = person.get('abstract', {}).get('value', '')[:200]

                logger.info(f"DBpedia person: {name} ({birth} - {death})")

                return {
                    "source": "dbpedia_person",
                    "name": name,
                    "birthDate": birth,
                    "deathDate": death,
                    "abstract": abstract
                }
            else:
                logger.warning("No DBpedia results, trying different offset...")
                return self.dbpedia_random_person()
        except Exception as e:
            logger.error(f"DBpedia error: {e}, falling back to category")
            return self.wikipedia_random_from_category()

    # ========================================================================
    # Strategy 4: DBpedia random event
    # ========================================================================

    def dbpedia_random_event(self) -> Dict:
        """从DBpedia随机获取历史事件"""
        client = DBpediaClient()
        offset = random.randint(0, 10000)

        sparql = f"""
        SELECT DISTINCT ?event ?name ?date WHERE {{
          ?event a dbo:Event .
          ?event foaf:name ?name .
          ?event dbo:date ?date .
          FILTER(?date > "1600-01-01"^^xsd:date)
          FILTER(?date < "1950-01-01"^^xsd:date)
        }}
        LIMIT 1
        OFFSET {offset}
        """

        try:
            result = client.query(sparql)
            bindings = result.get('results', {}).get('bindings', [])

            if bindings:
                event = bindings[0]
                name = event.get('name', {}).get('value', '')
                date = event.get('date', {}).get('value', '')

                logger.info(f"DBpedia event: {name} ({date})")

                return {
                    "source": "dbpedia_event",
                    "name": name,
                    "date": date
                }
        except Exception as e:
            logger.error(f"DBpedia event error: {e}")

        # Fallback
        return self.wikipedia_random_from_category()

    # ========================================================================
    # Strategy 5: Wikipedia random from historical categories
    # ========================================================================

    def wikipedia_random_from_category(self) -> Dict:
        """从Wikipedia历史分类中随机获取页面"""

        category = random.choice(self.history_categories)
        logger.info(f"Selected category: {category}")

        try:
            # Use Wikipedia API to get category members
            api_url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": category,
                "cmlimit": 500,
                "cmtype": "page",
                "format": "json"
            }
            # Add User-Agent header to avoid 403 error
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            response = requests.get(api_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            members = data.get('query', {}).get('categorymembers', [])

            if not members:
                logger.warning(f"No members in {category}, retrying...")
                return self.wikipedia_random_from_category()

            # Random member
            selected = random.choice(members)
            page_title = selected['title']

            logger.info(f"Category member: {page_title}")

            return {
                "source": "wikipedia_category",
                "category": category,
                "title": page_title,
                "url": f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}"
            }
        except Exception as e:
            logger.error(f"Category API error: {e}")
            # Final fallback: use LLM to generate
            return self.llm_generate_historical_concept()

    # ========================================================================
    # Strategy 6: Random keyword search
    # ========================================================================

    def random_keyword_search(self) -> Dict:
        """随机关键词组合搜索 - 使用扩展池子提高多样性"""
        from src.tools.search_tools import call_serper_api

        # Use expanded pools to generate diverse combinations
        queries = self.expanded_pools.generate_search_queries()
        query = random.choice(queries)

        logger.info(f"Random search query: {query}")

        try:
            results_json = call_serper_api(query)
            results = json.loads(results_json)

            if results and len(results) > 0:
                # Random from top 5 results
                selected = random.choice(results[:5])

                return {
                    "source": "keyword_search",
                    "query": query,
                    "title": selected.get('title', ''),
                    "url": selected.get('link', ''),
                    "snippet": selected.get('snippet', '')[:200]
                }
        except Exception as e:
            logger.error(f"Keyword search failed: {e}")

        # Fallback
        return self.wikipedia_random_from_category()

    # ========================================================================
    # NEW STRATEGIES
    # ========================================================================

    def llm_generate_cold_historical_entity(self) -> Dict:
        """专门生成冷门历史实体 - 难度更高"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        prompt = """Generate ONE COLD/OBSCURE historical entity (3000 BC - 1950 AD).

CRITICAL: This must be a LESSER-KNOWN entity that requires deep historical research.
AVOID: Any famous ruler, major war, well-known empire, or household name.

PRIORITIZE:
- Minor/local rulers or kingdoms
- Obscure treaties or agreements
- Forgotten rebellions or uprisings
- Historical figures from underdocumented regions
- Defunct states or polities
- Historical trade routes or commercial leagues
- Ancient cities now lost/ruined
- Historical natural disasters with limited documentation
- Pre-colonial African/Asian/American polities (beyond famous ones)
- Medieval European minor states

Examples of COLD entities (DO NOT use):
- "Sultanate of Ifat" (medieval Ethiopian Muslim state)
- "Treaty of Nerchinsk" (1689 Sino-Russian border)
- "Kingdom of Dendi" (Songhai successor state)
- "Republic of Corsica" (18th century short-lived state)
- "War of the Golden Stool" (1900 Ashanti conflict)
- "Maji Maji Rebellion" (1905-1907 East Africa)
- "Hanseatic League Lübeck" (medieval trade city)
- "Great Lakes Mutiny" (Indian army 1857-1858)

Return ONLY the entity name (2-6 words):"""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}], temperature=1.0)
            concept = response.strip()
            concept = concept.replace("**", "").replace("*", "").strip()

            if len(concept) > 100:
                concept = concept[:100]

            logger.info(f"LLM generated COLD historical entity: {concept}")

            return {
                "source": "llm_cold_historical_entity",
                "title": concept,
                "type": "historical_entity"
            }

        except Exception as e:
            logger.error(f"Cold entity generation failed: {e}")
            return self.llm_generate_historical_concept()

    def wikipedia_random_from_subcategory(self) -> Dict:
        """从历史相关分类及其子分类中递归随机选择页面"""
        try:
            # 随机选择主分类
            category = random.choice(self.history_categories)

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
                "type": "historical_entity"
            }

        except Exception as e:
            logger.error(f"Wikipedia subcategory error: {e}")
            return self.llm_generate_historical_concept()

    def dbpedia_random_historical_entity(self) -> Dict:
        """从DBpedia随机获取多种类型的历史实体"""
        from apis.historical_apis import DBpediaClient

        client = DBpediaClient()

        # 随机选择实体类型
        entity_types = ['battle', 'treaty', 'kingdom', 'movement', 'document']
        entity_type = random.choice(entity_types)

        offset = random.randint(0, 5000)

        try:
            if entity_type == 'battle':
                sparql = f"""
                SELECT DISTINCT ?battle ?name ?date WHERE {{
                  {{ ?battle a dbo:MilitaryConflict . }}
                  UNION {{ ?battle a dbo:Battle . }}
                  ?battle foaf:name ?name .
                  OPTIONAL {{ ?battle dbo:date ?date }}
                }}
                LIMIT 1
                OFFSET {offset}
                """
                result = client.query(sparql)
                bindings = result.get('results', {}).get('bindings', [])
                if bindings:
                    entity = bindings[0]
                    return {
                        "source": "dbpedia_battle",
                        "title": entity.get('name', {}).get('value', ''),
                        "date": entity.get('date', {}).get('value', ''),
                        "type": "battle"
                    }

            elif entity_type == 'treaty':
                sparql = f"""
                SELECT DISTINCT ?treaty ?name WHERE {{
                  ?treaty a dbo:Treaty .
                  ?treaty foaf:name ?name .
                }}
                LIMIT 1
                OFFSET {offset}
                """
                result = client.query(sparql)
                bindings = result.get('results', {}).get('bindings', [])
                if bindings:
                    entity = bindings[0]
                    return {
                        "source": "dbpedia_treaty",
                        "title": entity.get('name', {}).get('value', ''),
                        "type": "treaty"
                    }

            elif entity_type == 'kingdom':
                sparql = f"""
                SELECT DISTINCT ?kingdom ?name WHERE {{
                  {{ ?kingdom a dbo:Kingdom . }}
                  UNION {{ ?kingdom a dbo:Country . }}
                  UNION {{ ?kingdom a dbo:HistoricPlace . }}
                  ?kingdom foaf:name ?name .
                  FILTER(CONTAINS(LCASE(STR(?name)), "kingdom") ||
                         CONTAINS(LCASE(STR(?name)), "empire") ||
                         CONTAINS(LCASE(STR(?name)), "sultanate"))
                }}
                LIMIT 1
                OFFSET {offset}
                """
                result = client.query(sparql)
                bindings = result.get('results', {}).get('bindings', [])
                if bindings:
                    entity = bindings[0]
                    return {
                        "source": "dbpedia_kingdom",
                        "title": entity.get('name', {}).get('value', ''),
                        "type": "kingdom"
                    }

            elif entity_type == 'movement':
                sparql = f"""
                SELECT DISTINCT ?movement ?name WHERE {{
                  ?movement a dbo:SocialMovement .
                  ?movement foaf:name ?name .
                }}
                LIMIT 1
                OFFSET {offset}
                """
                result = client.query(sparql)
                bindings = result.get('results', {}).get('bindings', [])
                if bindings:
                    entity = bindings[0]
                    return {
                        "source": "dbpedia_movement",
                        "title": entity.get('name', {}).get('value', ''),
                        "type": "movement"
                    }

            else:  # document
                sparql = f"""
                SELECT DISTINCT ?doc ?name WHERE {{
                  {{ ?doc a dbo:Document . }}
                  UNION {{ ?doc a dbo:WrittenWork . }}
                  ?doc foaf:name ?name .
                  FILTER(?name < "1950-01-01"^^xsd:date)
                }}
                LIMIT 1
                OFFSET {offset}
                """
                result = client.query(sparql)
                bindings = result.get('results', {}).get('bindings', [])
                if bindings:
                    entity = bindings[0]
                    return {
                        "source": "dbpedia_document",
                        "title": entity.get('name', {}).get('value', ''),
                        "type": "document"
                    }

        except Exception as e:
            logger.error(f"DBpedia entity error: {e}")

        return self.dbpedia_random_person()

    def cross_domain_historical_connection(self) -> Dict:
        """生成历史与其他领域的交叉点入口"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        cross_domains = {
            "science": ["scientific discoveries", "inventions", "medical breakthroughs", "scientific revolution"],
            "religion": ["religious movements", "church history", "missionary activities", "religious conflicts"],
            "economics": ["economic history", "trade routes", "monetary systems", "industrial revolution"],
            "art": ["art movements", "artistic patrons", "cultural history", "architecture history"],
            "military": ["military technology", "warfare evolution", "fortifications", "naval history"],
            "social": ["social movements", "demographic changes", "migration patterns", "urbanization"],
        }

        domain = random.choice(list(cross_domains.keys()))
        topic = random.choice(cross_domains[domain])

        prompt = f"""Generate a specific, researchable historical topic about {topic}.

Requirements:
- Must be specific enough for multi-hop historical research
- Should require connecting multiple historical sources
- Avoid obvious/well-known topics
- Focus on less explored angles

Examples:
- "effect of printing press on Reformation"
- "silk road economic impact Central Asia"
- "Hussite wars military innovations"
- "medieval guild systems economic role"

Generate ONE topic (3-8 words):"""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}], temperature=0.9)
            concept = response.strip()
            concept = concept.replace("**", "").replace("*", "").strip()

            if len(concept) > 150:
                concept = concept[:150]

            logger.info(f"Cross-domain historical topic: {concept} ({domain})")

            return {
                "title": concept,
                "source": "cross_domain_historical",
                "domain": domain,
                "type": "historical_entity"
            }

        except Exception as e:
            logger.error(f"Cross-domain generation failed: {e}")
            return self.llm_generate_historical_concept()

    def temporal_historical_exploration(self) -> Dict:
        """按特定时代探索历史"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        eras = [
            ("Ancient Near East", "3000-500 BC: Mesopotamia, Egypt, Persia, Levant"),
            ("Classical Antiquity", "500 BC-500 AD: Greece, Rome, Han China"),
            ("Post-Classical", "500-1500 AD: Medieval Europe, Islamic Golden Age, Tang/Song China"),
            ("Early Modern", "1500-1800: Renaissance, Age of Discovery, Enlightenment"),
            ("Industrial Era", "1750-1900: Industrial Revolution, colonialism, nationalism"),
            ("Pre-Columbian Americas", "3000 BC-1500 AD: Olmec, Maya, Aztec, Inca"),
            ("Medieval Africa", "500-1500 AD: Ghana, Mali, Songhai, Great Zimbabwe"),
            ("Imperial China", "221 BC-1911 AD: Qin through Qing dynasties"),
            ("Southeast Asian Civilizations", "500-1500 AD: Srivijaya, Khmer, Majapahit"),
        ]

        era_name, era_context = random.choice(eras)

        prompt = f"""Generate a specific historical research topic from the {era_name} ({era_context}).

Requirements:
- Must be a specific event, figure, or phenomenon from this era
- Should require historical research
- Avoid well-documented famous topics
- Focus on lesser-known aspects

Examples:
- "Songhai Empire Askia Muhammad reign"
- "Kamakura shogunate legal reforms"
- "Ayyubid dynasty architectural achievements"
- "Srivijaya maritime trade control"

Generate ONE topic (3-7 words):"""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}], temperature=0.9)
            concept = response.strip()
            concept = concept.replace("**", "").replace("*", "").strip()

            if len(concept) > 150:
                concept = concept[:150]

            logger.info(f"Temporal historical topic: {concept} ({era_name})")

            return {
                "title": concept,
                "source": "temporal_historical",
                "era": era_name,
                "type": "historical_entity"
            }

        except Exception as e:
            logger.error(f"Temporal exploration failed: {e}")
            return self.llm_generate_historical_concept()


# ============================================================================
# Main Pipeline
# ============================================================================
