"""
Search Tools for Deep Research
Implements web search, URL crawling, and content extraction functionality
"""

import requests
import os
import json
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Any
from loguru import logger

# PDF: pypdf is the maintained successor of PyPDF2 (renamed in 2022).
try:
    from pypdf import PdfReader
except ImportError:  # fallback to deprecated PyPDF2 if pypdf not installed yet
    from PyPDF2 import PdfReader  # type: ignore

import io
import html2text
import time
import re
from datetime import datetime, timezone, timedelta

# Trafilatura: optional middle-layer for boilerplate-free main-content extraction.
# Falls back to html2text if not installed. Install via `pip install trafilatura`.
try:
    import trafilatura
    _TRAFILATURA_AVAILABLE = True
except ImportError:
    trafilatura = None  # type: ignore
    _TRAFILATURA_AVAILABLE = False
from openai import OpenAI
import wikipediaapi
from .subprocess_interpreter import SubprocessInterpreter

SEARCH_TOOL_SCHEMA = {
    "name": "search",
    "description": "Search the web for information using Google search",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["query"],
    }
}

SEARCH_WIKI_TOOL_SCHEMA = {
    "name": "search_wiki",
    "description": "Search Wikipedia for information about the given entities. Useful when you want to get detailed relevant information about entities.",
    "parameters": {
        "type": "object",
        "properties": {
            "entities": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["entities"],
    }
}

VISIT_URLS_TOOL_SCHEMA = {
    "name": "visit_urls",
    "description": "Visit the webpage content of the given URLs and extract the relevant information based on the query.",
    "parameters": {
        "type": "object",
        "properties": {
            "urls": {"type": "array", "items": {"type": "string"}},
            "query": {"type": "string"},
        },
        "required": ["urls", "query"],
    }
}

EXECUTE_CODE_TOOL_SCHEMA = {
    "name": "execute_code",
    "description": "Execute the given Python code snippets.",
    "parameters": {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
        },
        "required": ["code"],
    }
}

ALL_TOOL_SCHEMAS = [
    SEARCH_TOOL_SCHEMA,
    SEARCH_WIKI_TOOL_SCHEMA,
    VISIT_URLS_TOOL_SCHEMA,
    EXECUTE_CODE_TOOL_SCHEMA,
]

# Configuration constants
TRUNCATE_LENGTH = 60000
WIKI_TRUNCATE_LENGTH = 10000
VISIT_URLS_RAW_RETURN_MAX_TOKENS = int(os.getenv("VISIT_URLS_RAW_RETURN_MAX_TOKENS", "4000"))
EXTRACTOR_PROMPT_TEMPLATE = """
The following content is a webpage content:

{webpage_content}

Now, extract the relevant information for the given query, generating a paragraph as a report.
If the webpage content is not related to the query, please return "No relevant information found", along with the short summary and reasoning.

The query is: {query}
"""


def _env_flag(name: str, default: str = "0") -> bool:
    val = (os.getenv(name, default) or "").strip().lower()
    return val in {"1", "true", "yes", "y", "on"}


_REQUESTS_SESSION: Optional[requests.Session] = None

# Jina Reader circuit breaker: when r.jina.ai is unreachable, fail fast to
# html2text instead of blocking 60s per call. Resets only on process restart.
_JINA_FAILURE_COUNT = 0
_JINA_DISABLED = False

# Wikipedia circuit breaker: when en.wikipedia.org is unreachable, fail fast
# instead of retrying 10x with 1s sleeps (8+ minutes per call).
_WIKI_FAILURE_COUNT = 0
_WIKI_DISABLED = False


def _get_requests_session() -> requests.Session:
    """
    Shared requests session for Serper/Jina/crawl.

    Defaults to `trust_env=False` so broken proxy env vars won't break network calls.
    Set `LLM_TRUST_ENV=1` to opt back in.
    """
    global _REQUESTS_SESSION
    if _REQUESTS_SESSION is None:
        sess = requests.Session()
        sess.trust_env = _env_flag("LLM_TRUST_ENV", default="0")
        _REQUESTS_SESSION = sess
    return _REQUESTS_SESSION


def _build_openai_client(api_key: str, base_url: str) -> OpenAI:
    """
    OpenAI-compatible client used by `call_llm` for extraction.

    Defaults to `trust_env=False` so broken proxy env vars won't break LLM calls.
    Set `LLM_TRUST_ENV=1` to opt back in.
    """
    try:
        import httpx  # type: ignore

        trust_env = _env_flag("LLM_TRUST_ENV", default="0")
        http_client = httpx.Client(timeout=httpx.Timeout(60.0), trust_env=trust_env)
        return OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
    except Exception:
        return OpenAI(api_key=api_key, base_url=base_url)


