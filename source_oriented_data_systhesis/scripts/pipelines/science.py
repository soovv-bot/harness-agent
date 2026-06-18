#!/usr/bin/env python3
"""
ScienceEntryPointGenerator - Entry Point Generator for Science Domain

This module contains the entry point generation strategies for the Science domain.
"""

import random
import sys
import requests
from pathlib import Path
from typing import Dict
from loguru import logger

# Add deepforge to path (local copy)
deepforge_path = Path(__file__).parent.parent / "deepforge"
sys.path.insert(0, str(deepforge_path))

# Import shared modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from api.caller import APICaller
from pools import ExpandedSciencePools
from apis.science_apis import WikipediaScienceClient, WikidataScienceClient, DBpediaScienceClient, NobelPrizeScienceClient, PeriodicTableClient

class ScienceEntryPointGenerator:
    """
    科学数据入口点生成器 - 使用扩展池子

    使用多种策略生成科学相关的探索入口点
    覆盖全球所有科学学科、实体、概念
    """

    def __init__(self):
        # Use expanded pools for better diversity
        self.expanded_pools = ExpandedSciencePools()

        # Initialize all strategies
        self.strategies = {
            # Basic strategies (5)
            'llm_science_concept': self.llm_generate_science_concept,
            'wikipedia_science_angle': self.wikipedia_random_with_science_angle,
            'wikipedia_science_category': self.wikipedia_random_from_category,
            'random_science_keyword': self.random_science_keyword_search,
            'dbpedia_scientist': self.dbpedia_random_scientist,

            # Wikidata strategies (5)
            'wikidata_element': self.wikidata_chemical_element,
            'wikidata_physical_law': self.wikidata_physical_law,
            'wikidata_math_concept': self.wikidata_mathematical_concept,
            'wikidata_bio_structure': self.wikidata_biological_structure,
            'wikidata_instrument': self.wikidata_scientific_instrument,

            # Entity-based strategies (3)
            'periodic_table': self.periodic_table_element,
            'nobel_science': self.nobel_science_laureate,
            'famous_scientist': self.famous_scientist_pool,

            # Concept-based strategies (2+)
            'discovery_invention': self.scientific_discovery,
            'science_institution': self.scientific_institution,
        }

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        # Use expanded Wikipedia categories
        self.SCIENCE_CATEGORIES = self.expanded_pools.get_all_categories()

        # Initialize basic clients (no API key required)
        self.wikipedia_client = WikipediaScienceClient()
        self.wikidata_client = WikidataScienceClient()
        self.dbpedia_client = DBpediaScienceClient()
        self.nobel_science_client = NobelPrizeScienceClient()
        self.periodic_table_client = PeriodicTableClient()

        num_strategies = len(self.strategies)
        logger.info(f"Initialized with {len(self.SCIENCE_CATEGORIES)} categories and {num_strategies} strategies")

    def generate_random_entry(self) -> Dict:
        """使用随机策略生成入口点"""
        strategy_name = random.choice(list(self.strategies.keys()))
        strategy_func = self.strategies[strategy_name]
        return strategy_func()

    # ========================================================================
    # Strategy 1: LLM generates scientific concept
    # ========================================================================

    def llm_generate_science_concept(self) -> Dict:
        """使用LLM生成多样化科学概念 - 强调实体和概念"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        prompt = """Generate ONE random scientific concept from ANY scientific discipline.

CRITICAL DIVERSITY REQUIREMENTS:
- Mix ALL SCIENTIFIC DISCIPLINES equally (COMPREHENSIVE LIST):
  * Physical Sciences: Physics (classical, quantum, condensed matter), Chemistry (organic, inorganic, analytical), Astronomy, Astrophysics
  * Life Sciences: Biology (cellular, molecular), Botany (plant science, agriculture, horticulture), Zoology (animal science, entomology, ornithology), Microbiology, Virology
  * Medical Sciences: Clinical medicine, Surgery, Pharmacology, Pharmacy, Pathology, Physiology, Anatomy, Neuroscience, Psychiatry, Nursing, Dentistry
  * Earth Sciences: Geology, Paleontology (fossils, dinosaurs), Oceanography, Meteorology, Climatology, Geophysics, Seismology, Volcanology
  * Formal Sciences: Mathematics (algebra, analysis, topology), Computer Science, Statistics, Logic, Information Theory
  * Engineering: Mechanical, Electrical, Civil, Chemical, Biomedical, Aerospace, Materials, Industrial
  * Agricultural Sciences: Agronomy, Crop science, Soil science, Forestry, Food science, Animal science
  * Psychological Sciences: Psychology, Cognitive science, Neuroscience, Educational psychology

