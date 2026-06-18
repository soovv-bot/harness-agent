"""
Agents module for OffSeeker
"""

from .base_agent import BaseSearchAgent
from .vllm_agent import VLLMSearchAgent

__all__ = [
    "BaseSearchAgent",
    "VLLMSearchAgent",
]

