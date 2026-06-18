"""Run a standard single-agent BrowseComp baseline on fixed sampled positions.

This script uses `trajectory_agent.py` as the baseline agent and evaluates the
same fixed 10-question sample used by the SearchHarness experiments.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv
from loguru import logger

ROOT = Path(__file__).resolve().parent
HARNESS_DIR = ROOT / "SearchHarness_0414"
if str(HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(HARNESS_DIR))

from run_browsecomp import LLMGrader, _decrypt  # type: ignore
from trajectory_agent import TrajectoryRecordingAgent


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
    seen = set()
    ordered: List[int] = []
    for pos in positions:
        if pos not in seen:
            seen.add(pos)
            ordered.append(pos)
    return ordered


def _load_fixed_sample(seed: int, sample_size: int) -> List[Dict[str, Any]]:
    logger.info("Loading BrowseComp dataset...")
    df = pd.read_csv("https://openaipublic.blob.core.windows.net/simple-evals/browse_comp_test_set.csv")
    examples = [row.to_dict() for _, row in df.iterrows()]
    rng = random.Random(seed)
    sample = rng.sample(examples, sample_size)
    logger.info(f"Loaded fixed sample of {len(sample)} examples")
    return sample


def _save_manifest(sample: List[Dict[str, Any]], manifest_path: Path) -> None:
    manifest: List[Dict[str, Any]] = []
    for i, example in enumerate(sample):
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


def _build_task_prompt(question: str) -> str:
    return (
        "Solve the following web-search task carefully. "
        "Use the available tools to gather and verify evidence. "
        "Only output <answer>...</answer> when you are sufficiently confident.\n\n"
        f"Question:\n{question}"
    )


def run_single_baseline_task(
    task_index: int,
    question: str,
    correct_answer: str,
    agent: TrajectoryRecordingAgent,
    grader: LLMGrader,
    trajectory_path: str,
) -> Dict[str, Any]:
    start = time.time()
    result = agent.run_with_trajectory(
        task=_build_task_prompt(question),
        save_trajectory=True,
        trajectory_path=trajectory_path,
    )
    answer = result.get("answer") or ""
    metadata = result.get("metadata") or {}
    status = metadata.get("status", "unknown")

    grade = grader.grade(question, answer, correct_answer)
    elapsed = time.time() - start
    logger.info(
        f"[Baseline Task {task_index}] correct={grade['correct']} | "
        f"answer='{str(answer)[:60]}' | status={status} | {elapsed:.1f}s"
    )

    return {
        "task_index": task_index,
        "question_preview": question[:150],
        "correct_answer": correct_answer,
        "extracted_answer": answer,
        "pipeline_answer_raw": str(answer)[:500],
        "pipeline_status": status,
        "is_correct": grade["correct"],
        "grader_extracted": grade["extracted_answer"],
        "grader_reasoning": grade["reasoning"],
        "elapsed_seconds": round(elapsed, 1),
        "agent_metadata": metadata,
    }


def run_fixed_baseline(
    seed: int,
    sample_size: int,
    positions: List[int],
    output_file: str,
    trajectory_dir: str,
    enable_hint: bool,
    temperature: float,
    max_turns: Optional[int],
    hard_safety_turns: int,
) -> None:
    load_dotenv()
    api_base = os.getenv("OPENAI_BASE_URL")
    api_key = os.getenv("OPENAI_API_KEY")
    model_id = os.getenv("MODEL_NAME", "deepseek-chat")
    grader_api_base = os.getenv("GRADER_OPENAI_BASE_URL") or api_base
    grader_api_key = os.getenv("GRADER_OPENAI_API_KEY") or api_key
    grader_model_id = os.getenv("GRADER_MODEL_NAME", "gpt-4o-2024-11-20")

    if not api_base or not api_key:
        raise RuntimeError("Missing OPENAI_BASE_URL / OPENAI_API_KEY in environment")

    sample = _load_fixed_sample(seed=seed, sample_size=sample_size)
    manifest_path = HARNESS_DIR / "docs" / f"seed{seed}_k{sample_size}_manifest.json"
    _save_manifest(sample, manifest_path)
    logger.info(f"Manifest saved to {manifest_path}")

    for pos in positions:
        if pos < 0 or pos >= len(sample):
            raise ValueError(f"Sample position {pos} is out of range for sample size {len(sample)}")

    grader = LLMGrader(api_base=grader_api_base, api_key=grader_api_key, model_id=grader_model_id)

    results: List[Dict[str, Any]] = []
    overall_start = time.time()
    logger.info(f"Running baseline fixed-sample evaluation for positions={positions}")

    for sample_position in positions:
        example = sample[sample_position]
        canary = example.get("canary", "")
        question = _decrypt(example.get("problem", ""), canary)
        answer = _decrypt(example.get("answer", ""), canary)
        trajectory_path = str(Path(trajectory_dir) / model_id.replace("/", "_") / f"task_{sample_position:06d}.json")
        agent = TrajectoryRecordingAgent(
            api_base=api_base,
            api_key=api_key,
            model_id=model_id,
            temperature=temperature,
            enable_hint=enable_hint,
            max_turns=max_turns,
            hard_safety_turns=hard_safety_turns,
            log_dir=trajectory_dir,
        )
        result = run_single_baseline_task(
            task_index=sample_position,
            question=question,
            correct_answer=answer,
            agent=agent,
            grader=grader,
            trajectory_path=trajectory_path,
        )
        result["sample_position"] = sample_position
        results.append(result)

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
        "grader_model_id": grader_model_id,
        "num_examples": total,
        "correct_count": correct,
        "accuracy": accuracy,
        "baseline_config": {
            "enable_hint": enable_hint,
            "temperature": temperature,
            "max_turns": max_turns,
            "hard_safety_turns": hard_safety_turns,
            "tool_strategy": "standard_single_agent",
            "quotas": "unlimited",
        },
        "total_elapsed_seconds": round(total_elapsed, 1),
        "results": results,
    }

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    Path(output_file).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print("BrowseComp Fixed-Sample Baseline Results")
    print("=" * 60)
    print(f"Seed:           {seed}")
    print(f"Sample size:    {sample_size}")
    print(f"Positions:      {positions}")
    print(f"Model:          {model_id}")
    print(f"Grader:         {grader_model_id}")
    print(f"Examples:       {total}")
    print(f"Correct:        {correct}")
    print(f"Accuracy:       {accuracy:.2%}")
    print(f"Total time:     {total_elapsed:.1f}s")
    print("=" * 60)
    for r in results:
        mark = "OK" if r.get("is_correct") else "X "
        print(f"  [{mark}] pos={r['sample_position']:>2} {str(r.get('extracted_answer', ''))[:60]:<60} | {r.get('pipeline_status', 'unknown')}")
    logger.info(f"Baseline results saved to: {output_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the standard baseline agent on fixed sample positions.")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--sample-size", type=int, required=True)
    parser.add_argument("--positions", type=str, required=True, help="Comma-separated positions and ranges, e.g. 0-9 or 1,3,5")
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--trajectory-dir", type=str, default="logs/baseline_trajectories")
    parser.add_argument("--temperature", type=float, default=0.6)
    parser.add_argument("--hard-safety-turns", type=int, default=200)
    parser.add_argument("--max-turns", type=int, default=None)
    parser.add_argument("--disable-hint", action="store_true")
    args = parser.parse_args()

    run_fixed_baseline(
        seed=args.seed,
        sample_size=args.sample_size,
        positions=_parse_positions(args.positions),
        output_file=args.output,
        trajectory_dir=args.trajectory_dir,
        enable_hint=not args.disable_hint,
        temperature=args.temperature,
        max_turns=args.max_turns,
        hard_safety_turns=args.hard_safety_turns,
    )


if __name__ == "__main__":
    main()
