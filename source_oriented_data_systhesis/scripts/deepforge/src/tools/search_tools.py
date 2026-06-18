"""Web search and content extraction tools

This module provides tools for web search, URL crawling, and content extraction.
It consolidates the functionality from the original search_tools.py and adds
missing functions that were imported from utils.tools.

Tool schemas for agent use are also defined here.
"""

import os
import json
import time
import uuid
import requests
from typing import Dict, Optional
from loguru import logger

from deepforge.config import settings


# ============================================================================
# Tool Schemas for Agent Use (OpenAI-compatible format)
# ============================================================================

SEARCH_GOOGLE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_google",
        "description": "Search the web for information",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The query to search for"}
            },
            "required": ["query"]
        }
    }
}

SEARCH_WIKI_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_wiki",
        "description": "Search the wikipedia for information",
        "parameters": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "The entity to search for"}
            },
            "required": ["entity"]
        }
    }
}

CRAWL_URL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "crawl_url_content",
        "description": "Crawl the webpage content of a url",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The url to crawl"},
            },
            "required": ["url"]
        }
    }
}


# ============================================================================
# Search Functions
# ============================================================================

def call_serper_api(query: str) -> str:
    """Call Serper API for search results

    This function searches the web using the Serper API directly.
    API docs: https://serper.dev/api-reference

    Args:
        query: The search query string

    Returns:
        JSON string of organic search results, or error message if failed
    """
    # Validate query parameter
    if not query or not query.strip():
        logger.warning("Empty query parameter provided to Serper API, skipping search")
        return json.dumps([])

    headers = {
        "X-API-KEY": settings.api.get_serper_key(),
        "Content-Type": "application/json"
    }
    data = {
        "q": query.strip(),
        "num": 10
    }

    url = "https://google.serper.dev/search"

    max_tries = 3
    for attempt in range(max_tries):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()

            # Return organic results as JSON string
            return json.dumps(result.get('organic', []))

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401 or e.response.status_code == 403:
                logger.error(f"Serper API authentication failed: {e}")
                logger.error(f"Please check your SERPER_API_KEY in .env file")
                break
            elif e.response.status_code == 400:
                logger.error(f"Serper API bad request (400): {e}")
                logger.error(f"Response: {e.response.text if hasattr(e.response, 'text') else 'No response text'}")
                logger.error(f"This usually means invalid API key or request format")
                break
            elif e.response.status_code == 429:
                logger.warning(f"Serper API rate limit hit (attempt {attempt + 1})")
                time.sleep(2)
                continue
            else:
                logger.error(f"Serper API error: {e}")
                break

        except requests.exceptions.Timeout:
            logger.error(f"Timeout calling serper api for query: {query}")
            if attempt < max_tries - 1:
                time.sleep(1)
                continue
            break

        except Exception as e:
            logger.error(f"Error calling serper api for query {query}: {e}")
            break

    return "No results found"


def call_jina_api(url: str) -> str:
    """Call Jina API to crawl URL content

    This function uses the Jina Reader API to extract clean text content
    from a webpage.

    Args:
        url: The URL to crawl

    Returns:
        Extracted text content, or empty string if failed
    """
    try:
        # Jina Reader API: https://r.jina.ai/http://example.com
        jina_url = f"https://r.jina.ai/{url}"

        # Add API key if available
        headers = {}
        if settings.api.jina_api_key:
            headers["Authorization"] = f"Bearer {settings.api.jina_api_key}"

        response = requests.get(jina_url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        if status_code == 429:
            # Rate limiting - log warning and skip
            logger.warning(f"Jina API rate limit (429) for {url}, skipping content extraction")
            return ""
        elif status_code == 451:
            # Legal restrictions - some sites (GitHub, etc.) block crawlers
            logger.info(f"URL blocked by legal restrictions (451): {url[:100]}...")
            return ""
        else:
            logger.error(f"Jina API HTTP error {status_code} for {url}: {e}")
            return ""

    except requests.exceptions.Timeout:
        logger.warning(f"Timeout fetching content from {url}")
        return ""
    except Exception as e:
        logger.error(f"Error calling Jina API for {url}: {e}")
        return ""


def get_html_content(url: str) -> str:
    """Get HTML content using Jina reader API

    This is a convenience function that extracts readable text content
    from a webpage using the Jina Reader API.

    Args:
        url: The URL to fetch content from

    Returns:
        Extracted text content
    """
    return call_jina_api(url)


def search_wiki(entity: str) -> str:
    """Search Wikipedia for entity information

    This function searches Wikipedia for information about an entity
    and returns the summary and a portion of the full text.

    Args:
        entity: The entity name to search for

    Returns:
        Wikipedia summary and text, or error message if not found
    """
    # Validate entity parameter
    if not entity or not entity.strip():
        logger.warning("Empty entity parameter provided to Wikipedia search, skipping")
        return ""

    try:
        import wikipediaapi
        wiki_wiki = wikipediaapi.Wikipedia(
            user_agent='DeepForge',
            language='en',
            extract_format=wikipediaapi.ExtractFormat.WIKI
        )
        page = wiki_wiki.page(entity)

        if page.exists():
            # Return summary + first 2000 chars of full text
            content = f"{page.summary}\n\n{page.text[:2000]}"
            return content
        else:
            return f"No Wikipedia page found for {entity}"

    except Exception as e:
        logger.error(f"Error searching Wikipedia for {entity}: {e}")
        return f"Error searching Wikipedia: {str(e)}"


# ============================================================================
# Legacy/Backward Compatibility Functions
# ============================================================================

# Re-export functions with original names for backward compatibility
# The original code imported these from utils.tools
__all__ = [
    'call_serper_api',
    'call_jina_api',
    'get_html_content',
    'search_wiki',
    'SEARCH_GOOGLE_SCHEMA',
    'SEARCH_WIKI_SCHEMA',
    'CRAWL_URL_SCHEMA',
]
