"""LLM client layer (RD §7, M2 step2).

All LLM access flows through this subpackage:

* ``llm.factory``   — low-level OpenAI-compatible client construction
* ``llm.client``    — ``get_llm_client()`` wrapper (business code uses this)
* ``llm.compat``    — reasoning/structuring compatibility across model families
* ``llm.errors``    — infra-error classification & retryability
* ``llm.profiles``  — per-model profiles loaded from ``llm/profiles.yaml``
"""

from llm.client import get_llm_client, llm_chat_completion
from llm.errors import classify_infra_error
from llm.factory import build_openai_client

__all__ = [
    "get_llm_client",
    "llm_chat_completion",
    "build_openai_client",
    "classify_infra_error",
]
