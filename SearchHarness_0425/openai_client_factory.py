from __future__ import annotations

import os
from typing import Optional


def _env_flag(name: str, default: str = "0") -> bool:
    val = (os.environ.get(name, default) or "").strip().lower()
    return val in {"1", "true", "yes", "y", "on"}


def _env_timeout(default: float = 180.0) -> float:
    raw = (os.environ.get("LLM_TIMEOUT_S") or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def build_openai_client(api_base: str, api_key: str, *, timeout_s: Optional[float] = None):
    """
    Create an OpenAI-compatible client.

    Defaults to `trust_env=False` so broken proxy env vars won't break LLM calls.
    Set `LLM_TRUST_ENV=1` to opt back in to environment proxy settings.
    """
    from openai import OpenAI  # type: ignore

    try:
        import httpx  # type: ignore
    except Exception:
        return OpenAI(base_url=api_base, api_key=api_key)

    trust_env = _env_flag("LLM_TRUST_ENV", default="0")
    effective_timeout = timeout_s if timeout_s is not None else _env_timeout()
    timeout = httpx.Timeout(effective_timeout)
    http_client = httpx.Client(timeout=timeout, trust_env=trust_env)
    return OpenAI(base_url=api_base, api_key=api_key, http_client=http_client)

