#!/usr/bin/env python3
"""
Academia and Scholarly Data APIs Client

This module provides clients for various academia and scholarly communication related APIs.

Supported APIs:
- OpenAlex: Open scholarly graph (papers, authors, institutions, journals, concepts)
- Semantic Scholar: Academic paper search and citation data
- arXiv: Preprint server for physics, mathematics, computer science
- PubMed: Biomedical and life sciences literature
- Crossref: DOI metadata and citation search
- ROR: Research organization registry
- ORCID: Researcher and contributor ID (public data)
- OpenCitations: Open citation data
- DOAJ: Directory of Open Access Journals
- Europe PMC: European literature repository

Usage:
    from academia_apis import (
        OpenAlexClient, SemanticScholarClient, ArXivClient,
        PubMedClient, CrossrefClient, RORClient
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
    """Base class for academia API clients"""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; AcademiaDataPipeline/1.0; +https://github.com/academic-research)'
        })

    def _get(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Optional[Dict]:
        """Make GET request and return JSON response"""
        try:
            req_headers = self.session.headers.copy()
            if headers:
                req_headers.update(headers)

            response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()

            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                return response.json()
            else:
                return {'content': response.text, 'status_code': response.status_code}

        except Exception as e:
            logger.error(f"{self.__class__.__name__} error: {e}")
            return None


# ============================================================================
# OpenAlex Client
# ============================================================================

class OpenAlexClient(BaseClient):
    """
    OpenAlex Client - Open scholarly graph

    OpenAlex is a fully open catalog of the global research system.
    It provides comprehensive data on papers, authors, institutions, journals, and concepts.

    API Docs: https://docs.openalex.org/
    Base URL: https://api.openalex.org

    No API key required. Email politer@gmail.com for faster rate limits.
    """

    BASE_URL = "https://api.openalex.org"

    def __init__(self, email: Optional[str] = None):
        """
        Initialize OpenAlex client

        Args:
            email: Optional email for rate limiting (mailto:email@example.com)
        """
        super().__init__()
        if email:
            self.session.params['mailto'] = email

    def get_random_paper(self, filter_params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Get random academic paper

        Args:
            filter_params: Optional filters like {'has_fulltext': true, 'from_publications': true}
        """
        try:
            # Get a random page
            params = {
                'per-page': 1,
                'filter': 'has_fulltext:true'
            }
            if filter_params:
                params['filter'].update(filter_params)

            # Get total count and random page
            url = f"{self.BASE_URL}/works"
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            total = data.get('meta', {}).get('count', 0)
            if total > 0:
                # Random page offset
                offset = random.randint(0, min(total - 1, 100000))
                params['page'] = offset // 200 + 1

                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()

                results = data.get('results', [])
                if results:
                    return self._format_paper(random.choice(results))

        except Exception as e:
            logger.error(f"OpenAlex paper error: {e}")

        return None

    def _format_paper(self, paper: Dict) -> Dict:
        """Format OpenAlex paper data"""
        return {
            'id': paper.get('id', '').split('/')[-1],
            'title': paper.get('title', ''),
            'year': paper.get('publication_year'),
            'type': paper.get('type', ''),
            'cited_by_count': paper.get('cited_by_count', 0),
            'concepts': [c.get('display_name') for c in paper.get('concepts', [])[:5]],
            'authorships': [a.get('author', {}).get('display_name') for a in paper.get('authorships', [])[:3]],
            'primary_location': paper.get('primary_location', {}).get('source', {}).get('display_name', ''),
            'openalex': paper.get('id', ''),
            'doi': paper.get('doi', ''),
            'pmid': paper.get('ids', {}).get('pmid', ''),
        }

    def get_random_author(self, works_count_min: int = 10) -> Optional[Dict]:
        """
        Get random author with minimum works

        Args:
            works_count_min: Minimum number of works for the author
        """
        try:
            # Search for authors with minimum works
            params = {
                'filter': f'has_orcid:true,works_count:>{works_count_min}',
                'per-page': 1
            }

            url = f"{self.BASE_URL}/authors"
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            total = data.get('meta', {}).get('count', 0)
            if total > 0:
                offset = random.randint(0, min(total - 1, 50000))
                params['page'] = offset // 200 + 1

                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()

                results = data.get('results', [])
                if results:
                    return self._format_author(random.choice(results))

        except Exception as e:
            logger.error(f"OpenAlex author error: {e}")

        return None

    def _format_author(self, author: Dict) -> Dict:
        """Format OpenAlex author data"""
        last_known_institution = author.get('last_known_institution', {})
        return {
            'id': author.get('id', '').split('/')[-1],
            'name': author.get('display_name', ''),
            'orcid': author.get('orcid', ''),
            'works_count': author.get('works_count', 0),
            'cited_by_count': author.get('cited_by_count', 0),
            'h_index': author.get('summary_stats', {}).get('h_index', 0),
            'last_known_institution': last_known_institution.get('display_name', ''),
            'country_code': last_known_institution.get('country_code', ''),
            'concepts': [c.get('display_name') for c in author.get('concepts', [])[:5]],
        }

    def get_random_institution(self, country: Optional[str] = None) -> Optional[Dict]:
        """
        Get random research institution

        Args:
            country: Optional country code filter
        """
        try:
            filter_str = 'type:education'
            if country:
                filter_str += f',country_code:{country}'

            params = {
                'filter': filter_str,
                'per-page': 1
            }

            url = f"{self.BASE_URL}/institutions"
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            total = data.get('meta', {}).get('count', 0)
            if total > 0:
                offset = random.randint(0, min(total - 1, 10000))
                params['page'] = offset // 200 + 1

                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()

                results = data.get('results', [])
                if results:
                    return self._format_institution(random.choice(results))

        except Exception as e:
            logger.error(f"OpenAlex institution error: {e}")

        return None

    def _format_institution(self, inst: Dict) -> Dict:
        """Format OpenAlex institution data"""
        return {
            'id': inst.get('id', '').split('/')[-1],
            'name': inst.get('display_name', ''),
            'country_code': inst.get('country_code', ''),
            'type': inst.get('type', ''),
            'works_count': inst.get('works_count', 0),
            'cited_by_count': inst.get('cited_by_count', 0),
            'homepage': inst.get('homepage_url', ''),
            'image': inst.get('image_url', ''),
        }

    def get_random_concept(self, level: int = 0) -> Optional[Dict]:
        """
        Get random research concept

        Args:
            level: Concept level (0-2, 0 = most specific)
        """
        try:
            # Use concepts endpoint or search
            params = {
                'filter': f'level:{level}',
                'per-page': 200
            }

            url = f"{self.BASE_URL}/concepts"
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            results = data.get('results', [])
            if results:
                concept = random.choice(results)
                # Safely extract ancestors
                ancestors_list = concept.get('ancestors', [])
                if ancestors_list and isinstance(ancestors_list, list):
                    ancestors = [a.get('display_name', '') if isinstance(a, dict) else str(a)
                                for a in ancestors_list[:3] if a]
                else:
                    ancestors = []

                return {
                    'id': concept.get('id', '').split('/')[-1] if concept.get('id') else '',
                    'name': concept.get('display_name', ''),
                    'level': concept.get('level', 0),
                    'wikidata': concept.get('wikidata', ''),
                    'ancestors': ancestors,
                    'works_count': concept.get('works_count', 0) if concept.get('works_count') else 0,
                }

        except Exception as e:
            logger.error(f"OpenAlex concept error: {e}")

        return None

    def get_random_journal(self, subject: Optional[str] = None) -> Optional[Dict]:
        """
        Get random journal

        Args:
            subject: Optional subject area filter
        """
        try:
            filter_str = 'type:journal'
            if subject:
                filter_str += f',subjects:{subject}'

            params = {
                'filter': filter_str,
                'per-page': 1
            }

            url = f"{self.BASE_URL}/sources"
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            total = data.get('meta', {}).get('count', 0)
            if total > 0:
                offset = random.randint(0, min(total - 1, 10000))
                params['page'] = offset // 200 + 1

                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()

                results = data.get('results', [])
                if results:
                    source = random.choice(results)
                    return {
                        'id': source.get('id', '').split('/')[-1],
                        'issn': source.get('issn_l', ''),
                        'name': source.get('display_name', ''),
                        'type': source.get('type', ''),
                        'works_count': source.get('works_count', 0),
                        'cited_by_count': source.get('cited_by_count', 0),
                        'h_index': source.get('summary_stats', {}).get('h_index', 0),
                        'is_oa': source.get('is_oa', False),
                        'homepage': source.get('homepage_url', ''),
                    }

        except Exception as e:
            logger.error(f"OpenAlex journal error: {e}")

        return None

    def search_papers_by_keyword(self, keyword: str, limit: int = 10) -> List[Dict]:
        """Search papers by keyword"""
        try:
            params = {
                'search': keyword,
                'per-page': limit
            }

            url = f"{self.BASE_URL}/works"
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            results = data.get('results', [])
            return [self._format_paper(p) for p in results]

        except Exception as e:
            logger.error(f"OpenAlex search error: {e}")
            return []

    def get_works_by_concept(self, concept: str, limit: int = 10) -> List[Dict]:
        """Get recent works by concept"""
        try:
            current_year = datetime.now().year
            params = {
                'filter': f'concepts:{concept},from_publication_date:{current_year-5}-01-01',
                'sort': 'cited_by_count:desc',
                'per-page': limit
            }

            url = f"{self.BASE_URL}/works"
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            results = data.get('results', [])
            return [self._format_paper(p) for p in results]

        except Exception as e:
            logger.error(f"OpenAlex concept works error: {e}")
            return []


