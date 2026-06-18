"""Gemini Agent with tool use capabilities

This module provides an agent that uses the Gemini model with
function calling capabilities for web exploration.
"""

import json
from typing import List, Dict, Optional
import tiktoken

from loguru import logger
from deepforge.config import settings
from deepforge.config.prompts import DEFAULT_SYSTEM_PROMPT
from deepforge.api.caller import APICaller
from deepforge.src.tools.search_tools import (
    call_serper_api,
    get_html_content,
    search_wiki,
)


# Maximum context length for DeepSeek (conservative estimate)
MAX_CONTEXT_LENGTH = 120000  # Leave some buffer
TRUNCATION_THRESHOLD = 100000  # Start truncating at this point

# Tool result length limits (in characters)
TOOL_RESULT_MAX_LENGTH = 10000  # Truncate each tool result to this many characters


def count_tokens(messages: List[Dict]) -> int:
    """Count tokens in messages using tiktoken

    Args:
        messages: List of message dictionaries

    Returns:
        Estimated token count
    """
    try:
        # Use cl100k_base encoding (same as GPT-4)
        encoding = tiktoken.get_encoding("cl100k_base")
        total = 0
        for msg in messages:
            # Count tokens in content
            if isinstance(msg.get("content"), str):
                total += len(encoding.encode(msg["content"]))
            # Count tokens in tool calls
            if "tool_calls" in msg:
                for tc in msg["tool_calls"]:
                    if tc.function and tc.function.name:
                        total += len(encoding.encode(tc.function.name))
                    if tc.function and tc.function.arguments:
                        total += len(encoding.encode(tc.function.arguments))
        return total
    except Exception:
        # Fallback: rough estimate (1 token ≈ 4 characters)
        return sum(len(str(msg.get("content", ""))) for msg in messages) // 4