- Mix TYPES OF CONCEPTS equally:
  * Entities: Elements, particles, cells, organisms, species, ecosystems, structures, objects
  * Theories: Quantum mechanics, evolution, relativity, plate tectonics, set theory
  * Laws: Newton's laws, thermodynamics, Mendel's laws, Hardy-Weinberg principle
  * Principles: Heisenberg uncertainty, natural selection, superposition
  * Equations: Schrödinger, Navier-Stokes, Michaelis-Menten
  * Phenomena: Superconductivity, photosynthesis, metamorphosis, volcanic eruption
  * Processes: Protein synthesis, nitrogen fixation, nuclear fusion, PCR
  * Structures: DNA double helix, cell membrane, crystal lattice, food web
  * Instruments: Microscope, telescope, chromatograph, spectrometer

- Mix ALL SCALE LEVELS:
  * Molecular/Atomic: Quarks, atoms, molecules, chemical bonds
  * Microscopic: Cells, organelles, bacteria, viruses
  * Organismal: Tissues, organs, organisms, behavior
  * Ecological: Populations, communities, ecosystems, biomes
  * Planetary/Cosmic: Geology, climate, planets, stars, galaxies

- Mix ALL ERAS:
  * Ancient: Classical biology, early medicine, alchemy
  * Classical: Taxonomy, genetics discovery, geological time scale
  * Modern: Antibiotics, DNA structure, plate tectonics, quantum theory
  * Contemporary: CRISPR, gravitational waves, AI in science

AVOID overused examples: E=mc², photosynthesis, DNA, evolution.

DIVERSE Examples (DO NOT use these):
- "Mycorrhizal fungi nutrient exchange" (botany/ecology)
- "K-T extinction event dinosaurs" (paleontology)
- "Phase I clinical trial design" (medical/pharmacology)
- "Chlorophyll fluorescence photosynthesis" (plant physiology)
- "Sedimentary sequence stratigraphy" (geology)
- "Doppler radar meteorology" (atmospheric science)
- "Neurotransmitter reuptake inhibition" (neuroscience/pharmacology)
- "Polyploid speciation plants" (botany/genetics)
- "Enzyme kinetics Michaelis-Menten" (biochemistry)
- "Hadal zone ocean ecology" (oceanography)
- "Operant conditioning behavior" (psychology)
- "Soil microbiome nitrogen cycling" (agricultural science)
- "Plate reconstruction paleomagnetism" (geophysics)
- "Antimicrobial resistance mechanisms" (microbiology/medicine)
- "Topological insulator surface states" (physics/materials science)

Format: Return ONLY the scientific concept name (2-5 words), nothing else.

Now generate ONE diverse scientific concept:"""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}])
            concept = response.strip()

            # Clean up common LLM artifacts
            for prefix in ["The ", "A ", "An "]:
                if concept.startswith(prefix):
                    concept = concept[len(prefix):]
            concept = concept.strip('"\'.')

            if len(concept) > 100:
                concept = concept[:100]

            logger.info(f"LLM generated science concept: {concept}")

            return {
                "title": concept,
                "source": "llm_science_concept",
                "type": "scientific_entity"
            }

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            # Fallback to expanded pools
            all_disciplines = self.expanded_pools.get_all_disciplines()
            all_entities = self.expanded_pools.get_all_entities()
            discipline = random.choice(all_disciplines)
            entity = random.choice(all_entities)
            fallback = f"{entity} {discipline}"
            return {
                "title": fallback,
                "source": "llm_science_concept",
                "type": "scientific_entity"
            }

    # ========================================================================
    # Strategy 2: Wikipedia random + scientific angle
    # ========================================================================

    def wikipedia_random_with_science_angle(self) -> Dict:
        """随机Wikipedia页面 + 从科学角度探索"""
        try:
            # Get random Wikipedia page
            url = "https://en.wikipedia.org/api/rest_v1/page/random/summary"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            original_title = data.get("title", "")
            logger.info(f"Random Wikipedia page: {original_title}")

            # Generate scientific angle
            scientific_angle = self.get_scientific_angle(original_title)

            logger.info(f"  Scientific angle: {scientific_angle}")

            return {
                "title": scientific_angle,
                "source": "wikipedia_science_angle",
                "original_title": original_title,
                "type": "scientific_entity"
            }

        except Exception as e:
            logger.error(f"Wikipedia random error: {e}")
            # Fallback
            return {
                "title": "Scientific concepts and theories",
                "source": "wikipedia_science_angle",
                "type": "scientific_entity"
            }

    def get_scientific_angle(self, title: str) -> str:
        """为任意词条生成科学相关的探索角度"""
        caller = APICaller(api_type="openai", model_name="deepseek-chat")

        prompt = f"""The Wikipedia page is about "{title}".

