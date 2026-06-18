"""
OffSeeker: Deep Research Inference Framework
A clean and modular implementation for deep research using VLLM
"""

from agents.base_agent import BaseSearchAgent
from agents.vllm_agent import VLLMSearchAgent
from tools.tool_processor import ToolProcessor

__version__ = "1.0.0"
__all__ = [
    "BaseSearchAgent",
    "VLLMSearchAgent",
    "ToolProcessor",
]

