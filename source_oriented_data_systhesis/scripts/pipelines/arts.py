#!/usr/bin/env python3
"""
ArtsEntryPointGenerator - Entry Point Generator for Arts Domain

This module contains the entry point generation strategies for the Arts domain.
"""

import random
import sys
import requests
import os
from pathlib import Path
from typing import Dict
from loguru import logger

# Add deepforge to path (local copy)
deepforge_path = Path(__file__).parent.parent / "deepforge"
sys.path.insert(0, str(deepforge_path))

# Import shared modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from api.caller import APICaller
from pools import ExpandedArtsPools
from apis.historical_apis import DBpediaClient
from apis.arts_apis import MetMuseumClient, MusicBrainzClient, OpenLibraryClient, MoMAClient, RijksmuseumClient, TMDbClient
from apis.arts_websites import ArtsyClient, SaatchiArtClient, BehanceClient, DeviantArtClient, AllMusicClient, BandcampClient, RateYourMusicClient, GoodreadsClient, PoetryFoundationClient, IMDbClient, LetterboxdClient, MUBIClient, ArchDailyClient, DezeenClient

class ArtsEntryPointGenerator:
    """
    Arts data entry point generator - Using expanded pools

    Uses multiple strategies to generate arts-related entry points
    Covers all art forms, eras, regions, and movements worldwide
    """

    def __init__(self):
        # Use expanded pools for better diversity
        self.expanded_pools = ExpandedArtsPools()

        # Initialize all strategies
        self.strategies = {
            # Basic strategies (8)
            'llm_cultural_concept': self.llm_generate_cultural_concept,
            'wikipedia_cultural_angle': self.wikipedia_random_with_cultural_angle,
            'wikipedia_cultural_category': self.wikipedia_random_from_category,
            'random_cultural_keyword': self.random_cultural_keyword_search,
            'dbpedia_cultural_entity': self.dbpedia_random_cultural_entity,
            'famous_artist_work': self.famous_artist_work,
            'cultural_institution': self.cultural_institution,
            'material_technique': self.material_technique_exploration,
            # Professional API strategies (3, no API key required)
            'met_museum': self.met_museum_random,
            'musicbrainz': self.musicbrainz_random,
            'open_library': self.open_library_random,
            # Professional website strategies (12+, no API required)
            'artsy': self.artsy_random,
            'saatchi_art': self.saatchi_random,
            'behance': self.behance_random,
            'deviantart': self.deviantart_random,
            'allmusic': self.allmusic_random,
            'bandcamp': self.bandcamp_random,
            'rateyourmusic': self.rateyourmusic_random,
            'goodreads': self.goodreads_random,
            'poetry_foundation': self.poetry_foundation_random,
            'imdb': self.imdb_random,
            'letterboxd': self.letterboxd_random,
            'mubi': self.mubi_random,
            'archdaily': self.archdaily_random,
            'dezeen': self.dezeen_random,
        }

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        # Use expanded Wikipedia categories
        self.CULTURAL_CATEGORIES = self.expanded_pools.get_all_categories()

        # Initialize basic API clients (no API key required)
        self.dbpedia_client = DBpediaClient()
        self.met_client = MetMuseumClient()
        self.musicbrainz_client = MusicBrainzClient()
        self.open_library_client = OpenLibraryClient()

        # Initialize professional website clients (no API key required)
        self.artsy_client = ArtsyClient()
        self.saatchi_client = SaatchiArtClient()
        self.behance_client = BehanceClient()
        self.deviantart_client = DeviantArtClient()
        self.allmusic_client = AllMusicClient()
        self.bandcamp_client = BandcampClient()
        self.rateyourmusic_client = RateYourMusicClient()
        self.goodreads_client = GoodreadsClient()
        self.poetry_client = PoetryFoundationClient()
        self.imdb_client = IMDbClient()
        self.letterboxd_client = LetterboxdClient()
        self.mubi_client = MUBIClient()
        self.archdaily_client = ArchDailyClient()
        self.dezeen_client = DezeenClient()

        # Initialize optional API clients (require API keys)
        self.moma_client = None
        self.rijks_client = None
        self.tmdb_client = None

        # Try to initialize optional clients if API keys are available
        moma_key = os.getenv('MOMA_API_KEY')
        if moma_key:
            try:
                self.moma_client = MoMAClient(api_key=moma_key)
                self.strategies['moma_museum'] = self.moma_random
                logger.info("MoMA client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize MoMA client: {e}")

        rijks_key = os.getenv('RIJKS_API_KEY')
        if rijks_key:
            try:
                self.rijks_client = RijksmuseumClient(api_key=rijks_key)
                self.strategies['rijksmuseum'] = self.rijksmuseum_random
                logger.info("Rijksmuseum client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Rijksmuseum client: {e}")

        tmdb_key = os.getenv('TMDB_API_KEY')
        if tmdb_key:
            try:
                self.tmdb_client = TMDbClient(api_key=tmdb_key)
                self.strategies['tmdb_movie'] = self.tmdb_random
                logger.info("TMDb client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize TMDb client: {e}")

        num_strategies = len(self.strategies)
        logger.info(f"Initialized with {len(self.CULTURAL_CATEGORIES)} categories and {num_strategies} strategies")

    def generate_random_entry(self) -> Dict:
        """使用随机策略生成入口点"""
        strategy_name = random.choice(list(self.strategies.keys()))
        strategy_func = self.strategies[strategy_name]
        return strategy_func()

    # ========================================================================
    # Strategy 1: LLM generates arts concept
    # ========================================================================

    def llm_generate_cultural_concept(self) -> Dict:
        """使用LLM生成多样化文化艺术概念 - 强调全球覆盖"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        prompt = """Generate ONE random cultural or artistic concept FROM AROUND THE WORLD.

