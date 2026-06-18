#!/usr/bin/env python3
"""
Unified Random Pipeline Framework

This module provides a unified framework for domain-specific random exploration pipelines.
All pipelines share the same core logic but have different strategies and pools.

Supported Domains:
- Historical (6 strategies)
- Geographical (6 strategies)
- Sports (8 strategies)
- Business (15+ strategies)
- Biography (12+ strategies)
- Science (15+ strategies)
- Future: Literary, etc.

Usage:
    # Historical
    python scripts/unified_pipeline.py --domain historical --num-iterations 10

    # Geographical
    python scripts/unified_pipeline.py --domain geographical --num-iterations 10

    # Business
    python scripts/unified_pipeline.py --domain business --num-iterations 10

    # Biography
    python scripts/unified_pipeline.py --domain biography --num-iterations 10

    # Science
    python scripts/unified_pipeline.py --domain science --num-iterations 10
"""

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional, Callable
from abc import ABC, abstractmethod
from loguru import logger as default_logger
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Configure logger to show DEBUG level
import logging
logging.basicConfig(level=logging.DEBUG)

logger = default_logger

# Add deepforge to path (local copy in scripts/deepforge)
deepforge_path = Path(__file__).parent / "deepforge"
sys.path.insert(0, str(deepforge_path))

from src.entities.explorers import gather_information
from src.qa_generation.generators import generate_qa_pair
from api.caller import APICaller

# Import domain-specific modules
sys.path.insert(0, str(Path(__file__).parent))
from pipelines import (
    HistoricalEntryPointGenerator,
    GeographicalEntryPointGenerator,
    SportsEntryPointGenerator,
    BusinessEntryPointGenerator,
    BiographyEntryPointGenerator,
    ScienceEntryPointGenerator,
    AcademiaEntryPointGenerator,
    CultureTraditionsEntryPointGenerator,
    ArtsEntryPointGenerator,
)


# ============================================================================
# BASE PIPELINE CLASS
# ============================================================================

