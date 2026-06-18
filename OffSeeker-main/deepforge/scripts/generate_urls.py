#!/usr/bin/env python3
"""
Stage 1: URL Generation

This script generates random nouns using LLM and searches for URLs using Serper API.

Usage:
    python scripts/generate_urls.py [--output data/urls.jsonl] [--num-nouns 100] [--urls-per-noun 10]
"""

import sys
import argparse
import json
from pathlib import Path
from typing import List, Dict
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from config import settings
from config.prompts import RANDOM_NOUNS_PROMPT
from api.caller import APICaller
from src.tools.search_tools import call_serper_api


def generate_urls(
    num_nouns: int = 5,
    urls_per_noun: int = 10,
    output_path: str = None
) -> List[Dict]:
    """Generate random nouns and search for URLs

    Args:
        num_nouns: Number of random nouns to generate
        urls_per_noun: Number of URLs to search per noun
        output_path: Path to save URLs (default: settings.paths.urls_path)

    Returns:
        List of dicts with noun and URLs
    """
    # Set default output path
    if output_path is None:
        output_path = settings.paths.urls_path

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Starting URL Generation")
    logger.info(f"  - Nouns to generate: {num_nouns}")
    logger.info(f"  - URLs per noun: {urls_per_noun}")
    logger.info(f"  - Output path: {output_file}")

    # Step 1: Generate random nouns using LLM
    logger.info(f"\nStep 1: Generating {num_nouns} random nouns...")

    prompt = RANDOM_NOUNS_PROMPT.format(batch_size=num_nouns)

    caller = APICaller(api_type="gemini", model_name=settings.api.gemini_model)
    response = caller.call_api([{"role": "user", "content": prompt}])

    # Parse generated nouns
    nouns = [line.strip() for line in response.strip().split("\n") if line.strip()]
    nouns = nouns[:num_nouns]  # Ensure we don't exceed specified count

    logger.info(f"Generated {len(nouns)} nouns")
    logger.info(f"Sample nouns: {nouns[:5]}")

    # Step 2: Search URLs for each noun
    logger.info(f"\nStep 2: Searching URLs for each noun...")

    all_results = []

    for i, noun in enumerate(nouns, 1):
        logger.info(f"[{i}/{len(nouns)}] Searching URLs for: {noun}")

        try:
            # Call Serper API (returns JSON string)
            search_results_json = call_serper_api(noun)
            search_results = json.loads(search_results_json)

            # Extract URLs from search results
            urls = []
            for result in search_results[:urls_per_noun]:
                if isinstance(result, dict) and "link" in result:
                    urls.append(result["link"])

            logger.info(f"  Found {len(urls)} URLs")

            all_results.append({
                "noun": noun,
                "urls": urls
            })

        except Exception as e:
            logger.error(f"  Error searching {noun}: {e}")

    # Step 3: Save results
    logger.info(f"\nStep 3: Saving results...")

    total_urls = 0
    with open(output_file, "w", encoding="utf-8") as f:
        for result in all_results:
            for url in result["urls"]:
                f.write(json.dumps({
                    "noun": result["noun"],
                    "url": url
                }, ensure_ascii=False) + "\n")
                total_urls += 1

    logger.info(f"\n✓ URL Generation Complete!")
    logger.info(f"  - Total nouns processed: {len(all_results)}")
    logger.info(f"  - Total URLs collected: {total_urls}")
    logger.info(f"  - Output saved to: {output_file}")

    return all_results


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Generate URLs from random nouns")
    parser.add_argument("--output", default=None, help="Output JSONL file path")
    parser.add_argument("--num-nouns", type=int, default=5, help="Number of nouns to generate")
    parser.add_argument("--urls-per-noun", type=int, default=10, help="URLs to search per noun")
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Generate URLs
    generate_urls(
        num_nouns=args.num_nouns,
        urls_per_noun=args.urls_per_noun,
        output_path=args.output
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
