"""Offline re-grading for a BrowseComp results JSON.

Re-runs the LLM grader on the existing (extracted_answer, correct_answer) pairs
from a results file, without re-running the pipeline. Useful when the original
grader was mis-configured (e.g. wrong API base / model name) and every
is_correct was forced to False.

Usage:
    cd SearchHarness_0425
    python regrade_results.py \
        --input results/cluster_run_seed123_k100.json \
        --output results/cluster_run_seed123_k100_regraded.json \
        --max-workers 4

Grader endpoint/model come from .env (corrected variable names):
    GRADER_API_BASE      -> grader base url
    GRADER_API_KEY        -> grader api key
    GRADER_MODEL          -> grader model id (default gpt-4o-2024-11-20)
Falls back to GRADER_OPENAI_BASE_URL / GRADER_OPENAI_API_KEY / GRADER_MODEL_NAME
and then to the main OPENAI_BASE_URL / OPENAI_API_KEY / MODEL_NAME.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from loguru import logger
from tqdm import tqdm

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
from deepseek_thinking_compat import build_chat_completion_kwargs  # noqa: E402
from openai_client_factory import build_openai_client  # noqa: E402

# Import the grader prompt + LLMGrader from the main eval module to stay in sync.
from run_browsecomp import GRADER_PROMPT, LLMGrader  # noqa: E402


def _resolve_grader_config() -> Dict[str, str]:
    api_base = (
        os.getenv("GRADER_API_BASE")
        or os.getenv("GRADER_OPENAI_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or ""
    )
    api_key = (
        os.getenv("GRADER_API_KEY")
        or os.getenv("GRADER_OPENAI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    )
    model_id = (
        os.getenv("GRADER_MODEL")
        or os.getenv("GRADER_MODEL_NAME")
        or "gpt-4o-2024-11-20"
    )
    return {"api_base": api_base, "api_key": api_key, "model_id": model_id}


def regrade_one(
    grader: LLMGrader,
    result: Dict[str, Any],
    *,
    prefer_trajectory: bool = False,
    traj_dir: Path | None = None,
) -> Dict[str, Any]:
    """Re-grade a single result row. Returns a NEW dict (copy)."""
    out = copy.deepcopy(result)
    question = result.get("question_preview", "")
    correct_answer = result.get("correct_answer", "")
    extracted = (result.get("extracted_answer") or "").strip()

    # If the question was truncated to a preview, try to recover the full
    # question from the trajectory file for a better grading prompt.
    if prefer_trajectory and traj_dir is not None and len(question) >= 145:
        ti = result.get("task_index")
        cand = traj_dir / f"task_{ti:06d}.json"
        if cand.exists():
            try:
                t = json.loads(cand.read_text(encoding="utf-8"))
                q = t.get("metadata", {}).get("question")
                if q:
                    question = q
            except Exception:
                pass

    # If the answer looks like a JSON answer block, unwrap it for grading.
    answer_to_grade = extracted
    if extracted.startswith("{"):
        try:
            payload = json.loads(extracted)
            inner = payload.get("answer", "")
            if inner:
                answer_to_grade = str(inner)
        except json.JSONDecodeError:
            pass

    # If no answer at all, mark as wrong without calling the API.
    if not answer_to_grade or answer_to_grade.lower() in {"unknown", "none", "null"}:
        out["is_correct"] = False
        out["grader_extracted"] = ""
        out["grader_reasoning"] = "no answer / Unknown"
        out["regraded"] = True
        return out

    grade = grader.grade(question, answer_to_grade, correct_answer)
    out["is_correct"] = bool(grade.get("correct", False))
    out["grader_extracted"] = grade.get("extracted_answer", "")
    out["grader_reasoning"] = grade.get("reasoning", "")
    out["regraded"] = True
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to original results JSON")
    parser.add_argument("--output", required=True, help="Path for regraded results JSON")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument(
        "--prefer-trajectory",
        action="store_true",
        help="Recover full question text from trajectory files for grading",
    )
    parser.add_argument(
        "--trajectory-dir",
        default=None,
        help="Directory with task_XXXXXX.json trajectory files",
    )
    args = parser.parse_args()

    load_dotenv()
    cfg = _resolve_grader_config()
    logger.info(
        f"Grader endpoint: {cfg['api_base']} | model={cfg['model_id']} | "
        f"key={'set' if cfg['api_key'] else 'MISSING'}"
    )
    if not cfg["api_base"] or not cfg["api_key"]:
        logger.error("Grader api_base or api_key missing. Check .env (GRADER_API_BASE / GRADER_API_KEY).")
        sys.exit(2)

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    results: List[Dict[str, Any]] = data.get("results", [])
    logger.info(f"Loaded {len(results)} results from {args.input}")

    # quick smoke test on a single call to fail fast on mis-config
    grader = LLMGrader(api_base=cfg["api_base"], api_key=cfg["api_key"], model_id=cfg["model_id"])
    logger.info("Smoke-testing grader with a dummy call...")
    smoke = grader.grade("What is 1+1?", "2", "2")
    if "Error" in str(smoke.get("reasoning", "")):
        logger.error(f"Grader smoke test FAILED: {smoke.get('reasoning')}")
        sys.exit(3)
    logger.info(f"Grader smoke test OK: {smoke}")

    traj_dir: Path | None = None
    if args.prefer_trajectory and args.trajectory_dir:
        traj_dir = Path(args.trajectory_dir)
        logger.info(f"Will recover full questions from {traj_dir}")

    new_results: List[Dict[str, Any]] = [None] * len(results)  # type: ignore[list-item]
    start = time.time()

    with ThreadPoolExecutor(max_workers=args.max_workers) as ex:
        futures = {
            ex.submit(
                regrade_one,
                grader,
                r,
                prefer_trajectory=args.prefer_trajectory,
                traj_dir=traj_dir,
            ): i
            for i, r in enumerate(results)
        }
        for fut in tqdm(as_completed(futures), total=len(futures), desc="Re-grading"):
            i = futures[fut]
            try:
                new_results[i] = fut.result()
            except Exception as e:
                logger.error(f"[task {results[i].get('task_index')}] regrade error: {e}")
                new_results[i] = copy.deepcopy(results[i])
                new_results[i]["regraded"] = False
                new_results[i]["grader_reasoning"] = f"regrade_error: {e}"

    correct = sum(1 for r in new_results if r.get("is_correct"))
    total = len(new_results)
    data["results"] = new_results
    data["regraded_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    data["regrade_grader_model_id"] = cfg["model_id"]
    data["regrade_grader_api_base"] = cfg["api_base"]
    data["correct_count"] = correct
    data["accuracy"] = round(correct / total, 4) if total else 0.0

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        f"Re-graded {total} tasks | correct={correct} | accuracy={data['accuracy']} "
        f"| wrote {args.output} | {time.time()-start:.1f}s"
    )


if __name__ == "__main__":
    main()
