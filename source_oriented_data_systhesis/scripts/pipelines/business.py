#!/usr/bin/env python3
"""
BusinessEntryPointGenerator - Entry Point Generator for Business Domain

This module contains the entry point generation strategies for the Business domain.
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
from pools import ExpandedBusinessPools
import os
from apis.business_apis import YahooFinanceClient, WikidataBusinessClient, DBpediaBusinessClient, WorldBankClient, SECClient
from apis.business_websites import BloombergClient, ReutersClient, ForbesClient, CNBCClient, BusinessInsiderClient, TechCrunchClient, YahooFinanceWebClient, FortuneClient, HBRClient

class BusinessEntryPointGenerator:
    """
    商业数据入口点生成器 - 使用扩展池子

    使用多种策略生成商业相关的探索入口点
    覆盖全球所有行业、公司类型、地区、商业功能
    """

    def __init__(self):
        # Use expanded pools for better diversity
        self.expanded_pools = ExpandedBusinessPools()

        # Initialize all strategies
        self.strategies = {
            # Basic strategies (5)
            'llm_business_concept': self.llm_generate_business_concept,
            'wikipedia_business_angle': self.wikipedia_random_with_business_angle,
            'wikipedia_business_category': self.wikipedia_random_from_category,
            'random_business_keyword': self.random_business_keyword_search,
            'dbpedia_business_entity': self.dbpedia_random_business_entity,

            # News API strategies (2)
            'newsapi_business': self.newsapi_business_headlines,
            'google_news': self.google_news_business,

            # Company data strategies (4)
            'yahoo_finance': self.yahoo_finance_random,
            'wikidata_company': self.wikidata_random_company,
            'fortune_lists': self.fortune_list_company,
            'sec_filings': self.sec_filing_random,

            # Economic data strategies (2)
            'world_bank': self.world_bank_indicator,
            'fred_economic': self.fred_indicator,

            # Business website strategies (8+, no API required)
            'bloomberg': self.bloomberg_random,
            'reuters': self.reuters_random,
            'forbes': self.forbes_random,
            'cnbc': self.cnbc_random,
            'business_insider': self.business_insider_random,
            'techcrunch': self.techcrunch_random,
            'yahoo_finance_web': self.yahoo_finance_web_random,
            'fortune_website': self.fortune_website_random,
            'hbr': self.hbr_random,
        }

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        # Use expanded Wikipedia categories
        self.BUSINESS_CATEGORIES = self.expanded_pools.get_all_categories()

        # Initialize basic clients (no API key required)
        self.yahoo_client = YahooFinanceClient()
        self.wikidata_client = WikidataBusinessClient()
        self.dbpedia_client = DBpediaBusinessClient()
        self.world_bank_client = WorldBankClient()

        # Initialize website clients (no API key required)
        self.bloomberg_client = BloombergClient()
        self.reuters_client = ReutersClient()
        self.forbes_client = ForbesClient()
        self.cnbc_client = CNBCClient()
        self.bi_client = BusinessInsiderClient()
        self.techcrunch_client = TechCrunchClient()
        self.yahoo_web_client = YahooFinanceWebClient()
        self.fortune_client = FortuneClient()
        self.hbr_client = HBRClient()

        # Initialize optional clients (require API keys)
        self.newsapi_client = None
        self.fred_client = None
        self.sec_client = SECClient()

        # Try to initialize optional clients if API keys are available
        newsapi_key = os.getenv('NEWSAPI_KEY')
        if newsapi_key:
            try:
                self.newsapi_client = NewsAPIClient(api_key=newsapi_key)
                logger.info("NewsAPI client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize NewsAPI client: {e}")

        fred_key = os.getenv('FRED_API_KEY')
        if fred_key:
            try:
                self.fred_client = FREDClient(api_key=fred_key)
                self.strategies['fred_economic'] = self.fred_indicator
                logger.info("FRED client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize FRED client: {e}")

        num_strategies = len(self.strategies)
        logger.info(f"Initialized with {len(self.BUSINESS_CATEGORIES)} categories and {num_strategies} strategies")

    def generate_random_entry(self) -> Dict:
        """使用随机策略生成入口点"""
        strategy_name = random.choice(list(self.strategies.keys()))
        strategy_func = self.strategies[strategy_name]
        return strategy_func()

    # ========================================================================
    # Strategy 1: LLM generates business concept
    # ========================================================================

    def llm_generate_business_concept(self) -> Dict:
        """使用LLM生成多样化商业概念 - 强调全球覆盖"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        prompt = """Generate ONE random business or economic concept FROM AROUND THE WORLD.

