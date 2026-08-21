"""Unified results schema + run spec (M1).

Every evaluation run writes one JSON payload. This module is the single place
that defines its envelope:

    {
        "schema_version": 1,
        "run_spec":   {... provenance: benchmark, models, budgets, git sha ...},
        "timestamp":  "...",          # volatile
        "accuracy": ..., "results": [...], "llm_usage": {...}, ...
        <runner-specific top-level keys preserved verbatim>
    }

Additive by design: all legacy top-level keys stay, consumers keep working.
`strip_volatile` removes time/usage fields so two runs can be compared for
byte-level replay equality (M1 reproducibility gate).
"""

from __future__ import annotations

import copy
import os
import platform
import subprocess
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = 1

# Keys whose values legitimately differ between two identical runs (wall
# clock, token spend) and must be excluded from byte-level replay comparison.
VOLATILE_TOP_LEVEL = ("timestamp", "total_elapsed_seconds", "llm_usage")
VOLATILE_RESULT_KEYS = ("elapsed_seconds", "elapsed")


def _git_sha() -> Optional[str]:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def collect_run_spec(
    benchmark: str,
    model_id: str,
    grader_model_id: str,
    pipeline_config: Dict[str, Any],
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Provenance for a run: what was executed, where, with what config."""
    spec: Dict[str, Any] = {
        "benchmark": benchmark,
        "model_id": model_id,
        "grader_model_id": grader_model_id,
        "pipeline_config": dict(pipeline_config),
        "git_sha": _git_sha(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "llm_cache_mode": (os.getenv("LLM_CACHE_MODE") or "off").strip() or "off",
        "crawler_engine": (os.getenv("CRAWLER_ENGINE") or "").strip() or None,
    }
    if extra:
        spec.update(extra)
    return spec


def finalize_payload(
    *,
    run_spec: Dict[str, Any],
    timestamp: str,
    results: List[Dict[str, Any]],
    llm_usage: Optional[Dict[str, Any]],
    metrics: Dict[str, Any],
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble the standard envelope around runner-specific fields."""
    payload: Dict[str, Any] = {"schema_version": SCHEMA_VERSION, "run_spec": run_spec}
    payload["timestamp"] = timestamp
    payload.update(metrics)
    payload["llm_usage"] = llm_usage
    if extra:
        payload.update(extra)
    payload["results"] = results
    return payload


_REQUIRED_KEYS = ("schema_version", "run_spec", "timestamp", "accuracy", "results")
_REQUIRED_RUN_SPEC_KEYS = ("benchmark", "model_id", "pipeline_config")


def validate_payload(payload: Dict[str, Any]) -> List[str]:
    """Return a list of violations (empty = valid). Never raises/mutates."""
    violations: List[str] = []
    if not isinstance(payload, dict):
        return ["payload is not a dict"]
    for key in _REQUIRED_KEYS:
        if key not in payload:
            violations.append(f"missing top-level key: {key}")
    if "schema_version" in payload and payload["schema_version"] != SCHEMA_VERSION:
        violations.append(f"schema_version {payload['schema_version']!r} != {SCHEMA_VERSION}")
    run_spec = payload.get("run_spec")
    if isinstance(run_spec, dict):
        for key in _REQUIRED_RUN_SPEC_KEYS:
            if key not in run_spec:
                violations.append(f"missing run_spec key: {key}")
    elif "run_spec" in payload:
        violations.append("run_spec is not a dict")
    accuracy = payload.get("accuracy")
    if "accuracy" in payload and not isinstance(accuracy, (int, float)):
        violations.append("accuracy is not numeric")
    if "results" in payload and not isinstance(payload["results"], list):
        violations.append("results is not a list")
    return violations


def strip_volatile(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Deep-copy payload minus volatile fields, for byte-level replay diff."""
    stripped = copy.deepcopy(payload)
    for key in VOLATILE_TOP_LEVEL:
        stripped.pop(key, None)
    for item in stripped.get("results") or []:
        if isinstance(item, dict):
            for key in VOLATILE_RESULT_KEYS:
                item.pop(key, None)
    return stripped
