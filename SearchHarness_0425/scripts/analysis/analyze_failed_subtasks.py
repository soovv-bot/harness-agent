#!/usr/bin/env python3
"""分析失败样本的 subtask 分发与候选合并流程。"""
import json
import sys
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
RESULTS = json.load(open(BASE / "results/seed123_full_glm52_partial.json"))

# pos -> trajectory path
failed = {r["sample_position"]: r for r in RESULTS["results"] if r["sample_position"] in (3, 6, 7, 9, 10)}


def analyze(traj_path, info):
    print(f"\n{'='*78}")
    print(f"POSITION {info['sample_position']} | status={info['pipeline_status']} | correct={info['correct_answer']!r}")
    print(f"extracted={info.get('extracted_answer','')!r}")
    print(f"trajectory: {traj_path}")
    print(f"{'='*78}")
    traj = json.load(open(traj_path))

    md = traj.get("metadata", {})
    print(f"iterations={md.get('iterations')} stop_reason={md.get('stop_reason')} is_correct={md.get('is_correct')}")

    # ---- Subtask 分发序列 ----
    print("\n--- Subtask 分发序列 ---")
    its = traj.get("iteration_summaries", [])
    for s in its:
        it = s.get("iteration", "?")
        ph = s.get("phase", "")
        st = (s.get("subtask", "") or "")[:75]
        nc = s.get("new_candidates", []) or []
        ec = s.get("eliminated_candidates", []) or []
        searches = s.get("searches", 0)
        crawls = s.get("crawls", 0)
        nc_short = nc if len(nc) <= 6 else f"{nc[:3]}...(+{len(nc)-3})"
        print(f"  iter={it} phase={ph:22s} srch={searches:3d} crawl={crawls:2d} | new={nc_short} elim={ec}")

    # ---- 候选池最终状态 ----
    ps = traj.get("pipeline_state", {})
    cr = ps.get("candidate_records", {})
    ss = ps.get("state_summary", {})
    print(f"\n--- 候选池最终状态 (共 {len(cr)} 条) ---")
    print(f"  current_candidates({len(ss.get('current_candidates',[]))}): {ss.get('current_candidates',[])}")
    print(f"  eliminated_candidates({len(ss.get('eliminated_candidates',[]))}): {ss.get('eliminated_candidates',[])}")
    # 正确答案是否出现在候选池
    correct = info["correct_answer"].strip().lower()
    found_correct = [n for n in cr.keys() if correct in n or n in correct]
    print(f"  正确答案在候选池? {'是: ' + str(found_correct) if found_correct else '否 ❌'}")
    if found_correct:
        rec = cr.get(found_correct[0], {})
        print(f"    record: status={rec.get('status')} verification={rec.get('verification_status')} confidence={rec.get('confidence')} hard_conflicts={len(rec.get('hard_conflicts',[]) or [])}")

    # ---- 给出最终答案的候选（extracted_answer）是否在池中 ----
    ext = (info.get("extracted_answer") or "").strip().lower()
    if ext and ext != "unknown":
        ext_in_pool = [n for n in cr.keys() if ext in n or n in ext]
        print(f"  最终答案在候选池? {'是: '+str(ext_in_pool) if ext_in_pool else '否'}")
        if ext_in_pool:
            rec = cr.get(ext_in_pool[0], {})
            print(f"    record: status={rec.get('status')} verification={rec.get('verification_status')} hard_conflicts={len(rec.get('hard_conflicts',[]) or [])}")

    # ---- Planner 规划次数与是否 replan ----
    pc = traj.get("planner_conversations", [])
    print(f"\n--- Planner 规划次数: {len(pc)} ---")

    # ---- 找关键失败点：正确答案是否被错误淘汰 ----
    print("\n--- 失败模式诊断 ---")
    if not found_correct:
        print(f"  ❌ 失败模式: 正确答案 {info['correct_answer']!r} 从未进入候选池 (subtask 未覆盖)")
    else:
        rec = cr.get(found_correct[0], {})
        if rec.get("status") == "eliminated":
            print(f"  ❌ 失败模式: 正确答案被错误淘汰 (eliminated)")
            hc = rec.get("hard_conflicts", [])
            if hc:
                print(f"     hard_conflicts: {hc[:2]}")
        elif rec.get("status") == "active":
            if ext and found_correct and ext_in_pool and ext_in_pool != found_correct:
                print(f"  ❌ 失败模式: 正确答案在池中但未被选为最终答案 (selection error)")
            elif not ext or ext == "unknown":
                print(f"  ❌ 失败模式: 正确答案在池中但 pipeline 未给出答案 (finalize failure, status={info['pipeline_status']})")
            else:
                print(f"  ⚠️ 失败模式: 候选池有正确答案但最终答案不匹配 (grader/extract mismatch?)")
        else:
            print(f"  ⚠️ 其他: record status={rec.get('status')}")

    return traj


for pos in [3, 6, 7, 9, 10]:
    info = failed[pos]
    tp = info.get("trajectory_path", "")
    if not tp:
        print(f"\nposition {pos}: 无 trajectory_path")
        continue
    full = BASE / tp
    if not full.exists():
        print(f"\nposition {pos}: 轨迹文件不存在 {full}")
        continue
    analyze(full, info)