# ============================================================================
# Semantic Scholar Client
# ============================================================================

class SemanticScholarClient(BaseClient):
    """
    Semantic Scholar Client

    Provides paper search, citation data, and author information.

    API Docs: https://api.semanticscholar.org/api-docs/
    Base URL: https://api.semanticscholar.org/graph/v1

    No API key required for basic usage (100 requests per 5 minutes).
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Semantic Scholar client

        Args:
            api_key: Optional API key for higher rate limits
        """
        super().__init__()
        if api_key:
            self.session.headers.update({'x-api-key': api_key})

    def get_paper_by_id(self, paper_id: str) -> Optional[Dict]:
        """Get paper details by ID (DOI, S2CorpusId, etc.)"""
        try:
            url = f"{self.BASE_URL}/paper/{paper_id}"
            params = {'fields': 'paperId,title,abstract,authors,year,citationCount,influentialCitationCount,venue,journal,fieldsOfStudy,openAccessPdf'}

            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            return self._format_paper(response.json())

        except Exception as e:
            logger.error(f"Semantic Scholar paper error: {e}")
            return None

    def _format_paper(self, paper: Dict) -> Dict:
        """Format Semantic Scholar paper data"""
        return {
            'paperId': paper.get('paperId', ''),
            'title': paper.get('title', ''),
            'abstract': paper.get('abstract', ''),
            'year': paper.get('year'),
            'citationCount': paper.get('citationCount', 0),
            'influentialCitationCount': paper.get('influentialCitationCount', 0),
            'venue': paper.get('venue', ''),
            'journal': paper.get('journal', {}).get('name', ''),
            'fieldsOfStudy': paper.get('fieldsOfStudy', []),
            'authors': [a.get('name', '') for a in paper.get('authors', [])[:5]],
            'openAccessPdf': paper.get('openAccessPdf', {}).get('url', ''),
        }

    def search_papers(self, query: str, limit: int = 10, year: Optional[str] = None) -> List[Dict]:
        """
        Search papers by query

        Args:
            query: Search query
            limit: Number of results (max 100)
            year: Optional year filter (e.g., "2020-2023")
        """
        try:
            params = {
                'query': query,
                'limit': min(limit, 100),
                'fields': 'paperId,title,abstract,authors,year,citationCount,venue,journal,fieldsOfStudy'
            }

            if year:
                params['year'] = year

            url = f"{self.BASE_URL}/paper/search"
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            papers = data.get('data', [])

            # Get details for each paper
            results = []
            for paper in papers[:limit]:
                results.append(self._format_paper(paper))

            return results

        except Exception as e:
            logger.error(f"Semantic Scholar search error: {e}")
            return []

    def get_author(self, author_id: str) -> Optional[Dict]:
        """Get author details"""
        try:
            url = f"{self.BASE_URL}/author/{author_id}"
            params = {'fields': 'authorId,name,paperCount,citationCount,hIndex,affiliations,homePage,papers'}

            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            return {
                'authorId': data.get('authorId', ''),
                'name': data.get('name', ''),
                'paperCount': data.get('paperCount', 0),
                'citationCount': data.get('citationCount', 0),
                'hIndex': data.get('hIndex', 0),
                'affiliations': data.get('affiliations', []),
                'homePage': data.get('homePage', ''),
            }

        except Exception as e:
            logger.error(f"Semantic Scholar author error: {e}")
            return None

    def search_authors(self, query: str, limit: int = 10) -> List[Dict]:
        """Search authors by name"""
        try:
            params = {
                'query': query,
                'limit': min(limit, 100)
            }

            url = f"{self.BASE_URL}/author/search"
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            authors = data.get('data', [])

            return [{
                'authorId': a.get('authorId', ''),
                'name': a.get('name', ''),
                'paperCount': a.get('paperCount', 0),
                'citationCount': a.get('citationCount', 0),
                'hIndex': a.get('hIndex', 0),
            } for a in authors[:limit]]

        except Exception as e:
            logger.error(f"Semantic Scholar author search error: {e}")
            return []


