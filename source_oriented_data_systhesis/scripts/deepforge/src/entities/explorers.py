"""Entity exploration functions

This module provides functions for exploring entities and gathering
information from the web using tools.
"""

import random
from typing import Optional

from deepforge.config import settings
from deepforge.config.prompts import EXPLORATION_PROMPT
from deepforge.src.entities.entity import Entity, EntityGraph
from deepforge.src.tools.search_tools import (
    SEARCH_GOOGLE_SCHEMA,
    SEARCH_WIKI_SCHEMA,
    CRAWL_URL_SCHEMA,
)


def get_random_depth() -> int:
    """Get random exploration depth with weighted distribution

    Returns depth value based on weights:
    - Depth 1: 10% probability
    - Depth 2: 40% probability
    - Depth 3: 40% probability
    - Depth 4: 10% probability

    Returns:
        Random depth value (1-4)
    """
    return random.choices([1, 2, 3, 4], weights=settings.generation.depth_weights)[0]


def exploration_step(name: str, description: Optional[str] = None) -> Optional[Entity]:
    """Explore a single entity and gather its properties and relations

    This function uses a Gemini agent with tools to search the web,
    crawl URLs, and search Wikipedia to gather information about
    an entity.

    Args:
        name: The entity name to explore
        description: Optional description of the entity

    Returns:
        Entity object with properties and relations, or None if failed
    """
    from src.agents.gemini_agent import GeminiAgent

    # Prepare tool schemas
    tool_schemas = [SEARCH_GOOGLE_SCHEMA, CRAWL_URL_SCHEMA, SEARCH_WIKI_SCHEMA]

    # Create agent and run exploration
    agent = GeminiAgent(tool_schemas)

    # Format description for prompt
    description_str = f" - {description}" if description else ""

    prompt = EXPLORATION_PROMPT.format(
        tool_schemas=tool_schemas,
        name=name,
        description=description_str
    )

    try:
        explore_result = agent.run_loop(prompt)

        # Parse the result from <result> tags
        if "<result>" in explore_result and "</result>" in explore_result:
            result_str = explore_result.split("<result>")[1].split("</result>")[0].strip()
            result_dict = eval(result_str)

            entity = Entity(name=name, description=description)
            entity.properties = result_dict.get("entity_self", [])
            entity.relations = result_dict.get("entity_relations", {})

            return entity
        else:
            return None

    except Exception as e:
        from loguru import logger
        logger.error(f"Error exploring entity {name}: {e}")
        return None


def relation_step(entity: Entity) -> str:
    """Select a random related entity from the entity's relations

    Args:
        entity: The entity to select a relation from

    Returns:
        Name of a randomly selected related entity

    Raises:
        AssertionError: If entity has no relations
    """
    assert len(entity.relations) > 0, "Entity must have at least one relation"
    relation = random.choice(list(entity.relations.items()))
    return relation[0]


def gather_information(name: str, depth: int = 2) -> EntityGraph:
    """Gather multi-hop information about an entity

    This function performs a multi-hop exploration starting from the
    given entity, following relations to explore connected entities.

    Args:
        name: The seed entity name to start exploration from
        depth: Number of hops to explore (default: 2)

    Returns:
        EntityGraph containing all explored entities and the transition path
    """
    from loguru import logger

    graph = EntityGraph()
    name_to_explore = name

    for i in range(depth):
        logger.info(f"Exploration step {i+1}/{depth}: {name_to_explore}")

        entity = exploration_step(name_to_explore)

        if entity is None:
            logger.warning(f"Failed to explore entity: {name_to_explore}")
            break

        # Choose next entity to explore (if there are relations)
        if entity.relations:
            name_to_explore = relation_step(entity)
        else:
            logger.info(f"Entity {entity.name} has no relations, stopping exploration")
            break

        # Add entity to graph
        graph.add_entity(entity)

    return graph


__all__ = [
    'get_random_depth',
    'exploration_step',
    'relation_step',
    'gather_information',
]
