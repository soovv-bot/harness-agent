#!/usr/bin/env python3
"""
Business and Financial Data APIs Client

This module provides clients for various business and financial data APIs.

Supported APIs:
- News APIs: NewsAPI, GDELT Event Database, Google News (RSS)
- Company Financial: SEC EDGAR, Yahoo Finance (yfinance), Alpha Vantage
- Company Information: OpenCorporates, Wikidata, DBpedia companies
- Economic Data: World Bank API, FRED (Federal Reserve), OECD
- Stock Market: Yahoo Finance, IEX Cloud (optional)
- Legal/Contracts: SEC filings, CourtListener
- Business Databases: Crunchbase (optional), Wikidata business entities

Usage:
    from business_apis import (
        NewsAPIClient, GDELTClient, YahooFinanceClient,
        WorldBankClient, SECClient, OpenCorporatesClient
    )
"""

import requests
import json
import random
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from loguru import logger


# ============================================================================
# Base Client
# ============================================================================

class BaseClient:
    """Base class for business API clients"""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; BusinessDataPipeline/1.0)'
        })

    def _get(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Optional[Dict]:
        """Make GET request and return JSON response"""
        try:
            req_headers = self.session.headers.copy()
            if headers:
                req_headers.update(headers)

            response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()

            # Check if response is JSON
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                return response.json()
            else:
                # For non-JSON responses, return text content
                return {'content': response.text, 'status_code': response.status_code}

        except requests.exceptions.HTTPError as e:
            logger.warning(f"{self.__class__.__name__} HTTP error: {e.response.status_code}")
            return None
        except requests.exceptions.Timeout:
            logger.warning(f"{self.__class__.__name__} timeout")
            return None
        except Exception as e:
            logger.error(f"{self.__class__.__name__} error: {e}")
            return None


# ============================================================================
# News APIs
# ============================================================================

class NewsAPIClient(BaseClient):
    """
    NewsAPI Client - https://newsapi.org/

    Free tier: 100 requests/day, news from last month
    Requires API key (free at https://newsapi.org/register)
    """

    BASE_URL = "https://newsapi.org/v2"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.api_key = api_key
        # Use demo key if none provided (limited functionality)
        if not self.api_key:
            logger.warning("No NewsAPI key provided, using demo endpoints only")

    def get_business_headlines(self, country: str = "us", page_size: int = 20) -> List[Dict]:
        """Get business headlines from a country"""
        if not self.api_key:
            # Fallback to alternative sources
            return self._get_demo_business_news()

        params = {
            "country": country,
            "category": "business",
            "pageSize": page_size,
            "apiKey": self.api_key
        }

        result = self._get(f"{self.BASE_URL}/top-headlines", params=params)
        if result:
            return result.get('articles', [])
        return []

    def search_business_news(self, query: str, from_days: int = 7, language: str = "en") -> List[Dict]:
        """Search for business news by keyword"""
        if not self.api_key:
            return self._get_demo_business_news()

        from_date = (datetime.now() - timedelta(days=from_days)).strftime("%Y-%m-%d")

        params = {
            "q": query,
            "from": from_date,
            "language": language,
            "sortBy": "relevancy",
            "apiKey": self.api_key
        }

        result = self._get(f"{self.BASE_URL}/everything", params=params)
        if result:
            return result.get('articles', [])
        return []

    def _get_demo_business_news(self) -> List[Dict]:
        """Demo news sources without API key"""
        # Return mock data for demo purposes
        return [
            {
                "title": "Global Markets Update",
                "description": "Markets show mixed performance as earnings season continues",
                "source": {"name": "Business Demo"},
                "url": "https://example.com/news",
                "publishedAt": datetime.now().isoformat()
            }
        ]


class GDELTClient(BaseClient):
    """
    GDELT Project Client - https://www.gdeltproject.org/

    GDELT monitors world news and provides event data.
    No API key required for basic usage.
    """

    BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

    def search_business_events(self, query: str, max_records: int = 10) -> List[Dict]:
        """Search GDELT for business-related events"""
        # GDELT uses a different API format (returns TSV/CSV)
        params = {
            "query": query,
            "mode": "ArtList",
            "maxrecords": max_records,
            "format": "json"
        }

        result = self._get(self.BASE_URL, params=params)
        if result and 'results' in result:
            return result['results'][:max_records]
        return []

    def get_financial_news_tone(self, keyword: str, timespan: int = 24) -> List[Dict]:
        """Get financial news with tone analysis for a keyword"""
        # GDELT's tone analysis
        params = {
            "query": keyword,
            "mode": "TimelineTone",
            "timespan": f"{timespan}hrs",
            "format": "json"
        }

        result = self._get(self.BASE_URL, params=params)
        if result and 'timeline' in result:
            return result['timeline']
        return []


class GoogleNewsClient(BaseClient):
    """
    Google News RSS Client - No API key required

    Uses Google News RSS feeds to get business news.
    """

    BASE_URL = "https://news.google.com/rss"

    def get_business_news(self, topic: str = "business", region: str = "US") -> List[Dict]:
        """Get business news from Google News RSS"""
        # Google News RSS format: https://news.google.com/rss/headlines/section/topic/REGION
        url = f"{self.BASE_URL}/headlines/section/{topic}/{region}?hl=en-US&gl=US&ceid=US:en"

        try:
            import feedparser
            feed = feedparser.parse(url)

            articles = []
            for entry in feed.entries[:20]:
                articles.append({
                    "title": entry.get('title', ''),
                    "link": entry.get('link', ''),
                    "published": entry.get('published', ''),
                    "summary": entry.get('summary', ''),
                    "source": entry.get('source', {}).get('title', 'Google News')
                })

            return articles

        except ImportError:
            # Fallback without feedparser
            logger.warning("feedparser not installed, using alternative")
            return self._get_business_news_alternative(topic)
        except Exception as e:
            logger.error(f"Google News error: {e}")
            return []

    def _get_business_news_alternative(self, topic: str) -> List[Dict]:
        """Alternative method to get news without feedparser"""
        # Use newsapi.org demo or other sources
        return [{"title": f"{topic.title()} News", "link": "https://news.google.com", "source": "Google News"}]


# ============================================================================
# Company Financial APIs
# ============================================================================

class YahooFinanceClient(BaseClient):
    """
    Yahoo Finance Client using yfinance library

    No API key required. Uses Yahoo's public finance data.
    """

    def __init__(self):
        super().__init__()
        try:
            import yfinance as yf
            self.yf = yf
            self.available = True
        except ImportError:
            logger.warning("yfinance not installed, some features unavailable")
            self.available = False

    def get_company_info(self, ticker: str) -> Optional[Dict]:
        """Get company information by ticker symbol"""
        if not self.available:
            return None

        try:
            stock = self.yf.Ticker(ticker)
            info = stock.info

            if info:
                return {
                    "ticker": ticker,
                    "name": info.get("longName", info.get("shortName", "")),
                    "sector": info.get("sector", ""),
                    "industry": info.get("industry", ""),
                    "market_cap": info.get("marketCap", 0),
                    "employees": info.get("fullTimeEmployees", 0),
                    "country": info.get("country", ""),
                    "website": info.get("website", ""),
                    "summary": info.get("longBusinessSummary", "")[:500]
                }
        except Exception as e:
            logger.error(f"Yahoo Finance error for {ticker}: {e}")

        return None

    def get_financial_statements(self, ticker: str) -> Optional[Dict]:
        """Get financial statements for a company"""
        if not self.available:
            return None

        try:
            stock = self.yf.Ticker(ticker)

            return {
                "ticker": ticker,
                "income_statement": stock.income_stmt.to_dict() if hasattr(stock, 'income_stmt') else {},
                "balance_sheet": stock.balance_sheet.to_dict() if hasattr(stock, 'balance_sheet') else {},
                "cash_flow": stock.cashflow.to_dict() if hasattr(stock, 'cashflow') else {}
            }
        except Exception as e:
            logger.error(f"Financial statements error for {ticker}: {e}")

        return None

    def get_stock_history(self, ticker: str, period: str = "1mo") -> Optional[List[Dict]]:
        """Get historical stock data"""
        if not self.available:
            return None

        try:
            stock = self.yf.Ticker(ticker)
            hist = stock.history(period=period)

            data = []
            for date, row in hist.iterrows():
                data.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "open": row.get("Open", 0),
                    "high": row.get("High", 0),
                    "low": row.get("Low", 0),
                    "close": row.get("Close", 0),
                    "volume": row.get("Volume", 0)
                })

            return data
        except Exception as e:
            logger.error(f"Stock history error for {ticker}: {e}")

        return None

    def get_random_company(self) -> Optional[Dict]:
        """Get info for a random well-known company"""
        # List of major company tickers
        tickers = [
            # Tech
            "AAPL", "MSFT", "GOOGL", "META", "AMZN", "NVDA", "TSLA", "AMD", "INTC",
            # Finance
            "JPM", "BAC", "WFC", "C", "GS", "MS", "BLK",
            # Healthcare
            "JNJ", "PFE", "UNH", "ABBV", "MRK",
            # Consumer
            "PG", "KO", "PEP", "MCD", "NKE", "SBUX",
            # Energy
            "XOM", "CVX", "COP", "SLB",
            # Industrial
            "CAT", "BA", "HON", "GE", "MMM",
            # International
            "TSM", "ASML", "SAP", "NESN", "RMS"
        ]

        ticker = random.choice(tickers)
        return self.get_company_info(ticker)

    def get_companies_by_sector(self, sector: str, limit: int = 10) -> List[Dict]:
        """Get companies from a specific sector"""
        # Map sector to relevant tickers
        sector_map = {
            "Technology": ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "TSLA"],
            "Finance": ["JPM", "BAC", "WFC", "C", "GS"],
            "Healthcare": ["JNJ", "PFE", "UNH", "ABBV"],
            "Consumer": ["PG", "KO", "MCD", "NKE"],
            "Energy": ["XOM", "CVX", "COP"],
            "Industrial": ["CAT", "BA", "HON", "GE"]
        }

        tickers = sector_map.get(sector, sector_map.get("Technology", []))
        companies = []

        for ticker in tickers[:limit]:
            info = self.get_company_info(ticker)
            if info:
                companies.append(info)

        return companies


