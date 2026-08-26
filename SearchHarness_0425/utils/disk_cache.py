"""Disk cache for LLM and HTTP calls — deterministic replay for eval runs.

M1 goal: same fixed sample + same cache → byte-identical results (modulo
volatile fields like elapsed_seconds/timestamps, which callers strip when
diffing). Two surfaces get cached:

- LLM calls (``chat_completion_with_structuring``) keyed by a hash of the
  request kwargs (stream flags excluded so streaming/non-streaming share).
- HTTP calls (Serper search, URL crawl, wiki lookup) keyed by a hash of the
  query/URL plus the fetch engine.

Modes (env ``LLM_CACHE_MODE``):

- ``off`` (default): no caching; behaviour identical to pre-cache code.
- ``record``: read-through + write-through (hit returns cached, miss calls
  network and stores).
- ``replay``: read-only. A miss raises :class:`DiskCacheMissError` instead of
  touching the network, so a full eval can run offline.

Layout: ``<root>/<subdir>/<sha256>.json`` where subdir is ``llm`` or ``http``.
Writes are atomic (tmp + os.replace) and the whole module is thread-safe.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional


class DiskCacheMissError(RuntimeError):
    """Raised in replay mode when a required entry is missing from the cache."""


_lock = threading.Lock()

# Key-normalization: fields that do not change the *content* of the response
# but would break hit-rate across replay configurations.
_LLM_VOLATILE_KEYS = {"stream", "stream_options"}


def get_cache_root() -> Path:
    env = (os.getenv("LLM_CACHE_DIR") or "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parent / ".llm_cache"


def cache_mode() -> str:
    return (os.getenv("LLM_CACHE_MODE") or "off").strip().lower()


def cache_enabled() -> bool:
    return cache_mode() in {"record", "replay", "replay_only", "strict"}


def replay_only() -> bool:
    return cache_mode() in {"replay", "replay_only", "strict"}


def make_llm_key(kwargs: Dict[str, Any]) -> str:
    """Deterministic hash of LLM request kwargs, ignoring stream flags."""
    normalized = {k: v for k, v in kwargs.items() if k not in _LLM_VOLATILE_KEYS}
    blob = json.dumps(normalized, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def make_http_key(kind: str, *parts: str) -> str:
    blob = "\x00".join((kind, *parts))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def get_entry(subdir: str, key: str) -> Optional[Dict[str, Any]]:
    """Return the cached payload dict, or None. Brave to corrupt files."""
    if not cache_enabled():
        return None
    path = get_cache_root() / subdir / f"{key}.json"
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def put_entry(subdir: str, key: str, payload: Dict[str, Any]) -> None:
    """Write payload atomically. No-op when cache disabled. Never raises."""
    if not cache_enabled() or replay_only():
        return
    path = get_cache_root() / subdir / f"{key}.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        blob = json.dumps(payload, ensure_ascii=False)
        tmp = path.with_suffix(path.suffix + f".{threading.get_ident()}.tmp")
        tmp.write_text(blob, encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        pass


def miss_or_raise(subdir: str, key: str, what: str) -> None:
    if replay_only():
        raise DiskCacheMissError(f"[replay] cache miss ({what}); refusing network call")


# --------------------------------------------------------------------------
# LLM message (de)serialization
# --------------------------------------------------------------------------

def message_to_cached_dict(message: Any) -> Dict[str, Any]:
    """Flatten an assistant message (OpenAI object or SimpleNamespace) to JSON."""
    d: Dict[str, Any] = {
        "role": getattr(message, "role", "assistant"),
        "content": getattr(message, "content", None),
        "reasoning_content": getattr(message, "reasoning_content", None),
        "tool_calls": None,
        "usage_metadata": getattr(message, "usage_metadata", None),
    }
    tool_calls = getattr(message, "tool_calls", None) or []
    if tool_calls:
        d["tool_calls"] = [
            {
                "id": getattr(tc, "id", ""),
                "type": getattr(tc, "type", "function"),
                "function": {
                    "name": getattr(getattr(tc, "function", None), "name", ""),
                    "arguments": getattr(getattr(tc, "function", None), "arguments", ""),
                },
            }
            for tc in tool_calls
        ]
    return d


def message_from_cached_dict(d: Dict[str, Any]) -> Any:
    """Rebuild a message quacking like OpenAI's ChatCompletionMessage."""
    def _tc(tc_dict: Dict[str, Any]) -> Any:
        fn = tc_dict.get("function") or {}
        return SimpleNamespace(
            id=tc_dict.get("id", ""),
            type=tc_dict.get("type", "function"),
            function=SimpleNamespace(name=fn.get("name", ""), arguments=fn.get("arguments", "")),
        )

    msg = SimpleNamespace(
        role=d.get("role", "assistant"),
        content=d.get("content"),
        reasoning_content=d.get("reasoning_content"),
        tool_calls=[_tc(t) for t in (d.get("tool_calls") or [])],
        usage_metadata=d.get("usage_metadata"),
    )
    msg.model_dump = lambda **_: {k: v for k, v in (
        ("role", msg.role),
        ("content", msg.content),
        ("reasoning_content", msg.reasoning_content),
        ("tool_calls", d.get("tool_calls")),
    ) if v}  # model_dump(exclude_none=True)-ish for assistant_message_to_dict
    return msg
