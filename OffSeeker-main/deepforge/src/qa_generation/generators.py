"""QA pair generation functions

This module provides functions for generating question-answer pairs
from entity graphs.
"""

import random
from typing import Tuple, Optional
from threading import Lock

from loguru import logger
from config import settings
from config.prompts import QA_GENERATION_PROMPT, DEFAULT_SYSTEM_PROMPT
from src.entities.entity import EntityGraph
from api.caller import APICaller


file_lock = Lock()


def ask_gemini(prompt: str) -> str:
    """Ask Gemini model a question

    Args:
        prompt: The prompt to send

    Returns:
        Model response
    """
    messages = [
        {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]
    caller = APICaller(api_type="gemini", model_name=settings.api.gemini_model)
    return caller.call_api(messages)


def generate_qa_pair(
    graph: EntityGraph,
    output_path: Optional[str] = None
) -> Tuple[Optional[str], Optional[str]]:
    """Generate a question-answer pair from an entity graph

    This function uses the Gemini model to generate a complex multi-hop
    question based on the entities and their relationships in the graph.

    Args:
        graph: EntityGraph containing explored entities
        output_path: Optional path to save the generated QA pair

    Returns:
        Tuple of (question, answer), or (None, None) if failed
    """
    # Build entity information string
    entity_infos = ""
    for entity in graph.entities:
        entity_infos += f"Entity: {entity.name}\n"
        entity_infos += f"Properties: {entity.properties}\n"
        entity_infos += f"Relations: {entity.relations}\n"
        entity_infos += "\n"

    # Create prompt
    prompt = QA_GENERATION_PROMPT.format(entity_infos=entity_infos)

    max_tries = settings.generation.max_qa_generation_tries

    for attempt in range(max_tries):
        try:
            response = ask_gemini(prompt)

            # Parse question and answer from response
            if "<question>" not in response or "<answer>" not in response:
                logger.warning(f"Attempt {attempt + 1}: Missing question or answer tags")
                continue

            question = response.split("<question>")[1].split("</question>")[0].strip()
            answer = response.split("<answer>")[1].split("</answer>")[0].strip()

            if not question or not answer:
                logger.warning(f"Attempt {attempt + 1}: Empty question or answer")
                continue

            # Save to file if path provided
            if output_path is not None:
                with file_lock:
                    from src.tools.file_utils import append_jsonl
                    from pathlib import Path

                    append_jsonl(Path(output_path), {
                        "entity": graph.transition_path[0],
                        "question": question,
                        "answer": answer,
                        "depth": graph.depth(),
                        "extra_info": graph.to_dict()
                    })

            logger.info(f"Generated QA pair (attempt {attempt + 1})")
            logger.info(f"  Question: {question[:100]}...")
            logger.info(f"  Answer: {answer}")

            return question, answer

        except Exception as e:
            logger.error(f"Error generating QA pair (attempt {attempt + 1}): {e}")

    logger.error(f"Failed to generate QA pair after {max_tries} attempts")
    return None, None


__all__ = [
    'ask_gemini',
    'generate_qa_pair',
]