class AlphaVantageClient(BaseClient):
    """
    Alpha Vantage Client - https://www.alphavantage.co/

    Free tier: 25 requests/day, 5 requests/minute
    Requires API key (free at https://www.alphavantage.co/support/#api-key)
    """

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.api_key = api_key or "demo"  # demo key for testing

    def get_company_overview(self, ticker: str) -> Optional[Dict]:
        """Get company overview data"""
        params = {
            "function": "OVERVIEW",
            "symbol": ticker,
            "apikey": self.api_key
        }

        result = self._get(self.BASE_URL, params=params)
        return result

    def get_income_statement(self, ticker: str) -> Optional[Dict]:
        """Get income statement data"""
        params = {
            "function": "INCOME_STATEMENT",
            "symbol": ticker,
            "apikey": self.api_key
        }

        result = self._get(self.BASE_URL, params=params)
        return result

    def get_balance_sheet(self, ticker: str) -> Optional[Dict]:
        """Get balance sheet data"""
        params = {
            "function": "BALANCE_SHEET",
            "symbol": ticker,
            "apikey": self.api_key
        }

        result = self._get(self.BASE_URL, params=params)
        return result

    def get_cash_flow(self, ticker: str) -> Optional[Dict]:
        """Get cash flow data"""
        params = {
            "function": "CASH_FLOW",
            "symbol": ticker,
            "apikey": self.api_key
        }

        result = self._get(self.BASE_URL, params=params)
        return result

    def get_earnings(self, ticker: str) -> Optional[Dict]:
        """Get earnings data"""
        params = {
            "function": "EARNINGS",
            "symbol": ticker,
            "apikey": self.api_key
        }

        result = self._get(self.BASE_URL, params=params)
        return result

    def get_news_sentiment(self, tickers: str = "AAPL", limit: int = 10) -> List[Dict]:
        """Get news with sentiment analysis"""
        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": tickers,
            "limit": limit,
            "apikey": self.api_key
        }

        result = self._get(self.BASE_URL, params=params)
        if result and 'feed' in result:
            return result['feed']
        return []