CRITICAL GLOBAL DIVERSITY REQUIREMENTS:
- Mix ALL BUSINESS SECTORS equally:
  * Technology: Software, Hardware, AI, Cloud, Cybersecurity, FinTech, EdTech, HealthTech
  * Finance: Banking, Investment, Insurance, Venture Capital, Private Equity, Asset Management
  * Healthcare: Pharmaceuticals, Biotechnology, Medical Devices, Telemedicine, Health Insurance
  * Consumer: Retail, E-commerce, Food & Beverage, Luxury Goods, Entertainment, Media
  * Industrial: Manufacturing, Automotive, Aerospace, Chemicals, Construction, Energy
  * Services: Consulting, Marketing, Logistics, Real Estate, Hospitality

- Mix ALL REGIONS equally:
  * North America: US, Canada, Mexico (Silicon Valley, New York, Toronto)
  * Europe: UK, Germany, France, Netherlands, Sweden, Switzerland, Ireland
  * Asia: China, Japan, South Korea, India, Singapore, Hong Kong, Southeast Asia
  * Latin America: Brazil, Argentina, Chile, Colombia, Mexico
  * Middle East & Africa: UAE, Saudi Arabia, Israel, South Africa, Nigeria
  * Oceania: Australia, New Zealand

- Mix COMPANY TYPES equally:
  * Startups (Seed, Series A, Series B+)
  * SMEs (Small and Medium Enterprises)
  * Large Corporations
  * Multinational Corporations
  * Family-owned businesses
  * State-owned enterprises
  * Fortune 500 companies

- Mix BUSINESS FUNCTIONS equally:
  * Finance & Accounting (CFO, treasury, financial planning)
  * Marketing & Sales (CMO, digital marketing, customer acquisition)
  * Operations & Supply Chain (COO, logistics, manufacturing)
  * Strategy & Management (CEO, board, corporate strategy)
  * Human Resources (CHRO, talent, organizational development)
  * Technology & IT (CTO, software engineering, data, cybersecurity)

- Mix BUSINESS TOPICS equally:
  * Strategy: Competitive advantage, market positioning, differentiation, M&A, IPO
  * Finance: Revenue, profit margin, EBITDA, valuation, capital structure
  * Marketing: Market segmentation, customer acquisition, brand equity, conversion
  * Operations: Supply chain, lean operations, quality management, automation
  * Leadership: Corporate governance, change management, organizational culture
  * Trends: Digital transformation, AI in business, ESG, sustainability

AVOID overused examples: Apple, Tesla, Amazon, Google, Microsoft, Meta, etc.

Examples (DO NOT use these, they illustrate the DIVERSITY we want):
- "SoftBank Vision Fund investment strategy"
- "Reliance Industries digital transformation"
- "Naspers e-commerce expansion Africa"
- "Grab super app business model"
- "MercadoLibre Latin American logistics"
- "Adyen European payments infrastructure"
- "Jollibee fast food expansion strategy"
- "BYD electric vehicle vertical integration"
- "Zomato food delivery India unit economics"
- "Kakao ecosystem business model"
- "Dangote cement African manufacturing"
- "Sea Group Southeast Asia super app"
- "Nubank Brazilian digital banking"
- "Flipkart e-commerce India vs Amazon"
- "Gojek super app Indonesia strategy"

