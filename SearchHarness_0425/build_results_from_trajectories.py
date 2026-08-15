"""Build a results JSON from saved trajectories + LLM grading.

Used when the eval pipeline completed all 50 tasks (trajectories saved) but
the final results JSON was not written (e.g. process was killed by the
`| head -30` output truncation).

Extracts the pipeline answer from each trajectory's messages (the last
<answer>...</answer> block in the assistant messages), then runs the LLM
grader against the BrowseComp ground truth, producing the same result schema
as run_browsecomp.py.

Usage:
    cd SearchHarness_0425
    python build_results_from_trajectories.py \
        --trajectory-dir logs/trajectories_v6 \
        --output results/browsecomp_v6.json \
        --seed 123 \
        --num-examples 50 \
        --max-workers 5
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv
from loguru import logger
from tqdm import tqdm

_HERE = Path(__file__).resolve().parent
# .env lives one directory up (parent of SearchHarness_0425/)
load_dotenv(_HERE.parent / ".env")

# Reuse the grader + extraction logic from run_browsecomp.py
import sys as _sys
_sys.path.insert(0, str(_HERE))
from run_browsecomp import LLMGrader, extract_answer_from_pipeline, _decrypt  # noqa: E402

TRAJ_MODEL_DIR = "GLM-5.2"  # sub-directory inside trajectory-dir


def _load_trajectories(trajectory_dir: Path) -> Dict[int, Dict[str, Any]]:
    """Map task_index -> trajectory dict."""
    model_dir = trajectory_dir / TRAJ_MODEL_DIR
    if not model_dir.exists():
        # fallback: maybe trajectories are directly under trajectory_dir
        model_dir = trajectory_dir
    out: Dict[int, Dict[str, Any]] = {}
    for p in sorted(model_dir.glob("task_*.json")):
        m = re.match(r"task_(\d+)\.json", p.name)
        if not m:
            continue
        idx = int(m.group(1))
        try:
            with open(p) as f:
                out[idx] = json.load(f)
        except Exception as e:
            logger.warning(f"failed to load {p.name}: {e}")
    return out


def _answer_from_trajectory(traj: Dict[str, Any]) -> tuple[str, str, str]:
    """Return (extracted_answer, raw_answer, status) from a trajectory."""
    # 1) Prefer pipeline_state if it carries an answer field.
    raw = ""
    # 2) Scan assistant messages for the LAST <answer>...</answer> block.
    msgs = traj.get("messages", []) or []
    answer_blocks: List[str] = []
    for m in msgs:
        if m.get("role") != "assistant":
            continue
        content = m.get("content", "") or ""
        found = re.findall(r"<answer>(.*?)</answer>", content, re.DOTALL | re.IGNORECASE)
        if found:
            answer_blocks.extend(found)
    if answer_blocks:
        raw = f"<answer>{answer_blocks[-1].strip()}</answer>"

    # Also check iteration_summaries for a final answer
    status = "completed" if raw else "no_answer"
    # Use the same extractor as run_browsecomp (it parses JSON inside <answer>)
    try:
        extracted = extract_answer_from_pipeline({"answer": raw}) if raw else ""
    except Exception:
        # Fallback: if the extractor chokes (e.g. answer is a bare number),
        # return the text inside the last <answer> block.
        extracted = answer_blocks[-1].strip() if answer_blocks else ""
    return extracted, raw, status


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trajectory-dir", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--num-examples", type=int, default=50)
    ap.add_argument("--max-workers", type=int, default=5)
    args = ap.parse_args()

    # Grader config from env (same fallbacks as regrade_results.py)
    gbase = os.getenv("GRADER_API_BASE") or os.getenv("GRADER_OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    gkey = os.getenv("GRADER_API_KEY") or os.getenv("GRADER_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    gmodel = os.getenv("GRADER_MODEL") or os.getenv("GRADER_MODEL_NAME") or os.getenv("MODEL_NAME", "deepseek-chat")
    if not (gbase and gkey):
        logger.error("Missing grader API base/key in .env")
        return 1
    grader = LLMGrader(api_base=gbase, api_key=gkey, model_id=gmodel)

    # Load dataset and sample exactly like run_browsecomp.py
    logger.info("Loading BrowseComp dataset...")
    df = pd.read_csv(
        "https://openaipublic.blob.core.windows.net/simple-evals/browse_comp_test_set.csv"
    )
    examples = [row.to_dict() for _, row in df.iterrows()]
    rng = random.Random(args.seed)
    examples = rng.sample(examples, args.num_examples)
    logger.info(f"Loaded {len(examples)} examples (seed={args.seed})")

    # Load trajectories
    traj_dir = Path(args.trajectory_dir)
    trajs = _load_trajectories(traj_dir)
    logger.info(f"Loaded {len(trajs)} trajectories from {traj_dir}")

    results: List[Dict[str, Any]] = []
    lock = __import__("threading").Lock()

    def _worker(i: int, example: Dict) -> Dict[str, Any]:
        canary = example.get("canary", "")
        question = _decrypt(example.get("problem", ""), canary)
        answer = _decrypt(example.get("answer", ""), canary)
        traj = trajs.get(i, {})
        if not isinstance(traj, dict):
            logger.error(f"[Task {i}] traj is {type(traj).__name__} not dict: {traj!r}")
            traj = {}
        extracted, raw, status = _answer_from_trajectory(traj)
        grade = grader.grade(question, extracted or raw, answer)
        elapsed = 0.0
        logger.info(f"[Task {i}] correct={grade['correct']} | answer='{extracted[:60]}' | status={status}")
        return {
            "task_index": i,
            "question_preview": question[:150],
            "correct_answer": answer,
            "extracted_answer": extracted,
            "pipeline_answer_raw": raw[:500] if raw else "",
            "pipeline_status": status,
            "failure_category": "" if extracted else "no_answer_in_trajectory",
            "is_correct": grade["correct"],
            "grader_extracted": grade["extracted_answer"],
            "grader_reasoning": grade["reasoning"],
            "grader_status": grade.get("status", "ok"),
            "grader_error_type": grade.get("error_type", ""),
            "elapsed_seconds": round(elapsed, 1),
            "trajectory_path": str(traj_dir / TRAJ_MODEL_DIR / f"task_{i:06d}.json"),
            "iterations": len(traj.get("iteration_summaries", [])) if traj else 0,
            "stop_reason": status,
        }

    with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        futs = {pool.submit(_worker, i, ex_dict): i for i, ex_dict in enumerate(examples)}
        for fut in tqdm(as_completed(futs), total=len(futs), desc="Grading"):
            try:
                r = fut.result()
                with lock:
                    results.append(r)
            except Exception as e:
                import traceback
                logger.error(f"worker error: {e}\n{traceback.format_exc()}")

    results.sort(key=lambda r: r["task_index"])
    n_correct = sum(1 for r in results if r["is_correct"])
    summary = {
        "total": len(results),
        "correct": n_correct,
        "accuracy": n_correct / len(results) if results else 0.0,
        "seed": args.seed,
        "trajectory_dir": str(traj_dir),
        "grader_model": gmodel,
    }
    out = {"summary": summary, "results": results}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    logger.info(f"Wrote {args.output} | accuracy={n_correct}/{len(results)} ({summary['accuracy']:.1%})")
    print(f"\n=== RESULTS ===\naccuracy: {n_correct}/{len(results)} ({summary['accuracy']:.1%})\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
