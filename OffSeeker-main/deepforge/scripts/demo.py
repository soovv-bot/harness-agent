"""
Demonstrate the complete 4-step pipeline and save intermediate results to data/show_case/

Step 1: URL Generation - Generate random nouns, search for URLs
Step 2: Seed Entity Extraction - Crawl URL content, extract long-tail entities
Step 3: Entity Graph & QA Generation - Build entity graphs, generate QA pairs
Step 4: Difficulty Enhancement - Enhance QA difficulty
"""

import os
import sys
import json
import random
from pathlib import Path
from typing import List, Dict
from loguru import logger

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from config.prompts import RANDOM_NOUNS_PROMPT, SIMPLE_ENTITY_EXTRACTION_PROMPT
from api.caller import APICaller
from src.tools.search_tools import call_serper_api, get_html_content


# ==================== Output Path Configuration ====================
OUTPUT_DIR = Path("data/show_case")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ==================== Step 1: URL Generation ====================
def step1_url_generation(num_nouns: int = 5, urls_per_noun: int = 3):
    """
    Step 1: Generate random nouns, use Serper API to search for URLs

    Args:
        num_nouns: Number of nouns to generate
        urls_per_noun: Number of URLs to search per noun

    Returns:
        List[Dict]: [{"noun": str, "urls": [str, ...]}, ...]
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Step 1: URL Generation - Generate {num_nouns} nouns, search {urls_per_noun} URLs per noun")
    logger.info(f"{'='*60}\n")

    # Use LLM to generate random nouns
    prompt = RANDOM_NOUNS_PROMPT.format(batch_size=num_nouns)

    caller = APICaller(api_type="gemini", model_name=settings.api.gemini_model)
    response = caller.call_api([{"role": "user", "content": prompt}])

    # Parse generated nouns
    nouns = [line.strip() for line in response.strip().split("\n") if line.strip()]
    nouns = nouns[:num_nouns]  # Ensure we don't exceed specified count

    logger.info(f"Generated nouns: {nouns}\n")

    # Search URLs for each noun
    results = []

    for noun in nouns:
        logger.info(f"Searching noun: {noun}")

        try:
            # Call Serper API (returns JSON string)
            search_results_json = call_serper_api(noun)
            search_results = json.loads(search_results_json)

            # Extract URLs from search results
            urls = []
            for result in search_results[:urls_per_noun]:
                if isinstance(result, dict) and "link" in result:
                    urls.append(result["link"])

            logger.info(f"  Found {len(urls)} URLs: {urls[:3]}...")

            results.append({
                "noun": noun,
                "urls": urls
            })

        except Exception as e:
            logger.error(f"  Error searching {noun}: {e}")

    # Save results
    output_file = OUTPUT_DIR / "step1_urls.jsonl"
    with open(output_file, "w", encoding="utf-8") as f:
        for result in results:
            for url in result["urls"]:
                f.write(json.dumps({
                    "noun": result["noun"],
                    "url": url
                }, ensure_ascii=False) + "\n")

    logger.info(f"\nStep 1 Complete! Collected {len([u for r in results for u in r['urls']])} URLs")
    logger.info(f"Results saved to: {output_file}\n")

    return results


# ==================== Step 2: Seed Entity Extraction ====================
def step2_entity_extraction(num_urls: int = 3):
    """
    Step 2: Crawl URL content, use LLM to extract long-tail entities

    Args:
        num_urls: Number of URLs to process

    Returns:
        List[Dict]: [{"url": str, "entities": [str, ...]}, ...]
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Step 2: Seed Entity Extraction - Process {num_urls} URLs, extract long-tail entities")
    logger.info(f"{'='*60}\n")

    # Read Step 1 output
    input_file = OUTPUT_DIR / "step1_urls.jsonl"
    if not input_file.exists():
        logger.error(f"File not found: {input_file}, please run Step 1 first")
        return []

    urls = []
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            urls.append(data["url"])

    # Randomly sample specified number of URLs
    urls = random.sample(urls, min(num_urls, len(urls)))

    results = []

    for url in urls:
        logger.info(f"Processing URL: {url}")

        try:
            # Crawl URL content
            content = get_html_content(url)
            logger.info(f"  Content length: {len(content)} characters")

            # Use LLM to extract entities
            prompt = SIMPLE_ENTITY_EXTRACTION_PROMPT.format(content=content[:3000])

            caller = APICaller(api_type="gemini", model_name=settings.api.gemini_model)
            response = caller.call_api([{"role": "user", "content": prompt}])

            # Parse extracted entities
            entities = [line.strip() for line in response.strip().split("\n") if line.strip()]
            entities = entities[:10]  # Limit quantity

            logger.info(f"  Extracted {len(entities)} entities: {entities[:5]}...")

            results.append({
                "url": url,
                "entities": entities
            })

        except Exception as e:
            logger.error(f"  Error processing {url}: {e}")

    # Save results
    output_file = OUTPUT_DIR / "step2_entities.jsonl"
    with open(output_file, "w", encoding="utf-8") as f:
        for result in results:
            for entity in result["entities"]:
                f.write(json.dumps({
                    "url": result["url"],
                    "entity": entity
                }, ensure_ascii=False) + "\n")

    # Also save as tmp/seed_entities.json format (for Step 3 use)
    all_entities = []
    for result in results:
        for entity in result["entities"]:
            all_entities.append({"name": entity})

    seed_file = Path("tmp/seed_entities.json")
    seed_file.parent.mkdir(parents=True, exist_ok=True)
    with open(seed_file, "w", encoding="utf-8") as f:
        json.dump(all_entities, f, ensure_ascii=False, indent=2)

    logger.info(f"\nStep 2 Complete! Extracted {len([e for r in results for e in r['entities']])} entities")
    logger.info(f"Results saved to: {output_file}")
    logger.info(f"Seed entities saved to: {seed_file}\n")

    return results


