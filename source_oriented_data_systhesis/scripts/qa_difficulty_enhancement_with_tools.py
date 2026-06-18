#!/usr/bin/env python3
"""
QA Difficulty Enhancement Module WITH TOOLS

The LLM uses tools DURING enhancement to:
- Search for entities to find MORE DESCRIPTIVE terms
- Discover alternative ways to describe things
- Find broader categories from search results

Key: Prioritize knowledge graph descriptions, use tools only when needed.
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
from src.tools.search_tools import (
    call_serper_api,
    search_wiki,
    SEARCH_GOOGLE_SCHEMA,
    SEARCH_WIKI_SCHEMA,
)


# ============================================================================
# PROMPT TEMPLATE
# ============================================================================

DIFFICULTY_ENHANCEMENT_WITH_TOOLS_PROMPT = """
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

## Your Tools

You can use the following tools to gather more descriptive information:

- search_google: Search the web for information. **REQUIRED parameter**: query (the search query string)
- search_wiki: Search Wikipedia for information. **REQUIRED parameter**: entity (the entity name to search)

IMPORTANT: Each tool call MUST include the required parameter. For example:
- To search: {{"name": "search_google", "arguments": {{"query": "Hainan province characteristics"}}}}
- To search Wikipedia: {{"name": "search_wiki", "arguments": {{"entity": "Hainan"}}}}

Here are the complete tool schemas:
{tool_schemas}

Please output only one function call at a time in json format, enclosed by <function_call> </function_call> tags.

## Enhancement Strategies

### Strategy 1: Abstract to Super-Categories

Replace specific identifiers with the broadest possible categories.

How to use tools:
1. Search for the entity to find what broader categories it belongs to
2. Use those super-categories instead of the specific name

| Specific (BAD) | Broad (GOOD) |
|--------------|-------------|
| "Hainan province" | "a tropical region", "Asian cuisine" |
| "Li people" | "local inhabitants", "ethnic groups" |
| "Barcelona" | "a large coastal city", "a metropolitan area" |
| "1993" | "late 20th century", "the 1990s" |
| "Catalonia" | "a European region", "an autonomous area" |

### Strategy 2: Describe Properties Without Keywords

Describe WHAT something is, not what it's CALLED.

How to use tools:
1. Search for the entity to find descriptive phrases
2. Extract properties/characteristics from search results
3. Use those properties instead of the name

| Keyword (BAD) | Property Description (GOOD) |
|--------------|----------------------------|
| "white cut chicken" | "poultry poached in plain water, relying on dipping sauces for flavor" |
| "Christmas" | "a major winter holiday celebrating the birth of Christianity's central figure" |

### Strategy 3: Remove Uniquely Identifying Conditions

Delete conditions that alone can identify the answer.

How to use tools:
1. Search to verify if a condition is truly unique
2. If it's too specific, replace with broader version

| Remove If | Replace With |
|-----------|-------------|
| Specific year | "late 20th century", "early 1990s" |
| Specific location | "southern Europe", "a tropical region" |
| Unique title | "the unifying ruler" |
| Specific number | "mid-40s", "around 40-50" |

### Strategy 4: Add True-but-Not-Unique Conditions

Add conditions that are TRUE but apply to MANY entities.

How to use tools:
1. Search for the condition to see how many entities match
2. Only use if it applies broadly

Examples of good non-unique conditions:
- "A country with four distinct seasons" → True for Japan, Korea, China, and many others
- "A region that hosted Olympics" → True for dozens of cities worldwide
- "A cuisine using rice as staple" → True for most of Asia
- "A former colonial power" → True for Spain, Portugal, Britain, France, Netherlands, etc.

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

1. **FIRST check the knowledge graph** - Extract existing descriptions from the graph
   - Look for properties, characteristics, or relations in the entity details
   - Use graph descriptions if they provide sufficiently broad alternatives

2. **ONLY use tools if graph information is insufficient**
   - Use tools when graph descriptions are too specific/obvious
   - Search to find broader categories or alternative descriptions

