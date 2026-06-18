"""Run BrowseComp on a fixed sampled subset.

This helper reconstructs the exact `random.sample(..., k)` set for a given seed
and sample size, then evaluates only the requested sample positions.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List

import pandas as pd
from dotenv import load_dotenv
from loguru import logger
from tqdm import tqdm

from run_browsecomp import LLMGrader, _decrypt, run_single_task

BROWSECOMP_URL = "https://openaipublic.blob.core.windows.net/simple-evals/browse_comp_test_set.csv"
_HERE = Path(__file__).resolve().parent
BROWSECOMP_CACHE = _HERE / "docs" / "browse_comp_test_set.csv"
LOCAL_FULL_SUBSET = _HERE / "docs" / "seed123_k10_full.json"


def _configure_console_logging() -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        level=os.getenv("LOG_LEVEL", "INFO"),
        enqueue=False,
        backtrace=False,
        diagnose=False,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}",
    )


def _parse_positions(raw: str) -> List[int]:
    positions: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_str, end_str = part.split("-", 1)
            start = int(start_str)
            end = int(end_str)
            step = 1 if end >= start else -1
            positions.extend(list(range(start, end + step, step)))
        else:
            positions.append(int(part))
    # Keep order but dedupe
    seen = set()
    ordered: List[int] = []
    for pos in positions:
        if pos not in seen:
            seen.add(pos)
            ordered.append(pos)
    return ordered


def _load_fixed_sample(seed: int, sample_size: int) -> List[Dict[str, Any]]:
    logger.info("Loading BrowseComp dataset...")
    if seed == 123 and sample_size == 10 and LOCAL_FULL_SUBSET.exists():
        logger.info(f"Using local fixed subset: {LOCAL_FULL_SUBSET}")
        subset = json.loads(LOCAL_FULL_SUBSET.read_text(encoding="utf-8"))
        return [
            {
                "problem_plaintext": item["question"],
                "answer_plaintext": item["answer"],
                "sample_position": item.get("sample_position"),
            }
            for item in subset
        ]
    if BROWSECOMP_CACHE.exists():
        logger.info(f"Using cached BrowseComp dataset: {BROWSECOMP_CACHE}")
        df = pd.read_csv(BROWSECOMP_CACHE)
    else:
        df = pd.read_csv(BROWSECOMP_URL)
        BROWSECOMP_CACHE.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(BROWSECOMP_CACHE, index=False)
        logger.info(f"Cached BrowseComp dataset to: {BROWSECOMP_CACHE}")
    examples = [row.to_dict() for _, row in df.iterrows()]
    rng = random.Random(seed)
    sample = rng.sample(examples, sample_size)
    logger.info(f"Loaded fixed sample of {len(sample)} examples")
    return sample


def _save_manifest(sample: List[Dict[str, Any]], manifest_path: Path) -> None:
    manifest: List[Dict[str, Any]] = []
    for i, example in enumerate(sample):
        if "problem_plaintext" in example:
            question = example.get("problem_plaintext", "")
            answer = example.get("answer_plaintext", "")
        else:
            canary = example.get("canary", "")
            question = _decrypt(example.get("problem", ""), canary)
            answer = _decrypt(example.get("answer", ""), canary)
        manifest.append({
            "sample_position": i,
            "answer": answer,
            "question_preview": question[:150],
        })
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def run_fixed_evaluation(
    seed: int,
    sample_size: int,
    positions: List[int],
    output_file: str,
    trajectory_dir: str,
    max_iterations: int,
    max_crawl_calls: int,
    max_planner_searches: int,
    max_executor_searches: int,
    max_total_searches: int,
    max_workers: int = 1,
    enable_query_critic: bool = True,
) -> None:
    from search_harness_pipeline_v4 import SearchHarnessPipelineV4
    from trajectory_recorder import TrajectoryRecorder

    print("[run] starting fixed-sample evaluation", flush=True)
    load_dotenv()
    api_base = os.getenv("OPENAI_BASE_URL")
    api_key = os.getenv("OPENAI_API_KEY")
    model_id = os.getenv("MODEL_NAME", "deepseek-chat")
    executor_model_id = os.getenv("EXECUTOR_MODEL_NAME") or model_id
    grader_api_base = os.getenv("GRADER_OPENAI_BASE_URL") or api_base
    grader_api_key = os.getenv("GRADER_OPENAI_API_KEY") or api_key
    grader_model_id = os.getenv("GRADER_MODEL_NAME", "gpt-4o-2024-11-20")

    sample = _load_fixed_sample(seed=seed, sample_size=sample_size)

    manifest_path = _HERE / "docs" / f"seed{seed}_k{sample_size}_manifest.json"
    _save_manifest(sample, manifest_path)
    logger.info(f"Manifest saved to {manifest_path}")

    for pos in positions:
        if pos < 0 or pos >= len(sample):
            raise ValueError(f"Sample position {pos} is out of range for sample size {len(sample)}")

    grader = LLMGrader(api_base=grader_api_base, api_key=grader_api_key, model_id=grader_model_id)
    pipeline_kwargs: Dict[str, Any] = {
        "max_iterations": max_iterations,
        "max_crawl_calls": max_crawl_calls,
    }

    logger.info(f"Running fixed-sample evaluation for positions={positions} with max_workers={max_workers}")

    def _worker(sample_position: int) -> Dict[str, Any]:
        example = sample[sample_position]
        if "problem_plaintext" in example:
            question = example.get("problem_plaintext", "")
            answer = example.get("answer_plaintext", "")
        else:
            canary = example.get("canary", "")
            question = _decrypt(example.get("problem", ""), canary)
            answer = _decrypt(example.get("answer", ""), canary)
        pipeline = SearchHarnessPipelineV4(
            api_base=api_base,
            api_key=api_key,
            model_id=model_id,
            executor_model_id=executor_model_id,
            max_planner_searches=max_planner_searches,
            max_executor_searches=max_executor_searches,
            max_total_searches=max_total_searches,
            enable_query_critic=enable_query_critic,
        )
        recorder_model_id = model_id if executor_model_id == model_id else f"{model_id}__exec__{executor_model_id}"
        recorder = TrajectoryRecorder(model_id=recorder_model_id, output_dir=trajectory_dir, task_index=sample_position)
        result = run_single_task(
            task_index=sample_position,
            question=question,
            correct_answer=answer,
            pipeline=pipeline,
            grader=grader,
            pipeline_kwargs=pipeline_kwargs,
            trajectory_recorder=recorder,
        )
        result["sample_position"] = sample_position
        return result

    results: List[Dict[str, Any]] = []
    results_lock = Lock()
    overall_start = time.time()

    if max_workers <= 1:
        for sample_position in tqdm(positions, desc="Evaluating"):
            print(f"[run] starting position={sample_position}", flush=True)
            result = _worker(sample_position)
            with results_lock:
                results.append(result)
            print(f"[run] finished position={sample_position} status={result.get('pipeline_status', 'unknown')}", flush=True)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_worker, sp): sp
                for sp in positions
            }
            for future in tqdm(as_completed(futures), total=len(futures), desc="Evaluating"):
                sample_position = futures[future]
                try:
                    result = future.result()
                    with results_lock:
                        results.append(result)
                    print(f"[run] finished position={sample_position} status={result.get('pipeline_status', 'unknown')}", flush=True)
                except Exception as e:
                    logger.error(f"Task position={sample_position} failed: {e}")
                    with results_lock:
                        results.append({
                            "sample_position": sample_position,
                            "task_index": sample_position,
                            "is_correct": False,
                            "error": str(e),
                            "pipeline_status": "error",
                        })

    total_elapsed = time.time() - overall_start
    results.sort(key=lambda x: x["sample_position"])
    correct = sum(1 for r in results if r.get("is_correct"))
    total = len(results)
    accuracy = correct / total if total else 0.0

    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seed": seed,
        "sample_size": sample_size,
        "positions": positions,
        "model_id": model_id,
        "executor_model_id": executor_model_id,
        "grader_model_id": grader_model_id,
        "num_examples": total,
        "correct_count": correct,
        "accuracy": accuracy,
        "total_elapsed_seconds": round(total_elapsed, 1),
        "pipeline_config": {
            "max_iterations": max_iterations,
            "max_crawl_calls": max_crawl_calls,
            "max_planner_searches": max_planner_searches,
            "max_executor_searches": max_executor_searches,
            "max_total_searches": max_total_searches,
        },
        "results": results,
    }

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    Path(output_file).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 60, flush=True)
    print("BrowseComp Fixed-Sample Evaluation Results", flush=True)
    print("=" * 60, flush=True)
    print(f"Seed:           {seed}", flush=True)
    print(f"Sample size:    {sample_size}", flush=True)
    print(f"Positions:      {positions}", flush=True)
    print(f"Model:          {model_id}", flush=True)
    if executor_model_id != model_id:
        print(f"Executor:       {executor_model_id}", flush=True)
    print(f"Grader:         {grader_model_id}", flush=True)
    print(f"Examples:       {total}", flush=True)
    print(f"Correct:        {correct}", flush=True)
    print(f"Accuracy:       {accuracy:.2%}", flush=True)
    print(f"Total time:     {total_elapsed:.1f}s", flush=True)
    print(f"Max workers:    {max_workers}", flush=True)
    print("=" * 60, flush=True)
    for r in results:
        mark = "OK" if r.get("is_correct") else "X "
        print(f"  [{mark}] pos={r['sample_position']:>2} {str(r.get('extracted_answer', ''))[:60]:<60} | {r.get('pipeline_status', 'unknown')}", flush=True)
    logger.info(f"Results saved to: {output_file}")


def main() -> None:
    _configure_console_logging()
    parser = argparse.ArgumentParser(description="Run BrowseComp on fixed sample positions.")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--sample-size", type=int, required=True)
    parser.add_argument("--positions", type=str, required=True, help="Comma-separated positions and ranges, e.g. 2-9 or 1,3,5")
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--trajectory-dir", type=str, default="training_trajectories")
    parser.add_argument("--max-iterations", type=int, default=6)
    parser.add_argument("--max-crawl-calls", type=int, default=30)
    parser.add_argument("--max-planner-searches", type=int, default=10)
    parser.add_argument("--max-executor-searches", type=int, default=20)
    parser.add_argument("--max-total-searches", type=int, default=120)
    parser.add_argument("--max-workers", type=int, default=1, help="Number of concurrent workers (1=sequential, >1=parallel)")
    parser.add_argument("--disable-query-critic", action="store_true", help="Allow executor search queries without query critic filtering.")
    args = parser.parse_args()

    run_fixed_evaluation(
        seed=args.seed,
        sample_size=args.sample_size,
        positions=_parse_positions(args.positions),
        output_file=args.output,
        trajectory_dir=args.trajectory_dir,
        max_iterations=args.max_iterations,
        max_crawl_calls=args.max_crawl_calls,
        max_planner_searches=args.max_planner_searches,
        max_executor_searches=args.max_executor_searches,
        max_total_searches=args.max_total_searches,
        max_workers=args.max_workers,
        enable_query_critic=not args.disable_query_critic,
    )


if __name__ == "__main__":
    main()
