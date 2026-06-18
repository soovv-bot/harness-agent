#!/usr/bin/env python3
"""
CultureTraditionsEntryPointGenerator - Entry Point Generator for Culturetraditions Domain

This module contains the entry point generation strategies for the Culturetraditions domain.
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
from pools import ExpandedCultureTraditionsPools
from apis.culture_traditions_apis import UNESCOClient, WikipediaCultureClient, WikidataCultureClient, DBpediaCultureClient, HolidayAPIClient

class CultureTraditionsEntryPointGenerator:
    """
    文化传统数据入口点生成器 - 使用扩展池子

    使用多种策略生成文化传统相关的探索入口点
    覆盖全球文化传统：节日、习俗、饮食、艺术等
    """

    def __init__(self):
        self.expanded_pools = ExpandedCultureTraditionsPools()

        # Initialize all strategies
        self.strategies = {
            # UNESCO strategies (2)
            'unesco_heritage': self.unesco_heritage_site,
            'unesco_intangible': self.unesco_intangible_heritage,

            # Wikidata strategies (6)
            'wikidata_festival': self.wikidata_traditional_festival,
            'wikidata_clothing': self.wikidata_traditional_clothing,
            'wikidata_food': self.wikidata_traditional_food,
            'wikidata_music': self.wikidata_traditional_music,
            'wikidata_practice': self.wikidata_cultural_practice,
            'wikidata_folk_art': self.wikidata_folk_art,

            # Basic strategies (3)
            'llm_culture_concept': self.llm_generate_culture_concept,
            'wikipedia_culture_category': self.wikipedia_random_from_category,
            'random_culture_keyword': self.random_culture_keyword_search,

            # Entity-based (2)
            'traditional_festival': self.traditional_festival_pool,
            'cultural_practice': self.cultural_practice_pool,

            # Cuisine & Arts (2)
            'traditional_food': self.traditional_food_pool,
            'traditional_music': self.traditional_music_pool,
        }

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        self.CULTURE_CATEGORIES = self.expanded_pools.get_all_categories()

        # Initialize API clients
        self.unesco_client = UNESCOClient()
        self.wikipedia_client = WikipediaCultureClient()
        self.wikidata_client = WikidataCultureClient()
        self.dbpedia_client = DBpediaCultureClient()
        self.holiday_client = HolidayAPIClient()

        num_strategies = len(self.strategies)
        logger.info(f"Initialized with {len(self.CULTURE_CATEGORIES)} categories and {num_strategies} strategies")

    def generate_random_entry(self) -> Dict:
        """使用随机策略生成入口点"""
        strategy_name = random.choice(list(self.strategies.keys()))
        strategy_func = self.strategies[strategy_name]
        return strategy_func()

    # ========================================================================
    # UNESCO Strategies
    # ========================================================================

    def unesco_heritage_site(self) -> Dict:
        """从UNESCO随机获取世界遗产"""
        try:
            site = self.unesco_client.get_random_heritage_site()

            if site:
                name = site.get('name', '')
                country = site.get('country', '')
                heritage_type = site.get('heritage_type', '')

                # Generate search concept
                if heritage_type:
                    search_concept = f"{name} {heritage_type}"
                else:
                    search_concept = name

                logger.info(f"UNESCO heritage: {name} ({country})")

                return {
                    "title": search_concept,
                    "source": "unesco_heritage",
                    "site_id": site.get('id', ''),
                    "name": name,
                    "country": country,
                    "type": "heritage_site"
                }

        except Exception as e:
            logger.error(f"UNESCO heritage error: {e}")

        # Fallback
        return self.llm_generate_culture_concept()

    def unesco_intangible_heritage(self) -> Dict:
        """从UNESCO随机获取非物质文化遗产"""
        try:
            heritage = self.unesco_client.get_random_intangible_heritage()

            if heritage:
                name = heritage.get('name', '')
                country = heritage.get('country', '')
                category = heritage.get('category', '')

                # Generate search concept
                if category:
                    search_concept = f"{name} intangible heritage"
                else:
                    search_concept = name

                logger.info(f"UNESCO intangible: {name} ({country})")

                return {
                    "title": search_concept,
                    "source": "unesco_intangible",
                    "item_id": heritage.get('id', ''),
                    "name": name,
                    "country": country,
                    "category": category,
                    "type": "intangible_heritage"
                }

        except Exception as e:
            logger.error(f"UNESCO intangible error: {e}")

        # Fallback
        return self.llm_generate_culture_concept()

    # ========================================================================
    # Wikidata Strategies
    # ========================================================================

    def wikidata_traditional_festival(self) -> Dict:
        """从Wikidata随机获取传统节日"""
        try:
            festivals = self.wikidata_client.get_traditional_festivals()

            if festivals:
                festival = random.choice(festivals)
                name = festival.get('name', '')
                country = festival.get('origin', '')
                festival_type = festival.get('type', '')

                # Generate search concept
                if festival_type:
                    search_concept = f"{name} festival"
                else:
                    search_concept = f"{name} {country} festival" if country else name

                logger.info(f"Wikidata festival: {name}")

                return {
                    "title": search_concept,
                    "source": "wikidata_festival",
                    "name": name,
                    "country": country,
                    "type": "festival"
                }

        except Exception as e:
            logger.error(f"Wikidata festival error: {e}")

        # Fallback to pool
        return self.traditional_festival_pool()

    def wikidata_traditional_clothing(self) -> Dict:
        """从Wikidata随机获取传统服饰"""
        try:
            clothing = self.wikidata_client.get_traditional_clothing()

            if clothing:
                item = random.choice(clothing)
                name = item.get('name', '')
                origin = item.get('origin', '')
                item_type = item.get('type', '')

                # Generate search concept
                if origin:
                    search_concept = f"{name} {origin}"
                elif item_type:
                    search_concept = f"{item_type} {name}"
                else:
                    search_concept = name

                logger.info(f"Wikidata clothing: {name}")

                return {
                    "title": search_concept,
                    "source": "wikidata_clothing",
                    "name": name,
                    "origin": origin,
                    "type": "clothing"
                }

        except Exception as e:
            logger.error(f"Wikidata clothing error: {e}")

        # Fallback
        return self.llm_generate_culture_concept()

    def wikidata_traditional_food(self) -> Dict:
        """从Wikidata随机获取传统食物"""
        try:
            foods = self.wikidata_client.get_traditional_foods()

            if foods:
                food = random.choice(foods)
                name = food.get('name', '')
                origin = food.get('origin', '')
                course = food.get('course', '')

                # Generate search concept
                if origin:
                    search_concept = f"{name} {origin} cuisine"
                elif course:
                    search_concept = f"{name} {course}"
                else:
                    search_concept = f"{name} traditional food"

                logger.info(f"Wikidata food: {name}")

                return {
                    "title": search_concept,
                    "source": "wikidata_food",
                    "name": name,
                    "origin": origin,
                    "course": course,
                    "type": "traditional_food"
                }

        except Exception as e:
            logger.error(f"Wikidata food error: {e}")

        # Fallback to pool
        return self.traditional_food_pool()

    def wikidata_traditional_music(self) -> Dict:
        """从Wikidata随机获取传统音乐"""
        try:
            music = self.wikidata_client.get_traditional_music()

            if music:
                item = random.choice(music)
                name = item.get('name', '')
                origin = item.get('origin', '')

                # Generate search concept
                if origin:
                    search_concept = f"{name} {origin}"
                else:
                    search_concept = f"{name} traditional music"

                logger.info(f"Wikidata music: {name}")

                return {
                    "title": search_concept,
                    "source": "wikidata_music",
                    "name": name,
                    "origin": origin,
                    "type": "traditional_music"
                }

        except Exception as e:
            logger.error(f"Wikidata music error: {e}")

        # Fallback to pool
        return self.traditional_music_pool()

    def wikidata_cultural_practice(self) -> Dict:
        """从Wikidata随机获取文化实践"""
        try:
            practices = self.wikidata_client.get_cultural_practices()

            if practices:
                practice = random.choice(practices)
                name = practice.get('name', '')
                origin = practice.get('origin', '')

                # Generate search concept
                if origin:
                    search_concept = f"{name} {origin}"
                else:
                    search_concept = f"{name} cultural practice"

                logger.info(f"Wikidata practice: {name}")

                return {
                    "title": search_concept,
                    "source": "wikidata_practice",
                    "name": name,
                    "origin": origin,
                    "type": "cultural_practice"
                }

        except Exception as e:
            logger.error(f"Wikidata practice error: {e}")

        # Fallback to pool
        return self.cultural_practice_pool()

    def wikidata_folk_art(self) -> Dict:
        """从Wikidata随机获取民间艺术"""
        try:
            arts = self.wikidata_client.get_folk_art()

            if arts:
                art = random.choice(arts)
                name = art.get('name', '')
                origin = art.get('origin', '')
                art_type = art.get('type', '')

                # Generate search concept
                if art_type:
                    search_concept = f"{art_type} {name}"
                elif origin:
                    search_concept = f"{name} {origin}"
                else:
                    search_concept = f"{name} folk art"

                logger.info(f"Wikidata folk art: {name}")

                return {
                    "title": search_concept,
                    "source": "wikidata_folk_art",
                    "name": name,
                    "origin": origin,
                    "type": "folk_art"
                }

        except Exception as e:
            logger.error(f"Wikidata folk art error: {e}")

        # Fallback to pool
        return self.llm_generate_culture_concept()

    # ========================================================================
    # Basic Strategies
    # ========================================================================

    def llm_generate_culture_concept(self) -> Dict:
        """使用LLM生成多样文化概念"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        prompt = """Generate ONE random culture or tradition concept from ANY world culture.