def _estimate_token_count(text: str) -> int:
    """Rough token estimate without requiring a tokenizer dependency."""
    if not text:
        return 0
    return max(1, len(text) // 4)


# P1-1B: Query-aware paragraph-level extraction.
# Splits crawled content into paragraphs, scores each by keyword overlap with
# the query, and returns the top-K most relevant paragraphs. This avoids the
# slow + expensive LLM extractor call for medium-length pages while preserving
# exact text (verbatim quotes) for evidence anchoring.
PARAGRAPH_EXTRACT_TOP_K = int(os.getenv("PARAGRAPH_EXTRACT_TOP_K", "12"))
PARAGRAPH_EXTRACT_MAX_CHARS = int(os.getenv("PARAGRAPH_EXTRACT_MAX_CHARS", "8000"))
PARAGRAPH_MIN_LENGTH = int(os.getenv("PARAGRAPH_MIN_LENGTH", "40"))


def _extract_relevant_paragraphs(content: str, query: str) -> str:
    """Extract the most query-relevant paragraphs from crawled content.

    Scoring: each paragraph gets +1 for every query keyword it contains
    (case-insensitive, word-boundary match). Paragraphs are sorted by score
    descending (stable: ties keep original order), then the top-K are joined.
    Output is capped at PARAGRAPH_EXTRACT_MAX_CHARS.
    """
    if not content or not query:
        return content[:PARAGRAPH_EXTRACT_MAX_CHARS]

    # Split on double newlines (paragraph boundaries). For pages that use
    # single newlines (e.g. html2text output), also split on runs of 2+ spaces.
    import re
    paragraphs = re.split(r"\n\s*\n", content)
    # Further split very long paragraphs at sentence boundaries
    refined: list[str] = []
    for p in paragraphs:
        p = p.strip()
        if len(p) < PARAGRAPH_MIN_LENGTH:
            continue
        if len(p) > 1500:
            # Split at sentence boundaries within the paragraph
            sentences = re.split(r'(?<=[.!?])\s+', p)
            buf = ""
            for s in sentences:
                if len(buf) + len(s) > 1500:
                    if buf:
                        refined.append(buf.strip())
                    buf = s
                else:
                    buf = buf + " " + s if buf else s
            if buf:
                refined.append(buf.strip())
        else:
            refined.append(p)

    if not refined:
        return content[:PARAGRAPH_EXTRACT_MAX_CHARS]

    # Extract keywords from the query (lowercase, strip punctuation)
    query_words = set(re.findall(r"[a-zA-Z0-9]{2,}", query.lower()))
    # Remove generic stop words
    stop_words = {"the", "a", "an", "of", "in", "to", "for", "and", "or", "is",
                   "was", "are", "were", "be", "been", "that", "this", "with",
                   "from", "by", "on", "at", "as", "it", "its", "has", "have",
                   "had", "not", "but", "which", "what", "who", "when", "where",
                   "how", "why", "all", "any", "some", "no", "yes"}
    keywords = {w for w in query_words if w not in stop_words and len(w) >= 3}
    if not keywords:
        keywords = query_words

    # Score each paragraph
    scored: list[tuple[int, int, str]] = []  # (score, original_index, text)
    for idx, p in enumerate(refined):
        p_lower = p.lower()
        score = sum(1 for kw in keywords if kw in p_lower)
        scored.append((score, idx, p))

    # Sort: highest score first, ties broken by original order
    scored.sort(key=lambda x: (-x[0], x[1]))

    # Take top-K
    selected = [s[2] for s in scored[:PARAGRAPH_EXTRACT_TOP_K]]
    result = "\n\n".join(selected)

    if len(result) > PARAGRAPH_EXTRACT_MAX_CHARS:
        result = result[:PARAGRAPH_EXTRACT_MAX_CHARS] + "...[truncated]"
    return result


def call_llm(
    prompt: str,
    max_tries: int = 10,
    model_name: str = "GLM-5.2",
):
    """
    Call LLM API for content extraction.

    Uses DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL if set, otherwise falls back to
    OPENAI_API_KEY / OPENAI_BASE_URL.

    Args:
        prompt: Prompt text
        max_tries: Maximum retry attempts
        model_name: Model name (default: GLM-5.2)

    Returns:
        Model response text
    """
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL") or os.getenv("OPENAI_BASE_URL", "https://preview.llm.tenyunc.com/v1")
    if not api_key:
        raise ValueError("Neither DEEPSEEK_API_KEY nor OPENAI_API_KEY is set in environment variables")

    messages = [
        {"role": "system", "content": "You are a helpful assistant. Answer directly. Do not reason."},
        {"role": "user", "content": prompt},
    ]

    for attempt in range(max_tries):
        try:
            client = _build_openai_client(api_key=api_key, base_url=base_url)
            chat_response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=2000,
            )
            content = chat_response.choices[0].message.content
            if content:
                return content
            # GLM-5.2 may put the answer in reasoning_content when content is empty
            reasoning = getattr(chat_response.choices[0].message, "reasoning_content", None) or ""
            if reasoning:
                return reasoning
            logger.warning(f"Empty content and reasoning on attempt {attempt}")
        except Exception as e:
            logger.warning(f"Error calling LLM API: {e}")
            if attempt < max_tries - 1:
                time.sleep(5)
            continue
    
    logger.error("All attempts failed to call LLM API")
    return "Failed to call LLM API"


# ---------------------------------------------------------------------------
# HTTP disk cache (M1 replay) — record/replay of Serper/crawl/wiki responses.
# Off by default; see disk_cache.py for modes. Never breaks a call on error.
# ---------------------------------------------------------------------------

def _http_cache_get(kind: str, *parts: str):
    """Return (key, text) where key is None when the cache is disabled."""
    try:
        import disk_cache as dc
        if not dc.cache_enabled():
            return None, None
        key = dc.make_http_key(kind, *parts)
        hit = dc.get_entry("http", key)
        if hit is not None and "text" in hit:
            return key, hit["text"]
        dc.miss_or_raise("http", key, f"{kind}: {parts[0][:120]!r}")
        return key, None
    except Exception as e:
        if type(e).__name__ == "DiskCacheMissError":
            raise
        return None, None


def _http_cache_put(kind: str, key, parts, text: str) -> None:
    if key is None:
        return
    try:
        import disk_cache as dc
        dc.put_entry("http", key, {"text": text, "kind": kind, "parts": list(parts)})
    except Exception:
        pass


def _call_serper_api(query: str) -> str:
    """
    Call Serper API for Google search.
    
    Args:
        query: Search query
        
    Returns:
        Search results as JSON string
    """
    cache_key, cached = _http_cache_get("serper", query)
    if cached is not None:
        return cached

    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        raise ValueError("SERPER_API_KEY is not set in environment variables")

    url = "https://google.serper.dev/search"

    payload = json.dumps({
        "q": query
    })
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json'
    }

    session = _get_requests_session()
    response = session.post(url, headers=headers, data=payload, timeout=30)
    if not response.ok:
        raise RuntimeError(
            f"Serper API {response.status_code}: {response.text[:500]} | query={query[:200]!r}"
        )
    _http_cache_put("serper", cache_key, (query,), response.text)
    return response.text


