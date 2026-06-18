#!/usr/bin/env python3
"""
SportsEntryPointGenerator - Entry Point Generator for Sports Domain

This module contains the entry point generation strategies for the Sports domain.
"""

import random
import sys
from pathlib import Path
from typing import Dict
from loguru import logger
import requests

# Add deepforge to path (local copy)
deepforge_path = Path(__file__).parent.parent / "deepforge"
sys.path.insert(0, str(deepforge_path))

# Import shared modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from api.caller import APICaller
from pools import ExpandedSportsPools
from apis.historical_apis import DBpediaClient

class SportsEntryPointGenerator:
    """
    体育数据入口点生成器 - 使用扩展池子

    使用多种策略生成体育相关的探索入口点
    覆盖全球所有运动类型、大洲、赛事级别
    """

    def __init__(self):
        # Use expanded pools for better diversity
        self.expanded_pools = ExpandedSportsPools()

        self.strategies = {
            'llm_sports_concept': self.llm_generate_sports_concept,
            'llm_cold_sports_entity': self.llm_generate_cold_sports_entity,
            'wikipedia_sports_angle': self.wikipedia_random_with_sports_angle,
            'wikipedia_sports_category': self.wikipedia_random_from_category,
            'wikipedia_subcategory': self.wikipedia_random_from_subcategory,
            'random_sports_keyword': self.random_sports_keyword_search,
            'dbpedia_sports_entity': self.dbpedia_random_sports_entity,
            'sports_statistics': self.sports_statistics_moment,
            'official_sports_website': self.official_sports_website,
            'cross_domain_sports': self.cross_domain_sports_connection,
            'temporal_sports': self.temporal_sports_exploration,
        }

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        # Use expanded Wikipedia categories
        self.SPORTS_CATEGORIES = self.expanded_pools.get_all_categories()

        # Initialize API clients
        self.dbpedia_client = DBpediaClient()

        logger.info(f"Initialized with {len(self.SPORTS_CATEGORIES)} categories and {len(self.strategies)} strategies")

    def generate_random_entry(self) -> Dict:
        """使用随机策略生成入口点"""
        strategy_name = random.choice(list(self.strategies.keys()))
        strategy_func = self.strategies[strategy_name]
        return strategy_func()

    def llm_generate_sports_concept(self) -> Dict:
        """使用LLM生成多样化体育概念 - 强调全球覆盖"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        prompt = """Generate ONE random sports concept from AROUND THE WORLD.

CRITICAL GLOBAL DIVERSITY REQUIREMENTS:
- Mix ALL SPORT TYPES equally:
  * Team sports: football/soccer, basketball, cricket, rugby, baseball, hockey, volleyball
  * Individual sports: tennis, golf, swimming, athletics, boxing, gymnastics, cycling
  * Combat sports: martial arts, wrestling, boxing, fencing, judo
  * Motorsports: F1, MotoGP, NASCAR, rallying
  * Winter sports: skiing, skating, curling, snowboarding
  * Water sports: swimming, diving, surfing, rowing, sailing
  * Extreme sports: skateboarding, climbing, surfing, BMX

- Mix different REGIONS equally:
  * Africa: football, athletics, cricket, rugby
  * Asia: cricket, football, table tennis, badminton, martial arts
  * Europe: football, basketball, rugby, tennis, F1
  * Americas: baseball, basketball, American football, soccer
  * Oceania: rugby, cricket, swimming, athletics

- Mix different ERAS:
  * Ancient: Ancient Olympics, traditional sports
  * Early modern: Late 19th century sports, early Olympics
  * 20th century: Post-war sports, golden age of sport
  * Contemporary: Modern sports, current athletes

- Mix different COMPETITION LEVELS:
  * Olympics (Summer, Winter, Paralympics)
  * World Championships (FIFA, IAAF, FIBA, etc.)
  * Professional leagues (NBA, Premier League, MLB, etc.)
  * Regional competitions (Asian Games, Commonwealth Games, etc.)

AVOID overused examples: Messi, Ronaldo, LeBron James, Michael Jordan, etc.

