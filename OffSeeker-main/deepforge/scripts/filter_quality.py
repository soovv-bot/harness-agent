#!/usr/bin/env python3
"""
Stage 6: Filter QA pairs by quality

This script tests if questions can be answered without web search
and filters out questions that are too easy.

Usage:
    python scripts/filter_quality.py --input data/qa_pairs_enhanced.jsonl --output data/qa_pairs_hard.jsonl
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from config import settings
from src.enhancement.quality import process_concurrently, filter_out_easy_data
from loguru import logger


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Filter QA pairs by quality")
    parser.add_argument("--input", required=True, help="Input JSONL file with QA pairs")
    parser.add_argument("--output", required=True, help="Output JSONL file for hard QA pairs")
    parser.add_argument("--tmp", help="Temporary output path (default: output_path.tmp)")
    parser.add_argument("--workers", type=int, default=settings.concurrency.quality_filter_workers,
                        help="Number of worker threads")
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Set temporary path
    if args.tmp:
        tmp_output_path = args.tmp
    else:
        tmp_output_path = str(Path(args.output).parent / f"{Path(args.output).stem}.tmp.jsonl")

    # Process QA pairs
    logger.info(f"Processing QA pairs from: {args.input}")
    process_concurrently(args.input, tmp_output_path, args.workers)

    # Filter out easy data
    logger.info(f"Filtering hard QA pairs to: {args.output}")
    filter_out_easy_data(tmp_output_path, args.output)

    # Clean up temp file
    Path(tmp_output_path).unlink(missing_ok=True)

    logger.info("Quality filtering complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