# ── Search result post-processing (accuracy core / 数据源管控) ───────────────
# Data-source governance for the agent: tiered credibility weighting,
# timeliness constraints, and cross-domain duplicate (repost) merging.
# All three stages are pure/deterministic (no LLM, no network) so they stay
# cheap and reproducible. Each is env-gated so prior behavior is restorable.
#
# Design goals (accuracy core):
#   1. 数据源分级可信权重: rerank by a 5-tier credibility model
#      (official docs / academic > authoritative media / encyclopedia >
#       vertical forums > generic web > UGC / self-media). Credibility is a
#      reranking feature (not a hard drop) so recall is preserved.
#   2. 时效性强制约束: for time-sensitive queries (events, policy, stock
#      prices, tech versions) drop results with a parseable publish date older
#      than the freshness window; relax for general-knowledge queries. In a
#      2026 environment this filters expired 2023/2024 content by default.
#   3. 去重与同源合并: beyond per-domain dedup, merge cross-domain reposts
#      (near-identical title+snippet on a different host) keeping the
#      higher-credibility original so mirrors don't dilute context.

# ── Tiered credibility model (数据源分级可信权重) ──────────────────────────────
# Higher tier = more trustworthy for factual research. Tier 2 (generic web)
# is the default and has no explicit domain list.
_CREDIBILITY_TIERS = {
    5: [
        # Official documentation
        "docs.python.org", "developer.mozilla.org", "developers.google.com",
        "docs.microsoft.com", "learn.microsoft.com", "kubernetes.io",
        "docs.docker.com", "react.dev", "vuejs.org", "angular.io",
        "nodejs.org", "go.dev", "rust-lang.org", "docs.github.com",
        "graphql.org", "kotlinlang.org", "swift.org", "php.net",
        "ruby-doc.org", "elixir-lang.org", "docs.aws.amazon.com",
        "cloud.google.com", "typescriptlang.org",
        # Academic / primary research
        "arxiv.org", "doi.org", "scholar.google.com", "pubmed.ncbi.nlm.nih.gov",
        "pmc.ncbi.nlm.nih.gov", "nature.com", "science.org", "acm.org",
        "ieeexplore.ieee.org", "jstor.org", "springer.com", "sciencedirect.com",
        "biorxiv.org", "medrxiv.org", "aclanthology.org", "openreview.net",
        "semanticscholar.org",
    ],
    4: [
        # Encyclopedia / official institutions (.gov/.edu handled by TLD rule)
        "wikipedia.org", "britannica.com", "loc.gov", "un.org", "who.int",
        "worldbank.org", "imf.org", "oecd.org", "nasa.gov",
        # Authoritative legacy media / wires
        "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "nytimes.com",
        "washingtonpost.com", "theguardian.com", "guardian.co.uk",
        "economist.com", "ft.com", "wsj.com", "bloomberg.com", "npr.org",
        "aljazeera.com", "scientificamerican.com",
        # Official statistics / registries
        "census.gov", "bls.gov", "stats.oecd.org", "data.worldbank.org",
    ],
    3: [
        # Vertical professional sites & curated databases
        "stackoverflow.com", "stackexchange.com", "mathoverflow.net",
        "serverfault.com", "superuser.com", "github.com",
        "imdb.com", "themoviedb.org", "musicbrainz.org", "discogs.com",
        "goodreads.com", "letterboxd.com", "rateyourmusic.com",
        "baseball-reference.com", "basketball-reference.com", "fbref.com",
        "pro-football-reference.com", "espn.com", "worldathletics.org",
        "fifa.com", "uefa.com", "mlb.com", "nba.com", "nfl.com",
        "crunchbase.com", "opencorporates.com", "icc-cricket.com",
    ],
    2: [],  # generic web — default tier
    1: [
        # UGC / self-media / content farms / press-release aggregators
        "reddit.com", "quora.com", "medium.com", "substack.com",
        "blogspot.com", "wordpress.com", "tumblr.com", "weebly.com",
        "wattpad.com", "wikihow.com", "answers.com", "prnewswire.com",
        "prweb.com", "businesswire.com", "globenewswire.com", "wikiwand.com",
        "fandom.com", "wikia.com", "buzzfeed.com", "dailymail.co.uk",
    ],
}

# Domains that bypass per-domain dedup (they host many relevant sub-pages).
_DEDUP_WHITELIST = {"wikipedia.org", "britannica.com"}


def _netloc_labels(url: str) -> List[str]:
    """Return lowercase domain labels (minus leading www) for a URL."""
    try:
        netloc = urlparse(url).netloc.lower().split(":")[0]
    except Exception:
        return []
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc.split(".") if netloc else []


def _domain_credibility(url: str) -> int:
    """Tiered data-source credibility (1=UGC/self-media .. 5=official/academic).

    Tier 2 (generic web) is the default. Official-institution TLDs/labels
    (.gov/.edu/.mil, incl. second-level like .gov.uk) map to tier 4, except
    SEC EDGAR (sec.gov) which is upgraded to tier 5 (official financial-report
    regulator). Official investor-relations subdomains (ir.*, investor.*,
    investors.*) also map to tier 5 (official financial reports / corporate
    official sites), so they receive the maximum source weight.
    """
    labels = _netloc_labels(url)
    if not labels:
        return 2
    # Official investor-relations / financial-report subdomain → tier 5.
    # Requires >=3 labels so bare `ir.com`-style hosts are not misclassified.
    if len(labels) >= 3 and labels[0] in _OFFICIAL_FINANCIAL_PREFIXES:
        return 5
    if any(lbl in {"gov", "edu", "mil"} for lbl in labels):
        # SEC EDGAR (sec.gov) → official financial-report regulator → tier 5.
        if ".".join(labels[-2:]) == "sec.gov":
            return 5
        return 4
    candidates = {".".join(labels)}
    if len(labels) >= 2:
        candidates.add(".".join(labels[-2:]))
    if len(labels) >= 3:
        candidates.add(".".join(labels[-3:]))
    # Explicit official financial-report archive domains → tier 5.
    for dom in _OFFICIAL_FINANCIAL_DOMAINS:
        if dom in candidates:
            return 5
    for tier in (5, 4, 3, 1):
        for dom in _CREDIBILITY_TIERS[tier]:
            if dom in candidates:
                return tier
    return 2


