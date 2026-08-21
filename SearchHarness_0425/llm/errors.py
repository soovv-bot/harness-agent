from __future__ import annotations

import re
from typing import Any, Optional


def _stringify_error(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, BaseException):
        return f"{value.__class__.__name__}: {value}"
    return str(value)


def classify_infra_error(value: Any) -> Optional[str]:
    text = _stringify_error(value).lower()
    if not text:
        return None

    auth_patterns = [
        r"invalid_api_key",
        r"incorrect api key",
        r"authentication",
        r"unauthorized",
        r"forbidden",
        r"key_model_access_denied",
        r"error code:\s*401",
        r"error code:\s*403",
        r"\b401\b",
        r"\b403\b",
    ]
    if any(re.search(pattern, text) for pattern in auth_patterns):
        return "auth_error"

    rate_limit_patterns = [
        r"rate limit",
        r"too many requests",
        r"quota",
        r"error code:\s*429",
        r"\b429\b",
    ]
    if any(re.search(pattern, text) for pattern in rate_limit_patterns):
        return "rate_limit"

    network_patterns = [
        r"timeout",
        r"timed out",
        r"connecterror",
        r"connection error",
        r"connection refused",
        r"remoteprotocolerror",
        r"network is unreachable",
        r"dns",
        r"name or service not known",
        r"temporary failure",
        r"proxy",
    ]
    if any(re.search(pattern, text) for pattern in network_patterns):
        return "network_error"

    service_patterns = [
        r"service unavailable",
        r"bad gateway",
        r"gateway timeout",
        r"internal server error",
        r"error code:\s*5\d\d",
        r"\b502\b",
        r"\b503\b",
        r"\b504\b",
    ]
    if any(re.search(pattern, text) for pattern in service_patterns):
        return "service_error"

    return None