class SECClient(BaseClient):
    """
    SEC EDGAR Client - https://www.sec.gov/edgar/

    Access to company filings (10-K, 10-Q, 8-K, etc.)
    No API key required, but requires user-agent header.
    """

    BASE_URL = "https://www.sec.gov/files/Edgar"

    def __init__(self):
        super().__init__()
        # SEC requires identifying User-Agent
        self.session.headers.update({
            'User-Agent': 'BusinessResearchBot/1.0 (research@example.com)'
        })

    def search_company_filings(self, company_name: str, filing_type: str = "10-K") -> List[Dict]:
        """Search for company filings"""
        # Using SEC's search API
        search_url = "https://www.sec.gov/cgi-bin/browse-edgar"

        params = {
            "company": company_name,
            "type": filing_type,
            "owner": "exclude",
            "count": 10,
            "output": "atom"
        }

        try:
            import xml.etree.ElementTree as ET
            response = self.session.get(search_url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                # Parse XML response
                root = ET.fromstring(response.content)

                filings = []
                for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry'):
                    title = entry.find('{http://www.w3.org/2005/Atom}title')
                    link = entry.find('{http://www.w3.org/2005/Atom}link')
                    updated = entry.find('{http://www.w3.org/2005/Atom}updated')

                    filings.append({
                        "title": title.text if title is not None else "",
                        "link": link.get('href') if link is not None else "",
                        "date": updated.text if updated is not None else ""
                    })

                return filings

        except Exception as e:
            logger.error(f"SEC filings search error: {e}")

        return []

    def get_filing_text(self, accession_number: str) -> Optional[str]:
        """Get full text of a filing by accession number"""
        # This would require parsing and fetching the actual filing
        # Simplified version
        return None


# ============================================================================
# Company Information APIs
# ============================================================================

class OpenCorporatesClient(BaseClient):
    """
    OpenCorporates Client - https://opencorporates.com/

    Largest open database of companies in the world.
    Free API tier available.
    """

    BASE_URL = "https://api.opencorporates.com"

    def __init__(self, api_token: Optional[str] = None):
        super().__init__()
        self.api_token = api_token

    def search_companies(self, query: str, jurisdiction: str = "us") -> Optional[Dict]:
        """Search for companies"""
        params = {
            "q": query,
            "jurisdiction_code": jurisdiction,
            "format": "json"
        }

        if self.api_token:
            params["api_token"] = self.api_token

        url = f"{self.BASE_URL}/companies/search"
        return self._get(url, params=params)

    def get_company(self, jurisdiction: str, company_number: str) -> Optional[Dict]:
        """Get company details"""
        params = {"format": "json"}
        if self.api_token:
            params["api_token"] = self.api_token

        url = f"{self.BASE_URL}/companies/{jurisdiction}/{company_number}"
        return self._get(url, params=params)

    def get_officers(self, jurisdiction: str, company_number: str) -> List[Dict]:
        """Get company officers/directors"""
        params = {"format": "json"}
        if self.api_token:
            params["api_token"] = self.api_token

        url = f"{self.BASE_URL}/companies/{jurisdiction}/{company_number}/officers"
        result = self._get(url, params=params)

        if result and 'officers' in result:
            return result['officers']
        return []


# ============================================================================
# Economic Data APIs
# ============================================================================

class WorldBankClient(BaseClient):
    """
    World Bank API Client - https://data.worldbank.org/

    No API key required. Access to global economic indicators.
    """

    BASE_URL = "https://api.worldbank.org/v2"

    def get_country_indicators(self, country_code: str = "US", indicator: str = "NY.GDP.MKTP.CD") -> List[Dict]:
        """Get economic indicator for a country"""
        url = f"{self.BASE_URL}/country/{country_code}/indicator/{indicator}"
        params = {"format": "json", "per_page": 10}

        result = self._get(url, params=params)
        if result and len(result) > 1:
            return result[1]  # First element is metadata, second is data
        return []

    def get_gdp(self, country_code: str = "ALL") -> List[Dict]:
        """Get GDP data for countries"""
        return self.get_country_indicators(country_code, "NY.GDP.MKTP.CD")

    def get_gdp_per_capita(self, country_code: str = "ALL") -> List[Dict]:
        """Get GDP per capita"""
        return self.get_country_indicators(country_code, "NY.GDP.PCAP.CD")

    def get_inflation(self, country_code: str = "ALL") -> List[Dict]:
        """Get inflation rate"""
        return self.get_country_indicators(country_code, "FP.CPI.TOTL.ZG")

    def get_unemployment(self, country_code: str = "ALL") -> List[Dict]:
        """Get unemployment rate"""
        return self.get_country_indicators(country_code, "SL.UEM.TOTL.ZS")

    def get_trade_data(self, country_code: str = "ALL") -> List[Dict]:
        """Get trade data"""
        # Exports
        exports = self.get_country_indicators(country_code, "NE.EXP.GNFS.CD")
        # Imports
        imports = self.get_country_indicators(country_code, "NE.IMP.GNFS.CD")

        return {"exports": exports, "imports": imports}

    def get_random_country_economy(self) -> Dict:
        """Get economic data for a random country"""
        countries = ["US", "CN", "JP", "DE", "GB", "FR", "IN", "BR", "CA", "AU"]
        country = random.choice(countries)

        return {
            "country": country,
            "gdp": self.get_gdp(country),
            "gdp_per_capita": self.get_gdp_per_capita(country),
            "inflation": self.get_inflation(country),
            "unemployment": self.get_unemployment(country)
        }


class FREDClient(BaseClient):
    """
    FRED (Federal Reserve Economic Data) Client - https://fred.stlouisfed.org/

    Requires API key (free at https://fred.stlouisfed.org/docs/api/api_key.html)
    """

    BASE_URL = "https://api.stlouisfed.org/fred"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.api_key = api_key

    def get_series(self, series_id: str) -> Optional[Dict]:
        """Get economic series data"""
        if not self.api_key:
            logger.warning("FRED API key required")
            return None

        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json"
        }

        url = f"{self.BASE_URL}/series/observations"
        return self._get(url, params=params)

    def get_gdp(self) -> Optional[Dict]:
        """Get US GDP data"""
        return self.get_series("GDP")

    def get_cpi(self) -> Optional[Dict]:
        """Get Consumer Price Index"""
        return self.get_series("CPIAUCSL")

    def get_unemployment_rate(self) -> Optional[Dict]:
        """Get US unemployment rate"""
        return self.get_series("UNRATE")

    def get_fed_funds_rate(self) -> Optional[Dict]:
        """Get Federal Funds Rate"""
        return self.get_series("FEDFUNDS")