class GeminiAgent:
    """Agent that uses Gemini with tools for web exploration

    This agent can call functions (tools) to search the web, crawl URLs,
    and search Wikipedia. It runs in a loop until a final result is produced.

    Attributes:
        messages: Conversation history
        tool_schemas: List of available tool schemas
        api_caller: API caller for Gemini
    """

    def __init__(self, tool_schemas: Optional[List[dict]] = None):
        """Initialize the GeminiAgent

        Args:
            tool_schemas: List of tool schemas for function calling
        """
        self.messages = []
        self.tool_schemas = tool_schemas or []
        self.api_caller = self._create_api_caller()

    def _create_api_caller(self) -> APICaller:
        """Create API caller for Gemini"""
        return APICaller(api_type="gemini", model_name=settings.api.gemini_model)

    def execute_tool(self, function_name: str, function_args: dict) -> str:
        """Execute a tool function

        Args:
            function_name: Name of the tool to execute
            function_args: Arguments to pass to the tool

        Returns:
            Result of the tool execution
        """
        tool_functions = {
            "search_google": lambda: call_serper_api(function_args.get("query", "")),
            "crawl_url_content": lambda: get_html_content(function_args.get("url", "")),
            "search_wiki": lambda: search_wiki(function_args.get("entity", "")),
        }

        if function_name not in tool_functions:
            return f"Unknown tool: {function_name}"

        try:
            logger.debug(f"Executing tool `{function_name}` with args: {function_args}")
            result = tool_functions[function_name]()

            # Truncate result if too long to prevent context overflow
            if isinstance(result, str) and len(result) > TOOL_RESULT_MAX_LENGTH:
                original_length = len(result)
                result = result[:TOOL_RESULT_MAX_LENGTH]
                result += f"\n\n[Content truncated from {original_length} to {TOOL_RESULT_MAX_LENGTH} characters]"
                logger.debug(f"Truncated {function_name} result from {original_length} to {TOOL_RESULT_MAX_LENGTH} characters")

            return result
        except Exception as e:
            logger.error(f"Error executing tool {function_name}: {e}")
            return f"Error: {str(e)}"

    def reset(self):
        """Reset conversation history"""
        self.messages = []

    def _truncate_messages_if_needed(self):
        """Truncate message history if approaching context length limit

        Keeps system prompt, first user message, and recent messages.
        Removes middle messages (tool calls and results) to reduce length.
        """
        token_count = count_tokens(self.messages)

        if token_count > TRUNCATION_THRESHOLD:
            logger.warning(f"Context length {token_count} exceeds threshold {TRUNCATION_THRESHOLD}, truncating...")

            # Keep system prompt (index 0)
            system_msg = self.messages[0] if self.messages and self.messages[0].get("role") == "system" else None

            # Keep first user message (index 1 or 0 if no system)
            first_user_idx = 0 if system_msg is None else 1
            first_user_msg = self.messages[first_user_idx] if first_user_idx < len(self.messages) else None

            # Keep last N messages (most recent context)
            keep_recent = 10  # Keep last 10 messages
            recent_messages = self.messages[-keep_recent:] if len(self.messages) > keep_recent else []

            # Rebuild messages list
            new_messages = []
            if system_msg:
                new_messages.append(system_msg)
            if first_user_msg:
                new_messages.append(first_user_msg)
            new_messages.extend(recent_messages)

            self.messages = new_messages
            new_token_count = count_tokens(self.messages)
            logger.info(f"Truncated messages from {token_count} to {new_token_count} tokens")

    def run_loop(self, prompt: str) -> Optional[str]:
        """Run agent loop until final result is produced

        The agent will:
        1. Send the prompt to the model
        2. If the model calls a tool, execute it and continue
        3. Repeat until the model produces a final answer

        Args:
            prompt: Initial prompt to send

        Returns:
            Final response from the model, or None if error
        """
        # Initialize conversation
        self.messages = [
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        max_iterations = 20  # Prevent infinite loops
        iteration = 0

        logger.debug(f"Starting agent loop with {len(self.tool_schemas)} tools")

        while iteration < max_iterations:
            iteration += 1

            try:
                # Truncate messages if approaching context limit
                self._truncate_messages_if_needed()

                logger.debug(f"Agent iteration {iteration}/{max_iterations}, messages: {len(self.messages)}")

                response_message = self.api_caller.call_api(self.messages, tools=self.tool_schemas)

                if response_message is None:
                    logger.error("API returned None")
                    return None

                # Get response content and tool calls
                response_content = response_message.content
                tool_calls = response_message.tool_calls

                logger.debug(f"Response content length: {len(response_content) if response_content else 0}")
                logger.debug(f"Tool calls: {len(tool_calls) if tool_calls else 0}")

                # Check if model wants to call tools
                if tool_calls:
                    # Process each tool call
                    for tool_call in tool_calls:
                        function_name = tool_call.function.name
                        # Parse arguments from JSON string
                        try:
                            function_args = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse tool arguments: {e}")
                            function_args = {}

                        logger.debug(f"Calling tool `{function_name}` with args: {function_args}")

                        # Execute the tool
                        tool_result = self.execute_tool(function_name, function_args)

                        # Add assistant response with tool call to conversation
                        self.messages.append({"role": "assistant", "content": response_content, "tool_calls": [tool_call]})

                        # Add tool result as a new message with tool_call_id
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": function_name,
                            "content": tool_result
                        })

                    # Continue the loop
                    continue

                else:
                    # Model produced final answer (no tool calls)
                    logger.debug(f"Agent produced final answer (no tool calls), iteration {iteration}")
                    logger.debug(f"Final answer preview: {response_content[:200] if response_content else 'None'}...")
                    return response_content

            except Exception as e:
                logger.error(f"Error in run_loop iteration {iteration}: {e}")
                import traceback
                traceback.print_exc()
                return None

        logger.warning(f"Agent loop exceeded max iterations ({max_iterations}) without producing final answer")
        logger.warning(f"Last messages count: {len(self.messages)}")
        return None


__all__ = ['GeminiAgent']