Generate a 2-5 word phrase that connects this topic to its SCIENTIFIC context.

Think about:
- Is this a scientific concept, theory, law, or principle?
- Is this a scientist, engineer, or researcher?
- Is this a scientific instrument, device, or tool?
- Is this a natural phenomenon with scientific explanation?
- Is this a material, substance, or chemical?
- Is this related to physics, chemistry, biology, mathematics, or engineering?
- What scientific discipline studies this?
- What scientific principles explain this?

Examples:
- "Albert Einstein" → "Einstein relativity theory"
- "Carbon" → "carbon element chemistry"
- "Rainbow" → "rainbow optical physics"
- "Bridge" → "bridge structural engineering"
- "Gravity" → "gravitational force physics"
- "DNA" → "DNA molecular biology genetics"
- "Prime number" → "prime number number theory"
- "Engine" → "heat engine thermodynamics"

For "{title}", return ONLY the 2-5 word scientific phrase, nothing else."""

        try:
            response = caller.call_api([{"role": "user", "content": prompt}])
            angle = response.strip()
            angle = angle.strip('"\'.')

            if len(angle) > 100:
                angle = angle[:100]

            return angle if angle else f"Scientific aspects of {title}"

        except Exception as e:
            logger.debug(f"Scientific angle extraction error: {e}")
            return f"Scientific aspects of {title}"

    # ========================================================================
    # Strategy 3: Wikipedia random from science categories
    # ========================================================================

    def wikipedia_random_from_category(self) -> Dict:
        """从科学相关分类中随机选择页面"""
        category = random.choice(self.SCIENCE_CATEGORIES)

        try:
            # Get pages from category using Wikipedia API
            api_url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": category,
                "cmlimit": 100,
                "cmtype": "page",
                "format": "json"
            }

            response = requests.get(api_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            members = data.get("query", {}).get("categorymembers", [])

            # Filter out subcategories
            pages = [m for m in members if m.get("ns") == 0]

            if not pages:
                logger.warning(f"No pages found in category {category}")
                return self.wikipedia_random_from_category()

            # Select random page
            page = random.choice(pages)
            title = page.get("title", "")

            logger.info(f"Selected from category '{category}': {title}")

            return {
                "title": title,
                "source": "wikipedia_science_category",
                "category": category,
                "type": "scientific_entity"
            }

        except Exception as e:
            logger.error(f"Wikipedia category error: {e}")
            # Fallback to LLM generation
            return self.llm_generate_science_concept()

    # ========================================================================
    # Strategy 4: Random scientific keyword search
    # ========================================================================

    def random_science_keyword_search(self) -> Dict:
        """使用扩展池子生成多样化科学关键词组合"""
        # Use expanded pools to generate diverse combinations
        queries = self.expanded_pools.generate_search_queries()
        search_term = random.choice(queries)

        logger.info(f"Science keyword search: {search_term}")

        return {
            "title": search_term,
            "source": "random_science_keyword",
            "type": "scientific_entity"
        }

    # ========================================================================
    # Strategy 5: DBpedia scientist
    # ========================================================================

    def dbpedia_random_scientist(self) -> Dict:
        """从DBpedia随机获取科学家"""
        try:
            # Randomly choose scientist type
            scientist_type = random.choice(['scientist', 'engineer'])
            results = []

            if scientist_type == 'scientist':
                results = self.dbpedia_client.get_scientists(limit=50)
            else:
                results = self.dbpedia_client.get_engineers(limit=50)

            if results:
                person = random.choice(results)
                name = person.get('name', '')

                logger.info(f"DBpedia {scientist_type}: {name}")

                return {
                    "title": name,
                    "source": "dbpedia_scientist",
                    "scientist_type": scientist_type,
                    "type": "scientist"
                }

        except Exception as e:
            logger.error(f"DBpedia scientist error: {e}")

        # Fallback to LLM generation
        return self.llm_generate_science_concept()

    # ========================================================================
    # Strategy 6: Wikidata chemical element
    # ========================================================================

    def wikidata_chemical_element(self) -> Dict:
        """从Wikidata随机获取化学元素"""
        try:
            elements = self.wikidata_client.get_chemical_elements()

            if elements:
                element = random.choice(elements)
                name = element.get('name', '')
                symbol = element.get('symbol', '')
                atomic_number = element.get('atomicNumber', '')

                concept = f"{name} ({symbol}) chemical element"
                if atomic_number:
                    concept = f"Element {atomic_number}: {name} ({symbol})"

                logger.info(f"Wikidata element: {name} ({symbol})")

                return {
                    "title": concept,
                    "source": "wikidata_element",
                    "name": name,
                    "symbol": symbol,
                    "atomicNumber": atomic_number,
                    "type": "chemical_element"
                }

        except Exception as e:
            logger.error(f"Wikidata element error: {e}")

        # Fallback
        return self.llm_generate_science_concept()

    # ========================================================================
    # Strategy 7: Wikidata physical law
    # ========================================================================

    def wikidata_physical_law(self) -> Dict:
        """从Wikidata随机获取物理定律"""
        try:
            laws = self.wikidata_client.get_physical_laws()

            if laws:
                law = random.choice(laws)
                name = law.get('name', '')
                field = law.get('field', '')

                concept = f"{name} {field}" if field else name

                logger.info(f"Wikidata physical law: {name}")

                return {
                    "title": concept,
                    "source": "wikidata_physical_law",
                    "name": name,
                    "field": field,
                    "type": "physical_law"
                }

        except Exception as e:
            logger.error(f"Wikidata physical law error: {e}")

        # Fallback
        return self.llm_generate_science_concept()

    # ========================================================================
    # Strategy 8: Wikidata mathematical concept
    # ========================================================================

    def wikidata_mathematical_concept(self) -> Dict:
        """从Wikidata随机获取数学概念"""
        try:
            concepts = self.wikidata_client.get_mathematical_concepts()

            if concepts:
                concept_obj = random.choice(concepts)
                name = concept_obj.get('name', '')

                logger.info(f"Wikidata math concept: {name}")

                return {
                    "title": name,
                    "source": "wikidata_math_concept",
                    "name": name,
                    "type": "mathematical_concept"
                }

        except Exception as e:
            logger.error(f"Wikidata math concept error: {e}")

        # Fallback
        return self.llm_generate_science_concept()

    # ========================================================================
    # Strategy 9: Wikidata biological structure
    # ========================================================================

    def wikidata_biological_structure(self) -> Dict:
        """从Wikidata随机获取生物结构"""
        try:
            structures = self.wikidata_client.get_biological_structures()

            if structures:
                structure = random.choice(structures)
                name = structure.get('name', '')
                struct_type = structure.get('type', '')

                concept = f"{name} biological structure"
                if struct_type:
                    concept = f"{name} {struct_type}"

                logger.info(f"Wikidata bio structure: {name}")

                return {
                    "title": concept,
                    "source": "wikidata_bio_structure",
                    "name": name,
                    "structure_type": struct_type,
                    "type": "biological_structure"
                }

        except Exception as e:
            logger.error(f"Wikidata bio structure error: {e}")

        # Fallback
        return self.llm_generate_science_concept()

    # ========================================================================
    # Strategy 10: Wikidata scientific instrument
    # ========================================================================

    def wikidata_scientific_instrument(self) -> Dict:
        """从Wikidata随机获取科学仪器"""
        try:
            instruments = self.wikidata_client.get_scientific_instruments()

            if instruments:
                instrument = random.choice(instruments)
                name = instrument.get('name', '')
                field = instrument.get('field', '')

                concept = f"{name} scientific instrument"
                if field:
                    concept = f"{name} {field}"

                logger.info(f"Wikidata instrument: {name}")

                return {
                    "title": concept,
                    "source": "wikidata_instrument",
                    "name": name,
                    "field": field,
                    "type": "scientific_instrument"
                }

        except Exception as e:
            logger.error(f"Wikidata instrument error: {e}")

        # Fallback
        return self.llm_generate_science_concept()

    # ========================================================================
    # Strategy 11: Periodic Table element
    # ========================================================================

    def periodic_table_element(self) -> Dict:
        """从周期表获取化学元素"""
        try:
            element = self.periodic_table_client.get_random_element()

            name = element.get('name', '')
            symbol = element.get('symbol', '')
            number = element.get('number', '')
            category = element.get('category', '')

            # Generate various search concepts
            concepts = [
                f"{name} ({symbol}) element properties",
                f"{name} chemical properties",
                f"{name} electron configuration",
                f"{name} {category}",
                f"Element {number}: {name} ({symbol})",
                f"{name} compounds and uses"
            ]
            concept = random.choice(concepts)

            logger.info(f"Periodic table: {name} ({symbol})")

            return {
                "title": concept,
                "source": "periodic_table",
                "name": name,
                "symbol": symbol,
                "atomicNumber": number,
                "category": category,
                "type": "chemical_element"
            }

        except Exception as e:
            logger.error(f"Periodic table error: {e}")

        # Fallback
        return self.llm_generate_science_concept()

    # ========================================================================
    # Strategy 12: Nobel Science laureate
    # ========================================================================

    def nobel_science_laureate(self) -> Dict:
        """从诺贝尔科学奖获取得主"""
        try:
            laureate = self.nobel_science_client.get_random_science_laureate()

            if laureate:
                name = laureate.get('name', '')
                category = laureate.get('category', '')
                year = laureate.get('year', '')

                # Generate search concept
                concepts = [
                    f"{name} Nobel Prize {category}",
                    f"{name} scientific contributions",
                    f"{name} {year} Nobel Prize",
                    f"{name} research and discoveries"
                ]
                concept = random.choice(concepts)

                logger.info(f"Nobel Science: {name}")

                return {
                    "title": concept,
                    "source": "nobel_science",
                    "name": name,
                    "category": category,
                    "year": year,
                    "type": "nobel_laureate"
                }

        except Exception as e:
            logger.error(f"Nobel Science error: {e}")

        # Fallback
        return self.llm_generate_science_concept()

    # ========================================================================
    # Strategy 13: Famous scientist pool
    # ========================================================================

    def famous_scientist_pool(self) -> Dict:
        """从著名科学家池中随机选择"""
        try:
            all_scientists = self.expanded_pools.FAMOUS_SCIENTISTS

            # Select random category
            category = random.choice(list(all_scientists.keys()))
            scientists = all_scientists[category]

            scientist = random.choice(scientists)

            # Generate search concept
            concepts = [
                f"{scientist} scientific contributions",
                f"{scientist} research and discoveries",
                f"{scientist} theories and principles",
                f"{scientist} {category}",
                f"{scientist} biography and legacy"
            ]
            concept = random.choice(concepts)

            logger.info(f"Famous scientist: {scientist} ({category})")

            return {
                "title": concept,
                "source": "famous_scientist",
                "scientist": scientist,
                "category": category,
                "type": "scientist"
            }

        except Exception as e:
            logger.error(f"Famous scientist pool error: {e}")

        # Fallback
        return self.llm_generate_science_concept()

    # ========================================================================
    # Strategy 14: Scientific discovery/invention
    # ========================================================================

    def scientific_discovery(self) -> Dict:
        """从科学发现/发明池中随机选择"""
        try:
            all_discoveries = []
            for discovery_list in self.expanded_pools.DISCOVERIES_INVENTIONS.values():
                all_discoveries.extend(discovery_list)

            discovery = random.choice(all_discoveries)

            # Generate search concept
            concepts = [
                f"{discovery} discovery",
                f"{discovery} scientific significance",
                f"{discovery} applications and impact",
                f"history of {discovery}",
                f"{discovery} principles and mechanisms"
            ]
            concept = random.choice(concepts)

            logger.info(f"Scientific discovery: {discovery}")

            return {
                "title": concept,
                "source": "discovery_invention",
                "discovery": discovery,
                "type": "discovery"
            }

        except Exception as e:
            logger.error(f"Discovery error: {e}")

        # Fallback
        return self.llm_generate_science_concept()

    # ========================================================================
    # Strategy 15: Scientific institution
    # ========================================================================

    def scientific_institution(self) -> Dict:
        """从科学机构池中随机选择"""
        try:
            all_institutions = []
            for inst_list in self.expanded_pools.INSTITUTIONS.values():
                all_institutions.extend(inst_list)

            institution = random.choice(all_institutions)

            # Generate search concept
            concepts = [
                f"{institution} research",
                f"{institution} scientific contributions",
                f"{institution} discoveries",
                f"{institution} facilities",
                f"{institution} history and mission"
            ]
            concept = random.choice(concepts)

            logger.info(f"Science institution: {institution}")

            return {
                "title": concept,
                "source": "science_institution",
                "institution": institution,
                "type": "institution"
            }

        except Exception as e:
            logger.error(f"Institution error: {e}")

        # Fallback
        return self.llm_generate_science_concept()


# ============================================================================
# Main Pipeline
# ============================================================================
