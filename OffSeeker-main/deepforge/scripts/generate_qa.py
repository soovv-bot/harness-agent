#!/usr/bin/env python3
"""
Stage 3 & 4: Generate QA pairs from seed entities

This script generates complex multi-hop question-answer pairs
from seed entities using web exploration.

Usage:
    python scripts/generate_qa.py [--config config.yaml]
"""

import sys
import argparse
from pathlib import Path
from typing import Tuple, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from config import settings
from config.prompts import EXPLORATION_PROMPT
from src.entities.entity import EntityGraph
from src.entities.explorers import gather_information, get_random_depth
from src.qa_generation.generators import generate_qa_pair
from src.qa_generation.validators import self_check_question, check_correctness
from src.enhancement.difficulty import difficulty_enhancement
from src.tools.file_utils import load_json, get_processed_entities, write_jsonl, append_jsonl
from src.tools.concurrency import run_concurrently
from loguru import logger
from threading import Lock


file_lock = Lock()


def process_seed_entity(
    entity_name: str,
    output_path: Optional[str] = None,
    graph_path: Optional[str] = None,
    check_difficulty: bool = True
) -> Tuple[Optional[str], Optional[str]]:
    """Process a single seed entity through the pipeline

    Args:
        entity_name: Name of the seed entity
        output_path: Path to save QA pairs
        graph_path: Path to save entity graphs
        check_difficulty: Whether to run difficulty enhancement

    Returns:
        Tuple of (question, answer), or (None, None) if failed
    """
    try:
        depth = get_random_depth()
        logger.info(f"Processing entity: {entity_name} (depth: {depth})")

        # Gather entity graph
        graph = gather_information(entity_name, depth)

        if graph.depth() == 0:
            logger.warning(f"No entities explored for: {entity_name}")
            return None, None

        # Save graph if path provided
        if graph_path is not None:
            append_jsonl(Path(graph_path), graph.to_dict())

        # Generate initial QA pair
        question, answer = generate_qa_pair(graph, None)

        if question is None or answer is None:
            logger.warning(f"Failed to generate QA pair for: {entity_name}")
            return None, None

        # Optional: Run difficulty enhancement
        if check_difficulty:
            enhanced_example = {
                "question": question,
                "answer": answer,
                "entity": graph.transition_path[0],
                "depth": graph.depth(),
                "extra_info": graph.to_dict()
            }

            difficulty_question, difficulty_answer = difficulty_enhancement(
                enhanced_example,
                None
            )

            if difficulty_question is not None:
                question, answer = difficulty_question, difficulty_answer

        # Self-check to verify question requires web search
        response = self_check_question({"question": question, "answer": answer})
        is_correct = check_correctness(question, answer, response)

        if is_correct:
            logger.info(f"Question too easy for: {entity_name}, skipping")
            return None, None

        # Save final QA pair
        if output_path is not None:
            with file_lock:
                append_jsonl(Path(output_path), {
                    "entity": graph.transition_path[0],
                    "question": question,
                    "answer": answer,
                    "depth": graph.depth(),
                    "extra_info": graph.to_dict()
                })

        logger.info(f"✓ Successfully processed: {entity_name}")
        return question, answer

    except Exception as e:
        logger.error(f"Error processing entity {entity_name}: {e}")
        return None, None


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Generate QA pairs from seed entities")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--seed-entities", default=None, help="Path to seed entities JSON file")
    parser.add_argument("--output", default=None, help="Output path for QA pairs")
    parser.add_argument("--graphs", default=None, help="Output path for entity graphs")
    parser.add_argument("--num-entities", type=int, default=None, help="Number of entities to process (default: all)")
    parser.add_argument("--no-difficulty", action="store_true", help="Skip difficulty enhancement")
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Load settings if config file exists
    config_file = Path(args.config)
    if config_file.exists():
        try:
            # Note: We can't use from_yaml if PyYAML is not installed
            # So we just use the default settings
            logger.info(f"Using default settings from config/settings.py")
        except Exception as e:
            logger.warning(f"Could not load config file: {e}")

    # Set default paths
    seed_path = Path(args.seed_entities) if args.seed_entities else settings.paths.seed_entities_path
    output_path = Path(args.output) if args.output else settings.paths.qa_pairs_all_path
    graph_path = Path(args.graphs) if args.graphs else settings.paths.seed_graph_path

    logger.info(f"Seed entities path: {seed_path}")
    logger.info(f"Output path: {output_path}")
    logger.info(f"Graph path: {graph_path}")

    # Load seed entities
    if not seed_path.exists():
        logger.error(f"Seed entities file not found: {seed_path}")
        logger.info(f"Please run generate_seed_entities.py first to generate seed entities")
        return 1

    seed_entities = load_json(seed_path)
    logger.info(f"Loaded {len(seed_entities)} seed entities")

    # Get already processed entities
    processed = get_processed_entities(output_path)
    logger.info(f"Already processed: {len(processed)} entities")

    # Filter entities to process
    entities_to_process = [
        item["name"] for item in seed_entities
        if item["name"] not in processed
    ]

    # Limit number of entities if specified
    if args.num_entities is not None:
        entities_to_process = entities_to_process[:args.num_entities]
        logger.info(f"Limited to {args.num_entities} entities")

    logger.info(f"Entities to process: {len(entities_to_process)}")

    if len(entities_to_process) == 0:
        logger.info("All entities have been processed already")
        return 0

    # Create processing function with fixed arguments
    def process_func(entity_name: str):
        return process_seed_entity(
            entity_name,
            str(output_path),
            str(graph_path),
            check_difficulty=not args.no_difficulty
        )

    # Process entities concurrently
    run_concurrently(
        entities_to_process,
        process_func,
        settings.concurrency.qa_generation_workers,
        "Generating QA pairs"
    )

    logger.info("QA generation pipeline complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
