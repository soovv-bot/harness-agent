"""Model reasoning profile loader.

Loads per-model reasoning configuration from ``model_profiles.yaml`` and
provides a ``ModelProfile`` for any model_id. Replaces the previously
hardcoded model detection / effort mapping in ``llm_reasoning_compat``.

Profiles are matched by case-insensitive substring against model_id; the
longest matching profile name wins. If no profile matches, ``default`` is
used. If the YAML file is missing or unreadable, built-in defaults are used
so the system keeps working.

Usage:
    from model_profiles import get_model_profile
    profile = get_model_profile("Kimi-K3")
    effort = profile.snap_effort("minimal")   # -> "low"
    if profile.minimal_effort_is_honored: ...
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

try:
    import yaml  # PyYAML is a project dependency
    _HAS_YAML = True
except ImportError:  # pragma: no cover
    _HAS_YAML = False

from loguru import logger


_DEFAULT_PROFILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "model_profiles.yaml"
)

# Override path via env (e.g. for tests or alternate configs).
_PROFILE_PATH_ENV = "MODEL_PROFILES_PATH"


@dataclass(frozen=True)
class ModelProfile:
    """Per-model reasoning behavior."""
    name: str
    thinking_enabled: bool
    can_disable_thinking: bool
    supported_efforts: List[str]
    default_effort: Optional[str]
    effort_mapping: Dict[str, str]
    preserve_reasoning_history: bool
    minimal_effort_is_honored: bool

    def snap_effort(self, effort: Optional[str]) -> Optional[str]:
        """Remap an effort value to one this model honors.

        - None → None (no effort param sent; endpoint uses its default)
        - explicit mapping → mapped value
        - already supported → unchanged
        - unsupported & unmapped → default_effort
        """
        if effort is None:
            return None
        if effort in self.effort_mapping:
            return self.effort_mapping[effort]
        if effort in self.supported_efforts:
            return effort
        return self.default_effort

    def is_minimal_request(self, reasoning_effort_override: Optional[str]) -> bool:
        """Mirror _resolve_effort semantics: was the *requested* effort the
        weakest setting (minimal / "none" alias / budget<=0)?

        Used by the structurer skip heuristic. Model-aware: if this profile
        honors minimal/low (minimal_effort_is_honored=True), a large
        reasoning_content is normal rather than evidence the endpoint ignored
        the request — return False so the skip does not fire.
        """
        if self.minimal_effort_is_honored:
            return False
        if reasoning_effort_override:
            return reasoning_effort_override in ("none", "minimal")
        budget_raw = (os.getenv("LLM_THINKING_BUDGET_TOKENS") or "").strip()
        if not budget_raw:
            return False
        try:
            return int(budget_raw) <= 0
        except ValueError:
            return False


# --- Built-in defaults (used if YAML is missing/unreadable) -------------------
# Kept in sync with model_profiles.yaml so the system works with no file.
_BUILTIN_PROFILES: Dict[str, dict] = {
    "Kimi-K3": {
        "thinking_enabled": True,
        "can_disable_thinking": False,
        "supported_efforts": ["low", "high", "max"],
        "default_effort": "max",
        "effort_mapping": {"minimal": "low", "medium": "high"},
        "preserve_reasoning_history": True,
        "minimal_effort_is_honored": True,
    },
    "GLM-5.2": {
        "thinking_enabled": True,
        "can_disable_thinking": False,
        "supported_efforts": ["max", "high"],
        "default_effort": "max",
        "effort_mapping": {},
        "preserve_reasoning_history": True,
        "minimal_effort_is_honored": False,
    },
    "default": {
        "thinking_enabled": False,
        "can_disable_thinking": True,
        "supported_efforts": ["minimal", "low", "medium", "high"],
        "default_effort": "minimal",
        "effort_mapping": {},
        "preserve_reasoning_history": False,
        "minimal_effort_is_honored": True,
    },
}


def _normalize_profile(name: str, raw: dict) -> ModelProfile:
    return ModelProfile(
        name=name,
        thinking_enabled=bool(raw.get("thinking_enabled", False)),
        can_disable_thinking=bool(raw.get("can_disable_thinking", True)),
        supported_efforts=list(raw.get("supported_efforts", ["minimal", "low", "medium", "high"])),
        default_effort=raw.get("default_effort"),
        effort_mapping=dict(raw.get("effort_mapping", {})),
        preserve_reasoning_history=bool(raw.get("preserve_reasoning_history", False)),
        minimal_effort_is_honored=bool(raw.get("minimal_effort_is_honored", True)),
    )


def _load_profiles() -> Dict[str, ModelProfile]:
    """Load profiles from YAML, falling back to built-in defaults."""
    path = (os.getenv(_PROFILE_PATH_ENV) or "").strip() or _DEFAULT_PROFILE_PATH
    raw_profiles: Dict[str, dict] = {}
    if _HAS_YAML and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            raw_profiles = data.get("profiles", {}) or {}
            if "default" in data:
                raw_profiles.setdefault("default", data["default"])
            logger.debug(f"[model_profiles] loaded {len(raw_profiles)} profiles from {path}")
        except Exception as e:
            logger.warning(f"[model_profiles] failed to load {path}: {e}; using built-in defaults")
            raw_profiles = {}
    elif not _HAS_YAML:
        logger.warning("[model_profiles] PyYAML not installed; using built-in defaults")
    else:
        logger.debug(f"[model_profiles] {path} not found; using built-in defaults")

    # Merge: built-in defaults as the base, YAML overrides on top.
    merged: Dict[str, dict] = dict(_BUILTIN_PROFILES)
    for k, v in raw_profiles.items():
        merged[k] = v
    return {k: _normalize_profile(k, v) for k, v in merged.items()}


# Cache profiles at first use (file + env are stable for a process lifetime).
_profiles_cache: Optional[Dict[str, ModelProfile]] = None


def _get_profiles() -> Dict[str, ModelProfile]:
    global _profiles_cache
    if _profiles_cache is None:
        _profiles_cache = _load_profiles()
    return _profiles_cache


def reload_profiles() -> None:
    """Force re-read of the YAML (e.g. after editing during a long session)."""
    global _profiles_cache
    _profiles_cache = None


def _match_profile_name(model_id: str, profiles: Dict[str, ModelProfile]) -> str:
    """Return the best-matching profile name for model_id.

    Case-insensitive substring match; longest matching profile name wins.
    Falls back to "default".
    """
    if not model_id:
        return "default"
    mid = model_id.lower()
    best = None
    best_len = -1
    for name in profiles:
        if name == "default":
            continue
        if name.lower() in mid:
            if len(name) > best_len:
                best = name
                best_len = len(name)
    return best or "default"


def get_model_profile(model_id: str) -> ModelProfile:
    """Get the reasoning profile for a model_id (substring match, cached)."""
    profiles = _get_profiles()
    name = _match_profile_name(model_id, profiles)
    return profiles[name]
