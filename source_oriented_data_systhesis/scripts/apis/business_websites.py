#!/usr/bin/env python3
"""
Business News Websites Client

This module provides clients for various business news websites and financial portals
that don't require API keys. It uses web scraping techniques to access public content.

Supported Websites:
- Bloomberg, Reuters, Forbes, Wall Street Journal (partial)
- Financial Times, CNBC, Business Insider
- Yahoo Finance, MarketWatch
- TechCrunch, VentureBeat (tech/startups)
- Seeking Alpha, The Motley Fool (investment)
- Fortune, Harvard Business Review

Usage:
    from apis.business_websites import (
        BloombergClient, ReutersClient, ForbesClient,
        CNBCClient, TechCrunchClient, YahooFinanceWebClient
    )
"""

import requests
import random
import json
import re
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger
from urllib.parse import urljoin, urlparse


# ============================================================================
# Base Website Client
# ============================================================================

class BaseWebsiteClient:
    """Base class for website scraping clients"""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

    def _get(self, url: str, params: Optional[Dict] = None) -> Optional[str]:
        """Make GET request and return HTML content"""
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            # Check if we got HTML
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' in content_type:
                return response.text
            else:
                logger.warning(f"{self.__class__.__name__}: Expected HTML, got {content_type}")
                return None

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.warning(f"{self.__class__.__name__}: Access forbidden (403)")
            elif e.response.status_code == 429:
                logger.warning(f"{self.__class__.__name__}: Rate limited (429)")
            else:
                logger.warning(f"{self.__class__.__name__}: HTTP error {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"{self.__class__.__name__}: Error - {e}")
            return None

    def _get_json(self, url: str, headers: Optional[Dict] = None) -> Optional[Dict]:
        """Make GET request and return JSON"""
        try:
            req_headers = self.session.headers.copy()
            if headers:
                req_headers.update(headers)

            response = self.session.get(url, headers=req_headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"{self.__class__.__name__}: JSON error - {e}")
            return None

    def _extract_title(self, html: str) -> str:
        """Extract title from HTML"""
        # Try common patterns
        patterns = [
            r'<h1[^>]*>(.*?)</h1>',
            r'<title[^>]*>(.*?)</title>',
            r'property="og:title"[^>]*content="([^"]*)"',
            r'name="headline"[^>]*content="([^"]*)"'
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                title = match.group(1).strip()
                # Remove HTML tags
                title = re.sub(r'<[^>]+>', '', title)
                return title[:200]
        return ""

    def _extract_description(self, html: str) -> str:
        """Extract description from HTML"""
        patterns = [
            r'name="description"[^>]*content="([^"]*)"',
            r'property="og:description"[^>]*content="([^"]*)"',
            r'<meta[^>]*name="twitter:description"[^>]*content="([^"]*)"'
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_article_text(self, html: str) -> str:
        """Extract article text from HTML"""
        # Common article container patterns
        patterns = [
            r'<article[^>]*>(.*?)</article>',
            r'<div[^>]*class="[^"]*article[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                text = match.group(1)
                # Remove HTML tags and decode entities
                text = re.sub(r'<[^>]+>', ' ', text)
                text = re.sub(r'\s+', ' ', text)
                return text.strip()[:500]
        return ""


# ============================================================================
# Bloomberg Client
# ============================================================================

class BloombergClient(BaseWebsiteClient):
    """
    Bloomberg Client - https://www.bloomberg.com/

    Note: Bloomberg has paywall and anti-scraping measures.
    This client uses their public RSS feeds where available.
    """

    BASE_URL = "https://www.bloomberg.com"
    RSS_URL = "https://feeds.bloomberg.com/markets/news.rss"

    def get_latest_headlines(self) -> List[Dict]:
        """Get latest business headlines from Bloomberg RSS"""
        try:
            import feedparser
            feed = feedparser.parse(self.RSS_URL)

            articles = []
            for entry in feed.entries[:20]:
                articles.append({
                    "title": entry.get('title', ''),
                    "link": entry.get('link', ''),
                    "published": entry.get('published', ''),
                    "summary": entry.get('summary', '')[:200],
                    "source": "Bloomberg"
                })

            return articles

        except ImportError:
            logger.warning("feedparser not installed for Bloomberg RSS")
            return self._get_fallback_articles()
        except Exception as e:
            logger.error(f"Bloomberg error: {e}")
            return self._get_fallback_articles()

    def _get_fallback_articles(self) -> List[Dict]:
        """Fallback when RSS not available"""
        return [
            {
                "title": "Global Markets Overview",
                "link": "https://www.bloomberg.com/markets",
                "summary": "Latest market updates and business news",
                "source": "Bloomberg"
            }
        ]

    def search_business_topics(self) -> List[str]:
        """Get business topic search terms"""
        return [
            "Bloomberg technology",
            "Bloomberg markets",
            "Bloomberg economy",
            "Bloomberg companies",
            "Bloomberg CEO interviews"
        ]


# ============================================================================
# Reuters Client
# ============================================================================

class ReutersClient(BaseWebsiteClient):
    """
    Reuters Client - https://www.reuters.com/

    Reuters provides RSS feeds for different categories.
    """

    BASE_URL = "https://www.reuters.com"
    RSS_FEEDS = {
        "business": "https://www.reuters.com/rssFeed/businessNews",
        "technology": "https://www.reuters.com/rssFeed/technologyNews",
        "markets": "https://www.reuters.com/finance/rss/news",
        "deals": "https://www.reuters.com/rssFeed/dealsNews"
    }

    def get_business_news(self, category: str = "business") -> List[Dict]:
        """Get business news by category"""
        rss_url = self.RSS_FEEDS.get(category, self.RSS_FEEDS["business"])

        try:
            import feedparser
            feed = feedparser.parse(rss_url)

            articles = []
            for entry in feed.entries[:15]:
                articles.append({
                    "title": entry.get('title', ''),
                    "link": entry.get('link', ''),
                    "published": entry.get('published', ''),
                    "summary": entry.get('summary', '')[:200],
                    "source": f"Reuters {category.title()}"
                })

            return articles

        except ImportError:
            return self._get_fallback_articles(category)
        except Exception as e:
            logger.error(f"Reuters error: {e}")
            return self._get_fallback_articles(category)

    def _get_fallback_articles(self, category: str) -> List[Dict]:
        """Fallback articles"""
        return [
            {
                "title": f"Reuters {category.title()} News",
                "link": f"https://www.reuters.com/{category}",
                "summary": f"Latest {category} news from Reuters",
                "source": "Reuters"
            }
        ]

    def get_random_article(self) -> Dict:
        """Get a random business article"""
        category = random.choice(list(self.RSS_FEEDS.keys()))
        articles = self.get_business_news(category)
        if articles:
            return random.choice(articles)
        return {"title": "Reuters Business", "source": "Reuters"}


# ============================================================================
# Forbes Client
# ============================================================================

class ForbesClient(BaseWebsiteClient):
    """
    Forbes Client - https://www.forbes.com/

    Uses public RSS feeds and API endpoints.
    """

    BASE_URL = "https://www.forbes.com"
    RSS_URL = "https://www.forbes.com/business/feed/"

    def get_business_headlines(self) -> List[Dict]:
        """Get business headlines"""
        try:
            import feedparser
            feed = feedparser.parse(self.RSS_URL)

            articles = []
            for entry in feed.entries[:15]:
                articles.append({
                    "title": entry.get('title', ''),
                    "link": entry.get('link', ''),
                    "published": entry.get('published', ''),
                    "author": entry.get('author', ''),
                    "source": "Forbes"
                })

            return articles

        except Exception as e:
            logger.error(f"Forbes error: {e}")
            return self._get_fallback_articles()

    def _get_fallback_articles(self) -> List[Dict]:
        """Fallback articles"""
        return [
            {
                "title": "Forbes Business Leadership",
                "link": "https://www.forbes.com/business/",
                "source": "Forbes"
            }
        ]

    def get_forbes_lists(self) -> List[Dict]:
        """Get Forbes lists (Fortune 500, 30 Under 30, etc.)"""
        lists = [
            {"name": "Fortune 500", "url": "https://www.forbes.com/fortune500/"},
            {"name": "Forbes 400", "url": "https://www.forbes.com/forbes-400/"},
            {"name": "30 Under 30", "url": "https://www.forbes.com/30-under-30/"},
            {"name": "World's Billionaires", "url": "https://www.forbes.com/billionaires/"},
            {"name": "Most Valuable Brands", "url": "https://www.forbes.com/brands/"},
            {"name": "America's Best Employers", "url": "https://www.forbes.com/best-employers/"}
        ]

        return lists

    def get_random_list_entry(self) -> Dict:
        """Get entry from a random Forbes list"""
        lists = self.get_forbes_lists()
        selected_list = random.choice(lists)
        list_name = selected_list['name']

        # Generate search concepts based on the list
        companies = ["Apple", "Microsoft", "Amazon", "Google", "Tesla"]
        selected_company = random.choice(companies)

        return {
            "title": f"{selected_company} {list_name}",
            "source": "forbes_list",
            "list_name": list_name,
            "company": selected_company
        }


# ============================================================================
# CNBC Client
# ============================================================================

class CNBCClient(BaseWebsiteClient):
    """
    CNBC Client - https://www.cnbc.com/

    Access to CNBC's business news and market data.
    """

    BASE_URL = "https://www.cnbc.com"
    RSS_URL = "https://www.cnbc.com/id/100003114/device/rss/rss.html"

    def get_latest_news(self) -> List[Dict]:
        """Get latest CNBC news"""
        try:
            import feedparser
            feed = feedparser.parse(self.RSS_URL)

            articles = []
            for entry in feed.entries[:15]:
                articles.append({
                    "title": entry.get('title', ''),
                    "link": entry.get('link', ''),
                    "published": entry.get('published', ''),
                    "summary": entry.get('summary', '')[:200],
                    "source": "CNBC"
                })

            return articles

        except Exception as e:
            logger.error(f"CNBC error: {e}")
            return self._get_fallback_articles()

    def _get_fallback_articles(self) -> List[Dict]:
        """Fallback articles"""
        return [
            {
                "title": "CNBC Markets",
                "link": "https://www.cnbc.com/markets/",
                "summary": "Latest market news from CNBC",
                "source": "CNBC"
            }
        ]


# ============================================================================
# Business Insider Client
# ============================================================================

class BusinessInsiderClient(BaseWebsiteClient):
    """
    Business Insider Client - https://www.businessinsider.com/

    Business news and analysis.
    """

    BASE_URL = "https://www.businessinsider.com"

    def get_sections(self) -> List[str]:
        """Get available sections"""
        return [
            "finance", "tech", "retail", "economy", "media",
            "strategy", "markets", "investing", "leadership"
        ]

    def get_random_section_article(self) -> Dict:
        """Get article from a random section"""
        sections = self.get_sections()
        section = random.choice(sections)

        topics = {
            "finance": ["banking", "wall street", "IPO", "SPAC"],
            "tech": ["AI", "software", "startups", "big tech"],
            "retail": ["e-commerce", "consumer trends", "supply chain"],
            "economy": ["inflation", "Fed", "recession", "GDP"],
            "strategy": ["management", "workplace", "careers"]
        }

        section_topics = topics.get(section, ["business"])
        topic = random.choice(section_topics)

        return {
            "title": f"Business Insider {section.title()} - {topic.title()}",
            "source": "business_insider",
            "section": section,
            "topic": topic
        }


# ============================================================================
# TechCrunch Client (Tech/Startups)
# ============================================================================

class TechCrunchClient(BaseWebsiteClient):
    """
    TechCrunch Client - https://techcrunch.com/

    Focus on technology and startup news.
    """

    BASE_URL = "https://techcrunch.com"
    RSS_URL = "https://techcrunch.com/feed/"

    def get_startup_news(self) -> List[Dict]:
        """Get startup and tech news"""
        try:
            import feedparser
            feed = feedparser.parse(self.RSS_URL)

            articles = []
            for entry in feed.entries[:15]:
                # Extract categories/tags
                categories = entry.get('tags', [])
                category_list = [c.get('term', '') for c in categories] if categories else []

                articles.append({
                    "title": entry.get('title', ''),
                    "link": entry.get('link', ''),
                    "published": entry.get('published', ''),
                    "categories": category_list[:3],
                    "source": "TechCrunch"
                })

            return articles

        except Exception as e:
            logger.error(f"TechCrunch error: {e}")
            return []

    def get_startup_topics(self) -> List[str]:
        """Get startup-related topics"""
        return [
            "Series A funding", "Venture capital", "Startup IPO",
            "Tech startup", "Unicorn startup", "Founder interviews",
            "Pitch deck", "Term sheet", "Due diligence",
            "Accelerator", "Incubator", "Angel investment"
        ]

    def get_random_startup_concept(self) -> Dict:
        """Get random startup-related concept"""
        topics = self.get_startup_topics()
        topic = random.choice(topics)

        startups = ["Stripe", "Discord", "Figma", "Notion", "Canva", "Instacart"]
        startup = random.choice(startups)

        return {
            "title": f"{startup} {topic}",
            "source": "techcrunch_startup",
            "topic": topic
        }


# ============================================================================
# VentureBeat Client (Tech/Business)
# ============================================================================

class VentureBeatClient(BaseWebsiteClient):
    """
    VentureBeat Client - https://venturebeat.com/

    Technology and business news.
    """

    BASE_URL = "https://venturebeat.com"
    CATEGORIES = ["ai", "games", "business", "metaverse"]

    def get_business_ai_news(self) -> List[str]:
        """Get AI and business topics"""
        return [
            "AI in business", "Enterprise AI", "Machine learning startups",
            "Generative AI business", "AI regulation", "Automation",
            "Computer vision", "Natural language processing", "AI ethics"
        ]

    def get_random_concept(self) -> Dict:
        """Get random VentureBeat concept"""
        topics = self.get_business_ai_news()
        topic = random.choice(topics)

        return {
            "title": topic,
            "source": "venturebeat",
            "category": random.choice(self.CATEGORIES)
        }


# ============================================================================
# Yahoo Finance Web Client
# ============================================================================

class YahooFinanceWebClient(BaseWebsiteClient):
    """
    Yahoo Finance Web Client - https://finance.yahoo.com/

    Web scraping for Yahoo Finance (doesn't require API key).
    """

    BASE_URL = "https://finance.yahoo.com"

    def get_trending_tickers(self) -> List[Dict]:
        """Get trending tickers"""
        # Yahoo Finance has an API endpoint for trending
        url = f"{self.BASE_URL}/v1/finance/trending/us"

        try:
            data = self._get_json(url)
            if data and 'finance' in data:
                result = data['finance'].get('result', [])
                if result and len(result) > 0:
                    quotes = result[0].get('quotes', [])
                    return [
                        {
                            "symbol": q.get('symbol', ''),
                            "name": q.get('longName', q.get('shortName', '')),
                            "source": "Yahoo Finance Trending"
                        }
                        for q in quotes[:10]
                    ]
        except Exception as e:
            logger.error(f"Yahoo Finance trending error: {e}")

        return self._get_fallback_tickers()

    def _get_fallback_tickers(self) -> List[Dict]:
        """Fallback tickers"""
        return [
            {"symbol": "AAPL", "name": "Apple Inc.", "source": "Yahoo Finance"},
            {"symbol": "MSFT", "name": "Microsoft Corporation", "source": "Yahoo Finance"},
            {"symbol": "GOOGL", "name": "Alphabet Inc.", "source": "Yahoo Finance"}
        ]

    def get_market_movers(self, mover_type: str = "gainers") -> List[Dict]:
        """Get market movers (gainers or losers)"""
        # Yahoo Finance has an endpoint for market movers
        endpoint = "gainners" if mover_type == "gainers" else "losers"
        url = f"{self.BASE_URL}/v1/finance/movers"

        try:
            data = self._get_json(url)
            if data:
                # Parse the response
                return []

        except Exception as e:
            logger.error(f"Yahoo Finance movers error: {e}")

        return []

    def get_random_ticker(self) -> Dict:
        """Get a random ticker"""
        tickers = self.get_trending_tickers()
        if tickers:
            return random.choice(tickers)

        # Fallback to predefined list
        fallback = [
            {"symbol": "AAPL", "name": "Apple", "source": "Yahoo Finance"},
            {"symbol": "TSLA", "name": "Tesla", "source": "Yahoo Finance"},
            {"symbol": "NVDA", "name": "NVIDIA", "source": "Yahoo Finance"}
        ]
        return random.choice(fallback)


# ============================================================================
# Seeking Alpha Client (Investment)
# ============================================================================

class SeekingAlphaClient(BaseWebsiteClient):
    """
    Seeking Alpha Client - https://seekingalpha.com/

    Investment analysis and financial news.
    """

    BASE_URL = "https://seekingalpha.com"

    def get_investment_topics(self) -> List[str]:
        """Get investment-related topics"""
        return [
            "Value investing", "Growth investing", "Dividend investing",
            "ETF strategy", "Options trading", "Technical analysis",
            "Fundamental analysis", "Earnings analysis", "Market outlook",
            "Sector analysis", "REITs", "Commodities", "Fixed income"
        ]

    def get_random_investment_concept(self) -> Dict:
        """Get random investment concept"""
        topics = self.get_investment_topics()
        topic = random.choice(topics)

        return {
            "title": topic,
            "source": "seeking_alpha",
            "category": "investment_analysis"
        }


# ============================================================================
# The Motley Fool Client (Investment)
# ============================================================================

class MotleyFoolClient(BaseWebsiteClient):
    """
    The Motley Fool Client - https://www.fool.com/

    Investment advice and stock analysis.
    """

    BASE_URL = "https://www.fool.com"

    def get_investing_themes(self) -> List[str]:
        """Get investing themes"""
        return [
            "Retirement planning", "Stock market basics", "Dividend stocks",
            "Growth stocks", "Value stocks", "Small cap stocks",
            "Tech stocks", "Healthcare stocks", "Consumer staples",
            "Financial stocks", "Energy stocks", "International stocks"
        ]

    def get_random_stock_concept(self) -> Dict:
        """Get random stock analysis concept"""
        themes = self.get_investing_themes()
        theme = random.choice(themes)

        stocks = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA"]
        stock = random.choice(stocks)

        return {
            "title": f"{stock} {theme}",
            "source": "motley_fool",
            "theme": theme
        }


# ============================================================================
# Fortune Client
# ============================================================================

class FortuneClient(BaseWebsiteClient):
    """
    Fortune Client - https://fortune.com/

    Business magazine with rankings and analysis.
    """

    BASE_URL = "https://fortune.com"

    def get_fortune_lists(self) -> List[Dict]:
        """Get Fortune ranking lists"""
        return [
            {"name": "Fortune 500", "url": "/fortune500/"},
            {"name": "Global 500", "url": "/global500/"},
            {"name": "Most Powerful Women", "url": "/most-powerful-women/"},
            {"name": "40 Under 40", "url": "/40-under-40/"},
            {"name": "World's Most Admired Companies", "url": "/worlds-most-admired-companies/"},
            {"name": "100 Best Companies to Work For", "url": "/best-companies/"}
        ]

    def get_random_fortune_company(self) -> Dict:
        """Get random company from Fortune lists"""
        lists = self.get_fortune_lists()
        selected_list = random.choice(lists)
        list_name = selected_list['name']

        # Sample companies from Fortune 500
        fortune_companies = [
            "Walmart", "Amazon", "Apple", "CVS Health", "UnitedHealth Group",
            "ExxonMobil", "Berkshire Hathaway", "Alphabet", "McKesson", "Cigna"
        ]
        company = random.choice(fortune_companies)

        return {
            "title": f"{company} Fortune 500 ranking",
            "source": "fortune",
            "list": list_name,
            "company": company
        }


# ============================================================================
# Harvard Business Review Client
# ============================================================================

class HBRClient(BaseWebsiteClient):
    """
    Harvard Business Review Client - https://hbr.org/

    Management and business theory content.
    """

    BASE_URL = "https://hbr.org"

    def get_management_topics(self) -> List[str]:
        """Get management and business topics"""
        return [
            "Leadership", "Strategy", "Innovation", "Organizational culture",
            "Change management", "Decision making", "Negotiation",
            "Digital transformation", "Operations", "Marketing strategy",
            "Corporate governance", "Business ethics", "Sustainability",
            "Diversity and inclusion", "Talent management"
        ]

    def get_random_management_concept(self) -> Dict:
        """Get random management concept"""
        topics = self.get_management_topics()
        topic = random.choice(topics)

        return {
            "title": topic,
            "source": "hbr",
            "category": "management_theory"
        }


# ============================================================================
# MarketWatch Client
# ============================================================================

class MarketWatchClient(BaseWebsiteClient):
    """
    MarketWatch Client - https://www.marketwatch.com/

    Financial news and market data.
    """

    BASE_URL = "https://www.marketwatch.com"

    def get_market_topics(self) -> List[str]:
        """Get market-related topics"""
        return [
            "Market volatility", "Sector performance", "Economic indicators",
            "Fed policy", "Interest rates", "Inflation data",
            "GDP report", "Employment data", "Consumer confidence",
            "Housing market", "Commodity prices", "Currency markets"
        ]

    def get_random_market_concept(self) -> Dict:
        """Get random market concept"""
        topics = self.get_market_topics()
        topic = random.choice(topics)

        return {
            "title": topic,
            "source": "marketwatch",
            "category": "market_analysis"
        }


# ============================================================================
# Convenience Functions
# ============================================================================

def get_bloomberg_client() -> BloombergClient:
    return BloombergClient()


def get_reuters_client() -> ReutersClient:
    return ReutersClient()


def get_forbes_client() -> ForbesClient:
    return ForbesClient()


def get_cnbc_client() -> CNBCClient:
    return CNBCClient()


def get_techcrunch_client() -> TechCrunchClient:
    return TechCrunchClient()


def get_business_insider_client() -> BusinessInsiderClient:
    return BusinessInsiderClient()


def get_yahoo_finance_web_client() -> YahooFinanceWebClient:
    return YahooFinanceWebClient()


def get_fortune_client() -> FortuneClient:
    return FortuneClient()


def get_hbr_client() -> HBRClient:
    return HBRClient()


if __name__ == "__main__":
    # Test clients
    logger.info("Testing Business Website Clients...")

    # Test Reuters
    reuters = get_reuters_client()
    articles = reuters.get_business_news("business")
    logger.info(f"Reuters: {len(articles)} articles")

    # Test Forbes
    forbes = get_forbes_client()
    lists = forbes.get_forbes_lists()
    logger.info(f"Forbes: {len(lists)} lists")

    # Test Yahoo Finance
    yahoo = get_yahoo_finance_web_client()
    tickers = yahoo.get_trending_tickers()
    logger.info(f"Yahoo Finance: {len(tickers)} trending tickers")

    logger.info("Website client tests completed!")
