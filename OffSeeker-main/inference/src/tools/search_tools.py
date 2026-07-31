"""
Search Tools for Deep Research
Implements web search, URL crawling, and content extraction functionality
"""

import requests
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional
from loguru import logger
from PyPDF2 import PdfReader
import io
import html2text
import time
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


def call_llm(
    prompt: str,
    max_tries: int = 10,
    model_name: str = "deepseek-chat",
):
    """
    Call LLM API for content extraction.

    Uses DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL if set, otherwise falls back to
    OPENAI_API_KEY / OPENAI_BASE_URL.

    Args:
        prompt: Prompt text
        max_tries: Maximum retry attempts
        model_name: Model name (default: deepseek-chat)

    Returns:
        Model response text
    """
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL") or os.getenv("OPENAI_BASE_URL", "https://preview.llm.tenyunc.com/v1")
    if not api_key:
        raise ValueError("Neither DEEPSEEK_API_KEY nor OPENAI_API_KEY is set in environment variables")

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt},
    ]

    for attempt in range(max_tries):
        try:
            client = _build_openai_client(api_key=api_key, base_url=base_url)
            chat_response = client.chat.completions.create(
                model=model_name,
                messages=messages,
            )
            content = chat_response.choices[0].message.content
            return content
        except Exception as e:
            logger.warning(f"Error calling DeepSeek API: {e}")
            if attempt < max_tries - 1:
                time.sleep(5)
            continue
    
    logger.error("All attempts failed to call DeepSeek API")
    return "Failed to call DeepSeek API"


def _call_serper_api(query: str) -> str:
    """
    Call Serper API for Google search.
    
    Args:
        query: Search query
        
    Returns:
        Search results as JSON string
    """
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
    return response.text


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
    response = session.get(api_url, headers=headers, timeout=60)
    response.raise_for_status()
    return response.text


def _call_html2text(url: str) -> str:
    """Use html2text to extract content from URL."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        session = _get_requests_session()
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        text_processor = html2text.HTML2Text()
        text_processor.ignore_links = True
        text_processor.ignore_images = True
        text_processor.ignore_tables = False
        content = text_processor.handle(response.text)
        return content

    except Exception as e:
        return f"Error crawling url: {url}: {str(e)}"


def _crawl_url(url: str) -> str:
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
    
    crawler_engine = os.getenv("CRAWLER_ENGINE", "html2text")
    if crawler_engine == "jina":
        try:
            return _call_jina_api(url)
        except Exception as e:
            logger.warning(f"Jina API failed, falling back to html2text: {e}")
            return _call_html2text(url)
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
            return _call_html2text(url)


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
    """Search Wikipedia for a single entity."""
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    wiki_wiki = wikipediaapi.Wikipedia(user_agent=user_agent, language='en')
    entity_page = wiki_wiki.page(entity)
    max_tries = 10
    title = entity
    content = ""
    
    for _ in range(max_tries):
        try:
            title = entity_page.title
            content = entity_page.text
            break
        except Exception as e:
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


def execute_code(code: str) -> str:
    """
    Execute Python code.
    
    Args:
        code: Python code string to execute
        
    Returns:
        Execution result as string
    """
    interpreter = SubprocessInterpreter(execution_timeout=300)
    return interpreter.run(code)
