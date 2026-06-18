#!/usr/bin/env python3
"""
BiographyEntryPointGenerator - Entry Point Generator for Biography Domain

This module contains the entry point generation strategies for the Biography domain.
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
from pools import ExpandedBiographyPools
from apis.biography_apis import WikipediaBioClient, WikidataPeopleClient, DBpediaPeopleClient, NobelPrizeClient, BiographyDotComClient

class BiographyEntryPointGenerator:
    """
    传记数据入口点生成器 - 使用扩展池子

    使用多种策略生成人物传记相关的探索入口点
    覆盖全球所有人物类型、职业、地区、时代
    """

    def __init__(self):
        # Use expanded pools for better diversity
        self.expanded_pools = ExpandedBiographyPools()

        # Initialize all strategies
        self.strategies = {
            # Basic strategies (5)
            'llm_biography_concept': self.llm_generate_biography_concept,
            'wikipedia_biography_angle': self.wikipedia_random_with_biography_angle,
            'wikipedia_biography_category': self.wikipedia_random_from_category,
            'random_biography_keyword': self.random_biography_keyword_search,
            'dbpedia_person': self.dbpedia_random_person,

            # Wikidata strategies (4)
            'wikidata_politician': self.wikidata_random_politician,
            'wikidata_scientist': self.wikidata_random_scientist,
            'wikidata_artist': self.wikidata_random_artist,
            'wikidata_nobel': self.wikidata_random_nobel_laureate,

            # Award-based strategies (2)
            'nobel_prize_api': self.nobel_prize_laureate,
            'award_winner': self.award_winner,

            # Biography website strategies (2+, no API required)
            'biography_dot_com': self.biography_dot_com_random,
            'famous_person_pool': self.famous_person_pool,
        }

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        # Use expanded Wikipedia categories
        self.BIOGRAPHY_CATEGORIES = self.expanded_pools.get_all_categories()

        # Initialize basic clients (no API key required)
        self.wikipedia_client = WikipediaBioClient()
        self.wikidata_client = WikidataPeopleClient()
        self.dbpedia_client = DBpediaPeopleClient()
        self.nobel_client = NobelPrizeClient()
        self.biography_dot_com_client = BiographyDotComClient()

        num_strategies = len(self.strategies)
        logger.info(f"Initialized with {len(self.BIOGRAPHY_CATEGORIES)} categories and {num_strategies} strategies")

    def generate_random_entry(self) -> Dict:
        """使用随机策略生成入口点"""
        strategy_name = random.choice(list(self.strategies.keys()))
        strategy_func = self.strategies[strategy_name]
        return strategy_func()

    # ========================================================================
    # Strategy 1: LLM generates biographical concept
    # ========================================================================

    def llm_generate_biography_concept(self) -> Dict:
        """使用LLM生成多样化传记概念 - 强调全球覆盖"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        prompt = """Generate ONE random biographical concept ABOUT A PERSON FROM AROUND THE WORLD.

CRITICAL GLOBAL DIVERSITY REQUIREMENTS:
- Mix ALL PERSON TYPES equally:
  * Political: presidents, prime ministers, revolutionaries, activists, diplomats
  * Business: entrepreneurs, CEOs, founders, investors, innovators
  * Scientific: physicists, chemists, biologists, mathematicians, inventors, researchers
  * Cultural: painters, writers, poets, musicians, composers, actors, directors, architects
  * Sports: athletes, Olympians, champions, coaches from various sports
  * Social: reformers, humanitarians, religious leaders, civil rights activists
  * Exploration: explorers, pioneers, adventurers, astronauts

- Mix ALL REGIONS equally:
  * North America: US, Canada, Mexico (beyond just US presidents)
  * Europe: UK, France, Germany, Italy, Spain, Russia (beyond just Western Europe)
  * East Asia: China, Japan, Korea, Mongolia, Taiwan
  * South Asia: India, Pakistan, Bangladesh, Sri Lanka, Nepal
  * Southeast Asia: Indonesia, Thailand, Vietnam, Philippines, Malaysia
  * Middle East: Saudi Arabia, UAE, Iran, Turkey, Egypt, Jordan
  * Africa: Nigeria, South Africa, Kenya, Ethiopia, Ghana, Egypt
  * Latin America: Brazil, Argentina, Mexico, Colombia, Chile, Peru
  * Oceania: Australia, New Zealand, Pacific Islands

- Mix ALL ERAS equally:
  * Ancient: ancient philosophers, emperors, mathematicians (before 500 AD)
  * Medieval: medieval rulers, scholars, artists (500-1500 AD)
  * Early Modern: Renaissance figures, enlightenment thinkers, explorers (1500-1800 AD)
  * 19th Century: industrial revolution figures, independence leaders, scientists
  * 20th Century: world wars figures, civil rights leaders, tech pioneers
  * Contemporary: modern leaders, tech founders, current celebrities

