"""LLM token usage & cost metering (T8, M0).

Single choke-point: ``record_usage(model_id, usage, meta)`` is called from
``llm_reasoning_compat.chat_completion_with_structuring`` and
``llm_client.llm_chat_completion`` — all LLM calls funnel through those two
functions, so no per-agent instrumentation is needed.

Features:
- Thread-safe accumulation (pipelines run in ThreadPoolExecutors).
- Per-tag attribution via ``usage_tag()`` context manager (thread-local); the
  fixed-sample runner tags each task with its sample position, the repeats
  runner tags by run index.
- Cost estimation from an optional ``model_pricing.yaml`` (USD per 1M tokens,
  input/output per profile substring-match) — same file can be overridden via
  ``LLM_PRICING_YAML`` env or entirely via ``LLM_PRICING_JSON`` env of the form
  ``{"Kimi-K3": {"input": 2.0, "output": 8.0}, "default": {"input": 0, ...}}``.
  Models without a price entry still report tokens; cost fields are omitted.
- ``snapshot()`` returns a JSON-serializable dict for embedding in run
  payloads and trajectory metadata.

The tracker is a process-global singleton (``get_tracker()``); each CLI
entrypoint calls ``reset()`` at start.
"""

from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional


# ── Usage normalization ───────────────────────────────────────────────


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def normalize_usage(usage: Any) -> Dict[str, int]:
    """Normalize an OpenAI-style usage object/dict into plain ints.

    Handles both ``CompletionUsage`` objects and plain dicts; extracts
    reasoning tokens when present (``completion_tokens_details``).
    """
    if usage is None:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "reasoning_tokens": 0}
    if not isinstance(usage, dict):
        get = lambda k: getattr(usage, k, None)  # noqa: E731
        details = getattr(usage, "completion_tokens_details", None)
        reasoning = getattr(details, "reasoning_tokens", None) if details is not None else None
    else:
        get = lambda k: usage.get(k)  # noqa: E731
        details = usage.get("completion_tokens_details") or {}
        reasoning = details.get("reasoning_tokens") if isinstance(details, dict) else getattr(
            details, "reasoning_tokens", None
        )
    prompt = _to_int(get("prompt_tokens"))
    completion = _to_int(get("completion_tokens"))
    total = _to_int(get("total_tokens")) or (prompt + completion)
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "reasoning_tokens": _to_int(reasoning),
    }


# ── Pricing ───────────────────────────────────────────────────────────

_DEFAULT_PRICING_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_pricing.yaml")

_pricing_cache: Optional[Dict[str, Dict[str, float]]] = None


def _load_pricing() -> Dict[str, Dict[str, float]]:
    """Load USD-per-1M-token prices. Absent file/env → empty (tokens only)."""
    global _pricing_cache
    if _pricing_cache is not None:
        return _pricing_cache

    table: Dict[str, Dict[str, float]] = {}

    raw_json = (os.getenv("LLM_PRICING_JSON") or "").strip()
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            for name, entry in (parsed or {}).items():
                table[str(name)] = {
                    "input": float(entry.get("input", 0.0)),
                    "output": float(entry.get("output", 0.0)),
                }
        except Exception:
            table = {}

    if not table:
        path = (os.getenv("LLM_PRICING_YAML") or "").strip() or _DEFAULT_PRICING_PATH
        if os.path.isfile(path):
            try:
                import yaml

                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                for name, entry in (data.get("pricing") or {}).items():
                    table[str(name)] = {
                        "input": float(entry.get("input", 0.0)),
                        "output": float(entry.get("output", 0.0)),
                    }
            except Exception:
                table = {}

    _pricing_cache = table
    return table


def lookup_price(model_id: str) -> Optional[Dict[str, float]]:
    """Best substring match (longest wins, like model_profiles); None if unknown."""
    table = _load_pricing()
    if not table or not model_id:
        return None
    mid = model_id.lower()
    best = None
    best_len = -1
    for name in table:
        if name == "default":
            continue
        if name.lower() in mid and len(name) > best_len:
            best = name
            best_len = len(name)
    if best is not None:
        return table[best]
    return table.get("default")


def reset_pricing_cache() -> None:
    """Drop the cache (tests / env edits)."""
    global _pricing_cache
    _pricing_cache = None