# ============================================================================
# ArXiv Client
# ============================================================================

class ArXivClient(BaseClient):
    """
    arXiv Client - Preprint server

    API Docs: http://arxiv.org/help/api/
    Base URL: http://export.arxiv.org/api/query

    No API key required.
    """

    BASE_URL = "http://export.arxiv.org/api/query"

    # arXiv categories
    CATEGORIES = {
        'physics': ['physics.*', 'astro-ph.*', 'cond-mat.*', 'gr-qc', 'hep-*', 'nucl-*'],
        'mathematics': ['math.*'],
        'computer_science': ['cs.*'],
        'quantitative_biology': ['q-bio.*'],
        'quantitative_finance': ['q-fin.*'],
        'statistics': ['stat.*'],
        'electrical_engineering': ['eess.*'],
        'economics': ['econ.*'],
    }

    def __init__(self):
        super().__init__()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; AcademiaDataPipeline/1.0)'
        })

    def get_random_paper(self, category: Optional[str] = None) -> Optional[Dict]:
        """
        Get random arXiv paper

        Args:
            category: Optional arXiv category (e.g., 'cs.AI', 'hep-ph')
        """
        try:
            # Build search query
            if category:
                search_query = f"cat:{category}"
            else:
                # Random category
                all_categories = []
                for cats in self.CATEGORIES.values():
                    all_categories.extend(cats)
                # Remove wildcards for search
                all_categories = [c.replace('*', '') for c in all_categories]
                category = random.choice(all_categories)
                search_query = f"cat:{category}*"

            # Get recent papers (last 30 days)
            params = {
                'search_query': f"{search_query}",
                'start': 0,
                'max_results': 100,
                'sortBy': 'lastUpdatedDate',
                'sortOrder': 'descending'
            }

            response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
            response.raise_for_status()

            # Parse Atom XML response
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)

            # Namespace for arXiv Atom format
            ns = {'atom': 'http://www.w3.org/2005/Atom',
                   'arxiv': 'http://arxiv.org/schemas/atom'}

            entries = root.findall('atom:entry', ns)
            if entries:
                entry = random.choice(entries)
                return self._format_arxiv_entry(entry, ns)

        except Exception as e:
            logger.error(f"arXiv random paper error: {e}")

        return None

    def _format_arxiv_entry(self, entry, ns: Dict) -> Dict:
        """Format arXiv entry data"""
        # Get ID (remove URL prefix)
        arxiv_id = entry.find('atom:id', ns).text.split('/')[-1]

        # Get categories
        categories = [cat.get('term', '') for cat in entry.findall('arxiv:primary_category', ns)]
        all_categories = [cat.get('term', '') for cat in entry.findall('atom:category', ns)]

        # Get authors
        authors = []
        for author in entry.findall('atom:author', ns):
            name = author.find('atom:name', ns)
            if name is not None:
                authors.append(name.text)

        # Get summary
        summary = entry.find('atom:summary', ns)
        summary_text = summary.text.strip() if summary is not None else ''

        # Get title
        title = entry.find('atom:title', ns)
        title_text = title.text.strip() if title is not None else ''

        # Get published date
        published = entry.find('atom:published', ns)
        published_text = published.text if published is not None else ''

        return {
            'id': arxiv_id,
            'title': title_text,
            'summary': summary_text,
            'published': published_text,
            'categories': categories,
            'all_categories': all_categories,
            'authors': authors[:10],
            'arxiv_url': f"https://arxiv.org/abs/{arxiv_id}",
        }

    def search_papers(self, query: str, limit: int = 10) -> List[Dict]:
        """Search arXiv papers"""
        try:
            params = {
                'search_query': f"all:{query}",
                'start': 0,
                'max_results': min(limit, 100),
                'sortBy': 'relevance',
                'sortOrder': 'descending'
            }

            response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
            response.raise_for_status()

            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)

            ns = {'atom': 'http://www.w3.org/2005/Atom',
                   'arxiv': 'http://arxiv.org/schemas/atom'}

            entries = root.findall('atom:entry', ns)
            results = []
            for entry in entries[:limit]:
                results.append(self._format_arxiv_entry(entry, ns))

            return results

        except Exception as e:
            logger.error(f"arXiv search error: {e}")
            return []

    def get_random_category(self) -> str:
        """Get random arXiv category"""
        all_categories = []
        for cats in self.CATEGORIES.values():
            all_categories.extend(cats)
        return random.choice(all_categories)