class OECDClient(BaseClient):
    """
    OECD Data Client - https://data.oecd.org/

    No API key required for basic usage.
    """

    BASE_URL = "https://stats.oecd.org/SDMX-JSON/data"

    def get_data(self, dataset: str, filter: str = "") -> Optional[Dict]:
        """Get OECD data"""
        url = f"{self.BASE_URL}/{dataset}/{filter}"
        params = {"dimensionObservationStatus": "all"}

        return self._get(url, params=params)

    def get_gdp_by_country(self) -> Optional[Dict]:
        """Get GDP by country"""
        return self.get_data("QNA", "")

    def get_unemployment_by_country(self) -> Optional[Dict]:
        """Get unemployment by country"""
        return self.get_data("LMUNRYY", "")


# ============================================================================
# Stock Market APIs
# ============================================================================

class IEXCloudClient(BaseClient):
    """
    IEX Cloud Client - https://iexcloud.io/

    Requires API key. Free tier: 100,000 requests/month.
    """

    BASE_URL = "https://cloud.iexapis.com/v1"

    def __init__(self, api_key: Optional[str] = None, sandbox: bool = True):
        super().__init__()
        self.api_key = api_key
        if sandbox:
            # Use sandbox for testing
            self.BASE_URL = "https://sandbox.iexapis.com/stable"

    def get_company(self, symbol: str) -> Optional[Dict]:
        """Get company info"""
        if not self.api_key:
            return None

        params = {"token": self.api_key}
        return self._get(f"{self.BASE_URL}/stock/{symbol}/company", params=params)

    def get_stats(self, symbol: str) -> Optional[Dict]:
        """Get company stats"""
        if not self.api_key:
            return None

        params = {"token": self.api_key}
        return self._get(f"{self.BASE_URL}/stock/{symbol}/stats", params=params)

    def get_news(self, symbol: str, limit: int = 10) -> List[Dict]:
        """Get company news"""
        if not self.api_key:
            return []

        params = {"token": self.api_key}
        result = self._get(f"{self.BASE_URL}/stock/{symbol}/news/last/{limit}", params=params)

        if result and isinstance(result, list):
            return result
        return []


