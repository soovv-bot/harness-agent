#!/usr/bin/env python3
"""Test exploration with actual DeepSeek API"""

import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from src.agents.gemini_agent import GeminiAgent
from src.tools.search_tools import (
    SEARCH_GOOGLE_SCHEMA,
    CRAWL_URL_SCHEMA,
    SEARCH_WIKI_SCHEMA,
)

# Test exploration prompt (same as used in exploration_enhanced.py)
EXPLORATION_WITH_CONTEXT_PROMPT = """
You are an agent that can search the web for information and crawl the webpage content of a url.
Your task is to gather ample information about the entity, including two core aspects:
1. The entity itself, such as its description, properties, relevant events, etc.
2. The relationships between the entity and other entities, such as its neighbors, etc.

You can use the following tools to help you:
- search_google: Search the web for information. **REQUIRED parameter**: query (the search query string)
- crawl_url_content: Crawl the webpage content of a url. **REQUIRED parameter**: url (the webpage URL to crawl)
- search_wiki: Search the wikipedia for information. **REQUIRED parameter**: entity (the entity name to search)

IMPORTANT: Each tool call MUST include the required parameter. For example:
- To search for "Nginx": {{"name": "search_google", "arguments": {{"query": "Nginx web server"}}}}
- To crawl a URL: {{"name": "crawl_url_content", "arguments": {{"url": "https://example.com"}}}}
- To search Wikipedia: {{"name": "search_wiki", "arguments": {{"entity": "Nginx"}}}}

Here are the complete tool schemas:
{tool_schemas}

Please output only one function call at a time in json format, enclosed by <function_call> </function_call> tags.

You should first leverage tools to gather information about the entity, and finally output the final result in the following json format:
<result>
{{
    "entity_self": [
        "value1",
        "value2",
        "value3"
    ],
    "entity_relations": {{
        "entity1": "relation1",
        "entity2": "relation2",
        "entity3": "relation3"
    }}
}}
</result>

## Entry Point Context

This exploration is based on an entry point generated from the following source:

- **Source**: {entry_source}
- **Entry Point URL**: {entry_url}

Additional metadata about this entry point:
{entry_metadata}

Use this context to:
- Start your exploration with relevant information from the entry point source
- Prioritize exploring entities and relationships mentioned in the source material
- Build upon the existing knowledge from the entry point rather than starting from scratch

If a URL is provided, consider crawling it first to gather comprehensive initial information about the entity.

Now please start to gather information about the entity.
When generating properties and relations, do not use high-frequency entities instead of unpopular entities (such as low-profile players, niche research institutions, non-mainstream foundations, etc.)
Here is the entity you should explore: {name}{description}
"""


def test_exploration():
    """Test exploration with a simple entity"""
    logger.info("=" * 70)
    logger.info("Testing Exploration with DeepSeek API")
    logger.info("=" * 70)

    # Prepare tool schemas
    tool_schemas = [SEARCH_GOOGLE_SCHEMA, CRAWL_URL_SCHEMA, SEARCH_WIKI_SCHEMA]

    # Create agent
    agent = GeminiAgent(tool_schemas)

    # Test entry point
    test_entry = {
        "title": "Hainanese chicken rice",
        "source": "wikidata_food",
        "name": "Hainanese chicken rice",
        "origin": "Hainan",
        "course": "Main course",
        "url": "https://en.wikipedia.org/wiki/Hainanese_chicken_rice"
    }

    # Format entry point context
    entry_source = test_entry.get('source', 'Unknown')
    entry_url = test_entry.get('url', 'Not provided')

    # Format metadata for display
    metadata_items = []
    for key, value in test_entry.items():
        if key not in ['title', 'source', 'url', 'name'] and value:
            metadata_items.append(f"- **{key}**: {value}")

    entry_metadata = "\n".join(metadata_items) if metadata_items else "No additional metadata"

    # Use context-aware prompt
    name = "Hainanese chicken rice"
    description_str = " - A popular Southeast Asian dish"
    prompt = EXPLORATION_WITH_CONTEXT_PROMPT.format(
        tool_schemas=tool_schemas,
        name=name,
        description=description_str,
        entry_source=entry_source,
        entry_url=entry_url,
        entry_metadata=entry_metadata
    )

    logger.info(f"Testing exploration for: {name}")
    logger.info(f"Prompt length: {len(prompt)}")

    # Run exploration
    result = agent.run_loop(prompt)

    logger.info("=" * 70)
    logger.info("EXPLORATION RESULT")
    logger.info("=" * 70)

    if result is None:
        logger.error("Agent returned None!")
        return None

    logger.info(f"Result length: {len(result)}")
    logger.info(f"Result preview:\n{result[:500]}...")

    # Check for <result> tags
    if "<result>" in result and "</result>" in result:
        result_str = result.split("<result>")[1].split("</result>")[0].strip()
        logger.info(f"Found <result> tags!")
        logger.info(f"Result JSON: {result_str[:200]}...")

        try:
            import json
            result_dict = json.loads(result_str)
            logger.info(f"Successfully parsed result JSON")
            logger.info(f"  entity_self: {len(result_dict.get('entity_self', []))} items")
            logger.info(f"  entity_relations: {len(result_dict.get('entity_relations', {}))} items")
            return result_dict
        except Exception as e:
            logger.error(f"Failed to parse result JSON: {e}")
            logger.info(f"Trying eval instead...")
            try:
                result_dict = eval(result_str)
                logger.info(f"Successfully parsed result with eval")
                logger.info(f"  entity_self: {len(result_dict.get('entity_self', []))} items")
                logger.info(f"  entity_relations: {len(result_dict.get('entity_relations', {}))} items")
                return result_dict
            except Exception as e2:
                logger.error(f"Failed to parse result with eval: {e2}")
                return None
    else:
        logger.warning("No <result> tags found in result!")
        logger.info(f"Full result:\n{result}")
        return None


if __name__ == "__main__":
    test_exploration()