CRITICAL GLOBAL DIVERSITY REQUIREMENTS:
- Mix ALL ART FORMS equally:
  * Visual Arts: painting, sculpture, photography, calligraphy, digital art, installation art
  * Music: classical, folk, traditional, contemporary, from all regions
  * Literature: poetry, prose, drama, from all literary traditions
  * Architecture: temples, palaces, modern buildings, from all architectural traditions
  * Performing Arts: theater, dance, opera, from all performance traditions
  * Film and Media: cinema, television, video art, animation
  * Design and Crafts: fashion, textiles, pottery, jewelry, from all craft traditions
  * Cultural Heritage: sites, monuments, festivals, rituals, intangible heritage

- Mix ALL REGIONS equally:
  * East Asia (China, Japan, Korea, Mongolia)
  * Southeast Asia (Indonesia, Thailand, Vietnam, etc.)
  * South Asia (India, Pakistan, Bangladesh, Nepal, etc.)
  * Central Asia (Silk Road traditions)
  * West Asia/Middle East (Persian, Arabic, Ottoman, etc.)
  * North Africa (Egypt, Maghreb, Nubian traditions)
  * Sub-Saharan Africa (West, East, Central, Southern African traditions)
  * Europe (Western, Eastern, Northern, Southern)
  * Americas (Pre-Columbian, Colonial, Contemporary North & South America)
  * Oceania (Aboriginal, Maori, Pacific Islander traditions)
  * Diaspora (African, Asian, Jewish diaspora traditions)

- Mix ALL TIME PERIODS:
  * Prehistoric (cave paintings, rock art)
  * Ancient (Egypt, Mesopotamia, Greece, Rome, China, India, Americas)
  * Medieval (Byzantine, Islamic, Chinese, Japanese, European)
  * Early Modern (Renaissance, Mughal, Qing, Edo, Ottoman)
  * 19th Century (Romanticism, Impressionism, global revival movements)
  * Early 20th Century (Modernism, global avant-garde movements)
  * Post-War (Abstract Expressionism, postcolonial art movements)
  * Contemporary (digital art, global contemporary art)

- Mix different cultural contexts:
  * Religious and spiritual traditions (Buddhist, Christian, Hindu, Islamic, Jewish, indigenous)
  * Court and patronage traditions (imperial, royal, aristocratic)
  * Folk and popular traditions (vernacular, rural, urban popular)
  * Revolutionary and avant-garde movements
  * Diaspora and postcolonial expressions
  * Digital and new media practices

AVOID overused examples: Mona Lisa, Beethoven, Shakespeare, Picasso, etc.

Examples (DO NOT use these, they illustrate the DIVERSITY we want):
- "Yoruba beadwork traditions"
- "Heian period Japanese literature"
- "Mughal miniature painting"
- " Aboriginal dot painting"
- "Javanese gamelan music"
- "Korean Minhwa folk painting"
- "Andean textile weaving"
- "Ethiopian icon painting"
- "Noh theater traditions"
- "Balinese shadow puppetry"
- "Ming Dynasty porcelain"
- "Swahili carved doors"
- "Berber carpet weaving"
- "Sri Lankan Kandyan dance"
- "Maori whakairo carving"
- "Arabic calligraphy styles"

Format: Return ONLY the cultural/artistic concept name (2-6 words), nothing else.

Now generate ONE diverse concept:"""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}])
            concept = response.strip()

            # Clean up common LLM artifacts
            for prefix in ["The ", "A ", "An "]:
                if concept.startswith(prefix):
                    concept = concept[len(prefix):]
            concept = concept.strip('"\'')

            if len(concept) > 100:
                concept = concept[:100]

            logger.info(f"LLM generated cultural concept: {concept}")

            return {
                "title": concept,
                "source": "llm_cultural_concept",
                "type": "cultural_artistic_entity"
            }

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            # Fallback to expanded pools
            all_art_types = self.expanded_pools.get_all_art_types()
            all_regions = self.expanded_pools.get_all_regions()
            art_type = random.choice(all_art_types)
            region = random.choice(all_regions)
            fallback = f"{region} {art_type}"
            return {
                "title": fallback,
                "source": "llm_cultural_concept",
                "type": "cultural_artistic_entity"
            }

    # ========================================================================
    # Strategy 2: Wikipedia random + arts angle
    # ========================================================================

    def wikipedia_random_with_cultural_angle(self) -> Dict:
        """随机Wikipedia页面 + 从文化艺术角度探索"""
        try:
            # Get random Wikipedia page
            url = "https://en.wikipedia.org/api/rest_v1/page/random/summary"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            original_title = data.get("title", "")
            logger.info(f"Random Wikipedia page: {original_title}")

            # Generate arts angle
            cultural_angle = self.get_cultural_angle(original_title)

            logger.info(f"  Cultural/arts angle: {cultural_angle}")

            return {
                "title": cultural_angle,
                "source": "wikipedia_cultural_angle",
                "original_title": original_title,
                "type": "cultural_artistic_entity"
            }

        except Exception as e:
            logger.error(f"Wikipedia random error: {e}")
            # Fallback
            return {
                "title": "Cultural and artistic traditions",
                "source": "wikipedia_cultural_angle",
                "type": "cultural_artistic_entity"
            }

    def get_cultural_angle(self, title: str) -> str:
        """为任意词条生成文化艺术相关的探索角度"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        prompt = f"""The Wikipedia page is about "{title}".