# ==================== Step 3: Entity Graph & QA Generation ====================
def step3_qa_generation(num_entities: int = 2):
    """
    Step 3: Read entities, use web exploration to build entity graphs, generate QA pairs

    Args:
        num_entities: Number of entities to process

    Returns:
        Tuple[List[Dict], List[Dict]]: (entity_graphs, qa_pairs)
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Step 3: Entity Graph & QA Generation - Process {num_entities} entities")
    logger.info(f"{'='*60}\n")

    # Read entities
    seed_file = Path("tmp/seed_entities.json")
    if not seed_file.exists():
        logger.error(f"File not found: {seed_file}, please run Step 2 first")
        return [], []

    with open(seed_file, "r", encoding="utf-8") as f:
        seed_entities = json.load(f)

    # Randomly sample specified number of entities
    seed_entities = random.sample(seed_entities, min(num_entities, len(seed_entities)))

    # Import entity exploration and QA generation modules
    from src.entities.explorers import gather_information
    from src.qa_generation.generators import generate_qa_pair

    entity_graphs = []
    qa_pairs = []

    for seed_data in seed_entities:
        seed_entity = seed_data["name"]
        logger.info(f"\nProcessing entity: {seed_entity}")

        try:
            # Step 3a: Build Entity Graph
            logger.info(f"  [3a] Building Entity Graph...")
            entity_graph = gather_information(seed_entity, depth=2)

            logger.info(f"    Graph contains {len(entity_graph.entity_dict)} entities")
            logger.info(f"    Transition path: {entity_graph.transition_path}")

            # Save entity graph
            entity_graphs.append(entity_graph.to_dict())

            # Step 3b: Generate QA Pair
            logger.info(f"  [3b] Generating QA Pair...")
            question, answer = generate_qa_pair(entity_graph)

            if question and answer:
                qa_pair = {
                    "question": question,
                    "answer": answer,
                    "entity": seed_entity,
                    "depth": entity_graph.depth()
                }
                qa_pairs.append(qa_pair)

                logger.info(f"    Question: {question[:100]}...")
                logger.info(f"    Answer: {answer}")

        except Exception as e:
            logger.error(f"  Error processing entity {seed_entity}: {e}")
            import traceback
            traceback.print_exc()

    # Save entity graphs
    graphs_file = OUTPUT_DIR / "step3_entity_graphs.jsonl"
    with open(graphs_file, "w", encoding="utf-8") as f:
        for graph in entity_graphs:
            f.write(json.dumps(graph, ensure_ascii=False) + "\n")

    # Save QA pairs
    qa_file = OUTPUT_DIR / "step3_qa_pairs.jsonl"
    with open(qa_file, "w", encoding="utf-8") as f:
        for qa in qa_pairs:
            f.write(json.dumps(qa, ensure_ascii=False) + "\n")

    logger.info(f"\nStep 3 Complete!")
    logger.info(f"  - Built {len(entity_graphs)} Entity Graphs")
    logger.info(f"  - Generated {len(qa_pairs)} QA Pairs")
    logger.info(f"  - Entity Graphs saved to: {graphs_file}")
    logger.info(f"  - QA Pairs saved to: {qa_file}\n")

    return entity_graphs, qa_pairs


# ==================== Step 4: Difficulty Enhancement ====================
def step4_difficulty_enhancement():
    """
    Step 4: Enhance QA pair difficulty, make questions more vague

    Returns:
        List[Dict]: enhanced_qa_pairs
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Step 4: Difficulty Enhancement - Enhance QA difficulty")
    logger.info(f"{'='*60}\n")

    # Read Step 3 output
    input_file = OUTPUT_DIR / "step3_qa_pairs.jsonl"
    if not input_file.exists():
        logger.error(f"File not found: {input_file}, please run Step 3 first")
        return []

    qa_pairs = []
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            qa_pairs.append(json.loads(line))

    logger.info(f"Loaded {len(qa_pairs)} QA pairs\n")

    # Import difficulty enhancement module
    from src.enhancement.difficulty import difficulty_enhancement

    enhanced_qa_pairs = []

    for i, qa in enumerate(qa_pairs):
        logger.info(f"Enhancing QA {i+1}/{len(qa_pairs)}")
        logger.info(f"  Original question: {qa['question'][:80]}...")

        try:
            # difficulty_enhancement requires extra_info field
            qa_with_extra = {
                **qa,
                "extra_info": {}  # Simplified handling, should actually contain entity graph
            }

            enhanced_question, enhanced_answer = difficulty_enhancement(qa_with_extra)

            if enhanced_question and enhanced_answer:
                enhanced_qa_pairs.append({
                    "question": enhanced_question,
                    "answer": enhanced_answer,
                    "entity": qa["entity"],
                    "depth": qa["depth"]
                })
                logger.info(f"  Enhanced question: {enhanced_question[:80]}...")
            else:
                # If enhancement fails, keep original QA
                enhanced_qa_pairs.append(qa)
                logger.info(f"  Enhancement failed, keeping original question")

        except Exception as e:
            logger.error(f"  Error enhancing QA: {e}")
            # If enhancement fails, keep original QA
            enhanced_qa_pairs.append(qa)

    # Save enhanced QA pairs
    output_file = OUTPUT_DIR / "step4_qa_enhanced.jsonl"
    with open(output_file, "w", encoding="utf-8") as f:
        for qa in enhanced_qa_pairs:
            f.write(json.dumps(qa, ensure_ascii=False) + "\n")

    logger.info(f"\nStep 4 Complete! Enhanced {len(enhanced_qa_pairs)} QA pairs")
    logger.info(f"Results saved to: {output_file}\n")

    return enhanced_qa_pairs


