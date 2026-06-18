#!/usr/bin/env python3
"""
QA Difficulty Enhancement Module WITHOUT TOOLS

Simplified version that only uses knowledge graph information to enhance questions.
No external API calls needed during enhancement.
"""

import json
from typing import Dict, Optional
from loguru import logger
import sys
from pathlib import Path

# Add deepforge to path (local copy)
deepforge_path = Path(__file__).parent / "deepforge"
sys.path.insert(0, str(deepforge_path))

# Load .env file (settings.py will handle finding the .env file)

from api.caller import APICaller
from config import settings


# ============================================================================
# PROMPT TEMPLATE
# ============================================================================

DIFFICULTY_ENHANCEMENT_SIMPLE_PROMPT = """
You are an expert at creating HIGH-ENTROPY questions that require genuine multi-hop research.

## Core Principle: MAXIMIZE INFORMATION ENTROPY

A good difficult question should have MAXIMAL SEARCH SPACE initially, then narrow down through exploration.

BAD EXAMPLES (Low entropy, easy to pinpoint):
- "China's southernmost province" → Directly points to Hainan
- "The Li ethnic minority" → Geographically specific
- "Died in 1993" → Too specific temporally
- "Catalan city" → Immediately narrows to Barcelona area

GOOD EXAMPLES (High entropy, broad search space):
- "A tropical island region in monsoon Asia" → Could be anywhere from Philippines to Indonesia
- "A cuisine emphasizing rice and seafood" → Virtually all of East/Southeast Asia
- "Late 20th century" → 30+ year range
- "A Mediterranean coastal city" → From Spain to Turkey to Israel

## Enhancement Strategies

### Strategy 1: Abstract to Super-Categories
Replace specific identifiers with the broadest possible categories.

| Specific (BAD) | Broad (GOOD) |
|--------------|-------------|
| "German geographer" | "a European earth scientist" |
| "Hainan province" | "a tropical region", "Asian cuisine" |
| "Li people" | "local inhabitants", "ethnic groups" |
| "Barcelona" | "a large coastal city", "a metropolitan area" |
| "1993" | "late 20th century", "the 1990s" |

### Strategy 2: Describe Properties Without Keywords
Describe WHAT something is, not what it's CALLED.

| Keyword (BAD) | Property Description (GOOD) |
|--------------|----------------------------|
| "white cut chicken" | "poultry poached in plain water, relying on dipping sauces for flavor" |
| "Christmas" | "a major winter holiday celebrating the birth of Christianity's central figure" |

### Strategy 3: Remove Uniquely Identifying Conditions
Delete conditions that alone can identify the answer.

| Remove If | Replace With |
|-----------|-------------|
| Specific year | "late 20th century", "early 1990s" |
| Specific location | "southern Europe", "a tropical region" |
| Unique title | "the unifying ruler" |
| Specific number | "mid-40s", "around 40-50" |

### Strategy 4: Add True-but-Not-Unique Conditions
Add conditions that are TRUE but apply to MANY entities.

Examples of good non-unique conditions:
- "A country with four distinct seasons" → True for Japan, Korea, China, and many others
- "A region that hosted Olympics" → True for dozens of cities worldwide
- "A cuisine using rice as staple" → True for most of Asia

## Current Task

Original Question: {question}
Answer: {answer}

Context: {domain} domain | {num_entities} entities in graph

## Complete Knowledge Graph

{graph_info}

Use the entity details above to:
- Extract property descriptions instead of entity names
- Find broader categories for abstraction
- Identify synonyms and related terms
- Ensure enhanced question doesn't contradict the graph information

## Instructions

1. **Apply ALL applicable enhancement strategies** to maximize entropy:
   - Abstract to super-categories
   - Use property descriptions without keywords
   - Remove uniquely identifying conditions
   - Add true-but-not-unique conditions

2. Reconstruct the question to maximize initial search space
3. Ensure the answer is still findable through exploration

## Output Format

<question>
[Your enhanced question using broad, high-entropy descriptions]
</question>

<answer>
{answer}
</answer>
"""


# ============================================================================
# ENHANCEMENT AGENT (NO TOOLS)
# ============================================================================