Generate a 2-5 word phrase that connects this topic to its CULTURAL or ARTISTIC context.

Think about:
- Is this person an artist, writer, composer, architect, dancer, performer, or artisan?
- Is this place a cultural site, museum, gallery, performance venue, or architectural monument?
- Is this object a work of art, musical composition, literary work, or cultural artifact?
- Is this organization a cultural institution, museum, gallery, or arts organization?
- Is this event a festival, exhibition, performance, or cultural celebration?
- What artistic or cultural tradition is this associated with?
- What material, technique, or style does this represent?

Examples:
- "Michelangelo" → "Michelangelo Renaissance sculpture"
- "Paris" → "Paris art museums collections"
- "Symphony" → "classical music symphonic tradition"
- "Kyoto" → "Kyoto traditional arts temples"
- "Silk" → "silk textile weaving traditions"
- "Festival" → "traditional cultural festivals"
- "Bronze" → "bronze casting sculpture techniques"

For "{title}", return ONLY the 2-5 word cultural/artistic phrase, nothing else."""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}])
            angle = response.strip()
            angle = angle.strip('"\'')

            if len(angle) > 100:
                angle = angle[:100]

            return angle if angle else f"Cultural history of {title}"

        except Exception as e:
            logger.debug(f"Cultural angle extraction error: {e}")
            return f"Cultural history of {title}"

    # ========================================================================
    # Strategy 3: Wikipedia random from arts categories
    # ========================================================================

    def wikipedia_random_from_category(self) -> Dict:
        """从文化艺术相关分类中随机选择页面"""
        category = random.choice(self.CULTURAL_CATEGORIES)

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
                "source": "wikipedia_cultural_category",
                "category": category,
                "type": "cultural_artistic_entity"
            }

        except Exception as e:
            logger.error(f"Wikipedia category error: {e}")
            # Fallback to LLM generation
            return self.llm_generate_cultural_concept()

    # ========================================================================
    # Strategy 4: Random arts keyword search
    # ========================================================================

    def random_cultural_keyword_search(self) -> Dict:
        """Using expanded pools生成多样化文化艺术关键词组合"""
        # Use expanded pools to generate diverse combinations
        queries = self.expanded_pools.generate_search_queries()
        search_term = random.choice(queries)

        logger.info(f"Cultural/arts keyword search: {search_term}")

        return {
            "title": search_term,
            "source": "random_cultural_keyword",
            "type": "cultural_artistic_entity"
        }

    # ========================================================================
    # Strategy 5: DBpedia cultural entities
    # ========================================================================

    def dbpedia_random_cultural_entity(self) -> Dict:
        """
        从DBpedia随机获取文化艺术实体

        随机选择以下类型之一:
        - 艺术家 (Artists)
        - 作品 (Works - paintings, compositions, literary works)
        - 运动流派 (Movements/Schools)
        """
        # Randomly select entity type
        entity_types = ['artist', 'architect', 'writer', 'composer', 'movement']
        entity_type = random.choice(entity_types)

        try:
            if entity_type == 'artist':
                # Try to get visual artists from DBpedia
                sparql = """
                SELECT DISTINCT ?artist ?name ?movement WHERE {
                  ?artist a dbo:Artist .
                  ?artist foaf:name ?name .
                  OPTIONAL { ?artist dbo:movement ?movement }
                  FILTER(LANG(?name) = "en")
                }
                LIMIT 50
                OFFSET %d
                """ % random.randint(0, 500)

                results = self.dbpedia_client.query(sparql)
                bindings = results.get('results', {}).get('bindings', [])

                if bindings:
                    artist = random.choice(bindings)
                    name = artist.get('name', {}).get('value', '')
                    movement = artist.get('movement', {}).get('value', '')

                    logger.info(f"DBpedia artist: {name}")

                    return {
                        "title": name,
                        "source": "dbpedia_cultural_entity",
                        "entity_type": "artist",
                        "movement": movement,
                        "type": "cultural_artistic_entity"
                    }

            elif entity_type == 'architect':
                sparql = """
                SELECT DISTINCT ?architect ?name WHERE {
                  ?architect a dbo:Architect .
                  ?architect foaf:name ?name .
                  FILTER(LANG(?name) = "en")
                }
                LIMIT 50
                OFFSET %d
                """ % random.randint(0, 100)

                results = self.dbpedia_client.query(sparql)
                bindings = results.get('results', {}).get('bindings', [])

                if bindings:
                    architect = random.choice(bindings)
                    name = architect.get('name', {}).get('value', '')

                    logger.info(f"DBpedia architect: {name}")

                    return {
                        "title": name,
                        "source": "dbpedia_cultural_entity",
                        "entity_type": "architect",
                        "type": "cultural_artistic_entity"
                    }

            elif entity_type == 'writer':
                sparql = """
                SELECT DISTINCT ?writer ?name WHERE {
                  ?writer a dbo:Writer .
                  ?writer foaf:name ?name .
                  FILTER(LANG(?name) = "en")
                }
                LIMIT 50
                OFFSET %d
                """ % random.randint(0, 500)

                results = self.dbpedia_client.query(sparql)
                bindings = results.get('results', {}).get('bindings', [])

                if bindings:
                    writer = random.choice(bindings)
                    name = writer.get('name', {}).get('value', '')

                    logger.info(f"DBpedia writer: {name}")

                    return {
                        "title": name,
                        "source": "dbpedia_cultural_entity",
                        "entity_type": "writer",
                        "type": "cultural_artistic_entity"
                    }

            elif entity_type == 'composer':
                sparql = """
                SELECT DISTINCT ?composer ?name WHERE {
                  ?composer a dbo:Composer .
                  ?composer foaf:name ?name .
                  FILTER(LANG(?name) = "en")
                }
                LIMIT 50
                OFFSET %d
                """ % random.randint(0, 100)

                results = self.dbpedia_client.query(sparql)
                bindings = results.get('results', {}).get('bindings', [])

                if bindings:
                    composer = random.choice(bindings)
                    name = composer.get('name', {}).get('value', '')

                    logger.info(f"DBpedia composer: {name}")

                    return {
                        "title": name,
                        "source": "dbpedia_cultural_entity",
                        "entity_type": "composer",
                        "type": "cultural_artistic_entity"
                    }

            else:  # movement
                sparql = """
                SELECT DISTINCT ?movement ?name WHERE {
                  ?movement a dbo:ArtMovement .
                  ?movement rdfs:label ?name .
                  FILTER(LANG(?name) = "en")
                }
                LIMIT 30
                OFFSET %d
                """ % random.randint(0, 50)

                results = self.dbpedia_client.query(sparql)
                bindings = results.get('results', {}).get('bindings', [])

                if bindings:
                    movement = random.choice(bindings)
                    name = movement.get('name', {}).get('value', '')

                    logger.info(f"DBpedia movement: {name}")

                    return {
                        "title": name,
                        "source": "dbpedia_cultural_entity",
                        "entity_type": "movement",
                        "type": "cultural_artistic_entity"
                    }

        except Exception as e:
            logger.error(f"DBpedia cultural entity error: {e}")

        # Fallback to LLM generation
        return self.llm_generate_cultural_concept()

    # ========================================================================
    # Strategy 6: Famous artist and work
    # ========================================================================

    def famous_artist_work(self) -> Dict:
        """
        从著名艺术家和作品池中随机选择

        包括:
        - 著名艺术家 + 作品组合
        - 著名艺术家单独
        - 著名作品单独
        """
        # Choose random type
        choice_type = random.choice(['artist_work', 'artist_only', 'work_only'])

        try:
            if choice_type == 'artist_work':
                # Select random artist category
                category = random.choice(list(self.expanded_pools.FAMOUS_ARTISTS.keys()))
                if self.expanded_pools.FAMOUS_ARTISTS[category]:
                    artist = random.choice(self.expanded_pools.FAMOUS_ARTISTS[category])

                    # Map to corresponding work category
                    work_map = {
                        "visual_artists": "visual_artworks",
                        "composers": "musical_works",
                        "writers": "literary_works",
                        "architects": "architectural_monuments"
                    }
                    work_category = work_map.get(category, "visual_artworks")

                    if work_category in self.expanded_pools.FAMOUS_WORKS:
                        if self.expanded_pools.FAMOUS_WORKS[work_category]:
                            work = random.choice(self.expanded_pools.FAMOUS_WORKS[work_category])
                            concept = f"{artist} {work}"

                            logger.info(f"Famous artist + work: {concept}")

                            return {
                                "title": concept,
                                "source": "famous_artist_work",
                                "choice_type": "artist_work",
                                "artist": artist,
                                "work": work,
                                "type": "cultural_artistic_entity"
                            }

            elif choice_type == 'artist_only':
                category = random.choice(list(self.expanded_pools.FAMOUS_ARTISTS.keys()))
                if self.expanded_pools.FAMOUS_ARTISTS[category]:
                    artist = random.choice(self.expanded_pools.FAMOUS_ARTISTS[category])
                    concept = f"{artist} works and style"

                    logger.info(f"Famous artist only: {artist}")

                    return {
                        "title": concept,
                        "source": "famous_artist_work",
                        "choice_type": "artist_only",
                        "artist": artist,
                        "type": "cultural_artistic_entity"
                    }

            else:  # work_only
                work_category = random.choice(list(self.expanded_pools.FAMOUS_WORKS.keys()))
                if self.expanded_pools.FAMOUS_WORKS[work_category]:
                    work = random.choice(self.expanded_pools.FAMOUS_WORKS[work_category])
                    concept = f"{work} analysis and significance"

                    logger.info(f"Famous work only: {work}")

                    return {
                        "title": concept,
                        "source": "famous_artist_work",
                        "choice_type": "work_only",
                        "work": work,
                        "type": "cultural_artistic_entity"
                    }

        except Exception as e:
            logger.error(f"Famous artist/work error: {e}")

        # Fallback
        return self.llm_generate_cultural_concept()

    # ========================================================================
    # Strategy 7: Cultural institutions and venues
    # ========================================================================

    def cultural_institution(self) -> Dict:
        """
        从文化机构池中随机选择

        包括:
        - 博物馆
        - 表演场地
        - 节庆活动
        """
        # Select random institution category
        inst_category = random.choice(list(self.expanded_pools.INSTITUTIONS.keys()))

        try:
            if self.expanded_pools.INSTITUTIONS[inst_category]:
                institution = random.choice(self.expanded_pools.INSTITUTIONS[inst_category])

                # Generate a search concept based on the institution
                concepts = [
                    f"{institution} collection highlights",
                    f"{institution} famous works",
                    f"{institution} history and architecture",
                    f"{institution} cultural significance",
                    f"{institution} {inst_category}",
                ]
                concept = random.choice(concepts)

                logger.info(f"Cultural institution: {institution}")

                return {
                    "title": concept,
                    "source": "cultural_institution",
                    "institution": institution,
                    "institution_category": inst_category,
                    "type": "cultural_artistic_entity"
                }

        except Exception as e:
            logger.error(f"Cultural institution error: {e}")

        # Fallback
        return self.llm_generate_cultural_concept()

    # ========================================================================
    # Strategy 8: Materials and techniques exploration
    # ========================================================================

    def material_technique_exploration(self) -> Dict:
        """
        生成材料和工艺探索的入口点

        包括:
        - 材料 + 艺术形式组合
        - 技术传统
        - 工艺实践
        """
        try:
            # Select random material category
            material_category = random.choice(list(self.expanded_pools.MATERIALS.keys()))

            if self.expanded_pools.MATERIALS[material_category]:
                material = random.choice(self.expanded_pools.MATERIALS[material_category])

                # Select random art type
                all_art_types = self.expanded_pools.get_all_art_types()
                art_type = random.choice(all_art_types)

                # Also possibly select a region
                all_regions = self.expanded_pools.get_all_regions()
                region = random.choice(all_regions)

                # Generate different query patterns
                patterns = [
                    f"{material} {art_type}",
                    f"{material} techniques in {region}",
                    f"{material} crafting traditions",
                    f"{material} art history",
                    f"{region} {material} artistry",
                ]
                concept = random.choice(patterns)

                logger.info(f"Material/technique: {material} + {art_type}")

                return {
                    "title": concept,
                    "source": "material_technique",
                    "material": material,
                    "material_category": material_category,
                    "art_type": art_type,
                    "region": region,
                    "type": "cultural_artistic_entity"
                }

        except Exception as e:
            logger.error(f"Material/technique error: {e}")

        # Fallback
        return self.llm_generate_cultural_concept()

    # ========================================================================
    # Strategy 9: Met Museum random artwork
    # ========================================================================

    def met_museum_random(self) -> Dict:
        """
        从Metropolitan Museum of Art随机获取艺术品

        Met API无需API密钥，包含40万+藏品
        """
        try:
            # Get random artwork from Met
            artwork = self.met_client.get_random_object()

            if artwork and artwork.get('title'):
                title = artwork.get('title')
                artist = artwork.get('artistDisplayName', '')
                culture = artwork.get('culture', '')
                medium = artwork.get('medium', '')
                department = artwork.get('department', '')

                # Build search concept
                if artist:
                    concept = f"{title} by {artist}"
                else:
                    concept = f"{title} ({department})"

                logger.info(f"Met Museum: {concept}")

                return {
                    "title": concept,
                    "source": "met_museum",
                    "artwork_title": title,
                    "artist": artist,
                    "culture": culture,
                    "department": department,
                    "type": "cultural_artistic_entity"
                }

        except Exception as e:
            logger.error(f"Met Museum error: {e}")

        # Fallback
        return self.llm_generate_cultural_concept()

    # ========================================================================
    # Strategy 10: MusicBrainz random composer
    # ========================================================================

    def musicbrainz_random(self) -> Dict:
        """
        从MusicBrainz随机获取音乐家或作品

        MusicBrainz无需API密钥，是开源音乐百科
        """
        try:
            # Randomly choose between composer and traditional music
            choice = random.choice(['classical_composer', 'traditional_music'])

            if choice == 'classical_composer':
                composer = self.musicbrainz_client.get_random_classical_composer()
                if composer:
                    name = composer.get('name', '')
                    if 'name' in composer:
                        concept = f"{name} compositions and style"
                    else:
                        concept = f"Classical composer {name}"

                    logger.info(f"MusicBrainz composer: {name}")

                    return {
                        "title": concept,
                        "source": "musicbrainz",
                        "entity_type": "composer",
                        "name": name,
                        "type": "cultural_artistic_entity"
                    }

            else:  # traditional_music
                tradition = self.musicbrainz_client.get_random_traditional_music()
                if tradition:
                    region = tradition.get('region', '')
                    name = tradition.get('name', '')
                    concept = f"{name} musical traditions"

                    logger.info(f"MusicBrainz traditional: {name}")

                    return {
                        "title": concept,
                        "source": "musicbrainz",
                        "entity_type": "traditional_music",
                        "name": name,
                        "region": region,
                        "type": "cultural_artistic_entity"
                    }

        except Exception as e:
            logger.error(f"MusicBrainz error: {e}")

        # Fallback
        return self.llm_generate_cultural_concept()

    # ========================================================================
    # Strategy 11: Open Library random book
    # ========================================================================

    def open_library_random(self) -> Dict:
        """
        从Open Library随机获取图书

        Open Library无需API密钥，包含数百万图书记录
        """
        try:
            # Randomly choose between classic literature and non-western literature
            choice = random.choice(['classic', 'non_western', 'random'])

            if choice == 'classic':
                book = self.open_library_client.get_random_book(subject="Classic literature")
            elif choice == 'non_western':
                book = self.open_library_client.get_random_book(subject="Japanese literature")
            else:
                book = self.open_library_client.get_random_book()

            if book:
                title = book.get('title', '')
                author = book.get('author_name', book.get('author_name', ['Unknown'])[0] if isinstance(book.get('author_name'), list) else 'Unknown')
                subject = book.get('subject', '')

                if author:
                    concept = f"{title} by {author}"
                else:
                    concept = f"{title} (literary work)"

                logger.info(f"Open Library: {concept}")

                return {
                    "title": concept,
                    "source": "open_library",
                    "book_title": title,
                    "author": author,
                    "subject": subject,
                    "type": "cultural_artistic_entity"
                }

        except Exception as e:
            logger.error(f"Open Library error: {e}")

        # Fallback
        return self.llm_generate_cultural_concept()

    # ========================================================================
    # Strategy 12: MoMA random artwork (requires API key)
    # ========================================================================

    def moma_random(self) -> Dict:
        """
        从MoMA随机获取现代艺术作品

        需要MOMA_API_KEY环境变量
        """
        if not self.moma_client:
            return self.llm_generate_cultural_concept()

        try:
            artwork = self.moma_client.get_random_artwork()

            if artwork:
                title = artwork.get('title', '')
                artist = artwork.get('artist', '')
                date = artwork.get('date', '')

                if artist:
                    concept = f"{title} by {artist}"
                else:
                    concept = f"{title} (MoMA collection)"

                logger.info(f"MoMA: {concept}")

                return {
                    "title": concept,
                    "source": "moma_museum",
                    "artwork_title": title,
                    "artist": artist,
                    "date": date,
                    "type": "cultural_artistic_entity"
                }

        except Exception as e:
            logger.error(f"MoMA error: {e}")

        # Fallback
        return self.llm_generate_cultural_concept()

    # ========================================================================
    # Strategy 13: Rijksmuseum random artwork (requires API key)
    # ========================================================================

    def rijksmuseum_random(self) -> Dict:
        """
        从Rijksmuseum随机获取荷兰黄金时代艺术品

        需要RIJKS_API_KEY环境变量
        """
        if not self.rijks_client:
            return self.llm_generate_cultural_concept()

        try:
            # Randomly choose between random collection and Dutch masters
            choice = random.choice(['random', 'dutch_masters'])

            if choice == 'random':
                artwork = self.rijks_client.get_random_collection()
            else:
                artworks = self.rijks_client.get_dutch_masters(limit=50)
                if artworks:
                    artwork = random.choice(artworks)
                else:
                    artwork = None

            if artwork:
                title = artwork.get('title', '')
                artist = artwork.get('principalMaker', '')
                long_title = artwork.get('longTitle', '')

                if long_title:
                    concept = long_title
                elif artist:
                    concept = f"{title} by {artist}"
                else:
                    concept = f"{title} (Rijksmuseum)"

                logger.info(f"Rijksmuseum: {title}")

                return {
                    "title": concept,
                    "source": "rijksmuseum",
                    "artwork_title": title,
                    "artist": artist,
                    "type": "cultural_artistic_entity"
                }

        except Exception as e:
            logger.error(f"Rijksmuseum error: {e}")

        # Fallback
        return self.llm_generate_cultural_concept()

    # ========================================================================
    # Strategy 14: TMDb random movie (requires API key)
    # ========================================================================

    def tmdb_random(self) -> Dict:
        """
        从TMDb随机获取电影信息

        需要TMDB_API_KEY环境变量
        """
        if not self.tmdb_client:
            return self.llm_generate_cultural_concept()

        try:
            # Randomly choose between random movie and world cinema
            choice = random.choice(['random', 'world_cinema'])

            if choice == 'world_cinema':
                movie = self.tmdb_client.get_random_movie()
            else:
                movie = self.tmdb_client.get_random_movie()

            if movie:
                title = movie.get('title', '')
                original_title = movie.get('original_title', '')
                overview = movie.get('overview', '')
                release_date = movie.get('release_date', '')

                # Prefer original title for non-English films
                if original_title and original_title != title:
                    concept = f"{original_title} ({title}) - film analysis"
                else:
                    concept = f"{title} - film analysis"

                logger.info(f"TMDb: {title}")

                return {
                    "title": concept,
                    "source": "tmdb",
                    "movie_title": title,
                    "original_title": original_title,
                    "release_date": release_date,
                    "type": "cultural_artistic_entity"
                }

        except Exception as e:
            logger.error(f"TMDb error: {e}")

        # Fallback
        return self.llm_generate_cultural_concept()

    # ========================================================================
    # Professional Website Strategies (No API Required)
    # ========================================================================

    # Strategy 15: Artsy
    def artsy_random(self) -> Dict:
        """从Artsy随机获取艺术家或作品"""
        try:
            choice = random.choice(['artist', 'artwork'])
            if choice == 'artist':
                result = self.artsy_client.get_random_artist()
            else:
                result = self.artsy_client.get_random_artwork()

            if result:
                logger.info(f"Artsy: {result.get('title')}")
                return {
                    "title": result.get('title'),
                    "source": "artsy",
                    "url": result.get('url'),
                    "type": "cultural_artistic_entity"
                }
        except Exception as e:
            logger.error(f"Artsy error: {e}")
        return self.llm_generate_cultural_concept()

    # Strategy 16: Saatchi Art
    def saatchi_random(self) -> Dict:
        """从Saatchi Art随机获取艺术品"""
        try:
            result = self.saatchi_client.get_random_artwork()
            if result:
                logger.info(f"Saatchi Art: {result.get('title')}")
                return {
                    "title": result.get('title'),
                    "source": "saatchi_art",
                    "url": result.get('url'),
                    "type": "cultural_artistic_entity"
                }
        except Exception as e:
            logger.error(f"Saatchi Art error: {e}")
        return self.llm_generate_cultural_concept()

    # Strategy 17: Behance
    def behance_random(self) -> Dict:
        """从Behance随机获取创意项目"""
        try:
            result = self.behance_client.get_random_project()
            if result:
                logger.info(f"Behance: {result.get('title')}")
                return {
                    "title": result.get('title'),
                    "source": "behance",
                    "url": result.get('url'),
                    "type": "cultural_artistic_entity"
                }
        except Exception as e:
            logger.error(f"Behance error: {e}")
        return self.llm_generate_cultural_concept()

    # Strategy 18: DeviantArt
    def deviantart_random(self) -> Dict:
        """从DeviantArt随机获取数字艺术作品"""
        try:
            result = self.deviantart_client.get_random_artwork()
            if result:
                logger.info(f"DeviantArt: {result.get('title')}")
                return {
                    "title": result.get('title'),
                    "source": "deviantart",
                    "url": result.get('url'),
                    "type": "cultural_artistic_entity"
                }
        except Exception as e:
            logger.error(f"DeviantArt error: {e}")
        return self.llm_generate_cultural_concept()

    # Strategy 19: AllMusic
    def allmusic_random(self) -> Dict:
        """从AllMusic随机获取专辑或艺术家"""
        try:
            choice = random.choice(['artist', 'album', 'mood'])
            if choice == 'artist':
                result = self.allmusic_client.get_random_artist()
            elif choice == 'album':
                result = self.allmusic_client.get_random_album()
            else:
                result = self.allmusic_client.get_by_mood(random.choice([
                    'playful', 'tense-anxious', 'wistful', 'peaceful', 'confident'
                ]))

            if result:
                logger.info(f"AllMusic: {result.get('title')}")
                return {
                    "title": result.get('title'),
                    "source": "allmusic",
                    "url": result.get('url'),
                    "type": "cultural_artistic_entity"
                }
        except Exception as e:
            logger.error(f"AllMusic error: {e}")
        return self.llm_generate_cultural_concept()

    # Strategy 20: Bandcamp
    def bandcamp_random(self) -> Dict:
        """从Bandcamp随机发现音乐"""
        try:
            result = self.bandcamp_client.get_random_discovery()
            if result:
                logger.info(f"Bandcamp: {result.get('title')}")
                return {
                    "title": result.get('title'),
                    "source": "bandcamp",
                    "url": result.get('url'),
                    "type": "cultural_artistic_entity"
                }
        except Exception as e:
            logger.error(f"Bandcamp error: {e}")
        return self.llm_generate_cultural_concept()

    # Strategy 21: RateYourMusic
    def rateyourmusic_random(self) -> Dict:
        """从RateYourMusic随机获取音乐榜单"""
        try:
            result = self.rateyourmusic_client.get_random_chart()
            if result:
                logger.info(f"RateYourMusic: {result.get('title')}")
                return {
                    "title": result.get('title'),
                    "source": "rateyourmusic",
                    "url": result.get('url'),
                    "type": "cultural_artistic_entity"
                }
        except Exception as e:
            logger.error(f"RateYourMusic error: {e}")
        return self.llm_generate_cultural_concept()

    # Strategy 22: Goodreads
    def goodreads_random(self) -> Dict:
        """从Goodreads随机获取图书"""
        try:
            choice = random.choice(['genre', 'author', 'list'])
            if choice == 'genre':
                result = self.goodreads_client.get_random_book()
            elif choice == 'author':
                result = self.goodreads_client.get_by_author()
            else:
                result = self.goodreads_client.get_listopia()

            if result:
                logger.info(f"Goodreads: {result.get('title')}")
                return {
                    "title": result.get('title'),
                    "source": "goodreads",
                    "url": result.get('url'),
                    "type": "cultural_artistic_entity"
                }
        except Exception as e:
            logger.error(f"Goodreads error: {e}")
        return self.llm_generate_cultural_concept()

    # Strategy 23: Poetry Foundation
    def poetry_foundation_random(self) -> Dict:
        """从Poetry Foundation随机获取诗歌"""
        try:
            choice = random.choice(['theme', 'movement'])
            if choice == 'theme':
                result = self.poetry_client.get_random_poem()
            else:
                result = self.poetry_client.get_by_movement()

            if result:
                logger.info(f"Poetry Foundation: {result.get('title')}")
                return {
                    "title": result.get('title'),
                    "source": "poetry_foundation",
                    "url": result.get('url'),
                    "type": "cultural_artistic_entity"
                }
        except Exception as e:
            logger.error(f"Poetry Foundation error: {e}")
        return self.llm_generate_cultural_concept()

    # Strategy 24: IMDb
    def imdb_random(self) -> Dict:
        """从IMDb随机获取电影或电视节目"""
        try:
            choice = random.choice(['chart', 'genre', 'world_cinema'])
            if choice == 'chart':
                result = self.imdb_client.get_random_chart()
            elif choice == 'genre':
                result = self.imdb_client.get_by_genre()
            else:
                result = self.imdb_client.get_world_cinema()

            if result:
                logger.info(f"IMDb: {result.get('title')}")
                return {
                    "title": result.get('title'),
                    "source": "imdb",
                    "url": result.get('url'),
                    "type": "cultural_artistic_entity"
                }
        except Exception as e:
            logger.error(f"IMDb error: {e}")
        return self.llm_generate_cultural_concept()

    # Strategy 25: Letterboxd
    def letterboxd_random(self) -> Dict:
        """从Letterboxd随机获取电影信息"""
        try:
            choice = random.choice(['review', 'genre', 'lists'])
            if choice == 'review':
                result = self.letterboxd_client.get_random_review()
            elif choice == 'genre':
                result = self.letterboxd_client.get_by_genre()
            else:
                result = self.letterboxd_client.get_lists()

            if result:
                logger.info(f"Letterboxd: {result.get('title')}")
                return {
                    "title": result.get('title'),
                    "source": "letterboxd",
                    "url": result.get('url'),
                    "type": "cultural_artistic_entity"
                }
        except Exception as e:
            logger.error(f"Letterboxd error: {e}")
        return self.llm_generate_cultural_concept()

    # Strategy 26: MUBI
    def mubi_random(self) -> Dict:
        """从MUBI随机获取策展电影"""
        try:
            choice = random.choice(['showing', 'notebook', 'country'])
            if choice == 'showing':
                result = self.mubi_client.get_showing()
            elif choice == 'notebook':
                result = self.mubi_client.get_notebook()
            else:
                result = self.mubi_client.get_by_country()

            if result:
                logger.info(f"MUBI: {result.get('title')}")
                return {
                    "title": result.get('title'),
                    "source": "mubi",
                    "url": result.get('url'),
                    "type": "cultural_artistic_entity"
                }
        except Exception as e:
            logger.error(f"MUBI error: {e}")
        return self.llm_generate_cultural_concept()

    # Strategy 27: ArchDaily
    def archdaily_random(self) -> Dict:
        """从ArchDaily随机获取建筑项目"""
        try:
            choice = random.choice(['project', 'region'])
            if choice == 'project':
                result = self.archdaily_client.get_random_project()
            else:
                result = self.archdaily_client.get_by_region()

            if result:
                logger.info(f"ArchDaily: {result.get('title')}")
                return {
                    "title": result.get('title'),
                    "source": "archdaily",
                    "url": result.get('url'),
                    "type": "cultural_artistic_entity"
                }
        except Exception as e:
            logger.error(f"ArchDaily error: {e}")
        return self.llm_generate_cultural_concept()

    # Strategy 28: Dezeen
    def dezeen_random(self) -> Dict:
        """从Dezeen随机获取设计和建筑新闻"""
        try:
            result = self.dezeen_client.get_random_category()
            if result:
                logger.info(f"Dezeen: {result.get('title')}")
                return {
                    "title": result.get('title'),
                    "source": "dezeen",
                    "url": result.get('url'),
                    "type": "cultural_artistic_entity"
                }
        except Exception as e:
            logger.error(f"Dezeen error: {e}")
        return self.llm_generate_cultural_concept()


# ============================================================================
# Main Pipeline
# ============================================================================
