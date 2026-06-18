"""Entity and EntityGraph data structures

This module provides the core data structures for representing entities
and their relationships in the knowledge graph.
"""

from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field


@dataclass
class Entity:
    """Represents an entity with properties and relations

    An entity can be a person, place, thing, concept, etc. that has been
    extracted from web content during the exploration process.

    Attributes:
        name: The name of the entity
        description: Optional description of the entity
        properties: List of entity's self-descriptive properties
        relations: Dictionary mapping related entity names to their relationships
    """

    name: str
    description: Optional[str] = None
    properties: List[str] = field(default_factory=list)
    relations: Dict[str, str] = field(default_factory=dict)

    def __str__(self) -> str:
        return (
            f"Entity(name={self.name}, "
            f"properties length={len(self.properties)}, "
            f"relations length={len(self.relations)})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to dictionary representation

        Returns:
            Dictionary containing all entity data
        """
        return {
            "name": self.name,
            "description": self.description,
            "properties": self.properties,
            "relations": self.relations,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Entity":
        """Create Entity from dictionary representation

        Args:
            data: Dictionary containing entity data

        Returns:
            New Entity instance
        """
        entity = cls(name=data["name"], description=data.get("description"))
        entity.properties = data.get("properties", [])
        entity.relations = data.get("relations", {})
        return entity


@dataclass
class EntityGraph:
    """Graph of entities with transition path

    The EntityGraph manages a collection of entities and tracks the
    exploration path (transition path) that was taken to discover them.

    Attributes:
        entity_dict: Dictionary mapping entity names to Entity objects
        transition_path: List of entity names in exploration order
    """

    entity_dict: Dict[str, Entity] = field(default_factory=dict)
    transition_path: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"EntityGraph(entity_dict length={len(self.entity_dict)}, "
            f"transition_path length={len(self.transition_path)})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert graph to dictionary representation

        Returns:
            Dictionary containing all graph data
        """
        return {
            "entity_dict": {k: v.to_dict() for k, v in self.entity_dict.items()},
            "transition_path": self.transition_path,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EntityGraph":
        """Create EntityGraph from dictionary representation

        Args:
            data: Dictionary containing graph data

        Returns:
            New EntityGraph instance
        """
        graph = cls()
        for k, v in data["entity_dict"].items():
            graph.entity_dict[k] = Entity.from_dict(v)
        graph.transition_path = data.get("transition_path", [])
        return graph

    def add_entity(self, entity: Entity):
        """Add an entity to the graph

        Adds the entity to the entity_dict and appends its name to
        the transition_path if not already present.

        Args:
            entity: Entity to add
        """
        self.entity_dict[entity.name] = entity
        if entity.name not in self.transition_path:
            self.transition_path.append(entity.name)

    def get_entity(self, name: str) -> Optional[Entity]:
        """Get an entity by name

        Args:
            name: Entity name to look up

        Returns:
            Entity if found, None otherwise
        """
        return self.entity_dict.get(name)

    @property
    def entities(self) -> List[Entity]:
        """Get list of all entities in transition path order

        Returns:
            List of Entity objects
        """
        return [
            self.entity_dict[name]
            for name in self.transition_path
            if name in self.entity_dict
        ]

    def depth(self) -> int:
        """Get the depth of the exploration (number of entities in path)

        Returns:
            Number of entities in transition path
        """
        return len(self.transition_path)
