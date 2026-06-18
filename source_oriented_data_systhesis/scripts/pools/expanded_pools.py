#!/usr/bin/env python3
"""
Expanded Historical Data Pools

This module provides expanded, diverse pools for historical data generation,
designed to minimize regional and temporal bias.

Coverage:
- All continents and major regions
- Time periods from ancient to modern (3000 BC - 1950 AD)
- Multiple domains: political, military, cultural, economic, scientific, religious
"""

from typing import List, Dict, Set
import random

# ============================================================================
# EXPANDED HISTORICAL POOLS
# ============================================================================

class ExpandedHistoricalPools:
    """
    大规模历史数据池 - 覆盖全球、全时代、多领域
    Designed to minimize bias and maximize diversity
    """

    # ========== TIME PERIODS (覆盖全人类历史) ==========

    TIME_PERIODS = {
        "ancient": [
            "Bronze Age", "Iron Age", "Classical Antiquity", "Hellenistic Period",
            "Roman Republic", "Roman Empire", "Han Dynasty", "Maurya Empire",
            "Gupta Empire", "Axumite Kingdom", "Olmec", "Maya Preclassic",
            "Persian Empire", "Parthian Empire", "Qin Dynasty", "Three Kingdoms",
            "Late Antiquity", "Vedic Period", "Zhou Dynasty", "Mycenaean Greece"
        ],
        "medieval": [
            "Early Middle Ages", "High Middle Ages", "Late Middle Ages",
            "Islamic Golden Age", "Song Dynasty", "Tang Dynasty", "Yuan Dynasty",
            "Ming Dynasty", "Feudal Japan", "Heian Period", "Kamakura Period",
            "Viking Age", "Byzantine Empire", "Mongol Empire", "Delhi Sultanate",
            "Chola Empire", "Holy Roman Empire", "Crusades", "Joseon Dynasty"
        ],
        "early_modern": [
            "Renaissance", "Age of Discovery", "Reformation", "Counter-Reformation",
            "Ming Dynasty", "Qing Dynasty", "Edo Period", "Ottoman Empire",
            "Safavid Empire", "Mughal Empire", "Spanish Empire", "Portuguese Empire",
            "Age of Enlightenment", "Industrial Revolution", "French Revolution",
            "Napoleonic Era", "Meiji Restoration", "Colonial Era"
        ],
        "modern": [
            "Victorian Era", "Gilded Age", "Belle Époque", "Progressive Era",
            "Interwar Period", "Great Depression", "World War I", "World War II",
            "Cold War", "Post-colonial Era"
        ]
    }

    # ========== REGIONS (覆盖全球所有地区) ==========

    REGIONS = {
        "east_asia": [
            "China", "Japan", "Korea", "Mongolia", "Taiwan", "Manchuria",
            "Ryukyu Kingdom", "Tibet", "Xinjiang", "Inner Mongolia"
        ],
        "southeast_asia": [
            "Vietnam", "Thailand", "Cambodia", "Laos", "Myanmar", "Malaysia",
            "Indonesia", "Philippines", "Singapore", "Brunei", "East Timor",
            "Champa", "Srivijaya", "Majapahit", "Ayutthaya Kingdom"
        ],
        "south_asia": [
            "India", "Pakistan", "Bangladesh", "Sri Lanka", "Nepal", "Bhutan",
            "Maldives", "Afghanistan", "Bengal", "Punjab", "Kashmir",
            "Maratha Empire", "Mughal Empire", "Delhi Sultanate", "Vijayanagara Empire"
        ],
        "central_asia": [
            "Kazakhstan", "Uzbekistan", "Turkmenistan", "Kyrgyzstan", "Tajikistan",
            "Silk Road", "Samarkand", "Bukhara", "Khiva", "Khanate of Sibir"
        ],
        "west_asia": [
            "Turkey", "Iran", "Iraq", "Syria", "Lebanon", "Jordan", "Israel",
            "Palestine", "Saudi Arabia", "Yemen", "Oman", "UAE", "Kuwait",
            "Bahrain", "Qatar", "Armenia", "Georgia", "Azerbaijan", "Kurdistan",
            "Mesopotamia", "Anatolia", "Levant", "Arabian Peninsula"
        ],
        "north_africa": [
            "Egypt", "Libya", "Tunisia", "Algeria", "Morocco", "Sudan",
            "Maghreb", "Carthage", "Nubia", "Kush", "Fatimid Caliphate"
        ],
        "west_africa": [
            "Nigeria", "Ghana", "Mali", "Senegal", "Ivory Coast", "Benin",
            "Togo", "Burkina Faso", "Niger", "Guinea", "Sierra Leone", "Liberia",
            "Mali Empire", "Songhai Empire", "Ashanti Empire", "Oyo Empire"
        ],
        "east_africa": [
            "Ethiopia", "Kenya", "Tanzania", "Uganda", "Rwanda", "Burundi",
            "Somalia", "Djibouti", "Eritrea", "Sudan", "Madagascar",
            "Axum", "Zanzibar", "Swahili Coast", "Great Zimbabwe"
        ],
        "central_africa": [
            "DRC", "Congo", "Cameroon", "Central African Republic", "Gabon",
            "Equatorial Guinea", "Sao Tome", "Kongo Kingdom", "Luba Empire",
            "Lunda Empire", "Kingdom of Loango"
        ],
        "southern_africa": [
            "South Africa", "Zimbabwe", "Zambia", "Malawi", "Mozambique",
            "Botswana", "Namibia", "Lesotho", "Eswatini", "Angola",
            "Zulu Kingdom", "Xhosa", "Boer Republics", "Cape Colony"
        ],
        "europe": [
            "Britain", "France", "Germany", "Italy", "Spain", "Portugal",
            "Netherlands", "Belgium", "Switzerland", "Austria", "Poland",
            "Czech Republic", "Slovakia", "Hungary", "Romania", "Bulgaria",
            "Serbia", "Croatia", "Slovenia", "Greece", "Norway", "Sweden",
            "Denmark", "Finland", "Ireland", "Scotland", "Ukraine", "Russia",
            "Baltic States", "Balkans", "Scandinavia", "Iberian Peninsula"
        ],
        "russia": [
            "Russia", "Soviet Union", "Russian Empire", "Kievan Rus'",
            "Muscovy", "Siberia", "Caucasus", "Crimea", "Ukraine", "Belarus"
        ],
        "americas": [
            "United States", "Canada", "Mexico", "Brazil", "Argentina", "Chile",
            "Peru", "Colombia", "Venezuela", "Ecuador", "Bolivia", "Paraguay",
            "Uruguay", "Guatemala", "Cuba", "Haiti", "Dominican Republic",
            "Jamaica", "Trinidad", "Aztec Empire", "Inca Empire", "Maya Civilization"
        ],
        "oceania": [
            "Australia", "New Zealand", "Fiji", "Papua New Guinea", "Solomon Islands",
            "Vanuatu", "Samoa", "Tonga", "Tahiti", "Hawaii", "Micronesia",
            "Polynesia", "Melanesia", "Micronesia", "Maori", "Aboriginal Australia"
        ]
    }

    # ========== DOMAINS (多领域覆盖) ==========

    DOMAINS = {
        "political": [
            "empire", "kingdom", "republic", "democracy", "monarchy", "dynasty",
            "caliphate", "sultanate", "colonialism", "independence", "revolution",
            "treaty", "alliance", "confederation", "federation", "union",
            "sovereignty", "autonomy", "partition", "annexation", "diplomacy"
        ],
        "military": [
            "war", "battle", "siege", "campaign", "invasion", "conquest",
            "rebellion", "uprising", "insurgency", "guerrilla", "civil war",
            "crusade", "jihad", "military order", "fortress", "naval battle",
            "military strategy", "warfare", "peacekeeping", "armistice", "surrender"
        ],
        "cultural": [
            "renaissance", "enlightenment", "reformation", "philosophy", "art",
            "literature", "music", "architecture", "sculpture", "painting",
            "religion", "mythology", "folklore", "tradition", "festival",
            "language", "education", "university", "library", "manuscript"
        ],
        "economic": [
            "trade", "commerce", "merchant", "market", "currency", "banking",
            "industry", "manufacturing", "agriculture", "farming", "mining",
            "slavery", "labor", "union", "strike", "boycott", "tariff",
            "economic system", "feudalism", "capitalism", "socialism", "mercantilism"
        ],
        "scientific": [
            "discovery", "invention", "innovation", "scientific revolution",
            "medicine", "astronomy", "mathematics", "physics", "chemistry",
            "biology", "geography", "exploration", "expedition", "navigation",
            "technology", "engineering", "printing press", "gunpowder", "compass"
        ],
        "religious": [
            "Christianity", "Islam", "Buddhism", "Hinduism", "Judaism", "Sikhism",
            "Confucianism", "Taoism", "Shinto", "Zoroastrianism", "Jainism",
            "church", "temple", "mosque", "monastery", "pilgrimage",
            "crusade", "jihad", "missionary", "conversion", "schism", "heresy"
        ],
        "social": [
            "society", "class", "caste", "slavery", "serfdom", "feudalism",
            "women", "gender", "family", "marriage", "children", "education",
            "migration", "immigration", "diaspora", "refugee", "urbanization",
            "reform", "movement", "activism", "protest", "civil rights"
        ]
    }

    # ========== ROLES (人物角色) ==========

    ROLES = {
        "political": [
            "emperor", "king", "queen", "prince", "princess", "duke", "duchess",
            "president", "prime minister", "chancellor", "dictator", "revolutionary",
            "diplomat", "ambassador", "envoy", "delegate", "representative"
        ],
        "military": [
            "general", "admiral", "commander", "captain", "soldier", "warrior",
            "knight", "samurai", "martial artist", "mercenary", "conquistador",
            "strategist", "tactician", "veteran", "hero", "warlord"
        ],
        "religious": [
            "priest", "monk", "nun", "prophet", "saint", "mystic", "missionary",
            "imam", "rabbi", "guru", "lama", "shaman", "bishop", "pope", "caliph"
        ],
        "intellectual": [
            "philosopher", "scholar", "scientist", "inventor", "artist", "writer",
            "poet", "historian", "mathematician", "astronomer", "physician",
            "teacher", "professor", "researcher", "thinker", "intellectual"
        ],
        "economic": [
            "merchant", "trader", "banker", "industrialist", "entrepreneur",
            "craftsman", "artisan", "farmer", "laborer", "slave", "servant"
        ],
        "explorers": [
            "explorer", "navigator", "pioneer", "colonist", "settler",
            "missionary", "anthropologist", "archaeologist", "cartographer"
        ]
    }

    # ========== EVENTS (事件类型) ==========

    EVENTS = [
        "war", "battle", "siege", "invasion", "conquest", "rebellion", "revolution",
        "treaty", "alliance", "declaration of war", "peace treaty", "armistice",
        "coronation", "accession", "abdication", "succession", "dynastic change",
        "founding", "collapse", "fall of empire", "independence", "unification",
        "discovery", "invention", "innovation", "breakthrough", "publication",
        "reform", "movement", "campaign", "crusade", "jihad", "mission",
        "conference", "congress", "summit", "council", "synod",
        "assassination", "execution", "exile", "imprisonment", "escape"
    ]

    # ========== WIKIPEDIA CATEGORIES (扩展分类池) ==========

    WIKIPEDIA_CATEGORIES = {
        # By time period
        "time": [
            "Category:Bronze_Age", "Category:Iron_Age", "Category:Classical_antiquity",
            "Category:Middle_Ages", "Category:Renaissance", "Category:Early_modern_period",
            "Category:18th_century", "Category:19th_century", "Category:20th_century",
            "Category:Ancient_history", "Category:Medieval_history",
            "Category:Early_modern_history", "Category:Modern_history"
        ],
        # By region
        "region_africa": [
            "Category:History_of_Africa", "Category:African_empires",
            "Category:History_of_North_Africa", "Category:History_of_West_Africa",
            "Category:History_of_East_Africa", "Category:History_of_Central_Africa",
            "Category:History_of_Southern_Africa", "Category:Ancient_Egypt",
            "Category:Kingdoms_of_Africa", "Category:Decolonization_in_Africa"
        ],
        "region_americas": [
            "Category:History_of_the_Americas", "Category:Pre-Columbian_era",
            "Category:Colonization_of_the_Americas", "Category:History_of_North_America",
            "Category:History_of_South_America", "Category:History_of_Latin_America",
            "Category:History_of_the_United_States", "Category:History_of_Canada",
            "Category:History_of_Mexico", "Category:History_of_Brazil",
            "Category:Native-American_history", "Category:Indigenous_peoples_of_the_Americas"
        ],
        "region_asia": [
            "Category:History_of_Asia", "Category:History_of_East_Asia",
            "Category:History_of_Southeast_Asia", "Category:History_of_South_Asia",
            "Category:History_of_Central_Asia", "Category:History_of_West_Asia",
            "Category:Chinese_history", "Category:Japanese_history", "Category:Korean_history",
            "Category:Indian_history", "Category:History_of_the_Middle_East"
        ],
        "region_europe": [
            "Category:History_of_Europe", "Category:History_of_Western_Europe",
            "Category:History_of_Eastern_Europe", "Category:History_of_Northern_Europe",
            "Category:History_of_Southern_Europe", "Category:History_of_the_Balkans",
            "Category:Roman_Empire", "Category:Byzantine_Empire",
            "Category:Holy_Roman_Empire", "Category:Ottoman_Empire_in_Europe"
        ],
        "region_oceania": [
            "Category:History_of_Oceania", "Category:History_of_Australia",
            "Category:History_of_New_Zealand", "Category:History_of_the_Pacific_Islands",
            "Category:Polynesian_culture", "Category:Indigenous_Australians"
        ],
        # By domain
        "domain_political": [
            "Category:Political_history", "Category:Diplomacy", "Category:Treaties",
            "Category:International_relations", "Category:Government", "Category:Politics",
            "Category:Revolutions", "Category:Rebellions", "Category:Civil_wars",
            "Category:Wars_by_country", "Category:Peace_treaties"
        ],
        "domain_military": [
            "Category:Military_history", "Category:Battles", "Category:Wars",
            "Category:Military_leaders", "Category:Warfare", "Category:Sieges",
            "Category:Naval_battles", "Category:Military_campaigns"
        ],
        "domain_cultural": [
            "Category:Cultural_history", "Category:Art_history", "Category:Music_history",
            "Category:Literary_history", "Category:Philosophy", "Category:Religion",
            "Category:Science_and_technology_history", "Category:Education_history"
        ],
        "domain_economic": [
            "Category:Economic_history", "Category:Business_history", "Category:Labor_history",
            "Category:Trade", "Category:Industrial_history", "Category:Agricultural_history"
        ],
        "domain_social": [
            "Category:Social_history", "Category:Women's_history", "Category:Gender_history",
            "Category:Slavery", "Category:Migration_history", "Category:Urban_history"
        ],
        # By topic
        "topic": [
            "Category:Empires", "Category:Kingdoms", "Category:Colonialism",
            "Category:Decolonization", "Category:Nationalism", "Category:Imperialism",
            "Category:Exploration", "Category:Discovery_and_exploration",
            "Category:Historical_figures", "Category:Historians", "Category:Archaeology"
        ]
    }

    @classmethod
    def get_all_categories(cls) -> List[str]:
        """获取所有Wikipedia分类"""
        all_cats = []
        for category_list in cls.WIKIPEDIA_CATEGORIES.values():
            all_cats.extend(category_list)
        return all_cats

    @classmethod
    def get_random_combination(cls) -> Dict[str, str]:
        """
        生成随机的历史探索组合
        Returns: dict with time_period, region, domain, role, event
        """
        # Random time period
        era = random.choice(list(cls.TIME_PERIODS.keys()))
        time_period = random.choice(cls.TIME_PERIODS[era])

        # Random region
        region_key = random.choice(list(cls.REGIONS.keys()))
        region = random.choice(cls.REGIONS[region_key])

        # Random domain
        domain_key = random.choice(list(cls.DOMAINS.keys()))
        domain = random.choice(cls.DOMAINS[domain_key])

        # Random role
        role_key = random.choice(list(cls.ROLES.keys()))
        role = random.choice(cls.ROLES[role_key])

        # Random event
        event = random.choice(cls.EVENTS)

        return {
            "era": era,
            "time_period": time_period,
            "region_key": region_key,
            "region": region,
            "domain_key": domain_key,
            "domain": domain,
            "role_key": role_key,
            "role": role,
            "event": event
        }

    @classmethod
    def generate_search_queries(cls) -> List[str]:
        """生成多样化的搜索查询组合"""
        combinations = []

        # 1. Time + Region (e.g., "Medieval West Africa")
        era = random.choice(list(cls.TIME_PERIODS.keys()))
        time = random.choice(cls.TIME_PERIODS[era])
        region_key = random.choice(list(cls.REGIONS.keys()))
        region = random.choice(cls.REGIONS[region_key])
        combinations.append(f"{time} {region}")

        # 2. Region + Domain (e.g., "China trade history")
        region_key = random.choice(list(cls.REGIONS.keys()))
        region = random.choice(cls.REGIONS[region_key])
        domain_key = random.choice(list(cls.DOMAINS.keys()))
        domain = random.choice(cls.DOMAINS[domain_key])
        combinations.append(f"{region} {domain} history")

        # 3. Time + Domain (e.g., "Renaissance art")
        era = random.choice(list(cls.TIME_PERIODS.keys()))
        time = random.choice(cls.TIME_PERIODS[era])
        domain_key = random.choice(list(cls.DOMAINS.keys()))
        domain = random.choice(cls.DOMAINS[domain_key])
        combinations.append(f"{time} {domain}")

        # 4. Region + Role (e.g., "Japanese samurai")
        region_key = random.choice(list(cls.REGIONS.keys()))
        region = random.choice(cls.REGIONS[region_key])
        role_key = random.choice(list(cls.ROLES.keys()))
        role = random.choice(cls.ROLES[role_key])
        combinations.append(f"{region} {role}")

        # 5. Time + Region + Role (e.g., "19th century German philosopher")
        era = random.choice(list(cls.TIME_PERIODS.keys()))
        time = random.choice(cls.TIME_PERIODS[era])
        region_key = random.choice(list(cls.REGIONS.keys()))
        region = random.choice(cls.REGIONS[region_key])
        role_key = random.choice(list(cls.ROLES.keys()))
        role = random.choice(cls.ROLES[role_key])
        combinations.append(f"{time} {region} {role}")

        # 6. Region + Event (e.g., "French Revolution")
        region_key = random.choice(list(cls.REGIONS.keys()))
        region = random.choice(cls.REGIONS[region_key])
        event = random.choice(cls.EVENTS)
        combinations.append(f"{region} {event}")

        return combinations


