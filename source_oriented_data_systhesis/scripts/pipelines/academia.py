#!/usr/bin/env python3
"""
AcademiaEntryPointGenerator - Entry Point Generator for Academia Domain

This module contains the entry point generation strategies for the Academia domain.
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
from pools import ExpandedAcademiaPools
from apis.academia_apis import OpenAlexClient, SemanticScholarClient, ArXivClient, PubMedClient, CrossrefClient, RORClient, DOAJClient

class AcademiaEntryPointGenerator:
    """
    学术数据入口点生成器 - 使用扩展池子

    使用多种策略生成学术相关的探索入口点
    覆盖全球学术界：论文、学者、机构、概念等
    """

    def __init__(self):
        self.expanded_pools = ExpandedAcademiaPools()

        # Initialize all strategies
        self.strategies = {
            # OpenAlex strategies (4)
            'openalex_paper': self.openalex_random_paper,
            'openalex_author': self.openalex_random_author,
            'openalex_institution': self.openalex_random_institution,
            'openalex_concept': self.openalex_random_concept,

            # Semantic Scholar strategies (2)
            'semantic_scholar_paper': self.semantic_scholar_search_paper,
            'semantic_scholar_author': self.semantic_scholar_author,

            # Other API strategies (4)
            'arxiv_paper': self.arxiv_random_paper,
            'pubmed_article': self.pubmed_random_article,
            'crossref_work': self.crossref_random_work,
            'ror_organization': self.ror_random_organization,

            # Basic strategies (3)
            'llm_academic_concept': self.llm_generate_academic_concept,
            'wikipedia_academic_category': self.wikipedia_random_from_category,
            'random_academic_keyword': self.random_academic_keyword_search,

            # Entity-based strategies (2)
            'famous_scholar': self.famous_scholar_pool,
            'academic_venue': self.academic_venue_pool,
        }

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        self.ACADEMIC_CATEGORIES = self.expanded_pools.get_all_categories()

        # Initialize API clients
        self.openalex_client = OpenAlexClient()
        self.semantic_scholar_client = SemanticScholarClient()
        self.arxiv_client = ArXivClient()
        self.pubmed_client = PubMedClient()
        self.crossref_client = CrossrefClient()
        self.ror_client = RORClient()
        self.doaj_client = DOAJClient()

        num_strategies = len(self.strategies)
        logger.info(f"Initialized with {len(self.ACADEMIC_CATEGORIES)} categories and {num_strategies} strategies")

    def generate_random_entry(self) -> Dict:
        """使用随机策略生成入口点"""
        strategy_name = random.choice(list(self.strategies.keys()))
        strategy_func = self.strategies[strategy_name]
        return strategy_func()

    # ========================================================================
    # OpenAlex Strategies
    # ========================================================================

    def openalex_random_paper(self) -> Dict:
        """从OpenAlex随机获取学术论文"""
        try:
            paper = self.openalex_client.get_random_paper()

            if paper:
                title = paper.get('title', '')
                concepts = paper.get('concepts', [])

                # Generate search concept
                if concepts:
                    search_concept = f"{title} {concepts[0]}"
                else:
                    search_concept = title

                logger.info(f"OpenAlex paper: {title[:60]}...")

                return {
                    "title": search_concept,
                    "source": "openalex_paper",
                    "paper_id": paper.get('id', ''),
                    "year": paper.get('year'),
                    "citations": paper.get('cited_by_count', 0),
                    "type": "academic_paper"
                }

        except Exception as e:
            logger.error(f"OpenAlex paper error: {e}")

        # Fallback
        return self.llm_generate_academic_concept()

    def openalex_random_author(self) -> Dict:
        """从OpenAlex随机获取学者"""
        try:
            author = self.openalex_client.get_random_author(works_count_min=10)

            if author:
                name = author.get('name', '')
                institution = author.get('last_known_institution', '')
                concepts = author.get('concepts', [])

                # Generate search concept
                if concepts:
                    search_concept = f"{name} {concepts[0]}"
                elif institution:
                    search_concept = f"{name} {institution}"
                else:
                    search_concept = name

                logger.info(f"OpenAlex author: {name}")

                return {
                    "title": search_concept,
                    "source": "openalex_author",
                    "author_id": author.get('id', ''),
                    "orcid": author.get('orcid', ''),
                    "institution": institution,
                    "type": "scholar"
                }

        except Exception as e:
            logger.error(f"OpenAlex author error: {e}")

        # Fallback
        return self.famous_scholar_pool()

    def openalex_random_institution(self) -> Dict:
        """从OpenAlex随机获取学术机构"""
        try:
            institution = self.openalex_client.get_random_institution()

            if institution:
                name = institution.get('name', '')
                country = institution.get('country_code', '')

                search_concept = f"{name} research"

                logger.info(f"OpenAlex institution: {name}")

                return {
                    "title": search_concept,
                    "source": "openalex_institution",
                    "institution_id": institution.get('id', ''),
                    "name": name,
                    "country": country,
                    "type": "institution"
                }

        except Exception as e:
            logger.error(f"OpenAlex institution error: {e}")

        # Fallback
        return self.llm_generate_academic_concept()

    def openalex_random_concept(self) -> Dict:
        """从OpenAlex随机获取研究概念"""
        try:
            concept = self.openalex_client.get_random_concept(level=0)

            if concept:
                name = concept.get('name', '')
                ancestors = concept.get('ancestors', [])

                if ancestors:
                    search_concept = f"{name} {ancestors[0]}"
                else:
                    search_concept = name

                logger.info(f"OpenAlex concept: {name}")

                return {
                    "title": search_concept,
                    "source": "openalex_concept",
                    "concept_id": concept.get('id', ''),
                    "name": name,
                    "level": concept.get('level', 0),
                    "type": "research_concept"
                }

        except Exception as e:
            logger.error(f"OpenAlex concept error: {e}")

        # Fallback
        return self.llm_generate_academic_concept()

    # ========================================================================
    # Semantic Scholar Strategies
    # ========================================================================

    def semantic_scholar_search_paper(self) -> Dict:
        """从Semantic Scholar搜索论文"""
        try:
            # Random academic topics
            topics = [
                "machine learning", "quantum computing", "climate change",
                "cancer research", "neural networks", "gene editing",
                "economic inequality", "social networks", "dark matter",
                "renewable energy", "mental health", "urban planning",
                "epigenetics", "cryptocurrency", "robotics"
            ]

            topic = random.choice(topics)
            papers = self.semantic_scholar_client.search_papers(topic, limit=10)

            if papers:
                paper = random.choice(papers)
                title = paper.get('title', '')
                fields = paper.get('fieldsOfStudy', [])

                if fields:
                    search_concept = f"{title} {fields[0]}"
                else:
                    search_concept = title

                logger.info(f"Semantic Scholar: {title[:60]}...")

                return {
                    "title": search_concept,
                    "source": "semantic_scholar_paper",
                    "paper_id": paper.get('paperId', ''),
                    "year": paper.get('year'),
                    "citations": paper.get('citationCount', 0),
                    "type": "academic_paper"
                }

        except Exception as e:
            logger.error(f"Semantic Scholar error: {e}")

        # Fallback
        return self.llm_generate_academic_concept()

    def semantic_scholar_author(self) -> Dict:
        """从Semantic Scholar获取学者"""
        try:
            # Search for famous academics
            scholars = [
                "Geoffrey Hinton", "Yann LeCun", "Yoshua Bengio",
                "Andrew Ng", "Fei-Fei Li", "Michael Jordan",
                "Judea Pearl", "Bernhard Schölkopf", "Stuart Russell",
                "Peter Norvig"
            ]

            scholar = random.choice(scholars)
            authors = self.semantic_scholar_client.search_authors(scholar, limit=5)

            if authors:
                author = authors[0]
                name = author.get('name', '')

                search_concept = f"{name} research"

                logger.info(f"Semantic Scholar author: {name}")

                return {
                    "title": search_concept,
                    "source": "semantic_scholar_author",
                    "author_id": author.get('authorId', ''),
                    "name": name,
                    "paper_count": author.get('paperCount', 0),
                    "type": "scholar"
                }

        except Exception as e:
            logger.error(f"Semantic Scholar author error: {e}")

        # Fallback
        return self.famous_scholar_pool()

    # ========================================================================
    # ArXiv Strategy
    # ========================================================================

    def arxiv_random_paper(self) -> Dict:
        """从arXiv随机获取预印本"""
        try:
            # Random arXiv category
            categories = ['cs.AI', 'cs.LG', 'cs.CR', 'quant-ph', 'hep-ph',
                         'astro-ph', 'math-ph', 'cond-mat', 'stat.ML', 'q-bio']

            category = random.choice(categories)
            paper = self.arxiv_client.get_random_paper(category=category)

            if paper:
                title = paper.get('title', '')
                cats = paper.get('categories', [])

                if cats:
                    search_concept = f"{title} {cats[0]}"
                else:
                    search_concept = title

                logger.info(f"arXiv paper: {title[:60]}...")

                return {
                    "title": search_concept,
                    "source": "arxiv_paper",
                    "arxiv_id": paper.get('id', ''),
                    "categories": paper.get('categories', []),
                    "type": "preprint"
                }

        except Exception as e:
            logger.error(f"arXiv error: {e}")

        # Fallback
        return self.llm_generate_academic_concept()

    # ========================================================================
    # PubMed Strategy
    # ========================================================================

    def pubmed_random_article(self) -> Dict:
        """从PubMed随机获取生物医学文献"""
        try:
            article = self.pubmed_client.get_random_article()

            if article:
                title = article.get('title', '')
                journal = article.get('journal', '')

                if journal:
                    search_concept = f"{title} {journal}"
                else:
                    search_concept = title

                logger.info(f"PubMed article: {title[:60]}...")

                return {
                    "title": search_concept,
                    "source": "pubmed_article",
                    "pmid": article.get('pmid', ''),
                    "journal": journal,
                    "type": "academic_paper"
                }

        except Exception as e:
            logger.error(f"PubMed error: {e}")

        # Fallback
        return self.llm_generate_academic_concept()

    # ========================================================================
    # Crossref Strategy
    # ========================================================================

    def crossref_random_work(self) -> Dict:
        """从Crossref随机获取学术著作"""
        try:
            work = self.crossref_client.random_work()

            if work:
                title = work.get('title', '')
                venue = work.get('container_title', '')

                if venue:
                    search_concept = f"{title} {venue}"
                else:
                    search_concept = title

                logger.info(f"Crossref work: {title[:60]}...")

                return {
                    "title": search_concept,
                    "source": "crossref_work",
                    "doi": work.get('doi', ''),
                    "type": work.get('type', ''),
                    "type_field": "academic_work"
                }

        except Exception as e:
            logger.error(f"Crossref error: {e}")

        # Fallback
        return self.llm_generate_academic_concept()

    # ========================================================================
    # ROR Strategy
    # ========================================================================

    def ror_random_organization(self) -> Dict:
        """从ROR随机获取研究机构"""
        try:
            org = self.ror_client.get_random_organization()

            if org:
                name = org.get('name', '')
                country = org.get('country', {}).get('country_code', '')

                search_concept = f"{name} research"

                logger.info(f"ROR organization: {name}")

                return {
                    "title": search_concept,
                    "source": "ror_organization",
                    "ror_id": org.get('id', ''),
                    "name": name,
                    "country": country,
                    "type": "institution"
                }

        except Exception as e:
            logger.error(f"ROR error: {e}")

        # Fallback
        return self.llm_generate_academic_concept()

    # ========================================================================
    # Basic Strategies
    # ========================================================================

    def llm_generate_academic_concept(self) -> Dict:
        """使用LLM生成多样化学术概念"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        prompt = """Generate ONE random academic or scholarly concept.