# ============================================================================
# Legal/Contracts APIs
# ============================================================================

class CourtListenerClient(BaseClient):
    """
    CourtListener Client - https://www.courtlistener.com/api/

    Free access to US court opinions and filings.
    Requires API key (free at https://www.courtlistener.com/api/)
    """

    BASE_URL = "https://www.courtlistener.com/api/rest/v3"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.api_key = api_key

    def search_opinions(self, query: str, search_type: str = "opinions") -> Optional[Dict]:
        """Search court opinions"""
        if not self.api_key:
            return None

        params = {
            "q": query,
            "page_size": 10
        }

        headers = {"Authorization": f"Token {self.api_key}"}
        return self._get(f"{self.BASE_URL}/search/", params=params, headers=headers)

    def search_dockets(self, query: str) -> Optional[Dict]:
        """Search court dockets"""
        if not self.api_key:
            return None

        params = {"q": query, "page_size": 10}
        headers = {"Authorization": f"Token {self.api_key}"}

        return self._get(f"{self.BASE_URL}/search/dockets/", params=params, headers=headers)


# ============================================================================
# Business Database APIs
# ============================================================================

class CrunchbaseClient(BaseClient):
    """
    Crunchbase Client - https://data.crunchbase.com/

    Requires API key. Access to startup and company funding data.
    """

    BASE_URL = "https://api.crunchbase.com/api/v4"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.api_key = api_key

    def search_organizations(self, query: str) -> Optional[Dict]:
        """Search for organizations"""
        if not self.api_key:
            return None

        headers = {"X-cb-user-key": self.api_key}
        params = {"query": query}

        return self._get(f"{self.BASE_URL}/entities/organizations", params=params, headers=headers)

    def get_organization(self, permalink: str) -> Optional[Dict]:
        """Get organization details"""
        if not self.api_key:
            return None

        headers = {"X-cb-user-key": self.api_key}
        return self._get(f"{self.BASE_URL}/entities/organizations/{permalink}", headers=headers)


