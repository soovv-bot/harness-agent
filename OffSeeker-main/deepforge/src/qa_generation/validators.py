"""QA validation functions

This module provides functions for validating question-answer pairs,
including self-check and correctness verification.
"""

from loguru import logger
from config import settings
from config.prompts import QUALITY_CHECK_SYSTEM_PROMPT, CORRECTNESS_CHECK_PROMPT
from api.caller import APICaller


def self_check_question(data: dict) -> str:
    """Check if a question can be answered without web search

    This function directly asks the LLM to answer a question without
    any tools. If it can answer correctly, the question is too easy.

    Args:
        data: Dictionary containing 'question' key

    Returns:
        LLM response (including thinking and answer)
    """
    try:
        question = data['question']

        messages = [
            {"role": "system", "content": QUALITY_CHECK_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]

        caller = APICaller(api_type="gemini", model_name=settings.api.gemini_model)
        response = caller.call_api(messages)

        return response

    except Exception as e:
        logger.error(f"Error in self_check_question: {e}")
        return None


def check_correctness(question: str, ground_truth: str, model_answer: str) -> bool:
    """Check if the predicted answer is semantically equivalent to ground truth

    This function uses an LLM to judge whether the model's answer is
    semantically equivalent to the labeled answer.

    Args:
        question: The question being asked
        ground_truth: The labeled correct answer
        model_answer: The model's predicted answer

    Returns:
        True if answers are semantically equivalent, False otherwise
    """
    try:
        prompt = CORRECTNESS_CHECK_PROMPT.format(
            question=question,
            ground_truth=ground_truth,
            model_answer=model_answer
        )

        resp = APICaller(api_type="gemini", model_name=settings.api.gemini_model).call_api(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
        )

        judge_result = resp.lower() if resp else ""

        if "yes" in judge_result:
            return True
        else:
            return False

    except Exception as e:
        logger.error(f"Error in check_correctness: {e}")
        return False


def direct_ask_llm(data: dict) -> str:
    """Directly ask LLM to answer a question (for quality filtering)

    This is similar to self_check_question but extracts just the answer.

    Args:
        data: Dictionary containing 'question' key

    Returns:
        The LLM's answer, or None if failed
    """
    try:
        response = self_check_question(data)

        if response and "<answer>" in response:
            answer = response.split("<answer>")[1].split("</answer>")[0].strip()
            return answer

        return None

    except Exception as e:
        logger.error(f"Error in direct_ask_llm: {e}")
        return None


__all__ = [
    'self_check_question',
    'check_correctness',
    'direct_ask_llm',
]