def _domain_authority(url: str) -> int:
    """Backward-compatible alias (was a 1..3 score; now the 1..5 credibility tier)."""
    return _domain_credibility(url)


# Source-weight mapping (matches _CREDIBILITY_TIERS):
#   tier 5 → 10  official docs / academic / official financial reports
#   tier 4 → 8   encyclopedia / official institutions / authoritative media
#   tier 3 → 5   vertical professional
#   tier 2 → 3   generic web (default)
#   tier 1 → 2   UGC / self-media / press-release
# Rule: "2 high-weight (weight=10) sources agree → fact confirmed, stop".
_SOURCE_WEIGHTS = {5: 10, 4: 8, 3: 5, 2: 3, 1: 2}

# Subdomain prefixes signaling official investor relations / financial reports.
_OFFICIAL_FINANCIAL_PREFIXES = frozenset({
    "ir", "investor", "investors", "investorrelations", "finance",
})

# Domains that publish official financial reports (regulators / archives).
_OFFICIAL_FINANCIAL_DOMAINS = frozenset({
    "sec.gov",          # US SEC EDGAR — official filings
    "annualreports.com",  # official annual-report archive
})


def _source_weight(url: str) -> int:
    """Source credibility weight (10=official/academic/financial-report ..
    2=UGC/self-media). Mapping matches ``_CREDIBILITY_TIERS``:
      tier 5 → 10  (official docs / academic / official financial reports)
      tier 4 → 8   (encyclopedia / official institutions / authoritative media)
      tier 3 → 5   (vertical professional)
      tier 2 → 3   (generic web, default)
      tier 1 → 2   (UGC / self-media / press-release)
    """
    return _SOURCE_WEIGHTS.get(_domain_credibility(url), 3)


def is_authoritative_source(url: str) -> bool:
    """Return True if ``url`` belongs to a tier>=4 authoritative source.

    Tier 4 = encyclopedia / official institutions (.gov/.edu/.mil) / authoritative
    legacy media (reuters, bbc, nytimes, ...); tier 5 = official docs / academic /
    official financial reports (incl. ir.* / investor.* subdomains and sec.gov).
    This is a pure domain-table lookup independent of ``SRC_CREDIBILITY_ENABLED``
    (which only gates search-result *annotation*), so it is safe to reuse for
    early-stop / consensus decisions on executor evidence URLs.
    """
    try:
        return _domain_credibility(url or "") >= 4
    except Exception:
        return False


def authoritative_domains_in(urls) -> List[str]:
    """Return the set of distinct authoritative (weight>=8) base-domains among ``urls``.

    Used to count *independent* authoritative sources: two pieces of evidence
    from the same domain (e.g. two reuters.com pages) count once. ``urls`` is any
    iterable of URL strings; non-http strings are skipped.
    """
    seen: set = set()
    for u in urls or []:
        try:
            labels = _netloc_labels(u)
        except Exception:
            labels = []
        if not labels:
            continue
        if not is_authoritative_source(u):
            continue
        # base domain = last 2 labels (reuters.com, bbc.co.uk handled by table hit)
        base = ".".join(labels[-2:]) if len(labels) >= 2 else labels[0]
        seen.add(base)
    return sorted(seen)


def high_weight_sources_in(urls, min_weight: int = 10) -> List[str]:
    """Return distinct base-domains whose source weight >= ``min_weight``.

    Default ``min_weight=10`` selects only official docs / academic / official
    financial reports (tier 5). Used for the "2 high-weight sources agree →
    fact confirmed" early-stop rule: two such sources from *different* base
    domains corroborating one candidate suffice to terminate search without
    further rounds. Same-domain dedup applies (two ir.apple.com pages count once).
    """
    seen: set = set()
    for u in urls or []:
        try:
            if _source_weight(u) < min_weight:
                continue
            labels = _netloc_labels(u)
        except Exception:
            labels = []
        if not labels:
            continue
        base = ".".join(labels[-2:]) if len(labels) >= 2 else labels[0]
        seen.add(base)
    return sorted(seen)


# ── Timeliness (时效性强制约束) ───────────────────────────────────────────────
_REL_DATE_RE = re.compile(
    r"(\d+)\s*(second|minute|hour|day|week|month|year)s?\s*ago", re.IGNORECASE
)
_ABS_DATE_FORMATS = (
    "%Y-%m-%d", "%Y/%m/%d", "%b %d, %Y", "%B %d, %Y",
    "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d-%B-%Y",
)
# Query-type heuristics (rule-based; no LLM cost).
_TIME_SENSITIVE_RE = re.compile(
    r"\b(20\d{2}|latest|newest|recent|current|today|now|update(d)?|version|"
    r"release(d)?|price|stock|quote|score|result|champion|winner|policy|law|"
    r"gdp|inflation|election|announcement)\b"
    r"|新闻|最新|当前|现在|今天|近期|股价|比分|成绩|冠军|政策|版本|发布",
    re.IGNORECASE,
)
_GENERAL_KNOWLEDGE_RE = re.compile(
    r"\b(what is|who is|who invented|history of|definition of|biography of|"
    r"meaning of|introduction to)\b"
    r"|原理|公式|历史|定义|发明|生平|简介|是什么|是谁",
    re.IGNORECASE,
)