class SimpleEnhancementAgent:
    """Agent that enhances questions WITHOUT using external tools"""

    def __init__(self):
        self.api_caller = APICaller(api_type="gemini", model_name=settings.api.gemini_model)

    def enhance_question(
        self,
        question: str,
        answer: str,
        domain: str,
        num_entities: int,
        graph_info: str
    ) -> Optional[Dict]:
        """Enhance question using only knowledge graph information"""

        system_prompt = "You create challenging research questions by maximizing information entropy. Use the provided knowledge graph to find broad descriptive alternatives for specific terms."

        user_prompt = DIFFICULTY_ENHANCEMENT_SIMPLE_PROMPT.format(
            question=question,
            answer=answer,
            domain=domain,
            num_entities=num_entities,
            graph_info=graph_info
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            logger.info(f"Starting simple enhancement for: {question[:50]}...")
            response = self.api_caller.call_api(messages, tools=None)

            if response is None:
                logger.warning("Simple enhancement: API returned None")
                return None

            # Handle ChatCompletionMessage object
            response_content = response if isinstance(response, str) else (response.content if hasattr(response, 'content') else str(response))

            logger.debug(f"Simple enhancement: got response, length={len(response_content)}")

            # Parse response
            if "<question>" not in response_content or "<answer>" not in response_content:
                logger.warning("Simple enhancement: Invalid response format")
                logger.debug(f"Response preview: {response_content[:500]}...")
                return None

            enhanced_q = response_content.split("<question>")[1].split("</question>")[0].strip()
            enhanced_a = response_content.split("<answer>")[1].split("</answer>")[0].strip()

            logger.info(f"✓ Simple enhancement complete")

            return {
                "enhanced_question": enhanced_q,
                "enhanced_answer": enhanced_a,
                "original_question": question,
                "original_answer": answer,
                "thinking": "",  # No thinking in simple mode
                "search_summary": "Simple enhancement (no tools used)",
                "search_count": 0
            }

        except Exception as e:
            logger.error(f"Simple enhancement error: {e}")
            import traceback
            traceback.print_exc()
            return None


# ============================================================================
# MAIN FUNCTIONS
# ============================================================================

def format_graph_info(graph) -> str:
    """Format complete entity graph for prompt"""
    if not graph or not hasattr(graph, 'entity_dict'):
        return "No graph information available"

    path = getattr(graph, 'transition_path', [])
    num_entities = len(graph.entity_dict)

    # Build detailed graph info
    info_parts = [
        f"EXPLORATION GRAPH:",
        f"Total entities: {num_entities}",
        f"Exploration path: {' -> '.join(path)}",
        f"Depth: {graph.depth() if hasattr(graph, 'depth') else 'N/A'}",
        "",
        "ENTITY DETAILS:"
    ]

    # Add details for each entity
    for entity_name, entity_data in graph.entity_dict.items():
        info_parts.append(f"\n[{entity_name}]")

        if isinstance(entity_data, dict):
            # Add summary if available
            summary = entity_data.get('summary', '')
            if summary:
                # Truncate very long summaries
                if len(summary) > 500:
                    summary = summary[:500] + "..."
                info_parts.append(f"Summary: {summary}")

            # Add other key attributes
            for key, value in entity_data.items():
                if key != 'summary' and value and not key.startswith('_'):
                    value_str = str(value)
                    if len(value_str) < 200:  # Only include short values
                        info_parts.append(f"{key}: {value_str}")
        else:
            info_parts.append(str(entity_data)[:500])

    return "\n".join(info_parts)


def enhance_qa_difficulty_simple(
    question: str,
    answer: str,
    entity_graph=None,
    metadata: Optional[Dict] = None
) -> Optional[Dict]:
    """Enhance QA difficulty WITHOUT tools (simpler, faster, more reliable)"""

    domain = (metadata or {}).get('domain', 'general')
    num_entities = len(entity_graph.entity_dict) if entity_graph and hasattr(entity_graph, 'entity_dict') else 0

    graph_info = format_graph_info(entity_graph) if entity_graph else "{}"

    logger.info(f"Starting simple enhancement for: {question[:50]}...")

    try:
        agent = SimpleEnhancementAgent()
        return agent.enhance_question(
            question=question,
            answer=answer,
            domain=domain,
            num_entities=num_entities,
            graph_info=graph_info
        )

    except Exception as e:
        logger.error(f"Simple enhancement failed: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Enhance QA difficulty (simple version)")
    parser.add_argument("--question", help="Test question")
    parser.add_argument("--answer", help="Test answer")

    args = parser.parse_args()

    if args.question and args.answer:
        result = enhance_qa_difficulty_simple(args.question, args.answer)
        if result:
            print(f"Original: {args.question}")
            print()
            print(f"Enhanced: {result['enhanced_question']}")
            print()
            print(f"Answer: {result['enhanced_answer']}")