CRITICAL DIVERSITY REQUIREMENTS:
- Mix ALL WORLD REGIONS equally:
  * East Asia: Chinese, Japanese, Korean, Vietnamese, Thai, Indonesian, Filipino
  * South Asia: Indian, Pakistani, Bangladeshi, Sri Lankan, Nepalese
  * Middle East: Arab, Persian, Turkish, Jewish, Kurdish
  * Europe: British, French, German, Italian, Spanish, Russian, Nordic
  * Americas: Native American, Latin American, North American
  * Africa: North African, West African, East African, Southern African
  * Oceania: Polynesian, Melanesian, Micronesian, Australian Aboriginal

- Mix TYPES OF CULTURAL ELEMENTS equally:
  * Festivals: Christmas, Diwali, Eid, Lunar New Year, Thanksgiving
  * Traditional clothing: Kimono, Sari, Hanbok, Kilt, Poncho
  * Traditional food: Sushi, Curry, Tacos, Pasta, Dumplings
  * Traditional music: Flamenco, Tango, Samba, Folk songs
  * Traditional dance: Ballet, Bhangra, Hula, Irish dance
  * Customs: Wedding customs, Funeral rites, Coming of age ceremonies
  * Architecture: Temples, Churches, Mosques, Shrines
  * Art forms: Calligraphy, Pottery, Weaving, Wood carving
  * Folklore: Mythology, Legends, Fairy tales, Folk heroes
  * Religious practices: Prayer, Meditation, Pilgrimage, Fasting

