"""Statistical rigor for evaluation reports (M3 ②).

Two surfaces consume this module:

1. single-run payloads (``finalize_payload`` metrics) — ``accuracy_stats`` /
   ``accuracy_ci`` attach a bootstrap confidence interval to the bare
   accuracy number so downstream readers stop treating point estimates as
   law;
2. seed-repeat summaries (``run_seed_repeats.py``) — ``repeats_stats`` /
   ``repeats_ci`` aggregate variance across repeated runs.

Design constraints:
- deterministic: bootstrap RNG is seeded, so repeated runs on identical
  inputs produce byte-identical summaries (replay-friendly, cf. M1);
- dependency-free: pure stdlib, no numpy/scipy.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

DEFAULT_RESAMPLES = 10_000
DEFAULT_CI_LEVEL = 0.95
DEFAULT_SEED = 20260825  # project-constant so summaries are reproducible


def bootstrap_ci(
    accuracies: Sequence[float],
    *,
    n_resamples: int = DEFAULT_RESAMPLES,
    ci: float = DEFAULT_CI_LEVEL,
    seed: int = DEFAULT_SEED,
) -> Dict[str, Any]:
    """Percentile-bootstrap CI for the mean of per-example correctness.

    ``accuracies`` is a sequence of 0/1 (or fractional) per-per-example
    outcomes. Returns a dict with mean / bounds / metadata.
    """
    n = len(accuracies)
    if n == 0:
        return {
            "n": 0,
            "mean": None,
            "ci": level_tuple(None, None, ci),
            "resamples": 0,
            "method": "percentile-bootstrap",
        }

    point = sum(accuracies) / n
    if n == 1:
        lo = hi = float(accuracies[0])
        return {
            "n": 1,
            "mean": point,
            "ci": level_tuple(lo, hi, ci),
            "resamples": 0,
            "method": "degenerate (n=1)",
        }

    rng = random.Random(seed)
    means: List[float] = []
    for _ in range(n_resamples):
        total = sum(accuracies[rng.randrange(n)] for _ in range(n))
        means.append(total / n)
    means.sort()
    alpha = 1.0 - ci
    lo = means[max(0, int(alpha / 2 * n_resamples))]
    hi = means[min(n_resamples - 1, int((1 - alpha / 2) * n_resamples))]
    return {
        "n": n,
        "mean": point,
        "ci": level_tuple(lo, hi, ci),
        "resamples": n_resamples,
        "method": "percentile-bootstrap",
    }


def level_tuple(low: Optional[float], high: Optional[float], ci: float) -> Dict[str, Any]:
    return {"level": ci, "low": low, "high": high}


def accuracy_stats(results: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Bootstrap stats over a run's ``results`` list (uses ``is_correct``)."""
    outcomes = [1.0 if r.get("is_correct") else 0.0 for r in results]
    return bootstrap_ci(outcomes)


def repeats_stats(run_accuracies: Sequence[float]) -> Dict[str, Any]:
    """Variance aggregation across repeated runs (mean ± bootstrap CI).

    ``run_accuracies`` are the per-run accuracies from repeated evaluations
    of the same seed/sample. Adds spread diagnostics (std, min, max) so an
    unstable seed is visible at a glance.
    """
    n = len(run_accuracies)
    if n == 0:
        return {"n": 0, "mean": None, "std": None, "min": None, "max": None,
                "ci": level_tuple(None, None, DEFAULT_CI_LEVEL)}

    mean = sum(run_accuracies) / n
    if n == 1:
        std = 0.0
    else:
        var = sum((a - mean) ** 2 for a in run_accuracies) / (n - 1)
        std = math.sqrt(var)

    ci = bootstrap_ci(run_accuracies)
    return {
        "n": n,
        "mean": mean,
        "std": std,
        "min": min(run_accuracies),
        "max": max(run_accuracies),
        "ci": ci["ci"],
    }


def format_accuracy_line(stats: Dict[str, Any], *, percent: bool = True) -> str:
    """Human-readable one-liner, e.g. ``Accuracy: 42.0% [95% CI 33.0–51.0%, n=50]``."""
    n = stats.get("n", 0)
    mean = stats.get("mean")
    ci = stats.get("ci") or {}
    if mean is None:
        return "Accuracy: n/a (no results)"
    scale = 100.0 if percent else 1.0
    suffix = "%" if percent else ""
    low, high = ci.get("low"), ci.get("high")
    level = ci.get("level", DEFAULT_CI_LEVEL) * (100.0 if percent else 1.0)
    level_label = f"{level:.0f}%" if percent else f"{level:.2f}"
    if low is None or high is None:
        return f"Accuracy: {mean * scale:.1f}{suffix} (n={n})"
    return (
        f"Accuracy: {mean * scale:.1f}{suffix} "
        f"[{level_label} CI {low * scale:.1f}–{high * scale:.1f}{suffix}, n={n}]"
    )
