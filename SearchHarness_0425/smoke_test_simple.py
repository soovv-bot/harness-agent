"""Minimal real-LLM smoke test for SearchHarnessPipelineV4.

Runs ONE trivial question with tight budgets to verify the batch QueryCritic
refactor + finalizer fix don't break the real (non-fake) LLM path.

Usage:
    python smoke_test_simple.py [--question "..."] [--max-iterations 1]

Loads .env from the repo root (parent of this dir).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

# Load .env from repo root (parent of SearchHarness_0425).
_REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_REPO_ROOT / ".env")

from search_harness_pipeline_v4 import SearchHarnessPipelineV4  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Simple real-LLM smoke test.")
    parser.add_argument("--question", default="What is the capital of France?")
    parser.add_argument("--max-iterations", type=int, default=1)
    parser.add_argument("--max-crawl-calls", type=int, default=2)
    parser.add_argument("--max-planner-searches", type=int, default=2)
    parser.add_argument("--max-executor-searches", type=int, default=4)
    parser.add_argument("--max-total-searches", type=int, default=8)
    parser.add_argument("--disable-query-critic", action="store_true")
    args = parser.parse_args()

    api_base = os.getenv("OPENAI_BASE_URL", "")
    api_key = os.getenv("OPENAI_API_KEY", "")
    model_id = os.getenv("MODEL_NAME", "")
    executor_model_id = os.getenv("EXECUTOR_MODEL_NAME") or model_id
    if not api_base or not api_key:
        print("ERROR: OPENAI_BASE_URL / OPENAI_API_KEY not set in .env", flush=True)
        return 2

    # Quiet, timestamped console logs.
    logger.remove()
    logger.add(sys.stdout, level=os.getenv("LOG_LEVEL", "INFO"),
               format="{time:HH:mm:ss} | {level:<7} | {message}")

    print(f"[smoke] model={model_id} executor={executor_model_id}", flush=True)
    print(f"[smoke] api_base={api_base}", flush=True)
    print(f"[smoke] question={args.question!r}", flush=True)
    # Surface the thinking-mode config so smoke output self-documents the run.
    executor_thinking = (os.getenv("EXECUTOR_THINKING") or "<unset>").strip()
    thinking_budget = (os.getenv("LLM_THINKING_BUDGET_TOKENS") or "<unset>").strip()
    print(f"[smoke] EXECUTOR_THINKING={executor_thinking!r} LLM_THINKING_BUDGET_TOKENS={thinking_budget!r}", flush=True)

    pipeline = SearchHarnessPipelineV4(
        api_base=api_base, api_key=api_key, model_id=model_id,
        executor_model_id=executor_model_id,
        max_planner_searches=args.max_planner_searches,
        max_executor_searches=args.max_executor_searches,
        max_total_searches=args.max_total_searches,
        enable_query_critic=not args.disable_query_critic,
    )

    t0 = time.time()
    try:
        result = pipeline.run(
            question=args.question,
            max_iterations=args.max_iterations,
            max_crawl_calls=args.max_crawl_calls,
        )
    except Exception as e:
        print(f"[smoke] FAILED with exception: {e!r}", flush=True)
        import traceback
        traceback.print_exc()
        return 1

    elapsed = time.time() - t0
    answer = result.get("answer", "")
    status = result.get("status", "unknown")
    iterations = result.get("iterations", -1)

    print("=" * 60, flush=True)
    print(f"[smoke] status     = {status}", flush=True)
    print(f"[smoke] iterations = {iterations}", flush=True)
    print(f"[smoke] answer     = {answer!r}", flush=True)
    print(f"[smoke] elapsed    = {elapsed:.1f}s", flush=True)
    print("=" * 60, flush=True)

    # A trivial factual question should reach "finished" with a non-empty answer.
    ok = status == "finished" and bool(answer.strip())
    print(f"[smoke] RESULT     = {'PASS' if ok else 'CHECK'}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
