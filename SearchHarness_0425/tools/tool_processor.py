"""
Tool Call Processor for JSON-based Tool Calls
Processes JSON format tool calls for deep research agents
"""

import json
import re
from typing import Dict, List, Optional, Any, Callable
from loguru import logger

from .search_tools import (
    search,
    visit_urls,
    search_wiki,
    execute_code
)


class ToolProcessor:
    """Process JSON format tool calls."""
    
    def __init__(self):
        """Initialize tool call processor."""
        # Define available tools
        self.tools = {
            "search": self._execute_search,
            "visit_urls": self._execute_visit_urls,
            "search_wiki": self._execute_search_wiki,
            "execute_code": self._execute_execute_code,
        }
        
        logger.info("Initialized ToolProcessor")
    
    def extract_tool_calls(self, response: str) -> List[Dict]:
        """
        Extract tool calls from agent response.
        
        Args:
            response: Agent response text
            
        Returns:
            List of parsed tool call dictionaries
        """
        tool_calls = []
        
        # Find all <tool_call>...</tool_call> blocks
        tool_call_pattern = r'<tool_call>(.*?)</tool_call>'
        matches = re.findall(tool_call_pattern, response, re.DOTALL)
        
        for match in matches:
            try:
                # Parse JSON
                tool_call = json.loads(match.strip())
                tool_calls.append(tool_call)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse tool call JSON: {e}")
                logger.warning(f"Raw tool call: {match}")
                continue
        
        return tool_calls
    
    def execute_tool_calls(self, tool_calls: List[Dict]) -> List[str]:
        """
        Execute tool calls and return results.
        
        Args:
            tool_calls: List of tool call dictionaries
            
        Returns:
            List of execution results
        """
        results = []
        
        for tool_call in tool_calls:
            try:
                tool_name = tool_call.get("name")
                arguments = tool_call.get("arguments", {})
                
                if tool_name not in self.tools:
                    error_msg = f"Unknown tool: {tool_name}"
                    logger.error(error_msg)
                    results.append(f"Error: {error_msg}")
                    continue
                
                # Execute tool
                result = self.tools[tool_name](arguments)
                results.append(result)
                
            except Exception as e:
                error_msg = f"Error executing tool call {tool_call}: {str(e)}"
                logger.error(error_msg)
                results.append(f"Error: {error_msg}")
        
        return results
    
    def _execute_search(self, arguments: Dict) -> str:
        """Execute search tool."""
        query = arguments.get("query", [])
        if isinstance(query, str):
            query = [query]
        
        try:
            result = search(query)
            return result
        except Exception as e:
            return f"Error in search: {str(e)}"
    
    def _execute_visit_urls(self, arguments: Dict) -> str:
        """Execute URL visit tool."""
        urls = arguments.get("urls", [])
        if isinstance(urls, str):
            urls = [urls]
        query = arguments.get("query", "")
        
        try:
            results = visit_urls(urls, query)
            return "\n\n".join(results)
        except Exception as e:
            return f"Error in visit_urls: {str(e)}"
    

    def _execute_search_wiki(self, arguments: Dict) -> str:
        """Execute search_wiki tool."""
        entities = arguments.get("entities", [])
        if isinstance(entities, str):
            entities = [entities]
    
        try:
            results = search_wiki(entities)
            return results
        except Exception as e:
            return f"Error in search_wiki: {str(e)}"

    def _execute_execute_code(self, arguments: Dict) -> str:
        """Execute execute_code tool."""
        code = arguments.get("code", "")
    
        try:
            results = execute_code(code)
            return results
        except Exception as e:
            return f"Error in execute_code: {str(e)}"
    
    def format_tool_response(self, tool_calls: List[Dict], results: List[str]) -> str:
        """
        Format tool response for agent consumption.
        
        Args:
            tool_calls: List of tool call dictionaries
            results: List of execution results
            
        Returns:
            Formatted response string
        """
        if not tool_calls:
            return ""
        
        response_parts = []
        for i, (tool_call, result) in enumerate(zip(tool_calls, results)):
            response_parts.append(
                f"Tool: {tool_call['name']}\n"
                f"Result: {result}"
            )
        
        tool_response = "\n\n".join(response_parts)
        
        return f"<tool_response>\n{tool_response}\n</tool_response>"
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names."""
        return list(self.tools.keys())
    
    def add_custom_tool(self, name: str, function: Callable):
        """
        Add a custom tool to the processor.
        
        Args:
            name: Tool name
            function: Tool function to execute
        """
        self.tools[name] = function
        logger.info(f"Added custom tool: {name}")


def extract_answer(response: str) -> Optional[str]:
    """
    Extract final answer from response.
    
    Args:
        response: Agent response text
        
    Returns:
        Extracted answer or None
    """
    answer_pattern = r'<answer>(.*?)</answer>'
    match = re.search(answer_pattern, response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def extract_think(response: str) -> Optional[str]:
    """
    Extract thinking process from response.
    
    Args:
        response: Agent response text
        
    Returns:
        Extracted thinking or None
    """
    think_pattern = r'<think>(.*?)</think>'
    match = re.search(think_pattern, response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None