Format: Return ONLY the business concept name (2-6 words), nothing else.

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

            logger.info(f"LLM generated business concept: {concept}")

            return {
                "title": concept,
                "source": "llm_business_concept",
                "type": "business_entity"
            }

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            # Fallback to expanded pools
            all_industries = self.expanded_pools.get_all_industries()
            all_regions = self.expanded_pools.get_all_regions()
            industry = random.choice(all_industries)
            region = random.choice(all_regions)
            fallback = f"{region} {industry}"
            return {
                "title": fallback,
                "source": "llm_business_concept",
                "type": "business_entity"
            }

    # ========================================================================
    # Strategy 2: Wikipedia random + business angle
    # ========================================================================

    def wikipedia_random_with_business_angle(self) -> Dict:
        """随机Wikipedia页面 + 从商业角度探索"""
        try:
            # Get random Wikipedia page
            url = "https://en.wikipedia.org/api/rest_v1/page/random/summary"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            original_title = data.get("title", "")
            logger.info(f"Random Wikipedia page: {original_title}")

            # Generate business angle
            business_angle = self.get_business_angle(original_title)

            logger.info(f"  Business angle: {business_angle}")

            return {
                "title": business_angle,
                "source": "wikipedia_business_angle",
                "original_title": original_title,
                "type": "business_entity"
            }

        except Exception as e:
            logger.error(f"Wikipedia random error: {e}")
            # Fallback
            return {
                "title": "Business and economics",
                "source": "wikipedia_business_angle",
                "type": "business_entity"
            }

    def get_business_angle(self, title: str) -> str:
        """为任意词条生成商业相关的探索角度"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        prompt = f"""The Wikipedia page is about "{title}".

Generate a 2-5 word phrase that connects this topic to its BUSINESS or ECONOMIC context.

Think about:
- Is this person a CEO, founder, entrepreneur, investor, or business leader?
- Is this company a public corporation, private company, startup, or multinational?
- Is this place a business hub, financial center, or corporate headquarters?
- Is this product/service related to business operations, revenue, or markets?
- Is this concept related to finance, economics, management, or strategy?
- What industry or sector is this associated with?
- What business function or discipline does this relate to?

Examples:
- "Elon Musk" → "Tesla CEO business strategy"
- "New York" → "Wall Street financial markets"
- "iPhone" → "Apple product business model"
- "Cloud computing" → "cloud services market revenue"
- "Saudi Arabia" → "Saudi Aramco oil business"
- "Bitcoin" → "cryptocurrency market trading"
- "Harvard" → "Harvard Business School research"
- "AI" → "artificial intelligence business applications"

