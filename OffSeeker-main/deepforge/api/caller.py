"""Unified API caller for multiple LLM providers

This module provides a unified interface for calling different LLM APIs
including vLLM, OpenAI, DeepSeek, and Gemini.

It also provides backward compatibility functions for the original
call_api_gemini function.
"""

import os
from typing import List, Dict, Optional, Literal
from loguru import logger
from openai import OpenAI
from retry import retry

from config import settings


class APICaller:
    """Unified interface for calling different LLM APIs

    Supports:
    - vLLM (local model servers)
    - OpenAI (and OpenAI-compatible APIs)
    - DeepSeek
    - Gemini (via internal API gateway)
    """

    def __init__(
        self,
        api_type: Literal["vllm", "openai", "deepseek", "gemini"] = "openai",
        model_name: Optional[str] = None,
        **kwargs
    ):
        """Initialize the API caller

        Args:
            api_type: Type of API to call ("vllm", "openai", "deepseek", "gemini")
            model_name: Name of the model to use
            **kwargs: Additional configuration (e.g., llm_server_ip, llm_server_port)
        """
        self.api_type = api_type
        self.model_name = model_name
        self.kwargs = kwargs
        self.client = None

        self._initialize_client()

    def _initialize_client(self):
        """Initialize the appropriate API client based on api_type"""
        if self.api_type == "vllm":
            self._init_vllm_client()
        elif self.api_type == "openai":
            self._init_openai_client()
        elif self.api_type == "deepseek":
            self._init_deepseek_client()
        elif self.api_type == "gemini":
            self._init_gemini_client()
        else:
            raise ValueError(f"Unsupported api_type: {self.api_type}")

    def _init_vllm_client(self):
        """Initialize vLLM client for local model servers"""
        llm_server_ip = self.kwargs.get(
            'llm_server_ip',
            settings.api.local_model_ip
        )
        llm_server_port = self.kwargs.get(
            'llm_server_port',
            settings.api.local_model_port
        )

        if not llm_server_ip or not llm_server_port:
            raise ValueError("llm_server_ip and llm_server_port are required for vllm")

        os.environ["no_proxy"] = f"127.0.0.1,localhost,{llm_server_ip}"
        self.client = OpenAI(
            base_url=f"http://{llm_server_ip}:{llm_server_port}/v1",
            api_key="EMPTY",
        )
        logger.info(f"Initialized vLLM client at {llm_server_ip}:{llm_server_port}")

    def _init_openai_client(self):
        """Initialize OpenAI client"""
        api_key = self.kwargs.get('api_key') or settings.api.openai_api_key
        base_url = self.kwargs.get('base_url')

        if not base_url:
            # Get from config
            base_url = settings.api.get_openai_base_url()

        if not api_key:
            logger.warning("OPENAI_API_KEY not set in environment")

        self.client = OpenAI(base_url=base_url, api_key=api_key or "dummy")
        logger.info(f"Initialized OpenAI client with base_url: {base_url}")

    def _init_deepseek_client(self):
        """Initialize DeepSeek client"""
        api_key = self.kwargs.get('api_key') or settings.api.deepseek_api_key
        base_url = self.kwargs.get('base_url')

        if not base_url:
            # DeepSeek requires explicit base_url
            if not settings.api.deepseek_base_url:
                raise ValueError(
                    "DEEPSEEK_BASE_URL not configured. Please set it in .env file."
                )
            base_url = settings.api.deepseek_base_url

        if not api_key:
            logger.warning("DEEPSEEK_API_KEY not set in environment")

        self.client = OpenAI(base_url=base_url, api_key=api_key or "dummy")
        logger.info(f"Initialized DeepSeek client with base_url: {base_url}")

    def _init_gemini_client(self):
        """Initialize Gemini client via OpenAI-compatible API"""
        api_key = self.kwargs.get('api_key') or settings.api.openai_api_key
        base_url = self.kwargs.get('base_url')

        if not base_url:
            # Get from config
            base_url = settings.api.get_gemini_base_url()

        if not api_key:
            logger.warning("API key not set for Gemini client")

        self.client = OpenAI(base_url=base_url, api_key=api_key or "dummy")
        logger.info(f"Initialized Gemini client with base_url: {base_url}")

    @retry(tries=10, delay=1.0, backoff=2.0, max_delay=20)
    def call_api(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0,
        tools: Optional[List[Dict]] = None
    ):
        """Call the API with the given messages

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature
            tools: Optional list of tool schemas for function calling

        Returns:
            Response object with content and tool_calls (may contain tool_calls)
        """
        # All API types now use OpenAI-compatible interface
        return self._call_openai_compatible_api(messages, temperature, tools)

    def _call_openai_compatible_api(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        tools: Optional[List[Dict]] = None
    ):
        """Call OpenAI-compatible API (vLLM, OpenAI, DeepSeek)

        Returns:
            - If tools provided: Full message object with tool_calls
            - If no tools: Content string (for backward compatibility)
        """
        # Set no_proxy for vLLM
        if self.api_type == "vllm" and "llm_server_ip" in self.kwargs:
            llm_server_ip = self.kwargs['llm_server_ip']
            os.environ["no_proxy"] = f"127.0.0.1,localhost,{llm_server_ip}"

        try:
            call_params = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature
            }

            # Add tools parameter if provided (for function calling)
            if tools:
                call_params["tools"] = tools

            resp = self.client.chat.completions.create(**call_params)
            message = resp.choices[0].message

            # For backward compatibility:
            # - If tools are provided, return full message object (for tool_calls)
            # - If no tools, return just content string
            if tools:
                return message
            else:
                return message.content

        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise


# ============================================================================
# Backward Compatibility Functions
# ============================================================================

def call_api_gemini(messages: List[Dict[str, str]]) -> str:
    """Legacy function for calling Gemini API

    This function provides backward compatibility with the original
    utils.call_model_gemini.call_api_gemini function.

    Args:
        messages: List of message dicts

    Returns:
        The model's response text
    """
    caller = APICaller(api_type="gemini", model_name=settings.api.gemini_model)
    return caller.call_api(messages)


# Re-export for backward compatibility
__all__ = [
    'APICaller',
    'call_api_gemini',
]
