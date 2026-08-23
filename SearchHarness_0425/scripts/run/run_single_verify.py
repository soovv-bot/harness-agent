"""Run single BrowseComp questions by task_index for quick verification.

Uses the same seed-based sampling as run_browsecomp.py so task indices
match the 50-question eval. Runs only the specified task indices.

Usage:
    cd SearchHarness_0425
    python -m scripts.run.run_single_verify --task-indices 8 23 38 44 \
        --output results/verify_v7_lost4.json \
        --trajectory-dir logs/trajectories_v7_verify \
        --max-total-searches 160 --max-crawl-calls 40
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from loguru import logger

_HERE = Path(__file__).resolve().parents[2]
load_dotenv(_HERE.parent / ".env")

from scripts.run.run_browsecomp import run_single_task, resolve_primary_model, resolve_grader_config  # noqa: E402
from pipeline.orchestrator import SearchHarnessPipelineV4  # noqa: E402
from trajectory.recorder import TrajectoryRecorderEnhanced  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-indices", type=int, nargs="+", required=True,
                    help="Task indices to run (from seed-based 50-sample)")
    ap.add_argument("--output", required=True)
    ap.add_argument("--trajectory-dir", required=True)
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--num-pool", type=int, default=50, help="Pool size for sampling")
    ap.add_argument("--max-iterations", type=int, default=6)
    ap.add_argument("--max-planner-searches", type=int, default=10)
    ap.add_argument("--max-executor-searches", type=int, default=20)
    ap.add_argument("--max-total-searches", type=int, default=160)
    ap.add_argument("--max-crawl-calls", type=int, default=40)
    args = ap.parse_args()

    api_base = os.getenv("OPENAI_BASE_URL")
    api_key = os.getenv("OPENAI_API_KEY")
    model_id = resolve_primary_model()
    gcfg = resolve_grader_config(api_base or "", api_key or "", model_id)
    from run_browsecomp import LLMGrader
    grader = LLMGrader(api_base=gcfg["api_base"], api_key=gcfg["api_key"], model_id=gcfg["model_id"])

    logger.info("Loading BrowseComp dataset...")
    df = pd.read_csv(
        "https://openaipublic.blob.core.windows.net/simple-evals/browse_comp_test_set.csv"
    )
    examples = [row.to_dict() for _, row in df.iterrows()]
    rng = random.Random(args.seed)
    examples = rng.sample(examples, args.num_pool)

    pipeline_kwargs = {
        "max_iterations": args.max_iterations,
        "max_crawl_calls": args.max_crawl_calls,
    }

    results = []
    for idx in sorted(args.task_indices):
        if idx >= len(examples):
            logger.warning(f"task_index {idx} out of range (pool={args.num_pool})")
            continue
        ex = examples[idx]
        from run_browsecomp import _decrypt
        canary = ex.get("canary", "")
        question = _decrypt(ex.get("problem", ""), canary)
        answer = _decrypt(ex.get("answer", ""), canary)

        pipeline = SearchHarnessPipelineV4(
            api_base=api_base, api_key=api_key, model_id=model_id,
            max_planner_searches=args.max_planner_searches,
            max_executor_searches=args.max_executor_searches,
            max_total_searches=args.max_total_searches,
        )
        recorder = TrajectoryRecorderEnhanced(
            model_id=model_id, output_dir=args.trajectory_dir, task_index=idx
        )
        logger.info(f"=== Task {idx} === question: {question[:120]}")
        r = run_single_task(
            task_index=idx, question=question, correct_answer=answer,
            pipeline=pipeline, grader=grader, pipeline_kwargs=pipeline_kwargs,
            trajectory_recorder=recorder,
        )
        results.append(r)
        logger.info(f"[Task {idx}] correct={r['is_correct']} answer='{r.get('extracted_answer','')[:80]}'")

    n_correct = sum(1 for r in results if r["is_correct"])
    summary = {
        "total": len(results),
        "correct": n_correct,
        "accuracy": n_correct / len(results) if results else 0.0,
        "task_indices": args.task_indices,
        "seed": args.seed,
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump({"summary": summary, "results": results}, f, ensure_ascii=False, indent=2)
    logger.info(f"Wrote {args.output} | {n_correct}/{len(results)} ({summary['accuracy']:.1%})")
    print(f"\n=== VERIFY RESULTS ===\n{n_correct}/{len(results)} ({summary['accuracy']:.1%})\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
