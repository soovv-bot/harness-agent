"""BrowseComp evaluation for SearchHarness pipeline v4.

Loads the BrowseComp dataset, runs SearchHarnessPipelineV4 on each question,
and grades answers with an LLM grader. No modifications to the pipeline itself.

Usage:
    cd SearchHarness
    python run_browsecomp.py --num-examples 5 --max-workers 1
    python run_browsecomp.py --num-examples 50 --max-workers 3 --output results/browsecomp_v4.json
"""

import argparse
import base64
import hashlib
import json
import os
import random
import re
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv
from loguru import logger
from tqdm import tqdm

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from deepseek_thinking_compat import build_chat_completion_kwargs, chat_completion_with_structuring
from llm_error_utils import classify_infra_error
from openai_client_factory import build_openai_client

# ── BrowseComp decrypt ──────────────────────────────────────────────────


def _derive_key(password: str, length: int) -> bytes:
    hasher = hashlib.sha256()
    hasher.update(password.encode())
    key = hasher.digest()
    return key * (length // len(key)) + key[:length % len(key)]


def _decrypt(ciphertext_b64: str, password: str) -> str:
    encrypted = base64.b64decode(ciphertext_b64)
    key = _derive_key(password, len(encrypted))
    return bytes(a ^ b for a, b in zip(encrypted, key)).decode()


# ── Grader ──────────────────────────────────────────────────────────────


GRADER_PROMPT = """Judge whether the [response] correctly answers the [question].

[question]: {question}

[response]: {response}

[correct_answer]: {correct_answer}

Tolerate minor differences: missing middle name/initial, extra whitespace, different capitalization, abbreviations, aliases. Only mark false if the core identity is wrong.

Output JSON only (no markdown):
{{"extracted": "the answer extracted from response, or null if none", "correct": true/false, "reason": "brief explanation"}}"""


DEFAULT_MODEL_ID = "GLM-5.2"


def resolve_primary_model() -> str:
    return (
        os.getenv("MODEL_NAME")
        or os.getenv("ENTRY_POINT_MODEL")
        or os.getenv("MODEL")
        or DEFAULT_MODEL_ID
    ).strip()


def resolve_grader_config(model_api_base: str, model_api_key: str, model_id: str) -> Dict[str, str]:
    grader_api_base = (
        os.getenv("GRADER_API_BASE")
        or os.getenv("GRADER_OPENAI_BASE_URL")
        or model_api_base
        or ""
    )
    grader_api_key = (
        os.getenv("GRADER_API_KEY")
        or os.getenv("GRADER_OPENAI_API_KEY")
        or model_api_key
        or ""
    )
    grader_model_id = (
        os.getenv("GRADER_MODEL")
        or os.getenv("GRADER_MODEL_NAME")
        or model_id
        or DEFAULT_MODEL_ID
    ).strip()
    return {
        "api_base": grader_api_base,
        "api_key": grader_api_key,
        "model_id": grader_model_id,
    }


class LLMGrader:
    def __init__(self, api_base: str, api_key: str, model_id: str):
        self.client = build_openai_client(api_base, api_key)
        self.model_id = model_id

    def grade(self, question: str, response: str, correct_answer: str) -> Dict[str, Any]:
        prompt = GRADER_PROMPT.format(
            question=question,
            response=response,
            correct_answer=correct_answer,
        )
        try:
            message = chat_completion_with_structuring(
                self.client,
                model_id=self.model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                structurer_format_hint="Output the result as JSON with fields: correct, reason, extracted.",
            )
            text = getattr(message, "content", None) or ""
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if not json_match:
                logger.error(f"Grader: no JSON in response: {text[:200]}")
                return {"correct": False, "reasoning": "no JSON", "extracted_answer": ""}
            result = json.loads(json_match.group())
            return {
                "correct": bool(result.get("correct", False)),
                "reasoning": result.get("reason", ""),
                "extracted_answer": result.get("extracted", ""),
            }
        except Exception as e:
            infra_type = classify_infra_error(e)
            logger.error(f"Grading error: {e}")
            return {
                "correct": False,
                "reasoning": str(e),
                "extracted_answer": "",
                "status": "infra_error" if infra_type else "error",
                "error_type": infra_type or "",
            }


# ── Answer extraction from pipeline output ─────────────────────────────


def extract_answer_from_pipeline(result: Dict[str, Any]) -> str:
    """Extract the answer string from pipeline result.

    The pipeline returns answer via finalizer.to_answer_block() which is:
    <answer>{"status": "...", "answer": "...", ...}</answer>
    Or planner directly outputs <answer>...</answer>.
    """
    raw = result.get("answer", "")
    if not raw:
        return ""
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", raw, flags=re.DOTALL | re.IGNORECASE).strip()

    # Try to parse JSON inside <answer> tags
    answer_matches = re.findall(r"<answer>(.*?)</answer>", cleaned, re.DOTALL | re.IGNORECASE)
    if answer_matches:
        inner = answer_matches[-1].strip()
        try:
            payload = json.loads(inner)
            ans = payload.get("answer", "")
            if ans and ans != "Unknown":
                return ans
        except json.JSONDecodeError:
            pass
        # Fallback: raw text inside <answer>
        return inner.strip()

    # No tags — return raw
    return cleaned


# ── Single-task runner ─────────────────────────────────────────────────


def run_single_task(
    task_index: int,
    question: str,
    correct_answer: str,
    pipeline,
    grader: LLMGrader,
    pipeline_kwargs: Dict[str, Any],
    trajectory_recorder: Optional["TrajectoryRecorder"] = None,
) -> Dict[str, Any]:
    """Run pipeline on a single BrowseComp question and grade it."""
    start = time.time()

    if trajectory_recorder:
        trajectory_recorder.start(question=question, task_index=task_index, pipeline_config=pipeline_kwargs)
        pipeline.trajectory_recorder = trajectory_recorder

    try:
        pipeline_result = pipeline.run(question=question, **pipeline_kwargs)
    except Exception as e:
        infra_type = classify_infra_error(e)
        logger.error(f"[Task {task_index}] Pipeline error: {e}")
        logger.error(traceback.format_exc())
        return {
            "task_index": task_index,
            "question_preview": question[:150],
            "correct_answer": correct_answer,
            "extracted_answer": "",
            "pipeline_answer_raw": "",
            "pipeline_status": "infra_error" if infra_type else "unfinished",
            "is_correct": False,
            "error": str(e),
            "failure_category": infra_type or "pipeline_error",
            "elapsed_seconds": time.time() - start,
        }

    extracted_answer = extract_answer_from_pipeline(pipeline_result)
    raw_answer = pipeline_result.get("answer", "")
    status = pipeline_result.get("status", "unknown")
    answer_payload = pipeline_result.get("answer_payload") or {}
    failure_category = pipeline_result.get("failure_category") or answer_payload.get("error_type") or ""

    grade = grader.grade(question, extracted_answer or raw_answer, correct_answer)

    if trajectory_recorder:
        trajectory_recorder.update_grading(
            correct=grade["correct"],
            extracted_answer=grade["extracted_answer"],
            reasoning=grade["reasoning"],
        )

    elapsed = time.time() - start
    logger.info(
        f"[Task {task_index}] {grade['correct']=} | "
        f"answer='{extracted_answer[:60]}' | "
        f"status={status} | {elapsed:.1f}s"
    )

    return {
        "task_index": task_index,
        "question_preview": question[:150],
        "correct_answer": correct_answer,
        "extracted_answer": extracted_answer,
        "pipeline_answer_raw": raw_answer[:500] if raw_answer else "",
        "pipeline_status": status,
        "failure_category": failure_category,
        "is_correct": grade["correct"],
        "grader_extracted": grade["extracted_answer"],
        "grader_reasoning": grade["reasoning"],
        "grader_status": grade.get("status", "ok"),
        "grader_error_type": grade.get("error_type", ""),
        "elapsed_seconds": round(elapsed, 1),
    }


# ── Main evaluation loop ───────────────────────────────────────────────


def run_evaluation(
    api_base: str,
    api_key: str,
    model_id: str,
    grader_api_base: str,
    grader_api_key: str,
    grader_model_id: str,
    num_examples: int = 10,
    max_workers: int = 1,
    seed: Optional[int] = None,
    skip: int = 0,
    output_file: Optional[str] = None,
    # Pipeline parameters
    max_iterations: int = 6,
    max_crawl_calls: int = 12,
    # Trajectory recording
    save_trajectories: bool = True,
    trajectory_dir: str = "logs/trajectories",
    # Search budgets
    max_planner_searches: int = 10,
    max_executor_searches: int = 30,
    max_total_searches: int = 80,
):
    from search_harness_pipeline_v4 import SearchHarnessPipelineV4
    from trajectory_recorder import TrajectoryRecorder

    # Load dataset
    logger.info("Loading BrowseComp dataset...")
    df = pd.read_csv(
        "https://openaipublic.blob.core.windows.net/simple-evals/browse_comp_test_set.csv"
    )
    examples = [row.to_dict() for _, row in df.iterrows()]

    if num_examples:
        rng = random.Random(seed if seed is not None else 42)
        examples = rng.sample(examples, num_examples + skip)[skip:]

    logger.info(f"Loaded {len(examples)} examples")

    # Create grader once. Pipelines are created per worker to avoid shared mutable state across threads.
    grader = LLMGrader(api_base=grader_api_base, api_key=grader_api_key, model_id=grader_model_id)

    pipeline_kwargs: Dict[str, Any] = {
        "max_iterations": max_iterations,
        "max_crawl_calls": max_crawl_calls,
    }

    results: List[Dict] = []
    results_lock = Lock()

    def _worker(i: int, example: Dict) -> Dict:
        pipeline = SearchHarnessPipelineV4(
            api_base=api_base, api_key=api_key, model_id=model_id,
            max_planner_searches=max_planner_searches,
            max_executor_searches=max_executor_searches,
            max_total_searches=max_total_searches,
        )
        canary = example.get("canary", "")
        question = _decrypt(example.get("problem", ""), canary)
        answer = _decrypt(example.get("answer", ""), canary)
        # Create a per-task recorder
        recorder = TrajectoryRecorder(model_id=model_id, output_dir=trajectory_dir, task_index=i) if save_trajectories else None
        return run_single_task(
            task_index=i,
            question=question,
            correct_answer=answer,
            pipeline=pipeline,
            grader=grader,
            pipeline_kwargs=pipeline_kwargs,
            trajectory_recorder=recorder,
        )

    logger.info(f"Running evaluation with max_workers={max_workers}...")
    overall_start = time.time()

    if max_workers <= 1:
        # Sequential — better for debugging and API rate limits
        for i, example in enumerate(tqdm(examples, desc="Evaluating")):
            result = _worker(i, example)
            with results_lock:
                results.append(result)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_worker, i, example): i
                for i, example in enumerate(examples)
            }
            for future in tqdm(as_completed(futures), total=len(futures), desc="Evaluating"):
                try:
                    result = future.result()
                    with results_lock:
                        results.append(result)
                except Exception as e:
                    idx = futures[future]
                    logger.error(f"Task {idx} failed: {e}")
                    with results_lock:
                        results.append({
                            "task_index": idx,
                            "is_correct": False,
                            "error": str(e),
                        })

    total_elapsed = time.time() - overall_start

    # Sort by task_index
    results.sort(key=lambda x: x["task_index"])

    # Aggregate
    correct = sum(1 for r in results if r.get("is_correct"))
    total = len(results)
    accuracy = correct / total if total > 0 else 0

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"BrowseComp Evaluation Results (SearchHarness v4)")
    print(f"{'=' * 60}")
    print(f"Model:          {model_id}")
    print(f"Grader:         {grader_model_id}")
    print(f"Examples:       {total}")
    print(f"Correct:        {correct}")
    print(f"Accuracy:       {accuracy:.2%}")
    print(f"Total time:     {total_elapsed:.1f}s ({total_elapsed / max(total, 1):.1f}s/task)")
    print(f"Max workers:    {max_workers}")
    print(f"Pipeline:       max_iter={max_iterations}, planner_search={max_planner_searches}, executor_search={max_executor_searches}, total_search={max_total_searches}, max_crawl={max_crawl_calls}")
    print(f"{'=' * 60}\n")

    # Per-task breakdown
    for r in results:
        mark = "OK" if r.get("is_correct") else "X "
        ans = (r.get("extracted_answer") or "")[:60]
        status = r.get("pipeline_status", "")
        err = r.get("error", "")
        extra = f" | {err}" if err else ""
        print(f"  [{mark}] #{r['task_index']:3d} {ans:<60s} | {status}{extra}")

    # Save results
    if output_file:
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "model_id": model_id,
            "grader_model_id": grader_model_id,
            "num_examples": total,
            "correct_count": correct,
            "accuracy": accuracy,
            "total_elapsed_seconds": round(total_elapsed, 1),
            "pipeline_config": pipeline_kwargs,
            "results": results,
        }
        p = Path(output_file)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Results saved to: {output_file}")

    return accuracy, results