class BaseRandomPipeline(ABC):
    """
    Base class for random pipelines - Unified interface for all domain pipelines

    Subclasses must implement:
    - domain_name: Domain name
    - strategies: Strategy dictionary
    - pools: Data pools
    """

    def __init__(self):
        self.strategies = {}
        self.pools = {}
        self._initialize_strategies()
        self._initialize_pools()

    @abstractmethod
    def _initialize_strategies(self):
        """Initialize strategies for this domain - Subclasses must implement"""
        pass

    @abstractmethod
    def _initialize_pools(self):
        """Initialize data pools for this domain - Subclasses must implement"""
        pass

    def get_random_entry(self) -> Dict:
        """Randomly select a strategy to get an entry point"""
        strategy_name = random.choice(list(self.strategies.keys()))
        logger.info(f"Selected strategy: {strategy_name}")

        strategy_func = self.strategies[strategy_name]
        return strategy_func()

    def generate_qa_pair(self, entry_point: Dict, enhance_difficulty: bool = True,
                         depth: int = 2, difficulty_level: str = "medium") -> Optional[Dict]:
        """
        Generate QA pair from entry point - Common logic

        Args:
            entry_point: Entry point dict with title, source, and other metadata
            enhance_difficulty: Whether to enhance question difficulty (default: True)
            depth: Exploration depth in hops (1-4, default: 2)
            difficulty_level: Difficulty level for enhancement (easy, medium, hard)

        Returns:
            QA pair dict or None
        """
        try:
            # Determine search entity
            # For angle extraction strategies, use the angle (title), not the original title
            source = entry_point.get('source', '')
            if source in ['wikipedia_geographical_angle', 'wikipedia_history_angle']:
                # Use the extracted angle as search entity
                search_entity = entry_point.get('title', '')
            elif 'original_title' in entry_point:
                # For other strategies with original_title, use title if available
                search_entity = entry_point.get('title', entry_point.get('original_title', ''))
            else:
                search_entity = entry_point.get('title') or entry_point.get('name', '')

            if not search_entity:
                logger.warning("No search entity found")
                return None

            logger.info(f"Exploring {self.domain_name} entity: {search_entity} (depth: {depth})")

            # Step 1: Exploration with entry point context
            from exploration_enhanced import gather_information_with_context
            graph = gather_information_with_context(search_entity, depth=depth, entry_point=entry_point)

            logger.info(f"  Entities discovered: {len(graph.entity_dict)}")
            logger.info(f"  Path: {' → '.join(graph.transition_path)}")

            if len(graph.entity_dict) < 2:
                logger.warning(f"  Not enough entities for QA generation")
                return None

            # Step 2: QA generation
            question, answer = generate_qa_pair(graph)

            # Step 3: Difficulty enhancement (simple version without tools)
            enhanced_question = question
            enhanced_answer = answer
            enhancement_thinking = ""
            enhancement_validation = ""

            if enhance_difficulty:
                try:
                    from qa_difficulty_enhancement_simple import enhance_qa_difficulty_simple

                    result = enhance_qa_difficulty_simple(
                        question=question,
                        answer=answer,
                        entity_graph=graph,
                        metadata={
                            "domain": self.domain_name,
                            "entry_point": search_entity,
                            "difficulty_level": difficulty_level
                        }
                    )

                    if result:
                        enhanced_question = result["enhanced_question"]
                        enhanced_answer = result["enhanced_answer"]
                        enhancement_thinking = result.get("thinking", "")
                        enhancement_validation = result.get("validation", "")
                        logger.info(f"  ✓ Difficulty enhanced ({difficulty_level}) - simple mode (no tools)")

                except Exception as e:
                    logger.warning(f"  Difficulty enhancement failed: {e}, using original")

            qa_pair = {
                "domain": self.domain_name,
                "question": enhanced_question,
                "answer": enhanced_answer,
                "original_question": question,
                "original_answer": answer,
                "entry_point": search_entity,
                "entry_source": entry_point.get('source', ''),
                "original_entry": entry_point.get('original_title', search_entity),
                "depth": graph.depth(),
                "target_depth": depth,
                "path": graph.transition_path,
                "num_entities": len(graph.entity_dict),
                "source": f"{self.domain_name}_random",
                "is_enhanced": enhance_difficulty and result is not None,
                "difficulty_level": difficulty_level,
                "enhancement_thinking": enhancement_thinking,
                "enhancement_validation": enhancement_validation
            }

            logger.info(f"  ✓ QA generated")
            logger.info(f"  Q: {enhanced_question[:150]}...")
            logger.info(f"  A: {enhanced_answer}")

            return qa_pair

        except Exception as e:
            logger.error(f"{self.domain_name} QA generation failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    @property
    @abstractmethod
    def domain_name(self) -> str:
        """Domain name - Subclasses must implement"""
        pass


# ============================================================================
# DOMAIN-SPECIFIC PIPELINES
# ============================================================================

class HistoricalRandomPipeline(BaseRandomPipeline):
    """Historical domain random pipeline"""

    def __init__(self):
        super().__init__()

    def _initialize_strategies(self):
        """Initialize historical domain strategies (6 types)"""
        gen = HistoricalEntryPointGenerator()

        self.strategies = gen.strategies

    def _initialize_pools(self):
        """Initialize historical domain data pools"""
        from pools import ExpandedHistoricalPools
        self.pools = ExpandedHistoricalPools()

    @property
    def domain_name(self) -> str:
        return "historical"


class GeographicalRandomPipeline(BaseRandomPipeline):
    """Geographical domain random pipeline"""

    def __init__(self):
        super().__init__()

    def _initialize_strategies(self):
        """Initialize geographical domain strategies (6 types)"""
        gen = GeographicalEntryPointGenerator()

        self.strategies = gen.strategies

    def _initialize_pools(self):
        """Initialize geographical domain data pools"""
        from pools import ExpandedGeographicalPools
        self.pools = ExpandedGeographicalPools()

    @property
    def domain_name(self) -> str:
        return "geographical"


class SportsRandomPipeline(BaseRandomPipeline):
    """Sports domain random pipeline"""

    def __init__(self):
        super().__init__()

    def _initialize_strategies(self):
        """Initialize sports domain strategies (8 types)"""
        gen = SportsEntryPointGenerator()

        self.strategies = gen.strategies

    def _initialize_pools(self):
        """Initialize sports domain data pools"""
        from pools import ExpandedSportsPools
        self.pools = ExpandedSportsPools()

    @property
    def domain_name(self) -> str:
        return "sports"


class BusinessRandomPipeline(BaseRandomPipeline):
    """Business domain random pipeline"""

    def __init__(self):
        super().__init__()

    def _initialize_strategies(self):
        """Initialize business domain strategies (15+ types)"""
        gen = BusinessEntryPointGenerator()

        self.strategies = gen.strategies

    def _initialize_pools(self):
        """Initialize business domain data pools"""
        from pools import ExpandedBusinessPools
        self.pools = ExpandedBusinessPools()

    @property
    def domain_name(self) -> str:
        return "business"


class BiographyRandomPipeline(BaseRandomPipeline):
    """Biography domain random pipeline"""

    def __init__(self):
        super().__init__()

    def _initialize_strategies(self):
        """Initialize biography domain strategies (12+ types)"""
        gen = BiographyEntryPointGenerator()

        self.strategies = gen.strategies

    def _initialize_pools(self):
        """Initialize biography domain data pools"""
        from pools import ExpandedBiographyPools
        self.pools = ExpandedBiographyPools()

    @property
    def domain_name(self) -> str:
        return "biography"


class ScienceRandomPipeline(BaseRandomPipeline):
    """Science & Engineering domain random pipeline"""

    def __init__(self):
        super().__init__()

    def _initialize_strategies(self):
        """Initialize science domain strategies (15+ types)"""
        gen = ScienceEntryPointGenerator()

        self.strategies = gen.strategies

    def _initialize_pools(self):
        """Initialize science domain data pools"""
        from pools import ExpandedSciencePools
        self.pools = ExpandedSciencePools()

    @property
    def domain_name(self) -> str:
        return "science"


class AcademiaRandomPipeline(BaseRandomPipeline):
    """Academia domain random pipeline"""

    def __init__(self):
        super().__init__()

    def _initialize_strategies(self):
        """Initialize academia domain strategies (16+ types)"""
        gen = AcademiaEntryPointGenerator()

        self.strategies = gen.strategies

    def _initialize_pools(self):
        """Initialize academia domain data pools"""
        from pools import ExpandedAcademiaPools
        self.pools = ExpandedAcademiaPools()

    @property
    def domain_name(self) -> str:
        return "academia"


class CultureTraditionsRandomPipeline(BaseRandomPipeline):
    """Culture & Traditions domain random pipeline"""

    def __init__(self):
        super().__init__()

    def _initialize_strategies(self):
        """Initialize culture & traditions domain strategies (15 types)"""
        gen = CultureTraditionsEntryPointGenerator()

        self.strategies = gen.strategies

    def _initialize_pools(self):
        """Initialize culture & traditions domain data pools"""
        from pools import ExpandedCultureTraditionsPools
        self.pools = ExpandedCultureTraditionsPools()

    @property
    def domain_name(self) -> str:
        return "culture_traditions"


class ArtsRandomPipeline(BaseRandomPipeline):
    """Arts domain random pipeline"""

    def __init__(self):
        super().__init__()

    def _initialize_strategies(self):
        """Initialize arts domain strategies (25+ types)"""
        gen = ArtsEntryPointGenerator()

        self.strategies = gen.strategies

    def _initialize_pools(self):
        """Initialize arts domain data pools"""
        from pools import ExpandedArtsPools
        self.pools = ExpandedArtsPools()

    @property
    def domain_name(self) -> str:
        return "arts"


# ============================================================================
# PIPELINE FACTORY
# ============================================================================

class PipelineFactory:
    """
    Pipeline Factory - Create pipeline instances based on domain name

    Supported Domains:
    - historical: Historical data (6 strategies)
    - geographical: Geographical data (6 strategies)
    - sports: Sports data (8 strategies)
    - business: Business data (15+ strategies)
    - biography: Biography data (12+ strategies)
    - science: Science & Engineering data (15+ strategies)
    - academia: Academia & Scholarly Communication (16+ strategies)
    - culture_traditions: Culture & Traditions (15 strategies)
    - arts: Arts (25+ strategies)

    Future extensions:
    - literary: Literary data
    - music: Music data
    """

    PIPELINES = {
        "historical": HistoricalRandomPipeline,
        "geographical": GeographicalRandomPipeline,
        "sports": SportsRandomPipeline,
        "business": BusinessRandomPipeline,
        "biography": BiographyRandomPipeline,
        "science": ScienceRandomPipeline,
        "academia": AcademiaRandomPipeline,
        "culture_traditions": CultureTraditionsRandomPipeline,
        "arts": ArtsRandomPipeline,
    }

    @classmethod
    def create(cls, domain: str) -> BaseRandomPipeline:
        """
        Create a pipeline instance for the specified domain

        Args:
            domain: Domain name (historical, geographical, etc.)

        Returns:
            Pipeline instance

        Raises:
            ValueError: Unsupported domain
        """
        domain = domain.lower()
        if domain not in cls.PIPELINES:
            available = ", ".join(cls.PIPELINES.keys())
            raise ValueError(f"Unsupported domain: {domain}. Available: {available}")

        pipeline_class = cls.PIPELINES[domain]
        return pipeline_class()

    @classmethod
    def list_domains(cls) -> List[str]:
        """List all supported domains"""
        return list(cls.PIPELINES.keys())

    @classmethod
    def register_pipeline(cls, domain: str, pipeline_class: type):
        """
        Register a new pipeline type

        Args:
            domain: Domain name
            pipeline_class: Pipeline class (must inherit from BaseRandomPipeline)
        """
        if not issubclass(pipeline_class, BaseRandomPipeline):
            raise TypeError(f"{pipeline_class} must inherit from BaseRandomPipeline")

        cls.PIPELINES[domain.lower()] = pipeline_class
        logger.info(f"Registered pipeline: {domain}")


# ============================================================================
# MAIN RUN FUNCTION
# ============================================================================

def _single_iteration(pipelines: Dict, iteration_id: int, enhance_difficulty: bool,
                      depth: int = 2, difficulty_level: str = "medium") -> Dict:
    """
    Execute a single iteration - randomly select domain each time

    Args:
        pipelines: Dictionary of all pipeline instances
        iteration_id: Iteration number (for logging)
        enhance_difficulty: Whether to enhance question difficulty
        depth: Exploration depth (1-4 hops)
        difficulty_level: Difficulty level (easy, medium, hard)

    Returns:
        Result dict with keys: success, qa_pair, strategy, error, iteration_id
    """
    result = {
        "iteration_id": iteration_id,
        "success": False,
        "qa_pair": None,
        "strategy": None,
        "domain": None,
        "error": None
    }

    try:
        # Step 1: Randomly select a domain for this iteration
        domain = random.choice(list(pipelines.keys()))
        pipeline = pipelines[domain]
        result['domain'] = domain

        # Step 2: Get entry point from randomly selected domain
        entry_point = pipeline.get_random_entry()
        strategy = entry_point.get('source', '')
        result['strategy'] = strategy

        # Step 3: Generate QA (with optional difficulty enhancement)
        qa_pair = pipeline.generate_qa_pair(entry_point, enhance_difficulty=enhance_difficulty,
                                              depth=depth, difficulty_level=difficulty_level)

        if qa_pair:
            result['qa_pair'] = qa_pair
            result['success'] = True
        else:
            result['error'] = "QA generation returned None"

    except Exception as e:
        logger.error(f"Iteration {iteration_id} failed: {e}")
        result['error'] = str(e)

    return result


def run_pipeline(domain: str = None, num_iterations: int = 10, output_file: str = None,
                 enhance_difficulty: bool = True, random_domain: bool = False,
                 workers: int = 1, depth: int = 2, difficulty_level: str = "medium"):
    """
    Run the random pipeline for a specified or random domain

    Args:
        domain: Domain name (historical, geographical, etc.) - Optional if random_domain=True
        num_iterations: Number of iterations
        output_file: Output file path
        enhance_difficulty: Whether to enhance question difficulty (default: True)
        random_domain: If True, randomly select a domain (overrides domain parameter)
        workers: Number of concurrent workers (default: 1, no concurrency)
        depth: Exploration depth in hops (1-4, default: 2)
        difficulty_level: Difficulty level for enhancement (easy, medium, hard, default: medium)
    """
    load_dotenv()

    # Create all pipeline instances upfront
    all_pipelines = {}
    for d in PipelineFactory.list_domains():
        all_pipelines[d] = PipelineFactory.create(d)

    # Determine mode
    use_random_per_iteration = random_domain

    if use_random_per_iteration:
        logger.info(f"🎲 Random domain PER ITERATION (mixed domains)")
        pipelines_to_use = all_pipelines
        display_domain = "Mixed"
    else:
        # Use fixed domain
        if not domain:
            domain = random.choice(PipelineFactory.list_domains())
        logger.info(f"📌 Fixed domain: {domain}")
        pipelines_to_use = {domain: all_pipelines[domain]}
        display_domain = domain

    all_qa_pairs = []
    stats = {
        "strategies": {},
        "domains": {},
        "success": 0,
        "failed": 0
    }

    output_dir = Path(__file__).parent.parent / "data"
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 70)
    logger.info(f"{display_domain.upper()} RANDOM PIPELINE")
    logger.info("=" * 70)
    logger.info(f"Iterations: {num_iterations}")
    logger.info(f"Workers: {workers} ({'concurrent' if workers > 1 else 'sequential'})")
    logger.info(f"Available pipelines: {len(all_pipelines)}")
    if use_random_per_iteration:
        logger.info(f"Mode: Random domain per iteration")
    else:
        logger.info(f"Mode: Fixed domain: {list(pipelines_to_use.keys())[0]}")
    logger.info(f"Depth: {depth} hops")
    logger.info(f"Difficulty level: {difficulty_level}")
    logger.info(f"Difficulty enhancement: {'enabled' if enhance_difficulty else 'disabled'}")
    logger.info(f"Output directory: {output_dir}")

    # Determine output file
    if not output_file:
        if use_random_per_iteration:
            output_file = output_dir / "mixed_domains_qa.jsonl"
        else:
            output_file = output_dir / f"{list(pipelines_to_use.keys())[0]}_qa.jsonl"
    else:
        # Convert string to Path object if --output was used
        output_file = Path(output_file)

    # Create output directory if needed
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Output file: {output_file}")

    # Append mode: do NOT clear existing file
    # New data will be appended to existing file
    existing_count = 0
    if output_file.exists():
        with open(output_file, "r", encoding="utf-8") as f:
            existing_count = sum(1 for _ in f)
        logger.info(f"Existing entries in file: {existing_count} (will append)")

    # Thread-safe counter for progress tracking
    progress_lock = threading.Lock()
    completed_count = {'value': 0}

    def update_progress(result: Dict):
        """Update progress and stats in a thread-safe manner"""
        with progress_lock:
            completed_count['value'] += 1
            current = completed_count['value']

            if result['success']:
                stats['success'] += 1
                all_qa_pairs.append(result['qa_pair'])
                # Save immediately to file
                try:
                    with open(output_file, "a", encoding="utf-8") as f:
                        f.write(json.dumps(result['qa_pair'], ensure_ascii=False) + "\n")
                    logger.debug(f"  → Saved to {output_file}")
                except Exception as e:
                    logger.error(f"Failed to save QA: {e}")
            else:
                stats['failed'] += 1

            if result['strategy']:
                stats['strategies'][result['strategy']] = stats['strategies'].get(result['strategy'], 0) + 1

            if result.get('domain'):
                stats['domains'][result['domain']] = stats['domains'].get(result['domain'], 0) + 1

            # Log progress
            if result['success']:
                domain_str = f" [{result['domain']}]" if result.get('domain') else ""
                logger.info(f"✓ [{current}/{num_iterations}]{domain_str} Generated QA (strategy: {result['strategy']})")
            else:
                logger.warning(f"✗ [{current}/{num_iterations}] Failed (strategy: {result.get('strategy', 'N/A')}, error: {result.get('error', 'Unknown')})")

    # Execute iterations
    if workers > 1:
        # Concurrent execution
        logger.info(f"\n🚀 Starting {num_iterations} iterations with {workers} workers...")

        with ThreadPoolExecutor(max_workers=workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(_single_iteration, pipelines_to_use, i+1, enhance_difficulty, depth, difficulty_level): i+1
                for i in range(num_iterations)
            }

            # Process results as they complete
            for future in as_completed(futures):
                result = future.result()
                update_progress(result)

    else:
        # Sequential execution (original behavior)
        for i in range(num_iterations):
            logger.info(f"\n{'#' * 35}")
            logger.info(f"# ITERATION {i+1}/{num_iterations}")
            logger.info(f"{'#' * 35}")

            result = _single_iteration(pipelines_to_use, i+1, enhance_difficulty, depth, difficulty_level)
            update_progress(result)

    # Summary
    if all_qa_pairs:
        logger.info("\n" + "=" * 70)
        logger.info("PIPELINE COMPLETED!")
        logger.info("=" * 70)
        logger.info(f"Total QA pairs: {len(all_qa_pairs)}")
        logger.info(f"Success rate: {stats['success']}/{num_iterations} "
                   f"({100*stats['success']/num_iterations:.1f}%)")
        logger.info(f"Results saved to: {output_file}")

        # Show domain distribution if using random per iteration
        if stats.get('domains') and len(stats['domains']) > 1:
            logger.info("\nDomain distribution:")
            for domain, count in sorted(stats['domains'].items(), key=lambda x: -x[1]):
                pct = 100 * count / num_iterations
                logger.info(f"  {domain:20s} {count:2d} ({pct:5.1f}%)")

        logger.info("\nStrategy distribution:")
        for strategy, count in sorted(stats['strategies'].items(), key=lambda x: -x[1]):
            pct = 100 * count / num_iterations
            logger.info(f"  {strategy:30s} {count:2d} ({pct:5.1f}%)")

        logger.info(f"\n✅ Results saved to: {output_file}")

        # Show sample
        logger.info("\nSample QA pairs (first 3):")
        for i, qa in enumerate(all_qa_pairs[:3], 1):
            logger.info(f"\n[{i}] Source: {qa['entry_source']}")
            logger.info(f"    Entry: {qa['entry_point']}")
            logger.info(f"    Q: {qa['question'][:100]}...")
            logger.info(f"    A: {qa['answer']}")
    else:
        logger.warning("No QA pairs generated")


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Unified Random Pipeline Framework for Multi-Domain QA Generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Supported Domains:
  historical    - Historical data (6 strategies: LLM, Wikipedia angle,
                   DBpedia person, DBpedia event, Wikipedia category, Keyword search)

  geographical  - Geographical data (6 strategies: LLM, Wikipedia angle,
                   Wikipedia category, Keyword search, DBpedia feature, GeoNames)

  sports        - Sports data (8 strategies: LLM, Wikipedia angle, Wikipedia category,
                   Keyword search, DBpedia sports entity, Sports statistics,
                   Official websites, Local entity pools)

  business      - Business data (15+ strategies: LLM, Wikipedia angle,
                   Wikipedia category, Keyword search, DBpedia business entities,
                   NewsAPI, Google News, Yahoo Finance, Wikidata companies,
                   Fortune lists, SEC filings, World Bank, FRED,
                   Bloomberg, Reuters, Forbes, CNBC, Business Insider,
                   TechCrunch, Yahoo Finance Web, Fortune website, HBR)

  biography     - Biography data (12+ strategies: LLM, Wikipedia angle,
                   Wikipedia category, Keyword search, DBpedia people,
                   Wikidata politicians, Wikidata scientists, Wikidata artists,
                   Wikidata Nobel laureates, Nobel Prize API, Award winners,
                   Biography.com, Famous person pools)

  science       - Science & Engineering data (15+ strategies: LLM, Wikipedia angle,
                   Wikipedia category, Keyword search, DBpedia scientists,
                   Wikidata elements, Wikidata physical laws, Wikidata math concepts,
                   Wikidata bio structures, Wikidata instruments,
                   Periodic table elements, Nobel science prizes,
                   Famous scientists, Scientific discoveries/inventions,
                   Science institutions)

  academia      - Academia & Scholarly Communication (16+ strategies: OpenAlex papers/authors/institutions/concepts,
                   Semantic Scholar papers/authors, ArXiv preprints, PubMed articles,
                   Crossref works, ROR organizations, DOAJ journals,
                   LLM academic concepts, Wikipedia academic categories,
                   Academic keywords, Famous scholars, Academic venues)

  culture_traditions - Culture & Traditions (15 strategies: UNESCO heritage sites/intangible heritage,
                   Wikidata festivals/clothing/food/music/practices/folk art,
                   Wikipedia culture categories, LLM cultural concepts,
                   Festival/practice/food/music entity pools, Cultural keywords,
                   DBpedia festivals/traditions, Holiday API global holidays)

  arts          - Arts (25+ strategies: LLM arts concepts, Wikipedia arts angle/categories,
                   DBpedia artists/works/movements, Famous artists and works pools,
                   Met Museum, MusicBrainz, Open Library, TMDb, MoMA, Rijksmuseum,
                   Artsy, Saatchi Art, Behance, DeviantArt, AllMusic, Bandcamp,
                   RateYourMusic, Goodreads, Poetry Foundation, IMDb, Letterboxd,
                   MUBI, ArchDaily, Dezeen, Materials and techniques exploration)

