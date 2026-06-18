#!/usr/bin/env python3
"""
Stage 5: Enhance QA pair difficulty

This script makes questions more vague and ambiguous to increase difficulty.

Usage:
    python scripts/enhance_difficulty.py --input data/qa_pairs_all.jsonl --output data/qa_pairs_enhanced.jsonl
"""

import sys
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from config import settings
from src.enhancement.difficulty import difficulty_enhancement
from src.tools.file_utils import load_jsonl
from loguru import logger


def process_concurrently(data_list: list, output_path: str, max_workers: int = 10):
    """Process QA pairs concurrently to enhance difficulty

    Args:
        data_list: List of QA pair dictionaries
        output_path: Path to save enhanced QA pairs
        max_workers: Maximum number of worker threads
    """
    output_path_obj = Path(output_path)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(difficulty_enhancement, data, str(output_path_obj))
            for data in data_list
        ]

        for future in tqdm(futures, total=len(data_list), desc="Enhancing difficulty"):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Error processing QA pair: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Enhance QA pair difficulty")
    parser.add_argument("--input", required=True, help="Input JSONL file with QA pairs")
    parser.add_argument("--output", required=True, help="Output JSONL file for enhanced pairs")
    parser.add_argument("--workers", type=int, default=settings.concurrency.difficulty_enhancement_workers,
                        help="Number of worker threads")
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Load input data
    logger.info(f"Loading data from: {args.input}")
    data_list = load_jsonl(Path(args.input))
    logger.info(f"Loaded {len(data_list)} QA pairs")

    # Process
    process_concurrently(data_list, args.output, args.workers)

    logger.info("Difficulty enhancement complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