# ============================================================================
# Wikidata Business Entities
# ============================================================================

class WikidataBusinessClient(BaseClient):
    """
    Wikidata Business Client - Queries Wikidata SPARQL endpoint
    for business-related entities.
    """

    SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

    def __init__(self):
        super().__init__()
        self.session.headers.update({
            'Accept': 'application/sparql-results+json'
        })

    def query_sparql(self, sparql: str) -> List[Dict]:
        """Execute SPARQL query"""
        params = {
            "query": sparql,
            "format": "json"
        }

        result = self._get(self.SPARQL_ENDPOINT, params=params)
        if result and 'results' in result:
            return result['results'].get('bindings', [])
        return []

    def get_companies(self, limit: int = 50) -> List[Dict]:
        """Get random companies"""
        sparql = f"""
        SELECT ?company ?companyLabel ?industryLabel ?countryLabel WHERE {{
          ?company wdt:P31 wd:Q4830453.  # instance of business
          ?company wdt:P452 ?industry.   # has industry
          OPTIONAL {{ ?company wdt:P17 ?country. }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT {limit}
        """

        results = self.query_sparql(sparql)

        companies = []
        for r in results:
            companies.append({
                "id": r.get('company', {}).get('value', '').split('/')[-1],
                "name": r.get('companyLabel', {}).get('value', ''),
                "industry": r.get('industryLabel', {}).get('value', ''),
                "country": r.get('countryLabel', {}).get('value', '')
            })

        return companies

    def get_fortune_500_companies(self) -> List[Dict]:
        """Get Fortune 500 companies"""
        sparql = """
        SELECT ?company ?companyLabel ?revenue ?employees WHERE {
          ?company wdt:P31 wd:Q4830453.
          ?company wdt:P8398 ?fortune.  # Fortune 500 ranking
          OPTIONAL { ?company wdt:P2139 ?revenue. }
          OPTIONAL { ?company wdt:P1128 ?employees. }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 500
        """

        results = self.query_sparql(sparql)

        companies = []
        for r in results:
            companies.append({
                "name": r.get('companyLabel', {}).get('value', ''),
                "revenue": r.get('revenue', {}).get('value', ''),
                "employees": r.get('employees', {}).get('value', '')
            })

        return companies

    def get_startups(self, limit: int = 50) -> List[Dict]:
        """Get startup companies"""
        sparql = f"""
        SELECT ?company ?companyLabel ?industryLabel ?founded WHERE {{
          ?company wdt:P31/wdt:P279* wd:Q2908646.  # instance of startup or subclasses
          OPTIONAL {{ ?company wdt:P452 ?industry. }}
          OPTIONAL {{ ?company wdt:P571 ?founded. }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT {limit}
        """

        results = self.query_sparql(sparql)

        startups = []
        for r in results:
            startups.append({
                "name": r.get('companyLabel', {}).get('value', ''),
                "industry": r.get('industryLabel', {}).get('value', ''),
                "founded": r.get('founded', {}).get('value', '')
            })

        return startups

    def get_business_people(self, limit: int = 50) -> List[Dict]:
        """Get business people/CEOs"""
        sparql = f"""
        SELECT ?person ?personLabel ?positionLabel ?companyLabel WHERE {{
          ?person wdt:P39 ?position.
          ?position wdt:P279* wd:Q3053182.  # subclass of CEO or executive
          OPTIONAL {{ ?position wdt:P706 ?company. }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT {limit}
        """

        results = self.query_sparql(sparql)

        people = []
        for r in results:
            people.append({
                "name": r.get('personLabel', {}).get('value', ''),
                "position": r.get('positionLabel', {}).get('value', ''),
                "company": r.get('companyLabel', {}).get('value', '')
            })

        return people