- Mix GENDER AND BACKGROUNDS:
  * Women leaders, scientists, artists, activists
  * Non-Western figures who shaped their regions
  * Overlooked or underrepresented figures
  * Indigenous leaders and figures

AVOID overused examples: George Washington, Abraham Lincoln, Napoleon, Albert Einstein, Shakespeare, Leonardo da Vinci, etc.

Examples (DO NOT use these, they illustrate the DIVERSITY we want):
- "Sojourney Truth abolitionist women's rights"
- "Liu Bei Chinese warlord Three Kingdoms"
- "Funmilayo Ransome-Kuti Nigerian activist"
- "Lise Meitner physicist nuclear fission"
- "Chandrasekhar Venkata Raman physicist scattering"
- "Miriam Makeba South African singer activist"
- "Liu Cixin Chinese science fiction writer"
- "Tu Youyou artemisinin malaria researcher"
- "Ignaz Semmelweis handwashing pioneer"
- "Shirin Ebadi Iranian lawyer Nobel laureate"
- "Tenzing Norgay Sherpa mountaineer"
- "Rosalind Franklin DNA scientist"
- "Hatshepsut Egyptian female pharaoh"
- "Rani of Jhansi Indian queen warrior"
- "Samory Touré West African leader resistance"
- "Truganini Aboriginal Tasmanian leader"

Format: Return ONLY the person's name with 1-3 words of context (2-5 words total), nothing else.

Now generate ONE diverse biographical concept:"""

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

            logger.info(f"LLM generated biography concept: {concept}")

            return {
                "title": concept,
                "source": "llm_biography_concept",
                "type": "biographical_entity"
            }

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            # Fallback to expanded pools
            all_professions = self.expanded_pools.get_all_professions()
            all_regions = self.expanded_pools.get_all_regions()
            profession = random.choice(all_professions)
            region = random.choice(all_regions)
            fallback = f"{region} {profession}"
            return {
                "title": fallback,
                "source": "llm_biography_concept",
                "type": "biographical_entity"
            }

    # ========================================================================
    # Strategy 2: Wikipedia random + biographical angle
    # ========================================================================

    def wikipedia_random_with_biography_angle(self) -> Dict:
        """随机Wikipedia页面 + 从传记角度探索"""
        try:
            # Get random Wikipedia page
            url = "https://en.wikipedia.org/api/rest_v1/page/random/summary"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            original_title = data.get("title", "")
            logger.info(f"Random Wikipedia page: {original_title}")

            # Generate biographical angle
            biography_angle = self.get_biographical_angle(original_title)

            logger.info(f"  Biography angle: {biography_angle}")

            return {
                "title": biography_angle,
                "source": "wikipedia_biography_angle",
                "original_title": original_title,
                "type": "biographical_entity"
            }

        except Exception as e:
            logger.error(f"Wikipedia random error: {e}")
            # Fallback
            return {
                "title": "Notable people biography",
                "source": "wikipedia_biography_angle",
                "type": "biographical_entity"
            }

    def get_biographical_angle(self, title: str) -> str:
        """为任意词条生成传记相关的探索角度"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        prompt = f"""The Wikipedia page is about "{title}".

Generate a 2-5 word phrase that connects this topic to a BIOGRAPHICAL context.

Think about:
- Is this a person? What is their profession, achievement, or claim to fame?
- Is this place connected to notable people? Who lived or worked there?
- Is this an organization? Who founded it or led it?
- Is this an event? Who were the key figures involved?
- Is this a concept? Who developed, pioneered, or is associated with it?

Examples:
- "Apple" → "Steve Jobs Apple founder"
- "Brazil" → "Brazilian presidents biography"
- "Relativity" → "Albert Einstein relativity theory"
- "Feminism" → "feminist leaders biography"
- "Internet" → "internet pioneers biography"
- "Civil Rights" → "civil rights leaders"
- "Statue of Liberty" → "Frédéric Auguste Bartholdi sculptor"
- "Yellowstone" → "Yellowstone explorers biography"