# ============================================================================
# PubMed Client
# ============================================================================

class PubMedClient(BaseClient):
    """
    PubMed Client - Biomedical literature

    Uses NCBI E-utilities API.

    API Docs: https://www.ncbi.nlm.nih.gov/books/NBK25501/
    Base URL: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/

    No API key required for basic usage (3 requests/second without key).
    """

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize PubMed client

        Args:
            api_key: Optional NCBI API key for higher rate limits
        """
        super().__init__()
        if api_key:
            self.session.params['api_key'] = api_key

        # Required email for E-utilities
        self.session.params['email'] = 'academia_pipeline@example.com'
        self.session.params['tool'] = 'AcademiaDataPipeline'

    def search(self, query: str, limit: int = 20) -> List[str]:
        """
        Search PubMed and return PMIDs

        Args:
            query: Search query
            limit: Number of results (max 10000)
        """
        try:
            params = {
                'db': 'pubmed',
                'term': query,
                'retmax': min(limit, 10000),
                'retmode': 'xml'
            }

            url = f"{self.BASE_URL}/esearch.fcgi"
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)

            id_list = root.find('IdList')
            if id_list is not None:
                return [id.find('Id').text for id in id_list.findall('Id')]

        except Exception as e:
            logger.error(f"PubMed search error: {e}")

        return []

    def get_summary(self, pmid: str) -> Optional[Dict]:
        """Get PubMed article summary by PMID"""
        try:
            params = {
                'db': 'pubmed',
                'id': pmid,
                'retmode': 'xml'
            }

            url = f"{self.BASE_URL}/esummary.fcgi"
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)

            doc_sum = root.find('.//DocumentSummarySet/DocumentSummary')
            if doc_sum is not None:
                return self._format_pubmed_summary(doc_sum)

        except Exception as e:
            logger.error(f"PubMed summary error: {e}")

        return None

    def _format_pubmed_summary(self, doc_sum) -> Dict:
        """Format PubMed document summary"""
        def get_text(elem, tag):
            el = elem.find(tag)
            return el.text if el is not None else ''

        authors = []
        author_list = doc_sum.find('Authors')
        if author_list is not None:
            for author in author_list.findall('Author'):
                name_parts = []
                for name_part in ['LastName', 'ForeName', 'Initials']:
                    part = author.find(name_part)
                    if part is not None:
                        name_parts.append(part.text)
                if name_parts:
                    authors.append(' '.join(name_parts))

        journal = doc_sum.find('Source/Journal/Title')
        journal_title = journal.text if journal is not None else ''

        return {
            'pmid': get_text(doc_sum, 'Id'),
            'title': get_text(doc_sum, 'Title'),
            'abstract': get_text(doc_sum, 'Abstract/AbstractText'),
            'authors': authors[:10],
            'journal': journal_title,
            'pub_date': get_text(doc_sum, 'ArticleDate/Year'),
            'citation_count': get_text(doc_sum, 'PmcCitationCount') or '0',
            'pubmed_url': f"https://pubmed.ncbi.nlm.nih.gov/{get_text(doc_sum, 'Id')}/",
        }

    def get_random_article(self, subject: Optional[str] = None) -> Optional[Dict]:
        """
        Get random PubMed article

        Args:
            subject: Optional MeSH subject or keyword
        """
        try:
            # Build search query
            if subject:
                query = f"{subject}[MeSH Terms]"
            else:
                # Random common medical subjects
                subjects = [
                    'oncology', 'cardiology', 'neurology', 'immunology',
                    'genetics', 'pharmacology', 'biochemistry', 'microbiology',
                    'epidemiology', 'pathology', 'radiology', 'surgery'
                ]
                query = random.choice(subjects)

            # Search for recent articles
            recent_pmids = self.search(query, limit=100)
            if recent_pmids:
                # Get random PMID and fetch summary
                pmid = random.choice(recent_pmids)
                time.sleep(0.34)  # NCBI rate limit (3 requests/second)
                return self.get_summary(pmid)

        except Exception as e:
            logger.error(f"PubMed random article error: {e}")

        return None


# ============================================================================
# Crossref Client
# ============================================================================

class CrossrefClient(BaseClient):
    """
    Crossref Client - DOI metadata and citations

    API Docs: https://api.crossref.org/
    Base URL: https://api.crossref.org/works

    No API key required for basic usage.
    Polite pool recommended: https://www.crossref.org/services/metadata-delivery/rest-api/
    """

    BASE_URL = "https://api.crossref.org/works"

    def __init__(self, contact_email: Optional[str] = None):
        """
        Initialize Crossref client

        Args:
            contact_email: Recommended email for polite pool access
        """
        super().__init__()
        if contact_email:
            self.session.headers['User-Agent'] = f'AcademiaDataPipeline/1.0 (mailto:{contact_email})'

    def random_work(self, filter_type: Optional[str] = None) -> Optional[Dict]:
        """
        Get random work from Crossref

        Args:
            filter_type: Optional type filter (e.g., 'journal-article', 'proceedings-article')
        """
        try:
            # Get a random sample using cursor
            params = {
                'sample': 1,
                'select': 'DOI,title,author,published-print,type,container-title,member'
            }

            if filter_type:
                params['filter'] = f'type:{filter_type}'

            response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            items = data.get('message', {}).get('items', [])

            if items:
                return self._format_work(items[0])

        except Exception as e:
            logger.error(f"Crossref random work error: {e}")

        return None

    def _format_work(self, work: Dict) -> Dict:
        """Format Crossref work data"""
        authors = work.get('author', [])
        author_names = [f"{a.get('given', '')} {a.get('family', '')}".strip()
                       for a in authors[:5]]

        return {
            'doi': work.get('DOI', ''),
            'title': work.get('title', [''])[0] if work.get('title') else '',
            'authors': author_names,
            'type': work.get('type', ''),
            'container_title': work.get('container-title', [''])[0] if work.get('container-title') else '',
            'published': work.get('published-print', {}).get('date-time', ''),
            'member': work.get('member', ''),
            'url': f"https://doi.org/{work.get('DOI', '')}",
        }

    def search_works(self, query: str, limit: int = 10) -> List[Dict]:
        """Search Crossref works"""
        try:
            params = {
                'query': query,
                'limit': min(limit, 1000),
                'select': 'DOI,title,author,type,container-title'
            }

            response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            items = data.get('message', {}).get('items', [])

            return [self._format_work(item) for item in items[:limit]]

        except Exception as e:
            logger.error(f"Crossref search error: {e}")
            return []


# ============================================================================
# ROR Client
# ============================================================================

class RORClient(BaseClient):
    """
    ROR Client - Research Organization Registry

    API Docs: https://ror.org/docs/
    Base URL: https://api.ror.org/organizations

    No API key required.
    """

    BASE_URL = "https://api.ror.org/organizations"

    def get_random_organization(self, country: Optional[str] = None) -> Optional[Dict]:
        """
        Get random research organization

        Args:
            country: Optional country code (ISO 3166 alpha-2)
        """
        try:
            # Use search to get organizations
            # Get organizations by country or random sample
            if country:
                query = country
            else:
                # Use common research terms
                terms = ['university', 'institute', 'college', 'research', 'laboratory']
                query = random.choice(terms)

            params = {
                'query': query,
                'page': 1,
                'per_page': 20
            }

            response = self.session.get(f"{self.BASE_URL}", params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            items = data.get('items', [])

            if items:
                return random.choice(items)

        except Exception as e:
            logger.error(f"ROR random organization error: {e}")

        return None

    def get_organization_by_id(self, ror_id: str) -> Optional[Dict]:
        """Get organization by ROR ID"""
        try:
            url = f"{self.BASE_URL}/{ror_id}"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.error(f"ROR organization error: {e}")
            return None

    def search_organizations(self, query: str, limit: int = 10) -> List[Dict]:
        """Search ROR organizations"""
        try:
            params = {
                'query': query,
                'per_page': min(limit, 100)
            }

            response = self.session.get(f"{self.BASE_URL}", params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            return data.get('items', [])[:limit]

        except Exception as e:
            logger.error(f"ROR search error: {e}")
            return []


# ============================================================================
# DOAJ Client
# ============================================================================

class DOAJClient(BaseClient):
    """
    Directory of Open Access Journals Client

    API Docs: https://doaj.org/api/docs
    Base URL: https://doaj.org/api

    No API key required for basic read operations.
    """

    BASE_URL = "https://doaj.org/api"

    def get_random_journal(self, subject: Optional[str] = None) -> Optional[Dict]:
        """
        Get random open access journal

        Args:
            subject: Optional subject filter
        """
        try:
            params = {
                'pageSize': 100
            }

            url = f"{self.BASE_URL}/search/journals"
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            results = data.get('results', [])

            if results:
                return random.choice(results)

        except Exception as e:
            logger.error(f"DOAJ random journal error: {e}")

        return None

    def search_journals(self, query: str, limit: int = 10) -> List[Dict]:
        """Search DOAJ journals"""
        try:
            params = {
                'q': query,
                'pageSize': min(limit, 100)
            }

            url = f"{self.BASE_URL}/search/journals"
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            return data.get('results', [])[:limit]

        except Exception as e:
            logger.error(f"DOAJ search error: {e}")
            return []


# ============================================================================
# Usage Example
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("ACADEMIA APIS - TESTING")
    print("=" * 70)

    # Test OpenAlex
    print("\n1. Testing OpenAlex...")
    openalex = OpenAlexClient()

    paper = openalex.get_random_paper()
    if paper:
        print(f"  Paper: {paper['title'][:80]}...")

    author = openalex.get_random_author()
    if author:
        print(f"  Author: {author['name']} ({author['works_count']} works)")

    institution = openalex.get_random_institution()
    if institution:
        print(f"  Institution: {institution['name']} ({institution['country_code']})")

    concept = openalex.get_random_concept()
    if concept:
        print(f"  Concept: {concept['name']} (level {concept['level']})")

    # Test Semantic Scholar
    print("\n2. Testing Semantic Scholar...")
    ss = SemanticScholarClient()
    papers = ss.search_papers("machine learning", limit=3)
    print(f"  Found {len(papers)} papers")

    # Test arXiv
    print("\n3. Testing arXiv...")
    arxiv = ArXivClient()
    arxiv_paper = arxiv.get_random_paper()
    if arxiv_paper:
        print(f"  arXiv: {arxiv_paper['title'][:80]}...")

    # Test ROR
    print("\n4. Testing ROR...")
    ror = RORClient()
    org = ror.get_random_organization()
    if org:
        print(f"  Organization: {org.get('name', 'N/A')}")

    print("\n" + "=" * 70)
    print("API TESTS COMPLETED")
    print("=" * 70)
