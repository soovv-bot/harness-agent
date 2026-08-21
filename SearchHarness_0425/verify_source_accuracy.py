"""Quick smoke verification for the 数据源管控 (data-source accuracy) changes.

Runs ONE real Serper query on a time-sensitive topic, then prints the
before/after of `_postprocess_serper_results` so you can eyeball:
  - credibility rerank (official/encyclopedia above UGC)
  - stale-result drop (time-sensitive query)
  - cross-domain repost merge

Usage:  python verify_source_accuracy.py "your query here"
Default query if none given: a 2026 time-sensitive topic.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Load .env from repo root (two levels up: SearchHarness_0425 -> repo root)
ROOT = Path(__file__).resolve().parent.parent
_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from tools.search_tools import _call_serper_api, _postprocess_serper_results  # type: ignore


def _print(label, results):
    print(f"\n{'='*78}\n{label}  ({len(results)} results)\n{'='*78}")
    for i, r in enumerate(results):
        tier = r.get("credibility_tier", "-")
        ff = r.get("freshness_flag", "-")
        pub = r.get("freshness", {}).get("published", "-")
        date = r.get("date", "-")
        print(f"  [{i}] tier={tier} fresh={ff:9} pub={pub:11} date={date!r:24}")
        print(f"      {r.get('title','')[:70]}")
        print(f"      {r.get('link','')}")


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "latest AI model release 2026"
    print(f"QUERY: {query!r}  (time-sensitive: see source_quality below)")

    raw = _call_serper_api(query)
    data_raw = json.loads(raw)
    organic_before = data_raw.get("organic", [])

    processed = _postprocess_serper_results(raw, query)
    data_after = json.loads(processed)
    organic_after = data_after.get("organic", [])

    _print("BEFORE post-processing (raw Serper)", organic_before)
    _print("AFTER  post-processing (credibility + freshness + merge)",
           organic_after)

    print(f"\n{'='*78}\nMETA\n{'='*78}")
    for k in ("dedup_merges", "freshness_dropped", "source_quality"):
        v = data_after.get(k)
        if v is not None:
            print(f"  {k}: {json.dumps(v, ensure_ascii=False)}")

    # Quick assertions to confirm the pipeline did something non-trivial.
    assert len(organic_after) <= 8, "top-8 truncation failed"
    tiers = [r.get("credibility_tier") for r in organic_after]
    assert all(isinstance(t, int) for t in tiers), "credibility not annotated"
    print("\nOK: top-8 cap + credibility annotation verified.")


if __name__ == "__main__":
    main()