# ── Tracker ───────────────────────────────────────────────────────────


class UsageTracker:
    """Thread-safe run-level accumulator for token usage and cost."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._local = threading.local()
        self._reset_state()

    def _reset_state(self) -> None:
        self._records: List[Dict[str, Any]] = []
        self._by_key: Dict[str, Dict[str, Any]] = {}

    # -- attribution ----------------------------------------------------

    def current_tag(self) -> str:
        return getattr(self._local, "tag", "") or ""

    @contextmanager
    def usage_tag(self, tag: str) -> Iterator[None]:
        """Attribute all recorded calls in this thread to ``tag``."""
        prev = self.current_tag()
        self._local.tag = tag
        try:
            yield
        finally:
            self._local.tag = prev

    # -- recording ------------------------------------------------------

    def record(self, model_id: str, usage: Any, *, caller: str = "") -> Dict[str, int]:
        """Record one LLM call. Returns the normalized token counts."""
        n = normalize_usage(usage)
        tag = self.current_tag()
        entry = {
            "model": model_id or "unknown",
            "caller": caller or "",
            "tag": tag,
            **n,
        }
        price = lookup_price(model_id or "")
        with self._lock:
            self._records.append(entry)
            for key, bucket in ((model_id or "unknown", model_id or "unknown"), (f"tag:{tag}", tag), (f"caller:{caller}", caller)):
                if key.startswith("tag:") and not tag:
                    continue
                if key.startswith("caller:") and not caller:
                    continue
                agg = self._by_key.setdefault(key, self._fresh_bucket(name=bucket))
                agg["calls"] += 1
                agg["prompt_tokens"] += n["prompt_tokens"]
                agg["completion_tokens"] += n["completion_tokens"]
                agg["total_tokens"] += n["total_tokens"]
                agg["reasoning_tokens"] += n["reasoning_tokens"]
                if price is not None:
                    agg["cost_usd"] = round(
                        agg["cost_usd"]
                        + n["prompt_tokens"] * price["input"] / 1_000_000
                        + n["completion_tokens"] * price["output"] / 1_000_000,
                        6,
                    )
                    agg["priced"] = True
        return n

    @staticmethod
    def _fresh_bucket(name: str) -> Dict[str, Any]:
        return {
            "name": name,
            "calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "reasoning_tokens": 0,
            "cost_usd": 0.0,
            "priced": False,
        }

    # -- output ---------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """JSON-serializable summary: per-model + per-tag + per-caller buckets."""
        with self._lock:
            models = {
                k.rsplit(":", 1)[0] if ":" in k else k: dict(v)
                for k, v in sorted(self._by_key.items())
                if not k.startswith(("tag:", "caller:"))
            }
            tags = {
                v["name"]: {kk: vv for kk, vv in v.items() if kk not in ("name",)}
                for k, v in sorted(self._by_key.items())
                if k.startswith("tag:")
            }
            callers = {
                v["name"]: {kk: vv for kk, vv in v.items() if kk not in ("name",)}
                for k, v in sorted(self._by_key.items())
                if k.startswith("caller:")
            }
            total = self._fresh_bucket("total")
            any_priced = False
            for k, v in self._by_key.items():
                if k.startswith(("tag:", "caller:")):
                    continue
                total["calls"] += v["calls"]
                total["prompt_tokens"] += v["prompt_tokens"]
                total["completion_tokens"] += v["completion_tokens"]
                total["total_tokens"] += v["total_tokens"]
                total["reasoning_tokens"] += v["reasoning_tokens"]
                total["cost_usd"] = round(total["cost_usd"] + v["cost_usd"], 6)
                any_priced = any_priced or v["priced"]
            return {
                "total": {kk: vv for kk, vv in total.items() if kk != "name"},
                "by_model": models,
                "by_tag": tags,
                "by_caller": callers,
                "pricing_known": any_priced,
            }

    def reset(self) -> None:
        with self._lock:
            self._reset_state()


_tracker = UsageTracker()


def get_tracker() -> UsageTracker:
    return _tracker


def record_usage(model_id: str, usage: Any, *, caller: str = "") -> Dict[str, int]:
    return _tracker.record(model_id, usage, caller=caller)


@contextmanager
def usage_tag(tag: str) -> Iterator[None]:
    with _tracker.usage_tag(tag):
        yield