# ==================== Main ====================
def main():
    """Main flow: Execute four steps sequentially"""
    logger.info(f"\n{'#'*60}")
    logger.info(f"# DeepForge Pipeline Demo")
    logger.info(f"# All intermediate results will be saved to: {OUTPUT_DIR}")
    logger.info(f"{'#'*60}\n")

    # Step 1: URL Generation
    step1_results = step1_url_generation(num_nouns=5, urls_per_noun=3)

    # Step 2: Entity Extraction
    step2_results = step2_entity_extraction(num_urls=3)

    # Step 3: Entity Graph & QA Generation
    step3_graphs, step3_qa = step3_qa_generation(num_entities=2)

    # Step 4: Difficulty Enhancement
    step4_enhanced = step4_difficulty_enhancement()

    logger.info(f"\n{'#'*60}")
    logger.info(f"# All Steps Complete!")
    logger.info(f"# Results saved in: {OUTPUT_DIR}/")
    logger.info(f"{'#'*60}\n")

    # Print summary
    logger.info("Pipeline Summary:")
    logger.info(f"  Step 1 - URLs: {len([u for r in step1_results for u in r['urls']])}")
    logger.info(f"  Step 2 - Entities: {len([e for r in step2_results for e in r['entities']])}")
    logger.info(f"  Step 3 - Entity Graphs: {len(step3_graphs)}")
    logger.info(f"  Step 3 - QA Pairs: {len(step3_qa)}")
    logger.info(f"  Step 4 - Enhanced: {len(step4_enhanced)}")


if __name__ == "__main__":
    main()