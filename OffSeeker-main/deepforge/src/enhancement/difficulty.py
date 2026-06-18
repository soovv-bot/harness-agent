"""Difficulty enhancement for QA pairs

This module provides functionality to enhance the difficulty of
question-answer pairs by making questions more vague and ambiguous.
"""

import json
from typing import Tuple, Optional, Dict
from threading import Lock

from loguru import logger
from config import settings
from config.prompts import DIFFICULTY_ENHANCEMENT_PROMPT, DEFAULT_SYSTEM_PROMPT
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


def difficulty_enhancement(
    example: Dict[str, any],
    output_path: Optional[str] = None
) -> Tuple[Optional[str], Optional[str]]:
    """Enhance the difficulty of a question-answer pair

    This function makes the question more vague and ambiguous to
    increase the difficulty level.

    Args:
        example: Dictionary containing 'question', 'answer', 'entity', 'depth', 'extra_info'
        output_path: Optional path to save the enhanced QA pair

    Returns:
        Tuple of (enhanced_question, enhanced_answer), or (None, None) if failed
    """
    question = example["question"]
    answer = example["answer"]
    entity = example["entity"]
    extra_info = example["extra_info"]
    depth = example["depth"]

    # Format extra_info for the prompt
    extra_info_str = json.dumps(extra_info, ensure_ascii=False, indent=2)

    prompt = DIFFICULTY_ENHANCEMENT_PROMPT.format(
        question=question,
        answer=answer,
        extra_info=extra_info_str
    )

    try:
        response = ask_gemini(prompt)

        # Parse enhanced question and answer
        if "<question>" not in response or "<answer>" not in response:
            logger.error("Missing question or answer tags in difficulty enhancement response")
            return None, None

        enhanced_question = response.split("<question>")[1].split("</question>")[0].strip()
        enhanced_answer = response.split("<answer>")[1].split("</answer>")[0].strip()

        if output_path is not None:
            with file_lock:
                from src.tools.file_utils import append_jsonl
                from pathlib import Path

                append_jsonl(Path(output_path), {
                    "entity": entity,
                    "question": enhanced_question,
                    "answer": enhanced_answer,
                    "depth": depth,
                    "extra_info": extra_info
                })

        logger.info(f"Difficulty enhancement successful")
        return enhanced_question, enhanced_answer

    except Exception as e:
        logger.error(f"Error enhancing difficulty: {e}")
        return None, None


__all__ = [
    'difficulty_enhancement',
]