# ============================================================================
# DBpedia Business Entities
# ============================================================================

class DBpediaBusinessClient(BaseClient):
    """
    DBpedia Business Client - Queries DBpedia SPARQL endpoint
    for business-related entities.
    """

    SPARQL_ENDPOINT = "http://dbpedia.org/sparql"

    def __init__(self):
        super().__init__()
        self.session.headers.update({
            'Accept': 'application/sparql-results+json'
        })

    def query_sparql(self, sparql: str) -> Dict:
        """Execute SPARQL query"""
        params = {
            "query": sparql,
            "format": "json"
        }

        result = self._get(self.SPARQL_ENDPOINT, params=params)
        if result:
            return result
        return {'results': {'bindings': []}}

    def get_companies(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get companies from DBpedia"""
        sparql = f"""
        SELECT DISTINCT ?company ?name ?industry ?country WHERE {{
          ?company a dbo:Company .
          ?company foaf:name ?name .
          OPTIONAL {{ ?company dbo:industry ?industry }}
          OPTIONAL {{ ?company dbo:location ?country }}
          FILTER(LANG(?name) = "en")
        }}
        LIMIT {limit}
        OFFSET {offset}
        """

        result = self.query_sparql(sparql)
        bindings = result.get('results', {}).get('bindings', [])

        companies = []
        for b in bindings:
            companies.append({
                "name": b.get('name', {}).get('value', ''),
                "industry": b.get('industry', {}).get('value', ''),
                "country": b.get('country', {}).get('value', '')
            })

        return companies


# ============================================================================
# Convenience Functions
# ============================================================================

def get_news_client(api_key: Optional[str] = None) -> NewsAPIClient:
    """Get NewsAPI client instance"""
    return NewsAPIClient(api_key)


def get_yahoo_finance_client() -> YahooFinanceClient:
    """Get Yahoo Finance client instance"""
    return YahooFinanceClient()


def get_world_bank_client() -> WorldBankClient:
    """Get World Bank client instance"""
    return WorldBankClient()


def get_sec_client() -> SECClient:
    """Get SEC client instance"""
    return SECClient()


def get_wikidata_business_client() -> WikidataBusinessClient:
    """Get Wikidata business client instance"""
    return WikidataBusinessClient()


def get_dbpedia_business_client() -> DBpediaBusinessClient:
    """Get DBpedia business client instance"""
    return DBpediaBusinessClient()


if __name__ == "__main__":
    # Test clients
    logger.info("Testing Business API Clients...")

    # Test Yahoo Finance
    yahoo = get_yahoo_finance_client()
    if yahoo.available:
        company = yahoo.get_company_info("AAPL")
        if company:
            logger.info(f"Yahoo Finance: {company['name']} - {company['sector']}")

    # Test World Bank
    wb = get_world_bank_client()
    gdp = wb.get_gdp("US")
    if gdp:
        logger.info(f"World Bank: US GDP data points: {len(gdp)}")

    # Test Wikidata Business
    wikidata = get_wikidata_business_client()
    companies = wikidata.get_companies(limit=5)
    logger.info(f"Wikidata: Found {len(companies)} companies")

    logger.info("API client tests completed!")