Examples:
  # Run historical pipeline with 10 iterations
  python scripts/unified_pipeline.py --domain historical --num-iterations 10

  # Run geographical pipeline with 20 iterations
  python scripts/unified_pipeline.py --domain geographical --num-iterations 20

  # Run with RANDOM domain selection
  python scripts/unified_pipeline.py --random-domain --num-iterations 20

  # Run sports pipeline with 15 iterations
  python scripts/unified_pipeline.py --domain sports --num-iterations 15

  # Run business pipeline with 25 iterations
  python scripts/unified_pipeline.py --domain business --num-iterations 25

  # Run biography pipeline with 30 iterations
  python scripts/unified_pipeline.py --domain biography --num-iterations 30

  # Run science pipeline with 20 iterations
  python scripts/unified_pipeline.py --domain science --num-iterations 20

  # Run academia pipeline with 15 iterations
  python scripts/unified_pipeline.py --domain academia --num-iterations 15

  # Run culture_traditions pipeline with 20 iterations
  python scripts/unified_pipeline.py --domain culture_traditions --num-iterations 20

  # Run arts pipeline with 25 iterations
  python scripts/unified_pipeline.py --domain arts --num-iterations 25

  # Save to specific file
  python scripts/unified_pipeline.py --domain science --output data/batch_50.jsonl
        """
    )

    parser.add_argument(
        "--domain",
        type=str,
        default=None,
        choices=PipelineFactory.list_domains(),
        help="Domain to process (historical, geographical, etc.) - Not required if using --random-domain"
    )

    parser.add_argument(
        "--random-domain",
        action="store_true",
        help="Randomly select a domain (overrides --domain)"
    )

    parser.add_argument(
        "--num-iterations",
        type=int,
        default=10,
        help="Number of random iterations (default: 10)"
    )

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path (default: data/{domain}_qa.jsonl)"
    )

    parser.add_argument(
        "--no-enhance",
        action="store_true",
        help="Disable difficulty enhancement (keep original questions)"
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of concurrent workers (default: 1, no concurrency). Use 2-8 for faster processing"
    )

    parser.add_argument(
        "--depth",
        type=int,
        default=2,
        choices=[1, 2, 3, 4],
        help="Exploration depth in hops (default: 2). Higher = more complex questions"
    )

    parser.add_argument(
        "--difficulty-level",
        type=str,
        default="medium",
        choices=["easy", "medium", "hard"],
        help="Difficulty level for enhancement (default: medium). easy=light abstraction, medium=default, hard=maximum entropy"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.random_domain and not args.domain:
        parser.error("Either --domain or --random-domain must be specified")

    if args.workers < 1:
        parser.error("--workers must be at least 1")

    run_pipeline(
        domain=args.domain,
        num_iterations=args.num_iterations,
        output_file=args.output,
        enhance_difficulty=not args.no_enhance,
        random_domain=args.random_domain,
        workers=args.workers,
        depth=args.depth,
        difficulty_level=args.difficulty_level
    )


if __name__ == "__main__":
    main()