CRITICAL DIVERSITY REQUIREMENTS:
- Mix ALL ACADEMIC FIELDS equally:
  * Natural Sciences: Physics, Chemistry, Biology, Earth Sciences
  * Life Sciences: Medicine, Biomedical, Health Sciences
  * Formal Sciences: Mathematics, Computer Science, Statistics
  * Engineering: All engineering disciplines
  * Social Sciences: Economics, Psychology, Sociology, Political Science
  * Humanities: Philosophy, History, Literature, Languages

- Mix TYPES OF CONCEPTS equally:
  * Research topics: Climate change, machine learning, cancer immunotherapy
  * Methodologies: Longitudinal study, meta-analysis, experimental design
  * Theories: Game theory, string theory, social learning theory
  * Concepts: H-index, impact factor, peer review, citation analysis
  * Academic roles: Tenure track, postdoc, principal investigator
  * Publication venues: Journal, conference, arXiv, working paper
  * Metrics: Altmetrics, Eigenfactor, SJR, CiteScore

- Mix ACADEMIC LEVELS:
  * Undergraduate concepts
  * Graduate research topics
  * Postdoctoral research
  * Faculty research areas
  * Interdisciplinary topics

AVOID overused examples.

DIVERSE Examples:
- "bibliometric co-citation analysis"
- "grounded theory methodology"
- "structural equation modeling in social sciences"
- "double-blind peer review process"
- "h-index research impact measurement"
- "systematic literature review methodology"
- "academic journal rejection rates"
- "research reproducibility crisis"
- "open access publishing models"
- "research grant proposal writing"
- "faculty tenure evaluation criteria"
- "graduate student mentorship"
- "interdisciplinary research collaboration"
- "academic citation cartels"
- "journal impact factor criticism"

