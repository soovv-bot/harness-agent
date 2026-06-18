from __future__ import annotations

import os
from typing import Optional


def _env_flag(name: str, default: str = "0") -> bool:
    val = (os.environ.get(name, default) or "").strip().lower()
    return val in {"1", "true", "yes", "y", "on"}


def build_openai_client(api_base: str, api_key: str, *, timeout_s: Optional[float] = 60.0):
    """
    Create an OpenAI-compatible client.

    Defaults to `trust_env=False` so broken proxy env vars won't break LLM calls.
    Set `LLM_TRUST_ENV=1` to opt back in to environment proxy settings.
    """
    from openai import OpenAI

    try:
        import httpx  # type: ignore
    except Exception:
        return OpenAI(base_url=api_base, api_key=api_key)

    trust_env = _env_flag("LLM_TRUST_ENV", default="0")
    timeout = httpx.Timeout(timeout_s) if timeout_s is not None else httpx.Timeout(60.0)
    http_client = httpx.Client(timeout=timeout, trust_env=trust_env)
    return OpenAI(base_url=api_base, api_key=api_key, http_client=http_client)