def _is_time_sensitive_query(query: str) -> bool:
    """Cheap rule-based classifier: is this a freshness-sensitive query?"""
    q = (query or "").lower()
    if not q:
        return False
    if _GENERAL_KNOWLEDGE_RE.search(q):
        return False
    if _TIME_SENSITIVE_RE.search(q):
        return True
    return False


def _parse_serper_date(date_str: str, now_dt: datetime) -> Optional[datetime]:
    """Parse a Serper `date` field into a UTC datetime, or None.

    Handles relative ("3 days ago") and common absolute formats. Falls back to
    extracting the first 19xx/20xx year in the string.
    """
    if not date_str:
        return None
    s = date_str.strip()
    if not s:
        return None
    m = _REL_DATE_RE.match(s)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        if unit == "second": return now_dt - timedelta(seconds=n)
        if unit == "minute": return now_dt - timedelta(minutes=n)
        if unit == "hour":   return now_dt - timedelta(hours=n)
        if unit == "day":    return now_dt - timedelta(days=n)
        if unit == "week":   return now_dt - timedelta(weeks=n)
        if unit == "month":  return now_dt - timedelta(days=30 * n)
        if unit == "year":   return now_dt - timedelta(days=365 * n)
    for fmt in _ABS_DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    ym = re.search(r"\b(19|20)\d{2}\b", s)
    if ym:
        try:
            return datetime(int(ym.group(0)), 1, 1, tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _freshness_flag(age_days: int, max_age_days: int) -> str:
    """Categorize a result's age for reranking/filtering."""
    if age_days <= 30:
        return "fresh"
    if age_days <= max_age_days:
        return "recent"
    return "stale"


_FRESHNESS_SCORE = {"fresh": 3, "recent": 2, "stale": 0, "unknown": 1, "stale_kept": 1}

# ── Cross-domain repost merging (去重与同源合并) ──────────────────────────────
_STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or", "with",
    "is", "are", "was", "were", "by", "from", "as", "that", "this", "it",
}