- Mix CATEGORIES equally:
  * Life cycle customs: Birth, Coming of age, Marriage, Death
  * Daily customs: Greetings, Dining etiquette, Social norms
  * Seasonal customs: Spring festivals, Harvest festivals, Winter celebrations
  * Religious practices: Prayer, Rituals, Ceremonies, Pilgrimage
  * Artistic traditions: Music, Dance, Crafts, Architecture

DIVERSE Examples:
- "Japanese tea ceremony chanoyu"
- "Diwali festival of lights India"
- "Mexican Day of the DeadDia de los Muertos"
- "Chinese Lunar New Year traditions"
- "Scottish Highland games"
- "Indian wedding ceremony rituals"
- "Moroccan mint tea ceremony"
- "Balinese Hindu cremation ceremony"
- "Swedish midsummer festival"
- "Korean hanbok traditional clothing"
- "Italian slow food movement"
- "Polynesian hula dance"
- "Turkish carpet weaving"
- "Native American powwow gathering"
- "Ethiopian coffee ceremony"
- "Norwegian stave church architecture"
- "Thai Songkran water festival"

Format: Return ONLY the cultural/tradition concept name (2-5 words), nothing else.

Now generate ONE diverse culture concept:"""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}])
            concept = response.strip()

            # Clean up
            for prefix in ["The ", "A ", "An "]:
                if concept.startswith(prefix):
                    concept = concept[len(prefix):]
            concept = concept.strip('"\'.')

            if len(concept) > 100:
                concept = concept[:100]

            logger.info(f"LLM generated culture concept: {concept}")

            return {
                "title": concept,
                "source": "llm_culture_concept",
                "type": "culture_concept"
            }

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            # Fallback to pools
            all_festivals = self.expanded_pools.get_all_festivals()
            all_clothing = self.expanded_pools.get_all_clothing()
            all_items = all_festivals + all_clothing
            concept = random.choice(all_items)
            return {
                "title": concept,
                "source": "llm_culture_concept",
                "type": "culture_concept"
            }

    def wikipedia_random_from_category(self) -> Dict:
        """从文化相关分类中随机选择页面"""
        category = random.choice(self.CULTURE_CATEGORIES)

        try:
            api_url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": category,
                "cmlimit": 100,
                "cmtype": "page",
                "format": "json"
            }

            response = requests.get(api_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            members = data.get("query", {}).get("categorymembers", [])
            pages = [m for m in members if m.get("ns") == 0]

            if pages:
                page = random.choice(pages)
                title = page.get("title", "")

                logger.info(f"Selected from category '{category}': {title}")

                return {
                    "title": title,
                    "source": "wikipedia_culture_category",
                    "category": category,
                    "type": "culture_topic"
                }

        except Exception as e:
            logger.error(f"Wikipedia category error: {e}")

        # Fallback
        return self.llm_generate_culture_concept()

    def random_culture_keyword_search(self) -> Dict:
        """使用扩展池子生成多样化文化关键词组合"""
        queries = self.expanded_pools.generate_search_queries()
        search_term = random.choice(queries)

        logger.info(f"Culture keyword search: {search_term}")

        return {
            "title": search_term,
            "source": "random_culture_keyword",
            "type": "culture_concept"
        }

    # ========================================================================
    # Entity-Based Strategies
    # ========================================================================

    def traditional_festival_pool(self) -> Dict:
        """从传统节日池中随机选择"""
        try:
            all_festivals = self.expanded_pools.get_all_festivals()
            festival = random.choice(all_festivals)

            # Add culture context
            cultures = random.choice(self.expanded_pools.KEYWORD_COMPONENTS['cultures'])
            search_concept = f"{festival} {cultures}"

            logger.info(f"Traditional festival: {festival}")

            return {
                "title": search_concept,
                "source": "traditional_festival",
                "festival": festival,
                "type": "festival"
            }

        except Exception as e:
            logger.error(f"Traditional festival pool error: {e}")

        # Fallback
        return self.llm_generate_culture_concept()

    def cultural_practice_pool(self) -> Dict:
        """从文化实践池中随机选择"""
        try:
            # Get from life cycle, daily, or seasonal customs
            all_customs = []
            for custom_list in self.expanded_pools.CULTURAL_PRACTICES.values():
                all_customs.extend(custom_list)

            custom = random.choice(all_customs)

            # Add culture context
            cultures = random.choice(self.expanded_pools.KEYWORD_COMPONENTS['cultures'])
            search_concept = f"{custom} {cultures}"

            logger.info(f"Cultural practice: {custom}")

            return {
                "title": search_concept,
                "source": "cultural_practice",
                "practice": custom,
                "type": "cultural_practice"
            }

        except Exception as e:
            logger.error(f"Cultural practice pool error: {e}")

        # Fallback
        return self.llm_generate_culture_concept()

    def traditional_food_pool(self) -> Dict:
        """从传统食物池中随机选择"""
        try:
            all_foods = self.expanded_pools.get_all_cuisine()
            food = random.choice(all_foods)

            # Add culture context if not already included
            cultures = self.expanded_pools.KEYWORD_COMPONENTS['cultures']
            search_concept = f"{food} {random.choice(cultures)}"

            logger.info(f"Traditional food: {food}")

            return {
                "title": search_concept,
                "source": "traditional_food",
                "food": food,
                "type": "traditional_food"
            }

        except Exception as e:
            logger.error(f"Traditional food pool error: {e}")

        # Fallback
        return self.llm_generate_culture_concept()

    def traditional_music_pool(self) -> Dict:
        """从传统音乐池中随机选择"""
        try:
            all_music = self.expanded_pools.get_all_music()
            music = random.choice(all_music)

            # Add context
            search_concept = f"{music} traditional music"

            logger.info(f"Traditional music: {music}")

            return {
                "title": search_concept,
                "source": "traditional_music",
                "music": music,
                "type": "traditional_music"
            }

        except Exception as e:
            logger.error(f"Traditional music pool error: {e}")

        # Fallback
        return self.llm_generate_culture_concept()


# ============================================================================
# Main Pipeline
# ============================================================================
