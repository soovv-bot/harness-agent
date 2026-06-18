"""Quality filtering for QA pairs

This module provides functionality to filter QA pairs by quality,
testing if they can be answered without web search.
"""

from typing import Dict, List
from threading import Lock
from pathlib import Path

from loguru import logger
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

from deepforge.src.qa_generation.validators import direct_ask_llm, check_correctness
from deepforge.src.tools.file_utils import load_jsonl, write_jsonl


file_lock = Lock()


def get_data_id(data: dict) -> str:
    """Get unique identifier for a data item

    Args:
        data: Dictionary containing 'question' key

    Returns:
        The question as the unique identifier
    """
    return data['question']


def get_processed_data_ids(data_path: Path) -> set:
    """Get set of already processed data IDs

    Args:
        data_path: Path to the JSONL file

    Returns:
        Set of processed question strings
    """
    processed_data_ids = set()
    if not data_path.exists():
        return processed_data_ids

    data_list = load_jsonl(data_path)
    for data in data_list:
        processed_data_ids.add(get_data_id(data))

    return processed_data_ids


def process_data(data: dict, save_path: Path) -> bool:
    """Process a single QA pair to check if it's hard enough

    Args:
        data: Dictionary containing 'question' and 'answer'
        save_path: Path to save the result

    Returns:
        True if data is hard (passed the check), False otherwise
    """
    model_answer = direct_ask_llm(data)

    if model_answer is None:
        # If LLM couldn't answer, mark as hard
        data['is_hard_data'] = "True"
    else:
        is_correct = check_correctness(data['question'], data['answer'], model_answer)
        data['is_hard_data'] = str(not is_correct)

    # Save result
    with file_lock:
        from src.tools.file_utils import append_jsonl
        append_jsonl(save_path, data)

    return data['is_hard_data'] == "True"


def process_concurrently(
    file_path: str,
    save_path: str,
    max_workers: int = 10
):
    """Process QA pairs concurrently to filter quality

    Args:
        file_path: Input file path
        save_path: Output file path
        max_workers: Maximum number of worker threads
    """
    save_path_obj = Path(save_path)

    # Load input data
    data_list = load_jsonl(Path(file_path))
    logger.info(f"Total {len(data_list)} QA pairs to process")

    # Filter already processed
    processed_ids = get_processed_data_ids(save_path_obj)
    data_list = [data for data in data_list if get_data_id(data) not in processed_ids]
    logger.info(f"Processing {len(data_list)} QA pairs after filtering")

    # Process concurrently
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_data, data, save_path_obj): data for data in data_list}

        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing data"):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Error processing QA pair: {e}")


def filter_out_easy_data(tmp_output_path: str, output_path: str):
    """Filter out easy data, keeping only hard data

    Args:
        tmp_output_path: Temporary output file path
        output_path: Final output file path (hard data only)
    """
    hard_data_list = []

    data_list = load_jsonl(Path(tmp_output_path))
    for data in data_list:
        if data.get('is_hard_data') == "True":
            # Remove the temporary flag
            data_copy = data.copy()
            del data_copy['is_hard_data']
            hard_data_list.append(data_copy)

    logger.info(f"Hard data length: {len(hard_data_list)} (out of {len(data_list)} total)")

    write_jsonl(Path(output_path), hard_data_list)


__all__ = [
    'process_data',
    'process_concurrently',
    'filter_out_easy_data',
    'get_data_id',
    'get_processed_data_ids',
]