def _normalize_text_tokens(text: str) -> set:
    """Lowercase, strip punctuation, drop stopwords → token set for Jaccard."""
    if not text:
        return set()
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return {t for t in text.split() if t and t not in _STOPWORDS and len(t) > 1}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def _postprocess_serper_results(raw_json: str, query: str) -> str:
    """Post-process Serper results for data-source accuracy.

    Pipeline (all env-gated, failure-safe — any parse error returns the raw
    JSON unchanged so search never breaks on a malformed result):
      1. Per-domain dedup (encyclopedias + query-mentioned domains whitelisted).
      2. Annotate each result with credibility tier + freshness.
      3. Cross-domain repost merge (near-identical title+snippet on a different
         host → keep the higher-credibility original; log the dropped mirror).
      4. Timeliness filter for time-sensitive queries (drop clearly-stale
         results; relax for general knowledge; never drop below a floor of 3).
      5. Credibility-weighted rerank (credibility tier primary, freshness
         secondary, original Serper position tertiary — stable sort).
      6. Truncate to top-8.

    Env switches (default ON):
      SRC_CREDIBILITY_ENABLED, SRC_FRESHNESS_ENABLED,
      SRC_CROSSDOMAIN_DEDUP_ENABLED, SRC_FRESHNESS_MAX_AGE_DAYS (default 730).

    Args:
        raw_json: Raw Serper API response (JSON string).
        query: The search query (used for dedup whitelist + query-type).

    Returns:
        JSON string with processed (and annotated) organic results.
    """
    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return raw_json  # not valid JSON, return as-is

    organic = data.get("organic", [])
    if not organic:
        return raw_json

    credibility_on = _env_flag("SRC_CREDIBILITY_ENABLED", "1")
    freshness_on = _env_flag("SRC_FRESHNESS_ENABLED", "1")
    crossdomain_on = _env_flag("SRC_CROSSDOMAIN_DEDUP_ENABLED", "1")

    now_dt = datetime.now(timezone.utc)
    try:
        max_age_days = int(os.getenv("SRC_FRESHNESS_MAX_AGE_DAYS", "730") or "730")
    except ValueError:
        max_age_days = 730
    query_sensitive = _is_time_sensitive_query(query) if freshness_on else False
    query_lower = (query or "").lower()

    # 1. Per-domain dedup (whitelist encyclopedias + domains named in the query).
    seen_domains = set()
    deduped: List[Dict[str, Any]] = []
    for result in organic:
        link = result.get("link", "")
        labels = _netloc_labels(link)
        domain = ".".join(labels) if labels else link
        is_whitelisted = any(wd in domain for wd in _DEDUP_WHITELIST)
        if not is_whitelisted and labels and labels[0] in query_lower:
            is_whitelisted = True
        if domain in seen_domains and not is_whitelisted:
            continue
        seen_domains.add(domain)
        deduped.append(result)

    # 2. Annotate credibility + freshness (mutates result dicts in place).
    for result in deduped:
        tier = _domain_credibility(result.get("link", "")) if credibility_on else 2
        result["credibility_tier"] = tier
        result["credibility_score"] = tier
        date_str = result.get("date")
        pub_dt = _parse_serper_date(date_str, now_dt) if (freshness_on and date_str) else None
        if pub_dt:
            age_days = max(0, (now_dt - pub_dt).days)
            flag = _freshness_flag(age_days, max_age_days) if query_sensitive else "recent_or_dated"
            result["freshness"] = {"published": pub_dt.strftime("%Y-%m-%d"), "age_days": age_days}
            result["freshness_flag"] = flag
            result["freshness_score"] = _FRESHNESS_SCORE.get(flag, 1) if flag in _FRESHNESS_SCORE else 2
        else:
            result["freshness_flag"] = "unknown"
            result["freshness_score"] = _FRESHNESS_SCORE["unknown"]

    # 3. Cross-domain repost merge (同源合并). O(n^2) but n is small (~10).
    if crossdomain_on and len(deduped) > 1:
        title_tokens = [_normalize_text_tokens(r.get("title", "")) for r in deduped]
        snippet_tokens = [_normalize_text_tokens(r.get("snippet", "")) for r in deduped]
        domains = [".".join(_netloc_labels(r.get("link", ""))) for r in deduped]
        positions = [r.get("position", i) for i, r in enumerate(deduped)]
        dropped = set()
        merged_log: List[Dict[str, Any]] = []
        for i in range(len(deduped)):
            if i in dropped:
                continue
            for j in range(i + 1, len(deduped)):
                if j in dropped:
                    continue
                if domains[i] and domains[i] == domains[j]:
                    continue  # same domain handled in step 1
                if _jaccard(title_tokens[i], title_tokens[j]) >= 0.80 and \
                        _jaccard(snippet_tokens[i], snippet_tokens[j]) >= 0.50:
                    ci, cj = deduped[i]["credibility_tier"], deduped[j]["credibility_tier"]
                    if cj > ci or (cj == ci and positions[j] < positions[i]):
                        keep, drop = j, i
                    else:
                        keep, drop = i, j
                    dropped.add(drop)
                    merged_log.append({
                        "kept_link": deduped[keep].get("link", ""),
                        "dropped_link": deduped[drop].get("link", ""),
                        "dropped_domain": domains[drop],
                        "title_sim": round(_jaccard(title_tokens[i], title_tokens[j]), 2),
                        "snippet_sim": round(_jaccard(snippet_tokens[i], snippet_tokens[j]), 2),
                    })
        if dropped:
            deduped = [r for k, r in enumerate(deduped) if k not in dropped]
            data["dedup_merges"] = merged_log

    # 4. Timeliness filter (时效性强制约束) — time-sensitive queries only.
    if freshness_on and query_sensitive:
        kept = [r for r in deduped if r.get("freshness_flag") != "stale"]
        stale_dropped = [
            {"link": r.get("link", ""),
             "published": r.get("freshness", {}).get("published"),
             "age_days": r.get("freshness", {}).get("age_days")}
            for r in deduped if r.get("freshness_flag") == "stale"
        ]
        # Floor: never over-filter — if fewer than 3 survive, restore the
        # highest-credibility stale results (kept, but flagged) so the agent
        # still has sources to reason over and can see they are dated.
        if len(kept) < 3 and stale_dropped:
            stale_results = sorted(
                [r for r in deduped if r.get("freshness_flag") == "stale"],
                key=lambda r: -int(r.get("credibility_tier", 2)),
            )
            restored = stale_results[: 3 - len(kept)]
            restored_links = {r.get("link") for r in restored}
            for r in restored:
                r["freshness_flag"] = "stale_kept"
                r["freshness_score"] = _FRESHNESS_SCORE["stale_kept"]
            kept.extend(restored)
            stale_dropped = [d for d in stale_dropped if d["link"] not in restored_links]
        deduped = kept
        if stale_dropped:
            data["freshness_dropped"] = stale_dropped

    # 5. Credibility-weighted rerank (stable sort preserves Serper order within
    #    a tier). Credibility tier primary, freshness secondary, position last.
    if credibility_on or freshness_on:
        def _rerank_key(r):
            pos = r.get("position", 0)
            try:
                pos = int(pos)
            except (TypeError, ValueError):
                pos = 0
            return (
                -int(r.get("credibility_tier", 2)),
                -int(r.get("freshness_score", 1)),
                pos,
            )
        deduped.sort(key=_rerank_key)

    # 6. Truncate to top-8 to reduce token consumption.
    data["organic"] = deduped[:8]
    data["source_quality"] = {
        "query_time_sensitive": query_sensitive,
        "freshness_max_age_days": max_age_days if freshness_on else None,
        "credibility_enabled": credibility_on,
        "freshness_enabled": freshness_on,
        "crossdomain_dedup_enabled": crossdomain_on,
    }
    return json.dumps(data, ensure_ascii=False)


def _call_jina_api(url: str) -> str:
    """
    Call Jina API for URL content extraction.
    
    Args:
        url: URL to extract content from
        
    Returns:
        Extracted content as string
    """
    api_key = os.getenv("JINA_API_KEY")
    if not api_key:
        raise ValueError("JINA_API_KEY is not set in environment variables")
    
    api_url = "https://r.jina.ai/" + url
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Return-Format": "text"
    }

    session = _get_requests_session()
    jina_timeout = float(os.getenv("JINA_TIMEOUT_S", "10"))
    response = session.get(api_url, headers=headers, timeout=jina_timeout)
    response.raise_for_status()
    return response.text


