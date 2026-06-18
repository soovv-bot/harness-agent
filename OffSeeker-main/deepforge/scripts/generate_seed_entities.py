#!/usr/bin/env python3
"""
Stage 2: Seed Entity Extraction

This script crawls URL content and extracts long-tail entities using LLM.

Usage:
    python scripts/generate_seed_entities.py [--input data/urls.jsonl] [--output data/seed_entities.jsonl] [--num-urls 50]
"""

import sys
import argparse
import json
import random
from pathlib import Path
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from config import settings
from config.prompts import SIMPLE_ENTITY_EXTRACTION_PROMPT
from api.caller import APICaller
from src.tools.search_tools import get_html_content
from src.tools.file_utils import load_jsonl


def extract_entities_from_url(url: str, caller: APICaller) -> List[str]:
    """Extract entities from a single URL

    Args:
        url: URL to crawl and extract entities from
        caller: APICaller instance for LLM calls

    Returns:
        List of extracted entity names
    """
    try:
        # Crawl URL content
        content = get_html_content(url)

        if not content or len(content) < 100:
            logger.warning(f"  URL content too short or empty: {url}")
            return []

        # Use LLM to extract entities
        prompt = SIMPLE_ENTITY_EXTRACTION_PROMPT.format(content=content[:3000])
        response = caller.call_api([{"role": "user", "content": prompt}])

        # Parse extracted entities
        entities = [line.strip() for line in response.strip().split("\n") if line.strip()]

        return entities[:10]  # Limit to 10 entities per URL

    except Exception as e:
        logger.error(f"  Error processing {url}: {e}")
        return []


def generate_seed_entities(
    input_path: str = None,
    output_path: str = None,
    num_urls: int = 50,
    max_workers: int = 10
) -> List[Dict]:
    """Extract seed entities from URLs

    Args:
        input_path: Path to URLs JSONL file (default: settings.paths.urls_path)
        output_path: Path to save entities (default: settings.paths.seed_entities_path)
        num_urls: Number of URLs to process
        max_workers: Maximum number of concurrent workers

    Returns:
        List of dicts with URL and extracted entities
    """
    # Set default paths
    if input_path is None:
        input_path = settings.paths.urls_path
    if output_path is None:
        output_path = settings.paths.seed_entities_jsonl_path

    input_file = Path(input_path)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Starting Seed Entity Extraction")
    logger.info(f"  - Input file: {input_file}")
    logger.info(f"  - URLs to process: {num_urls}")
    logger.info(f"  - Output file: {output_file}")
    logger.info(f"  - Max workers: {max_workers}")

    # Step 1: Load URLs
    if not input_file.exists():
        logger.error(f"Input file not found: {input_file}")
        logger.info(f"Please run generate_urls.py first to generate URLs")
        return []

    url_data = load_jsonl(input_file)
    logger.info(f"Loaded {len(url_data)} URLs from {input_file}")

    # Randomly sample URLs if num_urls is less than total
    if num_urls < len(url_data):
        url_data = random.sample(url_data, num_urls)
        logger.info(f"Randomly sampled {num_urls} URLs")

    urls = [item["url"] for item in url_data]

    # Step 2: Extract entities concurrently
    logger.info(f"\nStep 2: Extracting entities from URLs...")

    caller = APICaller(api_type="gemini", model_name=settings.api.gemini_model)

    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(extract_entities_from_url, url, caller): url for url in urls}

        for i, future in enumerate(as_completed(futures), 1):
            url = futures[future]
            logger.info(f"[{i}/{len(urls)}] Processing: {url[:80]}...")

            try:
                entities = future.result()

                if entities:
                    logger.info(f"  Extracted {len(entities)} entities: {entities[:3]}")
                    results.append({
                        "url": url,
                        "entities": entities
                    })
                else:
                    logger.warning(f"  No entities extracted")

            except Exception as e:
                logger.error(f"  Error: {e}")

    # Step 3: Save results
    logger.info(f"\nStep 3: Saving results...")

    # Save as JSONL (one entity per line)
    total_entities = 0
    with open(output_file, "w", encoding="utf-8") as f:
        for result in results:
            for entity in result["entities"]:
                f.write(json.dumps({
                    "url": result["url"],
                    "entity": entity
                }, ensure_ascii=False) + "\n")
                total_entities += 1

    # Also save as JSON list for generate_qa.py compatibility
    all_entities = []
    for result in results:
        for entity in result["entities"]:
            all_entities.append({"name": entity})

    # Save to tmp/seed_entities.json for generate_qa.py
    seed_json_path = Path("tmp/seed_entities.json")
    seed_json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(seed_json_path, "w", encoding="utf-8") as f:
        json.dump(all_entities, f, ensure_ascii=False, indent=2)

    logger.info(f"\n✓ Seed Entity Extraction Complete!")
    logger.info(f"  - URLs processed: {len(results)}")
    logger.info(f"  - Total entities extracted: {total_entities}")
    logger.info(f"  - JSONL saved to: {output_file}")
    logger.info(f"  - JSON saved to: {seed_json_path}")

    return results


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Extract seed entities from URLs")
    parser.add_argument("--input", default=None, help="Input JSONL file with URLs")
    parser.add_argument("--output", default=None, help="Output JSONL file for entities")
    parser.add_argument("--num-urls", type=int, default=50, help="Number of URLs to process")
    parser.add_argument("--workers", type=int, default=10, help="Number of concurrent workers")
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Extract entities
    generate_seed_entities(
        input_path=args.input,
        output_path=args.output,
        num_urls=args.num_urls,
        max_workers=args.workers
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())