def main():
    parser = argparse.ArgumentParser(description="BrowseComp evaluation for SearchHarness v4")
    parser.add_argument("--num-examples", type=int, default=5, help="Number of examples to evaluate")
    parser.add_argument("--max-workers", type=int, default=1, help="Concurrent workers")
    parser.add_argument("--max-iterations", type=int, default=6, help="Pipeline max iterations")
    parser.add_argument("--max-planner-searches", type=int, default=10, help="Planner search budget (total)")
    parser.add_argument("--max-executor-searches", type=int, default=20, help="Executor search budget (per subtask)")
    parser.add_argument("--max-total-searches", type=int, default=120, help="Global search budget (safety net)")
    parser.add_argument("--max-crawl-calls", type=int, default=30, help="Pipeline max crawl calls")
    parser.add_argument("--output", type=str, default=None, help="Output JSON file path")
    parser.add_argument("--save-trajectories", type=bool, default=True, help="Save trajectory logs per task")
    parser.add_argument("--trajectory-dir", type=str, default="logs/trajectories", help="Directory for trajectory logs")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for example selection")
    parser.add_argument("--skip", type=int, default=0, help="Skip first N examples (for resuming)")
    args = parser.parse_args()

    load_dotenv()

    api_base = os.getenv("OPENAI_BASE_URL")
    api_key = os.getenv("OPENAI_API_KEY")
    model_id = resolve_primary_model()

    grader_cfg = resolve_grader_config(api_base or "", api_key or "", model_id)
    grader_api_base = grader_cfg["api_base"]
    grader_api_key = grader_cfg["api_key"]
    grader_model_id = grader_cfg["model_id"]

    if not api_base or not api_key:
        logger.error("Set OPENAI_BASE_URL and OPENAI_API_KEY in .env")
        sys.exit(1)

    if args.output is None:
        args.output = f"results/browsecomp_{model_id}_{args.num_examples}ex.json"

    run_evaluation(
        api_base=api_base,
        api_key=api_key,
        model_id=model_id,
        grader_api_base=grader_api_base,
        grader_api_key=grader_api_key,
        grader_model_id=grader_model_id,
        num_examples=args.num_examples,
        max_workers=args.max_workers,
        output_file=args.output,
        max_iterations=args.max_iterations,
        max_crawl_calls=args.max_crawl_calls,
        max_planner_searches=args.max_planner_searches,
        max_executor_searches=args.max_executor_searches,
        max_total_searches=args.max_total_searches,
        save_trajectories=args.save_trajectories,
        trajectory_dir=args.trajectory_dir,
        seed=args.seed,
        skip=args.skip,
    )


if __name__ == "__main__":
    main()