For "{title}", return ONLY the 2-5 word biographical phrase, nothing else."""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}])
            angle = response.strip()
            angle = angle.strip('"\'.')

            if len(angle) > 100:
                angle = angle[:100]

            return angle if angle else f"Biography of {title}"

        except Exception as e:
            logger.debug(f"Biography angle extraction error: {e}")
            return f"Biography of {title}"

    # ========================================================================
    # Strategy 3: Wikipedia random from biography categories
    # ========================================================================

    def wikipedia_random_from_category(self) -> Dict:
        """从传记相关分类中随机选择页面"""
        category = random.choice(self.BIOGRAPHY_CATEGORIES)

        try:
            # Get pages from category using Wikipedia API
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
                "source": "wikipedia_biography_category",
                "category": category,
                "type": "biographical_entity"
            }

        except Exception as e:
            logger.error(f"Wikipedia category error: {e}")
            # Fallback to LLM generation
            return self.llm_generate_biography_concept()

    # ========================================================================
    # Strategy 4: Random biographical keyword search
    # ========================================================================

    def random_biography_keyword_search(self) -> Dict:
        """使用扩展池子生成多样化传记关键词组合"""
        # Use expanded pools to generate diverse combinations
        queries = self.expanded_pools.generate_search_queries()
        search_term = random.choice(queries)

        logger.info(f"Biographical keyword search: {search_term}")

        return {
            "title": search_term,
            "source": "random_biography_keyword",
            "type": "biographical_entity"
        }

    # ========================================================================
    # Strategy 5: DBpedia person
    # ========================================================================

    def dbpedia_random_person(self) -> Dict:
        """从DBpedia随机获取人物"""
        try:
            # Get random person with offset
            offset = random.randint(0, 100)
            people = self.dbpedia_client.get_random_person(limit=10, offset=offset)

            if people:
                person = random.choice(people)
                name = person.get('name', '')
                birth_date = person.get('birthDate', '')

                logger.info(f"DBpedia person: {name} ({birth_date})")

                return {
                    "title": name,
                    "source": "dbpedia_person",
                    "birthDate": birth_date,
                    "type": "biographical_entity"
                }

        except Exception as e:
            logger.error(f"DBpedia person error: {e}")

        # Fallback to LLM generation
        return self.llm_generate_biography_concept()

    # ========================================================================
    # Strategy 6: Wikidata politician
    # ========================================================================

    def wikidata_random_politician(self) -> Dict:
        """从Wikidata随机获取政治家"""
        try:
            politicians = self.wikidata_client.get_politicians(limit=50)

            if politicians:
                person = random.choice(politicians)
                name = person.get('name', '')
                country = person.get('country', '')

                concept = f"{name} political leader"
                if country:
                    concept = f"{name} {country} politician"

                logger.info(f"Wikidata politician: {name}")

                return {
                    "title": concept,
                    "source": "wikidata_politician",
                    "name": name,
                    "country": country,
                    "type": "political_figure"
                }

        except Exception as e:
            logger.error(f"Wikidata politician error: {e}")

        # Fallback
        return self.llm_generate_biography_concept()

    # ========================================================================
    # Strategy 7: Wikidata scientist
    # ========================================================================

    def wikidata_random_scientist(self) -> Dict:
        """从Wikidata随机获取科学家"""
        try:
            scientists = self.wikidata_client.get_scientists(limit=50)

            if scientists:
                person = random.choice(scientists)
                name = person.get('name', '')
                description = person.get('description', '')
                country = person.get('country', '')

                concept = f"{name} scientist"
                if country:
                    concept = f"{name} {country} scientist"

                logger.info(f"Wikidata scientist: {name}")

                return {
                    "title": concept,
                    "source": "wikidata_scientist",
                    "name": name,
                    "description": description,
                    "country": country,
                    "type": "scientist"
                }

        except Exception as e:
            logger.error(f"Wikidata scientist error: {e}")

        # Fallback
        return self.llm_generate_biography_concept()

    # ========================================================================
    # Strategy 8: Wikidata artist
    # ========================================================================

    def wikidata_random_artist(self) -> Dict:
        """从Wikidata随机获取艺术家"""
        try:
            # Randomly choose artist type
            artist_types = [
                ('painters', self.wikidata_client.get_artists),
                ('writers', self.wikidata_client.get_writers),
                ('musicians', self.wikidata_client.get_musicians),
                ('actors', self.wikidata_client.get_actors)
            ]

            artist_type, get_func = random.choice(artist_types)
            artists = get_func(limit=50)

            if artists:
                person = random.choice(artists)
                name = person.get('name', '')

                concept = f"{name} {artist_type[:-1]}"

                logger.info(f"Wikidata {artist_type[:-1]}: {name}")

                return {
                    "title": concept,
                    "source": "wikidata_artist",
                    "name": name,
                    "artist_type": artist_type,
                    "type": "artist"
                }

        except Exception as e:
            logger.error(f"Wikidata artist error: {e}")

        # Fallback
        return self.llm_generate_biography_concept()

    # ========================================================================
    # Strategy 9: Wikidata Nobel laureate
    # ========================================================================

    def wikidata_random_nobel_laureate(self) -> Dict:
        """从Wikidata随机获取诺贝尔奖得主"""
        try:
            laureates = self.wikidata_client.get_nobel_laureates(limit=50)

            if laureates:
                person = random.choice(laureates)
                name = person.get('name', '')
                prize = person.get('prize', '')

                concept = f"{name} Nobel Prize winner"
                if prize:
                    concept = f"{name} {prize} Nobel laureate"

                logger.info(f"Wikidata Nobel laureate: {name}")

                return {
                    "title": concept,
                    "source": "wikidata_nobel",
                    "name": name,
                    "prize": prize,
                    "type": "nobel_laureate"
                }

        except Exception as e:
            logger.error(f"Wikidata Nobel error: {e}")

        # Fallback
        return self.llm_generate_biography_concept()

    # ========================================================================
    # Strategy 10: Nobel Prize API
    # ========================================================================

    def nobel_prize_laureate(self) -> Dict:
        """从诺贝尔奖API获取得主"""
        try:
            laureate = self.nobel_client.get_random_laureate()

            if laureate:
                name = laureate.get('name', '')
                category = laureate.get('category', '')
                year = laureate.get('year', '')

                concept = f"{name} Nobel Prize"
                if category:
                    concept = f"{name} {category} Nobel Prize {year}"

                logger.info(f"Nobel Prize API: {name}")

                return {
                    "title": concept,
                    "source": "nobel_prize_api",
                    "name": name,
                    "category": category,
                    "year": year,
                    "type": "nobel_laureate"
                }

        except Exception as e:
            logger.error(f"Nobel Prize API error: {e}")

        # Fallback
        return self.llm_generate_biography_concept()

    # ========================================================================
    # Strategy 11: Award winner
    # ========================================================================

    def award_winner(self) -> Dict:
        """从奖项得主池中随机选择"""
        try:
            # Get all award winners
            all_winners = []
            for award_list in self.expanded_pools.AWARD_WINNERS.values():
                all_winners.extend(award_list)

            winner = random.choice(all_winners)

            # Determine award type
            for award_name, award_list in self.expanded_pools.AWARD_WINNERS.items():
                if winner in award_list:
                    category = award_name.replace('_', ' ').title()
                    break

            concept = f"{winner} {category}"

            logger.info(f"Award winner: {winner}")

            return {
                "title": concept,
                "source": "award_winner",
                "person": winner,
                "award": category,
                "type": "award_winner"
            }

        except Exception as e:
            logger.error(f"Award winner error: {e}")

        # Fallback
        return self.llm_generate_biography_concept()

    # ========================================================================
    # Strategy 12: Biography.com
    # ========================================================================

    def biography_dot_com_random(self) -> Dict:
        """从Biography.com获取人物"""
        try:
            person = self.biography_dot_com_client.get_random_person()

            name = person.get('name', '')
            category = person.get('category', '')

            # Generate search concept
            concepts = [
                f"{name} biography",
                f"{name} life story",
                f"{name} early life",
                f"{name} career achievements",
                f"{name} legacy"
            ]
            concept = random.choice(concepts)

            logger.info(f"Biography.com: {name}")

            return {
                "title": concept,
                "source": "biography_dot_com",
                "name": name,
                "category": category,
                "type": "biographical_entity"
            }

        except Exception as e:
            logger.error(f"Biography.com error: {e}")

        # Fallback
        return self.llm_generate_biography_concept()

    # ========================================================================
    # Strategy 13: Famous person pool
    # ========================================================================

    def famous_person_pool(self) -> Dict:
        """从著名人物池中随机选择"""
        try:
            # Get all famous people
            famous_people = self.expanded_pools.FAMOUS_PEOPLE

            # Select random category
            main_category = random.choice(list(famous_people.keys()))

            if isinstance(famous_people[main_category], dict):
                # Has subcategories
                subcategories = famous_people[main_category]
                subcat_name = random.choice(list(subcategories.keys()))
                people_list = subcategories[subcat_name]
                category_name = f"{main_category}/{subcat_name}"
            else:
                # Direct list
                people_list = famous_people[main_category]
                category_name = main_category

            person = random.choice(people_list)

            # Generate search concept
            concepts = [
                f"{person} biography",
                f"{person} life and achievements",
                f"{person} legacy",
                f"{person} early life",
                f"{person} career"
            ]
            concept = random.choice(concepts)

            logger.info(f"Famous person pool: {person} ({category_name})")

            return {
                "title": concept,
                "source": "famous_person_pool",
                "person": person,
                "category": category_name,
                "type": "famous_person"
            }

        except Exception as e:
            logger.error(f"Famous person pool error: {e}")

        # Fallback
        return self.llm_generate_biography_concept()


# ============================================================================
# Main Pipeline
# ============================================================================
