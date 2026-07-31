"""
Shared LLM client + retry wrapper.

Replaces the 18 scattered `build_openai_client(...)` instantiations
with a cached singleton keyed by (api_base, api_key, timeout). Also
provides a thin retry helper around `chat.completions.create` for
transient errors, so callers don't each reimplement try/except loops.

Usage:
    from llm_client import get_llm_client, llm_chat_completion
    from config import settings

    s = settings()
    client = get_llm_client(s.api_base, s.api_key)
    resp = llm_chat_completion(client, model=s.model_id, messages=[...])
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from loguru import logger

from openai_client_factory import build_openai_client


_CLIENT_CACHE: Dict[str, Any] = {}
_CLIENT_CACHE_MAX = 8


def get_llm_client(api_base: str, api_key: str, *, timeout_s: Optional[float] = None):
    """Return a cached OpenAI client keyed by (api_base, api_key, timeout_s).

    Avoids re-instantiating httpx clients across the 5+ critic/controller
    components that each used to call build_openai_client independently.
    """
    cache_key = f"{api_base}::{api_key}::{timeout_s}"
    cached = _CLIENT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    # Evict oldest entry if cache full (FIFO-ish).
    if len(_CLIENT_CACHE) >= _CLIENT_CACHE_MAX:
        oldest_key = next(iter(_CLIENT_CACHE))
        _CLIENT_CACHE.pop(oldest_key, None)
    client = build_openai_client(api_base, api_key, timeout_s=timeout_s)
    _CLIENT_CACHE[cache_key] = client
    return client


def clear_llm_client_cache() -> None:
    """Drop all cached clients (useful for tests / config reload)."""
    _CLIENT_CACHE.clear()


def llm_chat_completion(
    client,
    *,
    model: str,
    messages: List[Dict[str, Any]],
    max_retries: int = 3,
    retry_base_delay: float = 1.0,
    retry_backoff: float = 2.0,
    **kwargs: Any,
):
    """Call chat.completions.create with bounded retry on transient errors.

    Retries on: APIConnectionError, APITimeoutError, RateLimitError,
    InternalServerError, and generic Exception-with-5xx-status. Raises
    after max_retries.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            return client.chat.completions.create(model=model, messages=messages, **kwargs)
        except Exception as exc:  # noqa: BLE001 — broad on purpose for retry
            last_exc = exc
            # Detect retryable error classes lazily (avoid hard import dep).
            retryable = _is_retryable(exc)
            if not retryable or attempt == max_retries:
                logger.error(
                    f"[llm_client] chat.completions.create failed "
                    f"(attempt {attempt}/{max_retries}): {type(exc).__name__}: {exc}"
                )
                raise
            delay = retry_base_delay * (retry_backoff ** (attempt - 1))
            logger.warning(
                f"[llm_client] transient error (attempt {attempt}/{max_retries}), "
                f"retrying in {delay:.1f}s: {type(exc).__name__}"
            )
            time.sleep(delay)
    # Defensive — loop should have raised already.
    assert last_exc is not None
    raise last_exc


def _is_retryable(exc: Exception) -> bool:
    """Check if an OpenAI client exception is worth retrying."""
    # Match by class name (string) to avoid importing openai error types here.
    name = type(exc).__name__
    retryable_names = {
        "APIConnectionError",
        "APITimeoutError",
        "RateLimitError",
        "InternalServerError",
        "APIStatusError",  # narrower check below
    }
    if name in retryable_names:
        # For APIStatusError, only retry 5xx.
        status = getattr(exc, "status_code", None)
        if status is not None:
            return 500 <= int(status) < 600
        return True
    # Fallback: retry on any 5xx status attr.
    status = getattr(exc, "status_code", None)
    if status is not None and 500 <= int(status) < 600:
        return True
    return False