For "{title}", return ONLY the 2-5 word business/economic phrase, nothing else."""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}])
            angle = response.strip()
            angle = angle.strip('"\'.')

            if len(angle) > 100:
                angle = angle[:100]

            return angle if angle else f"Business aspects of {title}"

        except Exception as e:
            logger.debug(f"Business angle extraction error: {e}")
            return f"Business aspects of {title}"

    # ========================================================================
    # Strategy 3: Wikipedia random from business categories
    # ========================================================================

    def wikipedia_random_from_category(self) -> Dict:
        """从商业相关分类中随机选择页面"""
        category = random.choice(self.BUSINESS_CATEGORIES)

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
                "source": "wikipedia_business_category",
                "category": category,
                "type": "business_entity"
            }

        except Exception as e:
            logger.error(f"Wikipedia category error: {e}")
            # Fallback to LLM generation
            return self.llm_generate_business_concept()

    # ========================================================================
    # Strategy 4: Random business keyword search
    # ========================================================================

    def random_business_keyword_search(self) -> Dict:
        """使用扩展池子生成多样化商业关键词组合"""
        # Use expanded pools to generate diverse combinations
        queries = self.expanded_pools.generate_search_queries()
        search_term = random.choice(queries)

        logger.info(f"Business keyword search: {search_term}")

        return {
            "title": search_term,
            "source": "random_business_keyword",
            "type": "business_entity"
        }

    # ========================================================================
    # Strategy 5: DBpedia business entities
    # ========================================================================

    def dbpedia_random_business_entity(self) -> Dict:
        """
        从DBpedia随机获取商业实体

        随机选择以下类型之一:
        - 公司 (Companies)
        - 商业人物 (Business people)
        - CEO (Chief Executive Officers)
        """
        # Randomly select entity type
        entity_types = ['company', 'businessperson', 'ceo']
        entity_type = random.choice(entity_types)

        try:
            if entity_type == 'company':
                results = self.dbpedia_client.get_companies(limit=50)
                if results:
                    entity = random.choice(results)
                    name = entity.get('name', '')
                    industry = entity.get('industry', '')

                    logger.info(f"DBpedia company: {name}")

                    return {
                        "title": name,
                        "source": "dbpedia_business_entity",
                        "entity_type": "company",
                        "industry": industry,
                        "type": "business_entity"
                    }

            elif entity_type == 'businessperson':
                # Query for business people
                sparql = """
                SELECT DISTINCT ?person ?name WHERE {
                  ?person a dbo:BusinessPerson .
                  ?person foaf:name ?name .
                  FILTER(LANG(?name) = "en")
                }
                LIMIT 50
                OFFSET %d
                """ % random.randint(0, 100)

                results = self.dbpedia_client.query_sparql(sparql)
                bindings = results.get('results', {}).get('bindings', [])

                if bindings:
                    person = random.choice(bindings)
                    name = person.get('name', {}).get('value', '')

                    logger.info(f"DBpedia business person: {name}")

                    return {
                        "title": name,
                        "source": "dbpedia_business_entity",
                        "entity_type": "businessperson",
                        "type": "business_entity"
                    }

            else:  # ceo
                sparql = """
                SELECT DISTINCT ?person ?name ?company WHERE {
                  ?person dbo:occupation ?occ .
                  ?occ rdfs:label "Chief executive officer"@en .
                  ?person foaf:name ?name .
                  OPTIONAL { ?person dbo:employer ?company . }
                  FILTER(LANG(?name) = "en")
                }
                LIMIT 50
                OFFSET %d
                """ % random.randint(0, 50)

                results = self.dbpedia_client.query_sparql(sparql)
                bindings = results.get('results', {}).get('bindings', [])

                if bindings:
                    person = random.choice(bindings)
                    name = person.get('name', {}).get('value', '')
                    company = person.get('company', {}).get('value', '')

                    logger.info(f"DBpedia CEO: {name}")

                    return {
                        "title": name,
                        "source": "dbpedia_business_entity",
                        "entity_type": "ceo",
                        "company": company,
                        "type": "business_entity"
                    }

        except Exception as e:
            logger.error(f"DBpedia business entity error: {e}")

        # Fallback to LLM generation
        return self.llm_generate_business_concept()

    # ========================================================================
    # Strategy 6: NewsAPI business headlines
    # ========================================================================

    def newsapi_business_headlines(self) -> Dict:
        """从NewsAPI获取商业头条"""
        if not self.newsapi_client:
            return self.llm_generate_business_concept()

        try:
            # Get business headlines from US
            articles = self.newsapi_client.get_business_headlines(country="us")

            if articles:
                article = random.choice(articles[:10])
                title = article.get('title', '')
                description = article.get('description', '')
                source = article.get('source', {}).get('name', 'NewsAPI')

                # Extract business entity from title
                search_concept = title[:100] if title else "Business news"

                logger.info(f"NewsAPI: {search_concept}")

                return {
                    "title": search_concept,
                    "source": "newsapi_business",
                    "description": description[:200],
                    "news_source": source,
                    "type": "business_entity"
                }

        except Exception as e:
            logger.error(f"NewsAPI error: {e}")

        # Fallback
        return self.llm_generate_business_concept()

    # ========================================================================
    # Strategy 7: Google News business
    # ========================================================================

    def google_news_business(self) -> Dict:
        """从Google News获取商业新闻"""
        try:
            import feedparser

            # Google News business RSS
            url = "https://news.google.com/rss/headlines/section/business/BUSINESS?hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(url)

            if feed.entries:
                entry = random.choice(feed.entries[:10])
                title = entry.get('title', '')
                source = entry.get('source', {}).get('title', 'Google News')

                logger.info(f"Google News: {title}")

                return {
                    "title": title[:100],
                    "source": "google_news",
                    "news_source": source,
                    "type": "business_entity"
                }

        except ImportError:
            logger.warning("feedparser not installed for Google News")
        except Exception as e:
            logger.error(f"Google News error: {e}")

        # Fallback
        return self.llm_generate_business_concept()

    # ========================================================================
    # Strategy 8: Yahoo Finance random company
    # ========================================================================

    def yahoo_finance_random(self) -> Dict:
        """从Yahoo Finance随机获取公司信息"""
        if not self.yahoo_client.available:
            return self.llm_generate_business_concept()

        try:
            # Get random company
            company = self.yahoo_client.get_random_company()

            if company:
                name = company.get('name', '')
                sector = company.get('sector', '')
                ticker = company.get('ticker', '')

                # Generate search concept
                concepts = [
                    f"{name} business strategy",
                    f"{name} financial performance",
                    f"{name} stock analysis",
                    f"{name} {sector} sector",
                    f"{name} competitive position"
                ]
                concept = random.choice(concepts)

                logger.info(f"Yahoo Finance: {name} ({ticker})")

                return {
                    "title": concept,
                    "source": "yahoo_finance",
                    "company": name,
                    "ticker": ticker,
                    "sector": sector,
                    "type": "business_entity"
                }

        except Exception as e:
            logger.error(f"Yahoo Finance error: {e}")

        # Fallback
        return self.llm_generate_business_concept()

    # ========================================================================
    # Strategy 9: Wikidata company
    # ========================================================================

    def wikidata_random_company(self) -> Dict:
        """从Wikidata随机获取公司"""
        try:
            # Randomly choose company type
            company_type = random.choice(['companies', 'fortune_500', 'startups', 'business_people'])

            if company_type == 'companies':
                companies = self.wikidata_client.get_companies(limit=50)
                if companies:
                    entity = random.choice(companies)
                    name = entity.get('name', '')
                    industry = entity.get('industry', '')
                    country = entity.get('country', '')

                    concept = f"{name} {industry}" if industry else name

                    logger.info(f"Wikidata company: {name}")

                    return {
                        "title": concept,
                        "source": "wikidata_company",
                        "company": name,
                        "industry": industry,
                        "country": country,
                        "type": "business_entity"
                    }

            elif company_type == 'fortune_500':
                companies = self.wikidata_client.get_fortune_500_companies()
                if companies:
                    entity = random.choice(companies[:50])
                    name = entity.get('name', '')

                    logger.info(f"Wikidata Fortune 500: {name}")

                    return {
                        "title": f"{name} Fortune 500 company",
                        "source": "wikidata_company",
                        "company": name,
                        "list": "Fortune 500",
                        "type": "business_entity"
                    }

            elif company_type == 'startups':
                startups = self.wikidata_client.get_startups(limit=50)
                if startups:
                    entity = random.choice(startups)
                    name = entity.get('name', '')
                    industry = entity.get('industry', '')

                    concept = f"{name} startup" if not industry else f"{name} {industry} startup"

                    logger.info(f"Wikidata startup: {name}")

                    return {
                        "title": concept,
                        "source": "wikidata_company",
                        "company": name,
                        "industry": industry,
                        "type": "startup"
                    }

            else:  # business_people
                people = self.wikidata_client.get_business_people(limit=50)
                if people:
                    entity = random.choice(people)
                    name = entity.get('name', '')
                    position = entity.get('position', '')
                    company = entity.get('company', '')

                    concept = f"{name} {position}" if position else name

                    logger.info(f"Wikidata business person: {name}")

                    return {
                        "title": concept,
                        "source": "wikidata_business_person",
                        "name": name,
                        "position": position,
                        "company": company,
                        "type": "business_entity"
                    }

        except Exception as e:
            logger.error(f"Wikidata error: {e}")

        # Fallback
        return self.llm_generate_business_concept()

    # ========================================================================
    # Strategy 10: Fortune lists
    # ========================================================================

    def fortune_list_company(self) -> Dict:
        """从Fortune榜单获取公司"""
        try:
            all_companies = self.expanded_pools.FAMOUS_COMPANIES

            # Select random category
            category = random.choice(list(all_companies.keys()))
            companies = all_companies[category]

            if companies:
                company = random.choice(companies)

                # Generate search concept based on category
                if category == "startups_unicorns":
                    concept = f"{company} unicorn startup valuation"
                elif "chinese" in category:
                    concept = f"{company} Chinese tech company"
                else:
                    concept = f"{company} {category.replace('_', ' ')}"

                logger.info(f"Fortune/Famous company: {company}")

                return {
                    "title": concept,
                    "source": "fortune_list",
                    "company": company,
                    "category": category,
                    "type": "business_entity"
                }

        except Exception as e:
            logger.error(f"Fortune list error: {e}")

        # Fallback
        return self.llm_generate_business_concept()

    # ========================================================================
    # Strategy 11: SEC filings
    # ========================================================================

    def sec_filing_random(self) -> Dict:
        """从SEC文件获取概念"""
        try:
            # Get famous companies for SEC filings
            companies = ["Apple", "Microsoft", "Amazon", "Tesla", "Google", "Meta", "NVIDIA"]
            company = random.choice(companies)

            filing_types = ["10-K Annual Report", "10-Q Quarterly Report", "8-K Current Report",
                           "Earnings Call Transcript", "Proxy Statement", "ESG Report"]
            filing = random.choice(filing_types)

            concept = f"{company} {filing}"

            logger.info(f"SEC filing concept: {concept}")

            return {
                "title": concept,
                "source": "sec_filings",
                "company": company,
                "filing_type": filing,
                "type": "business_entity"
            }

        except Exception as e:
            logger.error(f"SEC filing error: {e}")

        # Fallback
        return self.llm_generate_business_concept()

    # ========================================================================
    # Strategy 12: World Bank indicator
    # ========================================================================

    def world_bank_indicator(self) -> Dict:
        """从世界银行获取经济指标"""
        try:
            countries = ["US", "CN", "JP", "DE", "GB", "FR", "IN", "BR", "CA", "AU"]
            country = random.choice(countries)

            indicators = ["GDP", "GDP per capita", "Inflation", "Unemployment", "Trade"]
            indicator = random.choice(indicators)

            concept = f"{country} {indicator} economic data"

            logger.info(f"World Bank: {concept}")

            return {
                "title": concept,
                "source": "world_bank",
                "country": country,
                "indicator": indicator,
                "type": "economic_data"
            }

        except Exception as e:
            logger.error(f"World Bank error: {e}")

        # Fallback
        return self.llm_generate_business_concept()

    # ========================================================================
    # Strategy 13: FRED indicator
    # ========================================================================

    def fred_indicator(self) -> Dict:
        """从FRED获取经济指标"""
        if not self.fred_client:
            return self.llm_generate_business_concept()

        try:
            indicators = ["GDP", "CPI", "Unemployment Rate", "Federal Funds Rate"]
            indicator = random.choice(indicators)

            concept = f"US {indicator} data and analysis"

            logger.info(f"FRED: {indicator}")

            return {
                "title": concept,
                "source": "fred_economic",
                "indicator": indicator,
                "type": "economic_data"
            }

        except Exception as e:
            logger.error(f"FRED error: {e}")

        # Fallback
        return self.llm_generate_business_concept()

    # ========================================================================
    # Business Website Strategies (No API Required)
    # ========================================================================

    # Strategy 14: Bloomberg
    def bloomberg_random(self) -> Dict:
        """从Bloomberg获取商业新闻概念"""
        try:
            topics = self.bloomberg_client.search_business_topics()
            topic = random.choice(topics)

            logger.info(f"Bloomberg: {topic}")

            return {
                "title": topic,
                "source": "bloomberg",
                "type": "business_news"
            }

        except Exception as e:
            logger.error(f"Bloomberg error: {e}")
            return self.llm_generate_business_concept()

    # Strategy 15: Reuters
    def reuters_random(self) -> Dict:
        """从Reuters获取商业新闻"""
        try:
            category = random.choice(["business", "technology", "markets", "deals"])
            articles = self.reuters_client.get_business_news(category)

            if articles:
                article = random.choice(articles[:5])
                title = article.get('title', '')

                logger.info(f"Reuters: {title}")

                return {
                    "title": title[:100],
                    "source": "reuters",
                    "category": category,
                    "type": "business_news"
                }

        except Exception as e:
            logger.error(f"Reuters error: {e}")

        return self.llm_generate_business_concept()

    # Strategy 16: Forbes
    def forbes_random(self) -> Dict:
        """从Forbes获取榜单或文章"""
        try:
            result = self.forbes_client.get_random_list_entry()

            logger.info(f"Forbes: {result.get('title')}")

            return {
                "title": result.get('title'),
                "source": "forbes",
                "list": result.get('list_name'),
                "company": result.get('company'),
                "type": "business_news"
            }

        except Exception as e:
            logger.error(f"Forbes error: {e}")

        return self.llm_generate_business_concept()

    # Strategy 17: CNBC
    def cnbc_random(self) -> Dict:
        """从CNBC获取市场新闻"""
        try:
            articles = self.cnbc_client.get_latest_news()

            if articles:
                article = random.choice(articles[:5])
                title = article.get('title', '')

                logger.info(f"CNBC: {title}")

                return {
                    "title": title[:100],
                    "source": "cnbc",
                    "type": "business_news"
                }

        except Exception as e:
            logger.error(f"CNBC error: {e}")

        return self.llm_generate_business_concept()

    # Strategy 18: Business Insider
    def business_insider_random(self) -> Dict:
        """从Business Insider获取文章"""
        try:
            result = self.bi_client.get_random_section_article()

            logger.info(f"Business Insider: {result.get('title')}")

            return {
                "title": result.get('title'),
                "source": "business_insider",
                "section": result.get('section'),
                "type": "business_news"
            }

        except Exception as e:
            logger.error(f"Business Insider error: {e}")

        return self.llm_generate_business_concept()

    # Strategy 19: TechCrunch
    def techcrunch_random(self) -> Dict:
        """从TechCrunch获取创业新闻"""
        try:
            result = self.techcrunch_client.get_random_startup_concept()

            logger.info(f"TechCrunch: {result.get('title')}")

            return {
                "title": result.get('title'),
                "source": "techcrunch",
                "topic": result.get('topic'),
                "type": "startup_news"
            }

        except Exception as e:
            logger.error(f"TechCrunch error: {e}")

        return self.llm_generate_business_concept()

    # Strategy 20: Yahoo Finance Web
    def yahoo_finance_web_random(self) -> Dict:
        """从Yahoo Finance Web获取热门股票"""
        try:
            ticker = self.yahoo_web_client.get_random_ticker()
            name = ticker.get('name', '')
            symbol = ticker.get('symbol', '')

            # Generate various search concepts
            concepts = [
                f"{name} stock analysis",
                f"{name} financial results",
                f"{name} business outlook",
                f"{symbol} stock performance",
                f"{name} competitive analysis"
            ]
            concept = random.choice(concepts)

            logger.info(f"Yahoo Finance Web: {name}")

            return {
                "title": concept,
                "source": "yahoo_finance_web",
                "company": name,
                "symbol": symbol,
                "type": "stock_data"
            }

        except Exception as e:
            logger.error(f"Yahoo Finance Web error: {e}")

        return self.llm_generate_business_concept()

    # Strategy 21: Fortune Website
    def fortune_website_random(self) -> Dict:
        """从Fortune网站获取榜单公司"""
        try:
            result = self.fortune_client.get_random_fortune_company()

            logger.info(f"Fortune: {result.get('title')}")

            return {
                "title": result.get('title'),
                "source": "fortune",
                "list": result.get('list'),
                "company": result.get('company'),
                "type": "business_ranking"
            }

        except Exception as e:
            logger.error(f"Fortune error: {e}")

        return self.llm_generate_business_concept()

    # Strategy 22: HBR
    def hbr_random(self) -> Dict:
        """从HBR获取管理概念"""
        try:
            result = self.hbr_client.get_random_management_concept()

            logger.info(f"HBR: {result.get('title')}")

            return {
                "title": result.get('title'),
                "source": "hbr",
                "category": result.get('category'),
                "type": "management_concept"
            }

        except Exception as e:
            logger.error(f"HBR error: {e}")

        return self.llm_generate_business_concept()


# ============================================================================
# Main Pipeline
# ============================================================================