def _call_html2text(url: str) -> str:
    """Use html2text to extract content from URL."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        session = _get_requests_session()
        crawl_timeout = float(os.getenv("CRAWL_TIMEOUT_S", "15"))
        response = session.get(url, headers=headers, timeout=crawl_timeout)
        response.raise_for_status()
        text_processor = html2text.HTML2Text()
        text_processor.ignore_links = True
        text_processor.ignore_images = True
        text_processor.ignore_tables = False
        content = text_processor.handle(response.text)
        return content

    except Exception as e:
        return f"Error crawling url: {url}: {str(e)}"


def _call_trafilatura(url: str) -> str:
    """
    Middle-layer extractor: fetch raw HTML then use Trafilatura to extract
    main content (boilerplate-stripped, navigation/ads removed).

    Better than html2text for article-style pages (news, blogs, wikis) because
    it strips chrome/nav/footer and returns only the main text. Pure-Python,
    no API limits. Falls back to html2text if Trafilatura is unavailable or
    returns nothing (e.g. JS-heavy page with no HTML content).
    """
    if not _TRAFILATURA_AVAILABLE:
        return _call_html2text(url)
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        session = _get_requests_session()
        crawl_timeout = float(os.getenv("CRAWL_TIMEOUT_S", "15"))
        response = session.get(url, headers=headers, timeout=crawl_timeout)
        response.raise_for_status()
        # extract: main content text. include_tables keeps tabular data.
        # include_links keeps hyperlink context (important for research).
        extracted = trafilatura.extract(
            response.text,
            include_tables=True,
            include_links=True,
            include_images=False,
            favor_recall=True,  # err on the side of more content for research
        )
        if not extracted or len(extracted.strip()) < 50:
            # empty / useless extraction -> fall back to html2text
            return _call_html2text(url)
        return extracted
    except Exception:
        # any error -> fall back to html2text (never throw)
        return _call_html2text(url)


def _crawl_url(url: str) -> str:
    """Disk-cache wrapper — keyed by (crawler engine, url) since the engine
    changes the returned text. Replay-mode misses raise like network errors."""
    cache_key, cached = _http_cache_get("crawl", os.getenv("CRAWLER_ENGINE", "trafilatura"), url)
    if cached is not None:
        return cached
    result = _crawl_url_uncached(url)
    _http_cache_put("crawl", cache_key, (url,), result)
    return result


def _crawl_url_uncached(url: str) -> str:
    """
    Crawl the webpage content of the given URL.
    
    Args:
        url: URL to crawl
        
    Returns:
        Webpage content as string
    """
    # Check if the given value is a URL
    if not url.startswith("http"):
        return f"The given value is not a URL: {url}. Please check the URL and try again."
    
    global _JINA_FAILURE_COUNT, _JINA_DISABLED

    crawler_engine = os.getenv("CRAWLER_ENGINE", "trafilatura")
    if crawler_engine == "jina" and not _JINA_DISABLED:
        try:
            return _call_jina_api(url)
        except Exception as e:
            _JINA_FAILURE_COUNT += 1
            max_failures = int(os.getenv("JINA_MAX_FAILURES", "2"))
            if _JINA_FAILURE_COUNT >= max_failures:
                _JINA_DISABLED = True
                logger.warning(
                    f"Jina API failed {_JINA_FAILURE_COUNT}x (>= {max_failures}); "
                    f"disabling Jina for this run, using trafilatura/html2text. Last error: {e}"
                )
            else:
                logger.warning(f"Jina API failed, falling back to trafilatura: {e}")
            return _call_trafilatura(url)
    else:
        # Handle PDF files
        if url.endswith(".pdf"):
            try:
                session = _get_requests_session()
                response = session.get(url, timeout=60)
                response.raise_for_status()

                pdf_file = io.BytesIO(response.content)
                reader = PdfReader(pdf_file)
                text_content = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        text_content.append(text)

                return "\n".join(text_content)
            except Exception as e:
                return f"Error crawling PDF URL: {url}: {str(e)}"
        
        else:
            return _call_trafilatura(url)


def _visit_url(url: str, query: str) -> str:
    """
    Crawl the webpage content and extract information based on the query.

    Args:
        url: The URL to visit
        query: The query to extract information from the webpage
        
    Returns:
        Extracted information as string
    """
    content = _crawl_url(url)
    estimated_tokens = _estimate_token_count(content)

    # For shorter pages, return raw content directly so downstream agents can
    # reason over the original text instead of an extra extraction layer.
    if estimated_tokens <= VISIT_URLS_RAW_RETURN_MAX_TOKENS:
        return content

    # P1-1B: For medium-length pages, use query-aware paragraph extraction
    # instead of the slow LLM extractor. This preserves exact text (verbatim
    # quotes) for evidence anchoring and avoids a round-trip LLM call.
    # Threshold: if paragraph extraction yields a reasonable result, use it;
    # only fall through to LLM extraction for very long pages.
    if estimated_tokens <= VISIT_URLS_RAW_RETURN_MAX_TOKENS * 4:
        extracted = _extract_relevant_paragraphs(content, query)
        if extracted and len(extracted) > PARAGRAPH_MIN_LENGTH:
            return extracted

    if len(content) < TRUNCATE_LENGTH:
        try:
            extractor_prompt = EXTRACTOR_PROMPT_TEMPLATE.format(webpage_content=content, query=query)
            raw_content = call_llm(extractor_prompt)
            return raw_content
        except Exception as e:
            return f"Error extracting information from {url}: {str(e)}"
    else:
        TEMP_WINDOW_SIZE = round(TRUNCATE_LENGTH * 0.1)
        chunks = [content[i:i+TRUNCATE_LENGTH] for i in range(0, len(content), TRUNCATE_LENGTH - TEMP_WINDOW_SIZE)]

        def process_chunk(chunk):
            try:
                extractor_prompt = EXTRACTOR_PROMPT_TEMPLATE.format(webpage_content=chunk, query=query)
                raw_content = call_llm(extractor_prompt)
                return raw_content
            except Exception as e:
                logger.error(f"Error processing chunk: {str(e)}")
                return ""

        final_report = f"The content of the url: {url} is too long. So we have to split it into chunks. Here is the extracted information based on chunks:\n\n"
        try:
            with ThreadPoolExecutor(max_workers=8) as executor:
                chunk_results = list(executor.map(process_chunk, chunks))
                final_report += "\n\n".join(chunk_results)
        except Exception as e:
            return f"Error extracting information from {url}: {str(e)}"

        return final_report


def search(query: str | List[str]) -> str:
    """
    Search the web for information.
    
    Args:
        query: Search query or list of queries
        
    Returns:
        JSON string containing search results
    """
    if isinstance(query, list):
        return _search_multiple(query)
    else:
        return _search_single(query)


def _search_single(query: str) -> str:
    """Search with a single query."""
    query = str(query).strip()
    if not query:
        return json.dumps({"error": "Empty search query."}, ensure_ascii=False)
    try:
        result = _call_serper_api(query)
        # P0-1A: post-process results (dedup by domain, authority rerank, top-8 truncation)
        result = _postprocess_serper_results(result, query)
        return result
    except Exception as e:
        logger.error(f"Error in search for query={query[:200]!r}: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def _search_multiple(queries: List[str]) -> str:
    """Search with multiple queries in parallel."""
    final_result = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_search_single, q): q for q in queries}
        for future in as_completed(futures):
            try:
                result = future.result()
                result_dict = {
                    "query": futures[future],
                    "result": result,
                }
                final_result.append(result_dict)
            except Exception as e:
                logger.error(f"Error in searching: {e}")
                final_result.append({"query": futures[future], "error": str(e)})
    return json.dumps(final_result, ensure_ascii=False)


def crawl_urls(urls: List[str]) -> List[str]:
    """
    Crawl webpage content from given URLs.
    
    Args:
        urls: List of URLs to crawl
        
    Returns:
        List of webpage contents
    """
    url2content = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_crawl_url, url): url for url in urls}
        for future in as_completed(futures):
            try:
                result = future.result()
                url2content[futures[future]] = result
            except Exception as e:
                url2content[futures[future]] = f"Error crawling {futures[future]}: {str(e)}"
    
    # Sort results based on input URL order
    final_content_list = []
    for url in urls:
        final_content_list.append(url2content[url])
    return final_content_list


def visit_urls(urls: List[str], query: str) -> List[str]:
    """
    Visit URLs and extract content related to the query.
    
    Args:
        urls: List of URLs to visit
        query: Query to extract relevant information
        
    Returns:
        List of extracted content reports
    """
    url2response = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_visit_url, url, query): url for url in urls}
        for future in as_completed(futures):
            try:
                result = future.result()
                url2response[futures[future]] = result
            except Exception as e:
                url2response[futures[future]] = f"Error fetching {futures[future]}: {str(e)}"

    final_content_list = []
    for url, content in url2response.items():
        final_content_list.append(f"URL: {url}\n" + f"Report: {content}\n\n")
    return final_content_list


def _search_wiki(entity: str) -> str:
    """Disk-cache wrapper (replay-safe), keyed by entity name."""
    cache_key, cached = _http_cache_get("wiki", entity)
    if cached is not None:
        return cached
    result = _search_wiki_uncached(entity)
    _http_cache_put("wiki", cache_key, (entity,), result)
    return result


def _search_wiki_uncached(entity: str) -> str:
    """Search Wikipedia for a single entity."""
    global _WIKI_FAILURE_COUNT, _WIKI_DISABLED

    if _WIKI_DISABLED:
        return f"title: {entity}\n\nWikipedia is currently unreachable (circuit breaker open). Please use search or visit_urls instead.\n"

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    wiki_timeout = float(os.getenv("WIKI_TIMEOUT_S", "10"))
    wiki_wiki = wikipediaapi.Wikipedia(
        user_agent=user_agent, language='en', timeout=wiki_timeout, max_retries=0
    )
    entity_page = wiki_wiki.page(entity)
    max_tries = int(os.getenv("WIKI_MAX_TRIES", "2"))
    title = entity
    content = ""

    for attempt in range(max_tries):
        try:
            title = entity_page.title
            content = entity_page.text
            break
        except Exception as e:
            if attempt == max_tries - 1:
                _WIKI_FAILURE_COUNT += 1
                max_failures = int(os.getenv("WIKI_MAX_FAILURES", "1"))
                if _WIKI_FAILURE_COUNT >= max_failures:
                    _WIKI_DISABLED = True
                    logger.warning(
                        f"Wikipedia unreachable {_WIKI_FAILURE_COUNT}x (>= {max_failures}); "
                        f"disabling search_wiki for this run. Last error: {e}"
                    )
            time.sleep(1)
            continue

    if not content:
        return f"title: {title}\n\nNo relevant information found in the wikipedia. Please try other entities.\n"
    if len(content) > WIKI_TRUNCATE_LENGTH:
        return f"title: {title}\n\n{content[:WIKI_TRUNCATE_LENGTH]}...[TRUNCATED. Please use visit_urls to avoid too large content.]\n"
    return f"title: {title}\n\n{content}\n"


def search_wiki(entities: List[str]) -> str:
    """
    Search Wikipedia for information about given entities.
    
    Args:
        entities: List of entity names to search
        
    Returns:
        JSON string containing search results
    """
    final_result = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_search_wiki, q): q for q in entities}
        for future in as_completed(futures):
            try:
                result = future.result()
                final_result.append(result)
            except Exception as e:
                logger.error(f"Error in searching wiki: {e}")
                final_result.append(json.dumps({"error": str(e)}, ensure_ascii=False))
    return json.dumps(final_result, ensure_ascii=False)


def get_code_exec_interpreter(execution_timeout: int = 300):
    """Select code-execution backend via CODE_EXEC_BACKEND (M3 ①).

    subprocess (default) or docker (hardened sandbox, auto-fallback to
    subprocess when docker is unavailable).
    """
    from .docker_interpreter import select_interpreter

    backend = (os.getenv("CODE_EXEC_BACKEND", "subprocess") or "subprocess").strip().lower()
    return select_interpreter(execution_timeout=execution_timeout, backend=backend)


def execute_code(code: str) -> str:
    """
    Execute Python code.

    Args:
        code: Python code string to execute

    Returns:
        Execution result as string
    """
    return get_code_exec_interpreter(execution_timeout=300).run(code)