Format: Return ONLY the academic concept name (2-5 words), nothing else.

Now generate ONE diverse academic concept:"""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}])
            concept = response.strip()

            # Clean up
            for prefix in ["The ", "A ", "An "]:
                if concept.startswith(prefix):
                    concept = concept[len(prefix):]
            concept = concept.strip('"\'..')

            if len(concept) > 100:
                concept = concept[:100]

            logger.info(f"LLM generated academic concept: {concept}")

            return {
                "title": concept,
                "source": "llm_academic_concept",
                "type": "academic_concept"
            }

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            # Fallback to pools
            all_disciplines = self.expanded_pools.get_all_disciplines()
            topics = self.expanded_pools.KEYWORD_COMPONENTS['topics']
            concept = f"{random.choice(all_disciplines)} {random.choice(topics)}"
            return {
                "title": concept,
                "source": "llm_academic_concept",
                "type": "academic_concept"
            }

    def wikipedia_random_from_category(self) -> Dict:
        """从学术相关分类中随机选择页面"""
        category = random.choice(self.ACADEMIC_CATEGORIES)

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
                    "source": "wikipedia_academic_category",
                    "category": category,
                    "type": "academic_topic"
                }

        except Exception as e:
            logger.error(f"Wikipedia category error: {e}")

        # Fallback
        return self.llm_generate_academic_concept()

    def random_academic_keyword_search(self) -> Dict:
        """使用扩展池子生成多样化学术关键词组合"""
        queries = self.expanded_pools.generate_search_queries()
        search_term = random.choice(queries)

        logger.info(f"Academic keyword search: {search_term}")

        return {
            "title": search_term,
            "source": "random_academic_keyword",
            "type": "academic_concept"
        }

    # ========================================================================
    # Entity-Based Strategies
    # ========================================================================

    def famous_scholar_pool(self) -> Dict:
        """从著名学者池中随机选择"""
        try:
            all_scholars = []
            for scholar_list in self.expanded_pools.FAMOUS_ACADEMICS.values():
                all_scholars.extend(scholar_list)

            scholar = random.choice(all_scholars)

            # Generate search concept
            topics = self.expanded_pools.KEYWORD_COMPONENTS['topics']
            concept = f"{scholar} {random.choice(topics)}"

            logger.info(f"Famous scholar: {scholar}")

            return {
                "title": concept,
                "source": "famous_scholar",
                "scholar": scholar,
                "type": "scholar"
            }

        except Exception as e:
            logger.error(f"Famous scholar pool error: {e}")

        # Fallback
        return self.llm_generate_academic_concept()

    def academic_venue_pool(self) -> Dict:
        """从学术发表场所池中随机选择"""
        try:
            # Combine all venues
            venues = []

            # Journals (some famous ones)
            journals = [
                "Nature", "Science", "Cell", "The Lancet", "NEJM",
                "Physical Review Letters", "Journal of the ACM", "Econometrica",
                "Psychological Review", "American Sociological Review"
            ]
            venues.extend(journals)

            # Conferences
            conferences = [
                "NeurIPS", "ICML", "ACL", "CVPR", "ICCV",
                "AAAI", "IJCAI", "SIGGRAPH", "SIGMOD", "CHI"
            ]
            venues.extend(conferences)

            venue = random.choice(venues)

            # Generate search concept
            topics = self.expanded_pools.KEYWORD_COMPONENTS['topics']
            concept = f"{venue} {random.choice(topics)}"

            logger.info(f"Academic venue: {venue}")

            return {
                "title": concept,
                "source": "academic_venue",
                "venue": venue,
                "type": "publication_venue"
            }

        except Exception as e:
            logger.error(f"Academic venue pool error: {e}")

        # Fallback
        return self.llm_generate_academic_concept()


# ============================================================================
# Main Pipeline
# ============================================================================
