#!/usr/bin/env python3
"""Test script for OpenAI-compatible tool calling with DeepSeek API"""

import sys
import json
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

from api.caller import APICaller
from config.prompts import DEFAULT_SYSTEM_PROMPT
from loguru import logger


# Tool schemas in OpenAI format
SEARCH_GOOGLE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_google",
        "description": "Search Google for information",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string"
                }
            },
            "required": ["query"]
        }
    }
}

SEARCH_WIKI_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_wiki",
        "description": "Search Wikipedia for information about an entity",
        "parameters": {
            "type": "object",
            "properties": {
                "entity": {
                    "type": "string",
                    "description": "Entity name to search on Wikipedia"
                }
            },
            "required": ["entity"]
        }
    }
}

CRAWL_URL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "crawl_url_content",
        "description": "Crawl and extract content from a URL",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to crawl"
                }
            },
            "required": ["url"]
        }
    }
}


def execute_tool(function_name: str, function_args: dict) -> str:
    """Execute a tool function"""
    from src.tools.search_tools import call_serper_api, get_html_content, search_wiki

    tool_functions = {
        "search_google": lambda: call_serper_api(function_args.get("query", "")),
        "crawl_url_content": lambda: get_html_content(function_args.get("url", "")),
        "search_wiki": lambda: search_wiki(function_args.get("entity", "")),
    }

    if function_name not in tool_functions:
        return f"Unknown tool: {function_name}"

    try:
        logger.info(f"Executing tool `{function_name}` with args: {function_args}")
        result = tool_functions[function_name]()
        # Truncate result if too long
        if isinstance(result, str) and len(result) > 500:
            result = result[:500] + "..."
        return result
    except Exception as e:
        logger.error(f"Error executing tool {function_name}: {e}")
        return f"Error: {str(e)}"


def test_tool_calling():
    """Test tool calling with DeepSeek API"""

    # Initialize API caller with DeepSeek
    api_caller = APICaller(api_type="gemini", model_name="deepseek-chat")

    # Tool schemas
    tool_schemas = [SEARCH_GOOGLE_SCHEMA, SEARCH_WIKI_SCHEMA, CRAWL_URL_SCHEMA]

    # Test prompt
    prompt = "Search for information about 'Tesla Inc' and tell me what it is."

    # Initialize conversation
    messages = [
        {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]

    logger.info("=" * 70)
    logger.info("Testing OpenAI-compatible Tool Calling with DeepSeek API")
    logger.info("=" * 70)
    logger.info(f"Prompt: {prompt}")
    logger.info(f"Available tools: {[s['function']['name'] for s in tool_schemas]}")
    logger.info("")

    max_iterations = 5
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        logger.info(f"\n--- Iteration {iteration}/{max_iterations} ---")

        try:
            # Call API with tools
            response_message = api_caller.call_api(messages, tools=tool_schemas)

            if response_message is None:
                logger.error("API returned None")
                break

            response_content = response_message.content
            tool_calls = response_message.tool_calls

            if response_content:
                logger.info(f"Response: {response_content[:200]}...")
            else:
                logger.info("Response: [empty]")

            if tool_calls:
                logger.info(f"Tool calls: {len(tool_calls)}")

                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    try:
                        function_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse tool arguments: {e}")
                        function_args = {}

                    logger.info(f"  → {function_name}({function_args})")

                    # Execute tool
                    tool_result = execute_tool(function_name, function_args)
                    logger.info(f"  Result: {tool_result[:200]}...")

                    # Add assistant response to conversation
                    messages.append({"role": "assistant", "content": response_content, "tool_calls": [tool_call]})

                    # Add tool result with tool_call_id
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": tool_result
                    })

                # Continue to next iteration
                continue

            else:
                # Final answer
                logger.info("\n" + "=" * 70)
                logger.info("FINAL ANSWER (no more tool calls)")
                logger.info("=" * 70)
                logger.info(f"\n{response_content}\n")
                break

        except Exception as e:
            logger.error(f"Error in iteration {iteration}: {e}")
            import traceback
            traceback.print_exc()
            break

    if iteration >= max_iterations:
        logger.warning(f"Reached max iterations ({max_iterations})")


if __name__ == "__main__":
    test_tool_calling()