Examples (DO NOT use these, they illustrate the DIVERSITY we want):
- "Kenya national cricket team" (African cricket)
- "Table tennis at Asian Games" (Asian table tennis)
- "Women's rugby sevens Olympics" (Women's rugby)
- "Formula 1 Monaco Grand Prix" (F1 racing)
- "Kabaddi World Cup" (South Asian sport)
- "Sumo wrestling tournaments" (Japanese sport)
- "Basque pelota championships" (Regional sport)
- "Cycling Tour de Pyrenees" (Regional cycling)
- "Water polo European championship" (European water polo)
- "Surfing Pipeline Masters" (Surfing competition)

Format: Return ONLY the sports concept name (2-6 words), nothing else.

Now generate ONE diverse concept:"""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}])
            concept = response.strip()

            # Clean up any markdown formatting
            concept = concept.replace("**", "").replace("*", "").strip()

            if len(concept) > 100:
                concept = concept[:100]

            logger.info(f"LLM generated sports concept: {concept}")

            return {
                "title": concept,
                "source": "llm_sports_concept",
                "type": "sports_entity"
            }

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            # Fallback to expanded pools
            all_sports = self.expanded_pools.get_all_sports_types()
            all_comps = self.expanded_pools.get_all_competitions()
            sport = random.choice(all_sports)
            comp = random.choice(all_comps)
            fallback = f"{sport} {comp}"
            return {
                "title": fallback,
                "source": "llm_sports_concept",
                "type": "sports_entity"
            }

    def wikipedia_random_with_sports_angle(self) -> Dict:
        """
        从随机维基百科页面提取体育角度
        """
        try:
            # Get random Wikipedia page
            url = "https://en.wikipedia.org/api/rest_v1/page/random/summary"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            original_title = data.get("title", "")
            logger.info(f"Random Wikipedia page: {original_title}")

            # Extract sports angle
            sports_angle = self.get_sports_angle(original_title)

            logger.info(f"  Sports angle: {sports_angle}")

            return {
                "title": sports_angle,
                "source": "wikipedia_sports_angle",
                "original_title": original_title,
                "type": "sports_entity"
            }

        except Exception as e:
            logger.error(f"Wikipedia random error: {e}")
            # Fallback
            return {
                "title": "Sports events",
                "source": "wikipedia_sports_angle",
                "type": "sports_entity"
            }

    def get_sports_angle(self, title: str) -> str:
        """
        为任意维基百科页面提取体育角度

        任何话题都可能有其体育维度：
        - 人物 → 是否是运动员、教练、体育官员
        - 地点 → 体育场馆、赛事举办地
        - 组织 → 体育协会、俱乐部
        - 事件 → 体育赛事、奥运会
        - 物品 → 体育器材
        """
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        prompt = f"""The Wikipedia page is about "{title}".

Generate a 2-5 word phrase that connects this topic to its SPORTS context.

Think about:
- Is this person an athlete, coach, referee, or sports official?
- Is this place a sports venue, stadium, or host city?
- Is this organization a sports federation, league, or club?
- Is this event a sports competition, tournament, or championship?
- What sport(s) is this associated with?

Examples:
- "Michael Jordan" → "Michael Jordan basketball career"
- "Barcelona" → "FC Barcelona football club"
- "Rio de Janeiro" → "Rio sports venues Olympics"
- "International Olympic Committee" → "Olympic committee governance"
- "Wembley" → "Wembley Stadium events"
- "FIFA" → "FIFA World Cup tournaments"
- "Nike" → "Nike sports equipment sponsorship"
- "Australia" → "Australian sports achievements"

Generate ONLY the 2-5 word sports phrase, nothing else."""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}])
            angle = response.strip()
            angle = angle.replace("**", "").replace("*", "").strip()

            if len(angle) > 100:
                angle = angle[:100]

            return angle if angle else f"Sports history of {title}"

        except Exception as e:
            logger.debug(f"Sports angle extraction error: {e}")
            return f"Sports history of {title}"

    def wikipedia_random_from_category(self) -> Dict:
        """从体育相关分类中随机选择页面"""
        category = random.choice(self.SPORTS_CATEGORIES)

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
                "source": "wikipedia_sports_category",
                "category": category,
                "type": "sports_entity"
            }

        except Exception as e:
            logger.error(f"Wikipedia category error: {e}")
            # Fallback to LLM generation
            return self.llm_generate_sports_concept()

    def random_sports_keyword_search(self) -> Dict:
        """使用扩展池子生成多样化体育关键词组合"""
        # Use expanded pools to generate diverse combinations
        queries = self.expanded_pools.generate_search_queries()
        search_term = random.choice(queries)

        logger.info(f"Sports keyword search: {search_term}")

        return {
            "title": search_term,
            "source": "random_sports_keyword",
            "type": "sports_entity"
        }

    def dbpedia_random_sports_entity(self) -> Dict:
        """
        从DBpedia随机获取体育实体

        随机选择以下类型之一:
        - 运动员 (Athletes)
        - 体育队伍 (Teams/Clubs)
        - 赛事 (Competitions/Events)
        - 教练/经理 (Coaches/Managers)
        - 体育场馆 (Venues/Stadiums)
        - 体育联合会 (Federations/Organizations)
        """
        # Randomly select entity type (weighted for diversity)
        entity_types = ['athlete', 'team', 'competition', 'coach', 'venue', 'federation']
        entity_type = random.choice(entity_types)

        try:
            if entity_type == 'athlete':
                results = self.dbpedia_client.query_athletes(limit=50)
                if results:
                    entity = random.choice(results)
                    name = entity.get('name', {}).get('value', '')
                    sport = entity.get('sport', {}).get('value', '')

                    logger.info(f"DBpedia athlete: {name} ({sport})")

                    return {
                        "title": name,
                        "source": "dbpedia_sports_entity",
                        "entity_type": "athlete",
                        "sport": sport,
                        "type": "sports_entity"
                    }

            elif entity_type == 'team':
                results = self.dbpedia_client.query_sports_teams(limit=50)
                if results:
                    entity = random.choice(results)
                    name = entity.get('name', {}).get('value', '')
                    league = entity.get('league', {}).get('value', '')

                    logger.info(f"DBpedia team: {name} ({league})")

                    return {
                        "title": name,
                        "source": "dbpedia_sports_entity",
                        "entity_type": "team",
                        "league": league,
                        "type": "sports_entity"
                    }

            elif entity_type == 'competition':
                results = self.dbpedia_client.query_competitions(limit=50)
                if results:
                    entity = random.choice(results)
                    name = entity.get('name', {}).get('value', '')

                    logger.info(f"DBpedia competition: {name}")

                    return {
                        "title": name,
                        "source": "dbpedia_sports_entity",
                        "entity_type": "competition",
                        "type": "sports_entity"
                    }

            elif entity_type == 'coach':
                results = self.dbpedia_client.query_sports_coaches(limit=50)
                if results:
                    entity = random.choice(results)
                    name = entity.get('name', {}).get('value', '')
                    team = entity.get('team', {}).get('value', '')
                    sport = entity.get('sport', {}).get('value', '')

                    logger.info(f"DBpedia coach: {name} ({team})")

                    return {
                        "title": name,
                        "source": "dbpedia_sports_entity",
                        "entity_type": "coach",
                        "team": team,
                        "sport": sport,
                        "type": "sports_entity"
                    }

            elif entity_type == 'venue':
                results = self.dbpedia_client.query_sports_venues(limit=50)
                if results:
                    entity = random.choice(results)
                    name = entity.get('name', {}).get('value', '')
                    location = entity.get('location', {}).get('value', '')

                    logger.info(f"DBpedia venue: {name} ({location})")

                    return {
                        "title": name,
                        "source": "dbpedia_sports_entity",
                        "entity_type": "venue",
                        "location": location,
                        "type": "sports_entity"
                    }

            else:  # federation
                results = self.dbpedia_client.query_sports_federations(limit=50)
                if results:
                    entity = random.choice(results)
                    name = entity.get('name', {}).get('value', '')
                    sport = entity.get('sport', {}).get('value', '')

                    logger.info(f"DBpedia federation: {name}")

                    return {
                        "title": name,
                        "source": "dbpedia_sports_entity",
                        "entity_type": "federation",
                        "sport": sport,
                        "type": "sports_entity"
                    }

        except Exception as e:
            logger.error(f"DBpedia sports entity error: {e}")

        # Fallback to LLM generation
        return self.llm_generate_sports_concept()

    def sports_statistics_moment(self) -> Dict:
        """
        生成体育统计或历史时刻作为入口点

        包括:
        - 历史性比赛结果
        - 纪录保持者
        - 著名体育时刻
        """
        # Choose random type
        moment_types = ['record', 'historic_match', 'championship']
        moment_type = random.choice(moment_types)

        try:
            if moment_type == 'record':
                # Use famous athletes from pools
                category = random.choice(list(self.expanded_pools.FAMOUS_ATHLETES.keys()))
                athlete = random.choice(self.expanded_pools.FAMOUS_ATHLETES[category])
                concept = f"{athlete} world records {category}"

            elif moment_type == 'historic_match':
                # Use historic moments
                moment = random.choice(self.expanded_pools.HISTORIC_MOMENTS)
                concept = moment

            else:  # championship
                # Use famous venues
                venue_type = random.choice(list(self.expanded_pools.FAMOUS_VENUES.keys()))
                venue = random.choice(self.expanded_pools.FAMOUS_VENUES[venue_type])
                comp = random.choice(self.expanded_pools.get_all_competitions())
                concept = f"{venue} {comp}"

            logger.info(f"Sports statistics/moment: {concept}")

            return {
                "title": concept,
                "source": "sports_statistics",
                "moment_type": moment_type,
                "type": "sports_entity"
            }

        except Exception as e:
            logger.error(f"Sports statistics error: {e}")
            return self.llm_generate_sports_concept()

    def official_sports_website(self) -> Dict:
        """
        从官方体育网站获取数据作为入口点

        包括:
        - MMA/UFC (ufc.com)
        - Boxing (BoxRec.com)
        - Football (FIFA, UEFA, Premier League, etc.)
        - Basketball (NBA, FIBA, EuroLeague)
        - Tennis (ATP, WTA, Grand Slams)
        - Motorsports (F1, MotoGP, NASCAR)
        - Esports (Liquipedia, HLTV, LoL Esports)
        - Golf (PGA, European Tour)
        - Cricket (ICC, ESPNcricinfo)
        """
        # Get all official websites from expanded pools
        all_websites = []
        for sport, websites in self.expanded_pools.OFFICIAL_WEBSITES.items():
            for url in websites:
                all_websites.append({"sport": sport, "url": url})

        # Random website
        selected = random.choice(all_websites)
        sport = selected["sport"]
        url = selected["url"]

        # Extract website name from URL
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '').split('.')[0]
        website_name = domain.replace('.', ' ').title()

        # Generate a search concept based on the website
        concepts = [
            f"{website_name} records",
            f"{website_name} statistics",
            f"{website_name} championships",
            f"{website_name} history",
            f"{sport} data from {website_name}",
        ]
        concept = random.choice(concepts)

        logger.info(f"Official sports website: {website_name} ({sport})")

        return {
            "title": concept,
            "source": "official_sports_website",
            "sport": sport,
            "url": url,
            "website_name": website_name,
            "type": "sports_entity"
        }

    def llm_generate_cold_sports_entity(self) -> Dict:
        """专门生成冷门体育实体 - 难度更高"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        prompt = """Generate ONE COLD/OBSCURE sports entity.

CRITICAL: This must be a LESSER-KNOWN entity that requires deep searching.
AVOID: Any famous athlete, major league, well-known competition, or household name.

PRIORITIZE:
- Regional/local competitions (state leagues, amateur championships)
- Historical athletes from pre-1950s
- Emerging sports or traditional/indigenous games
- Minor leagues and lower divisions
- Paralympic athletes (less media coverage)
- Women's sports in non-dominant regions
- Niche combat sports (beyond boxing/MMA)
- Defunct tournaments and leagues
- Sports in developing nations

Examples of COLD entities (DO NOT use, but similar obscurity):
- "1950s Victorian Football League reserves"
- "Kabaddi federation Nepal"
- "Para swimming Baltic Championships"
- "Women's baseball 1940s league"
- "Basque pelota 1920s tournament"
- "East German handball league 1970s"

Return ONLY the entity name (2-6 words):"""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}], temperature=1.0)
            concept = response.strip()
            concept = concept.replace("**", "").replace("*", "").strip()

            if len(concept) > 100:
                concept = concept[:100]

            logger.info(f"LLM generated COLD sports entity: {concept}")

            return {
                "title": concept,
                "source": "llm_cold_sports_entity",
                "type": "sports_entity"
            }

        except Exception as e:
            logger.error(f"Cold entity generation failed: {e}")
            return self.llm_generate_sports_concept()

    def wikipedia_random_from_subcategory(self) -> Dict:
        """从体育相关分类及其子分类中递归随机选择页面"""
        try:
            # 随机选择主分类
            category = random.choice(self.SPORTS_CATEGORIES)

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
                "type": "sports_entity"
            }

        except Exception as e:
            logger.error(f"Wikipedia subcategory error: {e}")
            return self.llm_generate_sports_concept()

    def cross_domain_sports_connection(self) -> Dict:
        """生成体育与其他领域的交叉点入口"""
        cross_domains = {
            "politics": ["sports diplomacy", "Olympic politics", "sports boycotts", "sports nationalism"],
            "science": ["sports biomechanics", "exercise physiology", "sports medicine", "performance enhancement"],
            "technology": ["sports analytics", "VAR technology", "equipment innovation", "sports data science"],
            "culture": ["sports in literature", "sports films", "sports art", "sports and music"],
            "economics": ["sports economics", "sponsorship deals", "broadcasting rights", "sports betting"],
            "geography": ["sports by region", "stadium architecture", "sports tourism", "urban sports planning"],
            "sociology": ["sports and society", "gender in sports", "race in sports", "sports fandom"],
        }

        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        domain = random.choice(list(cross_domains.keys()))
        topic = random.choice(cross_domains[domain])

        prompt = f"""Generate a specific, researchable topic about {topic} in sports.

Requirements:
- Must be specific enough for multi-hop research
- Should require connecting multiple sources
- Avoid obvious/well-known topics
- Focus on less explored angles

Examples:
- "impact of VAR on Premier League referee decisions 2019-2023"
- "Cold War Olympic boycotts effect on athletes"
- "biomechanics analysis of cricket bowling techniques"
- "economic impact of World Cup on host cities"

Generate ONE topic (3-8 words):"""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}], temperature=0.9)
            concept = response.strip()
            concept = concept.replace("**", "").replace("*", "").strip()

            if len(concept) > 150:
                concept = concept[:150]

            logger.info(f"Cross-domain sports topic: {concept} ({domain})")

            return {
                "title": concept,
                "source": "cross_domain_sports",
                "domain": domain,
                "type": "sports_entity"
            }

        except Exception as e:
            logger.error(f"Cross-domain generation failed: {e}")
            return self.llm_generate_sports_concept()

    def temporal_sports_exploration(self) -> Dict:
        """按特定时代探索体育历史"""
        eras = [
            ("Ancient", "ancient Olympic Games, traditional sports, gladiatorial games, primitive competitions"),
            ("Medieval", "medieval tournaments, folk football, early ball games, jousting"),
            ("19th Century", "Victorian era sports, early codification, first international matches, amateurism"),
            ("Early 20th", "pre-WWI sports, early Olympics, golden age of baseball, professionalization"),
            ("Interwar", "1920s-1930s sports, political influences on sport, women's sports emergence"),
            ("Post-WWII", "1950s-1960s sports, television era, modern Olympics growth, Cold War sports"),
            ("Cold War Era", "Olympic boycotts, East-West rivalry, state-sponsored athletes, doping origins"),
            ("Pre-Internet", "1970s-1990s sports, pre-globalization era, commercialization beginnings"),
            ("Turn of Millennium", "1990s-2000s sports, Premier League formation, modern commercial sports"),
        ]

        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        era_name, era_context = random.choice(eras)

        prompt = f"""Generate a specific sports research topic from the {era_name} ({era_context}).

Requirements:
- Must be a specific event, athlete, or phenomenon from this era
- Should require historical research
- Avoid well-documented famous topics
- Focus on lesser-known aspects

Examples:
- "1924 Chamonix Winter Olympics opening ceremony"
- "1954 Hungarian football team Golden Year"
- "1972 Munich Olympics security aftermath"
- "Early 1900s lacrosse in Canada"

Generate ONE topic (3-7 words):"""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}], temperature=0.9)
            concept = response.strip()
            concept = concept.replace("**", "").replace("*", "").strip()

            if len(concept) > 150:
                concept = concept[:150]

            logger.info(f"Temporal sports topic: {concept} ({era_name})")

            return {
                "title": concept,
                "source": "temporal_sports",
                "era": era_name,
                "type": "sports_entity"
            }

        except Exception as e:
            logger.error(f"Temporal exploration failed: {e}")
            return self.llm_generate_sports_concept()