# ============================================================================
# DYNAMIC CATEGORY DISCOVERY
# ============================================================================

class DynamicCategoryDiscovery:
    """
    动态Wikipedia分类发现
    通过分类层次结构自动发现相关分类
    """

    DISCOVERY_SEEDS = [
        "Category:History",
        "Category:Historical_eras",
        "Category:Historiography",
        "Category:Chronology",
        "Category:History_by_country",
        "Category:History_by_continent",
        "Category:History_by_period"
    ]

    @staticmethod
    def get_subcategories(category: str, depth: int = 1) -> List[str]:
        """
        获取Wikipedia分类的子分类
        Args:
            category: 分类名称 (e.g., "Category:History")
            depth: 深度 (1=直接子分类, 2=递归)
        Returns:
            子分类列表
        """
        import requests

        api_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmtype": "subcat",
            "cmlimit": 500,
            "format": "json"
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        try:
            response = requests.get(api_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            members = data.get("query", {}).get("categorymembers", [])
            subcategories = [m["title"] for m in members]

            if depth > 1:
                for subcat in subcategories[:10]:  # Limit recursion
                    subcats = DynamicCategoryDiscovery.get_subcategories(subcat, depth-1)
                    subcategories.extend(subcats)

            return subcategories

        except Exception as e:
            print(f"Error discovering categories: {e}")
            return []

    @classmethod
    def discover_categories(cls, seed_categories: List[str] = None,
                           max_per_seed: int = 20) -> List[str]:
        """
        从种子分类出发发现相关分类
        """
        if seed_categories is None:
            seed_categories = cls.DISCOVERY_SEEDS

        all_categories = set()

        for seed in seed_categories:
            print(f"Discovering from: {seed}")
            subcats = cls.get_subcategories(seed, depth=1)
            all_categories.update(subcats[:max_per_seed])

        return list(all_categories)


# ============================================================================
# LLM-BASED DIVERSE GENERATION
# ============================================================================

class LLMDiverseGenerator:
    """
    使用LLM生成多样化的历史探索起点
    确保地域、时代、领域的多样性
    """

    @staticmethod
    def generate_diverse_concept(focus_region: str = None,
                                  focus_era: str = None) -> str:
        """
        生成多样化的历史概念
        Args:
            focus_region: 可选地区限制
            focus_era: 可选时代限制
        """
        # This would use APICaller to generate concepts
        # Implementation depends on your API setup
        pass


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("EXPANDED HISTORICAL POOLS - STATISTICS")
    print("=" * 70)

    pools = ExpandedHistoricalPools()

    print(f"\nTime Periods: {sum(len(v) for v in pools.TIME_PERIODS.values())}")
    print(f"  - Ancient: {len(pools.TIME_PERIODS['ancient'])}")
    print(f"  - Medieval: {len(pools.TIME_PERIODS['medieval'])}")
    print(f"  - Early Modern: {len(pools.TIME_PERIODS['early_modern'])}")
    print(f"  - Modern: {len(pools.TIME_PERIODS['modern'])}")

    print(f"\nRegions: {sum(len(v) for v in pools.REGIONS.values())}")
    for region_key, region_list in pools.REGIONS.items():
        print(f"  - {region_key}: {len(region_list)}")

    print(f"\nDomains: {sum(len(v) for v in pools.DOMAINS.values())}")
    for domain_key, domain_list in pools.DOMAINS.items():
        print(f"  - {domain_key}: {len(domain_list)}")

    print(f"\nRoles: {sum(len(v) for v in pools.ROLES.values())}")
    for role_key, role_list in pools.ROLES.items():
        print(f"  - {role_key}: {len(role_list)}")

    print(f"\nEvents: {len(pools.EVENTS)}")

    print(f"\nWikipedia Categories: {len(pools.get_all_categories())}")

    print("\n" + "=" * 70)
    print("SAMPLE RANDOM COMBINATIONS")
    print("=" * 70)

    for i in range(5):
        combo = pools.get_random_combination()
        print(f"\n[{i+1}] {combo['time_period']} | {combo['region']} | "
              f"{combo['domain']} | {combo['role']}")

    print("\n" + "=" * 70)
    print("SAMPLE SEARCH QUERIES")
    print("=" * 70)

    for i in range(5):
        queries = pools.generate_search_queries()
        for j, query in enumerate(queries):
            print(f"{j+1}. {query}")
        print()