3. **Apply ALL applicable enhancement strategies** to maximize entropy:
   - Abstract to super-categories
   - Use property descriptions without keywords
   - Remove uniquely identifying conditions
   - Add true-but-not-unique conditions

4. Reconstruct the question to maximize initial search space
5. Ensure the answer is still findable through exploration

## Output Format

<thinking>
[List the specific terms you identified and what you searched for.
Describe which strategies you applied and why.]
</thinking>

<question>
[Your enhanced question using broad, high-entropy descriptions]
</question>

<answer>
{answer}
</answer>

<tool_usage_summary>
[Summarize what you searched and what useful descriptions you found, or note that you used graph descriptions]
</tool_usage_summary>
"""


# ============================================================================
# AGENT WITH TOOLS
# ============================================================================

class EnhancementAgent:
    """Agent that uses tools to find descriptive alternatives"""

    def __init__(self):
        self.api_caller = APICaller(api_type="gemini", model_name=settings.api.gemini_model)

    def _format_tool_schemas(self) -> str:
        """Format tool schemas for prompt"""
        schemas = []
        for schema in [SEARCH_GOOGLE_SCHEMA, SEARCH_WIKI_SCHEMA]:
            # Handle both old and new schema formats
            if 'function' in schema:
                # New format with type: "function" wrapper
                func = schema['function']
                name = func['name']
                desc = func['description']
                params = func['parameters']
            else:
                # Old format
                name = schema['name']
                desc = schema['description']
                params = schema['parameters']
            schemas.append(f"- **{name}**: {desc}")
            schemas.append(f"  Parameters: {json.dumps(params, indent=2)}")
        return "\n".join(schemas)

    def execute_tool(self, function_name: str, function_args: dict) -> str:
        """Execute a tool function"""
        tool_functions = {
            "search_google": lambda: call_serper_api(function_args.get("query", "")),
            "search_wiki": lambda: search_wiki(function_args.get("entity", "")),
        }

        if function_name not in tool_functions:
            return f"Unknown tool: {function_name}"

        try:
            query = function_args.get("query", function_args.get("entity", ""))
            logger.info(f"[Enhancement Search] {function_name}: {query}")
            result = tool_functions[function_name]()
            if len(result) > 3000:
                result = result[:3000] + "\n...[truncated]"
            return result
        except Exception as e:
            logger.error(f"Tool error {function_name}: {e}")
            return f"Error: {str(e)}"

    def enhance_with_tools(
        self,
        question: str,
        answer: str,
        domain: str,
        num_entities: int,
        graph_info: str
    ) -> Optional[Dict]:
        """Enhance using tools to find descriptive alternatives"""

        system_prompt = """You create challenging research questions by maximizing information entropy. Use tools to find broad descriptive alternatives for specific terms."""

        # Format tool schemas for prompt
        tool_schemas_display = self._format_tool_schemas()

        user_prompt = DIFFICULTY_ENHANCEMENT_WITH_TOOLS_PROMPT.format(
            question=question,
            answer=answer,
            domain=domain,
            num_entities=num_entities,
            graph_info=graph_info,
            tool_schemas=tool_schemas_display
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        max_iterations = 8
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            try:
                logger.debug(f"Enhancement iteration {iteration}: calling API...")
                response = self.api_caller.call_api(messages, tools=[
                    SEARCH_GOOGLE_SCHEMA,
                    SEARCH_WIKI_SCHEMA
                ])

                if response is None:
                    logger.warning(f"Enhancement: API returned None at iteration {iteration}")
                    return None

                # Handle ChatCompletionMessage object (when tools are used)
                response_content = response.content if hasattr(response, 'content') else str(response)
                response_tool_calls = response.tool_calls if hasattr(response, 'tool_calls') else None

                logger.debug(f"Enhancement: got response, content_length={len(response_content) if response_content else 0}")

                # Check for tool calls
                if response_tool_calls:
                    try:
                        # Process tool calls from OpenAI format
                        for tool_call in response_tool_calls:
                            function_name = tool_call.function.name
                            # Parse arguments from JSON string
                            import json as json_mod
                            function_args = json_mod.loads(tool_call.function.arguments)

                            tool_result = self.execute_tool(function_name, function_args)

                            # Add assistant message with tool calls
                            messages.append({
                                "role": "assistant",
                                "content": response_content or "",
                                "tool_calls": [{
                                    "id": tool_call.id,
                                    "type": "function",
                                    "function": {
                                        "name": function_name,
                                        "arguments": tool_call.function.arguments
                                    }
                                }]
                            })
                            # Add tool result message
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": tool_result
                            })

                        continue

                    except Exception as e:
                        logger.error(f"Tool execution error: {e}")
                        continue

                # Check for legacy function_call format or final answer
                if response_content and "<function_call>" in response_content:
                    try:
                        function_call_content = response_content.split("<function_call>")[1].split("</function_call>")[0].strip()
                        function_call_data = eval(function_call_content)
                        function_name = function_call_data.get("name")
                        function_args = function_call_data.get("arguments", {})

                        tool_result = self.execute_tool(function_name, function_args)

                        messages.append({"role": "assistant", "content": response_content})
                        messages.append({
                            "role": "user",
                            "content": f"<tool_result>{tool_result}</tool_result>\n\nExtract useful descriptive phrases from these results. Continue searching for more entities if needed, then provide your final enhanced question."
                        })

                        continue

                    except Exception as e:
                        logger.error(f"Tool execution error: {e}")
                        continue

                else:
                    # Final answer
                    if not response_content or "<question>" not in response_content or "<answer>" not in response_content:
                        logger.warning(f"Enhancement: Invalid response format at iteration {iteration}")
                        logger.debug(f"Response preview: {response_content[:500] if response_content else 'None'}...")
                        return None

                    enhanced_q = response_content.split("<question>")[1].split("</question>")[0].strip()
                    enhanced_a = response_content.split("<answer>")[1].split("</answer>")[0].strip()

                    thinking = response_content.split("<thinking>")[1].split("</thinking>")[0].strip() if "<thinking>" in response_content else ""
                    search_summary = response_content.split("<tool_usage_summary>")[1].split("</tool_usage_summary>")[0].strip() if "<tool_usage_summary>" in response_content else ""

                    logger.info(f"✓ Enhanced with {iteration} searches")

                    return {
                        "enhanced_question": enhanced_q,
                        "enhanced_answer": enhanced_a,
                        "original_question": question,
                        "original_answer": answer,
                        "thinking": thinking,
                        "search_summary": search_summary,
                        "search_count": iteration
                    }

            except Exception as e:
                logger.error(f"Iteration {iteration} error: {e}")
                return None

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


def enhance_qa_difficulty_with_tools(
    question: str,
    answer: str,
    entity_graph=None,
    metadata: Optional[Dict] = None
) -> Optional[Dict]:
    """Enhance QA difficulty with tool validation"""
    # .env is loaded automatically by settings.py

    domain = (metadata or {}).get('domain', 'general')
    num_entities = len(entity_graph.entity_dict) if entity_graph and hasattr(entity_graph, 'entity_dict') else 0

    graph_info = format_graph_info(entity_graph) if entity_graph else "{}"

    logger.info(f"Starting tool-assisted enhancement for: {question[:50]}...")

    try:
        agent = EnhancementAgent()
        return agent.enhance_with_tools(
            question=question,
            answer=answer,
            domain=domain,
            num_entities=num_entities,
            graph_info=graph_info
        )

    except Exception as e:
        logger.error(f"Enhancement failed: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Enhance QA difficulty with tools")
    parser.add_argument("--question", help="Test question")
    parser.add_argument("--answer", help="Test answer")

    args = parser.parse_args()

    if args.question and args.answer:
        result = enhance_qa_difficulty_with_tools(args.question, args.answer)
        if result:
            print(f"Original: {args.question}")
            print(f"\nEnhanced: {result['enhanced_question']}")
            print(f"\nAnswer: {result['enhanced_answer']}")
            print(f"\nSearches: {result.get('search_count', 0)}")
            print(f"\nSummary: {result.get('search_summary', 'N/A')}")
