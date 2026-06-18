#!/usr/bin/env python3
"""
Enhanced exploration functions that utilize entry point metadata

This extends OffSeeker's gather_information to accept and utilize
the rich metadata from entry point generation.
"""

import json
from typing import Optional, Dict
from loguru import logger
import sys
from pathlib import Path

# Add deepforge to path (local copy)
deepforge_path = Path(__file__).parent / "deepforge"
sys.path.insert(0, str(deepforge_path))

from src.entities.explorers import exploration_step, gather_information as original_gather_info
from src.entities.entity import Entity, EntityGraph


# Enhanced exploration prompt with entry point context
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


def exploration_step_with_context(
    name: str,
    entry_point: Optional[Dict] = None,
    description: Optional[str] = None
) -> Optional[Entity]:
    """Explore a single entity with entry point context

    Args:
        name: The entity name to explore
        entry_point: Complete entry point dict with metadata (source, url, origin, etc.)
        description: Optional description of the entity

    Returns:
        Entity object with properties and relations, or None if failed
    """
    from src.agents.gemini_agent import GeminiAgent
    from src.tools.search_tools import (
        SEARCH_GOOGLE_SCHEMA,
        CRAWL_URL_SCHEMA,
        SEARCH_WIKI_SCHEMA,
    )

    # Prepare tool schemas
    tool_schemas = [SEARCH_GOOGLE_SCHEMA, CRAWL_URL_SCHEMA, SEARCH_WIKI_SCHEMA]

    # Create agent and run exploration
    agent = GeminiAgent(tool_schemas)

    # Format entry point context
    if entry_point:
        entry_source = entry_point.get('source', 'Unknown')
        entry_url = entry_point.get('url', 'Not provided')

        # Format metadata for display
        metadata_items = []
        for key, value in entry_point.items():
            if key not in ['title', 'source', 'url', 'name'] and value:
                metadata_items.append(f"- **{key}**: {value}")

        entry_metadata = "\n".join(metadata_items) if metadata_items else "No additional metadata"

        # Use context-aware prompt
        description_str = f" - {description}" if description else ""
        prompt = EXPLORATION_WITH_CONTEXT_PROMPT.format(
            tool_schemas=tool_schemas,
            name=name,
            description=description_str,
            entry_source=entry_source,
            entry_url=entry_url,
            entry_metadata=entry_metadata
        )
    else:
        # Fall back to standard exploration
        return exploration_step(name, description)

    try:
        logger.info(f"Starting exploration for entity: {name}")
        explore_result = agent.run_loop(prompt)

        # Check if agent returned a result
        if explore_result is None:
            logger.warning(f"Agent returned None for entity: {name}")
            return None

        logger.info(f"Agent returned result, length: {len(explore_result) if explore_result else 0}")

        # Parse the result from <result> tags
        if "<result>" in explore_result and "</result>" in explore_result:
            result_str = explore_result.split("<result>")[1].split("</result>")[0].strip()
            logger.debug(f"Result string: {result_str[:200]}...")
            result_dict = eval(result_str)

            entity = Entity(name=name, description=description)
            entity.properties = result_dict.get("entity_self", [])
            entity.relations = result_dict.get("entity_relations", {})

            logger.info(f"Successfully parsed entity: {name}, properties: {len(entity.properties)}, relations: {len(entity.relations)}")
            return entity
        else:
            logger.warning(f"No <result> tags found in agent output for entity: {name}")
            logger.debug(f"Agent output preview: {explore_result[:500]}...")
            return None

    except Exception as e:
        logger.error(f"Error exploring entity {name}: {e}")
        return None


def gather_information_with_context(
    name: str,
    depth: int = 2,
    entry_point: Optional[Dict] = None
) -> EntityGraph:
    """Gather multi-hop information with entry point context

    Args:
        name: The seed entity name to start exploration from
        depth: Number of hops to explore (default: 2)
        entry_point: Complete entry point dict with metadata

    Returns:
        EntityGraph containing all explored entities and the transition path
    """
    graph = EntityGraph()

    # Store entry point metadata in graph for later use
    if entry_point:
        if not hasattr(graph, 'entry_point_metadata'):
            graph.entry_point_metadata = {}
        graph.entry_point_metadata.update(entry_point)
        logger.info(f"Exploration with context from source: {entry_point.get('source', 'unknown')}")

    name_to_explore = name

    for i in range(depth):
        logger.info(f"Exploration step {i+1}/{depth}: {name_to_explore}")

        # Use enhanced exploration for first step with context
        if i == 0 and entry_point:
            entity = exploration_step_with_context(name_to_explore, entry_point)
        else:
            entity = exploration_step(name_to_explore)

        if entity is None:
            logger.warning(f"Failed to explore entity: {name_to_explore}")
            break

        # Choose next entity to explore (if there are relations)
        if entity.relations:
            from src.entities.explorers import relation_step
            name_to_explore = relation_step(entity)
        else:
            logger.info(f"Entity {entity.name} has no relations, stopping exploration")
            break

        # Add entity to graph
        graph.add_entity(entity)

    return graph


# Re-export original function for compatibility
gather_information = original_gather_info


if __name__ == "__main__":
    # Test
    test_entry = {
        "title": "Hainanese chicken rice",
        "source": "wikidata_food",
        "name": "Hainanese chicken rice",
        "origin": "Hainan",
        "course": "Main course",
        "url": "https://en.wikipedia.org/wiki/Hainanese_chicken_rice"
    }

    result = gather_information_with_context("Hainanese chicken rice", depth=1, entry_point=test_entry)
    print(f"Entities: {len(result.entity_dict)}")
    if hasattr(result, 'entry_point_metadata'):
        print(f"Metadata: {result.entry_point_metadata}")
