"""Diagnose wrong-answer trajectories.

For each trajectory file, report:
- searches / crawls / iters / stop_reason / final answer
- whether the gold answer appeared in: search results, candidate list, candidate_records
- top candidates (by supporting count) and their verification status
- where the gold was likely lost (never surfaced / surfaced but eliminated / surfaced but not chosen)
"""
import json, sys, re, os
from pathlib import Path

TRAJ_DIR = Path("logs/trajectories_eval10_hi/GLM-5.2")
MANIFEST = {x["sample_position"]: x for x in json.load(open("data/seed123_k10_manifest.json"))}
RESULTS = {}  # populated by CLI below
# (overridden by CLI args below if provided)

def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

def scan_text_for_gold(text, gold):
    """Check if gold (or significant token) appears in text."""
    if not text or not gold:
        return False
    ng = norm(gold)
    nt = norm(text)
    if ng and ng in nt:
        return True
    # token-level: gold tokens (len>=4) all present
    gtokens = [t for t in re.split(r"[\s\-,.:;\"'()/]+", gold.lower()) if len(t) >= 4]
    if gtokens and all(t.lower() in nt for t in gtokens):
        return True
    return False

def diagnose(pos):
    traj_file = TRAJ_DIR / f"task_{pos:06d}.json"
    if not traj_file.exists():
        return f"!! trajectory not found: {traj_file}"
    d = json.load(open(traj_file))
    md = d["metadata"]
    gold = MANIFEST[pos-1]["answer"].strip()
    res = RESULTS[pos]
    ans = (res.get("extracted_answer") or res.get("pipeline_answer_raw") or "").strip()

    search_log = d.get("search_log", [])
    events = d.get("events", [])
    cand_recs = d.get("pipeline_state", {}).get("candidate_records", {})
    # candidate_records may be dict or list
    cand_list = []
    if isinstance(cand_recs, dict):
        for name, rec in cand_recs.items():
            cand_list.append((name, rec))
    elif isinstance(cand_recs, list):
        for rec in cand_recs:
            cand_list.append((rec.get("name","?"), rec))

    # gather all search result text
    all_search_text = []
    for s in search_log:
        # search_log entries vary; try common fields
        if isinstance(s, dict):
            for k in ("results","result","snippets","content","raw","response","query_results"):
                v = s.get(k)
                if isinstance(v, (list, str)):
                    all_search_text.append(json.dumps(v, ensure_ascii=False))
    all_search_blob = " ".join(all_search_text)

    # gold in search results?
    gold_in_search = scan_text_for_gold(all_search_blob, gold)

    # gold in candidate list?
    gold_in_cands = any(scan_text_for_gold(name, gold) for name, _ in cand_list)

    # gold in any candidate record's evidence?
    gold_in_evidence = False
    for name, rec in cand_list:
        ev = json.dumps(rec, ensure_ascii=False) if isinstance(rec, dict) else str(rec)
        if scan_text_for_gold(ev, gold):
            gold_in_evidence = True

    # summarize candidate records
    cand_summary = []
    for name, rec in cand_list[:12]:
        if isinstance(rec, dict):
            status = rec.get("verification_status") or rec.get("status") or "?"
            support = rec.get("supporting_constraints") or rec.get("support_count") or 0
            try: support_n = len(support) if isinstance(support, (list,dict)) else support
            except: support_n = support
            cand_summary.append(f"{name[:30]}({status},sup={support_n})")
        else:
            cand_summary.append(f"{name[:30]}(?)")

    # count searches/crawls from events
    n_search = md.get("total_searches", 0)
    n_crawl = md.get("total_crawls", 0)
    n_llm = md.get("total_llm_calls", 0)

    out = []
    out.append(f"=== pos{pos} | correct={res.get('is_correct')} | status={md.get('status')} stop={md.get('stop_reason')} iters={md.get('iterations')} ===")
    out.append(f"  gold : {gold}")
    out.append(f"  ans  : {ans[:80]}")
    out.append(f"  budget: searches={n_search} crawls={n_crawl} llm={n_llm}")
    out.append(f"  gold found in search results? {gold_in_search}")
    out.append(f"  gold in candidate list?       {gold_in_cands}")
    out.append(f"  gold in candidate evidence?   {gold_in_evidence}")
    out.append(f"  candidates ({len(cand_list)}): " + " | ".join(cand_summary[:10]))
    out.append("")
    return "\n".join(out)

# Usage: diagnose_trajectories.py [--traj-dir DIR] [--results PATH] [pos ...]
# Defaults: traj-dir=logs/trajectories_rerun6_full/GLM-5.2 results=results/seed123_rerun6_full.json
import argparse
ap = argparse.ArgumentParser()
ap.add_argument("--traj-dir", default="logs/trajectories_rerun6_full/GLM-5.2")
ap.add_argument("--results", default="results/seed123_rerun6_full.json")
ap.add_argument("positions", nargs="*", type=int)
args = ap.parse_args()
TRAJ_DIR = Path(args.traj_dir)
if args.results and Path(args.results).exists():
    RESULTS = {r["sample_position"]: r for r in json.load(open(args.results))["results"]}
positions = args.positions or [2,5,6,7,8,10]
for p in positions:
    print(diagnose(p))
