#!/usr/bin/env python3
"""Offline failure-taxonomy analyzer (Plan E).

Scans generated trajectories and classifies each failed task into one of
four diagnostic buckets. The taxonomy turns the project's 41% error mass
(14% wrong + 27% no-answer on BrowseComp) into an actionable breakdown that
can be reported in the paper's error-analysis section and used to direct
future data-synthesis effort.

Categories
----------
1. ``candidate_failure``   — the agent never produced a concrete candidate
   (answer is empty / "Unknown" / no-answer folder). Indicates the
   Planner/Executor never converged on a hypothesis worth verifying.
2. ``search_failure``      — the agent hit the search/turn budget
   (``max_turns_reached`` / ``max_total_searches_reached``) without
   converging. Indicates retrieval exhaustion, not reasoning failure.
3. ``finalizer_failure``  — the agent reported ``completed`` but the answer
   is wrong (``answer_match == False`` with non-empty answer). Indicates a
   "strong-but-false" candidate the finalizer committed to — exactly the
   failure mode Plan A (self-verification) targets.
4. ``verification_failure``— the new self-verification layer refuted an
   otherwise-committed answer. Only present once Plan A is enabled in
   production runs; absent from legacy trajectories.

Usage
-----
    python failure_taxonomy.py [--root data/trajectories] \\
        [--out failure_taxonomy_report.json]

The script is read-only: it never modifies trajectory files.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

UNKNOWN_TOKENS = {"", "unknown", "none", "null", "n/a", "no answer"}
SEARCH_STOP_TRIGGERS = {
    "max_turns_reached",
    "max_total_searches_reached",
    "max_crawl_calls_reached",
    "max_iterations_reached",
}


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _is_unknown_answer(answer: str) -> bool:
    a = _norm(answer)
    return a in UNKNOWN_TOKENS or a.startswith("i don't know") or a.startswith("i cannot")


def _count_tool_calls(trajectory: List[Dict[str, Any]]) -> int:
    n = 0
    for m in trajectory or []:
        if m.get("role") == "assistant":
            if m.get("tool_calls"):
                n += len(m["tool_calls"])
        # OpenAI-style tool_call_id messages are tool results; not counted
    return n


def classify(task: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Return (category, evidence) for one trajectory file payload.

    ``correct`` is a non-failure sentinel used so the report covers the whole
    dataset, not just failures.
    """
    md = task.get("metadata", {}) or {}
    gen = task.get("generation_metadata", {}) or {}
    status = _norm(md.get("status") or gen.get("latest_status") or "")
    answer = task.get("answer") or md.get("final_answer") or gen.get("latest_answer") or ""
    answer_match = task.get("answer_match")
    trajectory = task.get("trajectory", []) or []
    tool_calls = _count_tool_calls(trajectory)
    turns = md.get("turns", len(trajectory))

    evidence = {
        "status": status,
        "answer_preview": (answer or "")[:120],
        "answer_match": answer_match,
        "turns": turns,
        "tool_calls": tool_calls,
    }

    # Success: answer explicitly matched ground truth.
    if answer_match is True:
        return "correct", evidence

    # Category 4: verification_failure (Plan A refuted a committed answer).
    # Detected via the new `verification` field written by SearchFinalizer.
    verification = md.get("verification") or task.get("verification")
    if isinstance(verification, dict) and verification.get("verdict") == "refuted":
        evidence["verification"] = verification
        return "verification_failure", evidence

    # Category 1: candidate_failure — no concrete candidate produced.
    if _is_unknown_answer(answer):
        # Distinguish search-budget exhaustion from plain non-convergence.
        if status in SEARCH_STOP_TRIGGERS:
            return "search_failure", evidence
        return "candidate_failure", evidence

    # Category 3: finalizer_failure — committed a wrong concrete answer.
    if answer_match is False or (answer_match is None and status == "completed" and answer):
        return "finalizer_failure", evidence

    # Category 2: search_failure — budget exhausted with some (unverified) answer.
    if status in SEARCH_STOP_TRIGGERS:
        return "search_failure", evidence

    # Fallback: non-terminal, no match, not obviously unknown.
    return "candidate_failure", evidence


def scan(root: Path) -> Dict[str, Any]:
    files = sorted(root.rglob("*.json"))
    files = [f for f in files if f.name not in {"generation_metadata.json", "batch_summary.json"}]
    per_file: List[Dict[str, Any]] = []
    cat_counter: Counter = Counter()
    # sub-bucket by source folder (answer_correct / answer_wrong / no_answer)
    folder_cat: Dict[str, Counter] = {}

    for f in files:
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:
            per_file.append({"file": str(f), "category": "parse_error", "error": str(exc)})
            cat_counter["parse_error"] += 1
            continue
        category, evidence = classify(payload)
        rel = f.relative_to(root)
        folder = rel.parts[0] if len(rel.parts) > 1 else "(root)"
        cat_counter[category] += 1
        folder_cat.setdefault(folder, Counter())[category] += 1
        per_file.append({
            "file": str(rel),
            "task_index": payload.get("task_index"),
            "category": category,
            **evidence,
        })

    total = sum(cat_counter.values())
    summary = {
        "root": str(root),
        "total_files": total,
        "categories": dict(cat_counter),
        "category_pct": {k: round(v / total * 100, 2) for k, v in cat_counter.items()} if total else {},
        "by_source_folder": {k: dict(v) for k, v in folder_cat.items()},
    }
    return {"summary": summary, "per_file": per_file}


def main() -> None:
    ap = argparse.ArgumentParser(description="Classify trajectory failures into a 4-bucket taxonomy.")
    ap.add_argument("--root", type=Path, default=Path("data/trajectories"))
    ap.add_argument("--out", type=Path, default=Path("failure_taxonomy_report.json"))
    ap.add_argument("--csv", type=Path, default=None, help="Optional per-file CSV output")
    args = ap.parse_args()

    if not args.root.exists():
        raise SystemExit(f"trajectory root not found: {args.root}")

    report = scan(args.root)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    s = report["summary"]
    print(f"Scanned {s['total_files']} trajectory files under {s['root']}")
    print("Category counts:")
    for cat, n in s["categories"].items():
        pct = s["category_pct"].get(cat, 0.0)
        print(f"  {cat:22s} {n:4d}  ({pct:.1f}%)")
    print("By source folder:")
    for folder, counts in s["by_source_folder"].items():
        print(f"  {folder:18s} {counts}")
    print(f"\nFull report: {args.out}")

    if args.csv:
        import csv
        with args.csv.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["file", "task_index", "category", "status", "answer_match", "turns", "tool_calls", "answer_preview"])
            for row in report["per_file"]:
                w.writerow([
                    row.get("file"), row.get("task_index"), row.get("category"),
                    row.get("status"), row.get("answer_match"), row.get("turns"),
                    row.get("tool_calls"), row.get("answer_preview", ""),
                ])
        print(f"CSV: {args.csv}")


if __name__ == "__main__":
    main()
