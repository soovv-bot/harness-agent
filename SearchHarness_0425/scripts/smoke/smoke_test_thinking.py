"""End-to-end smoke test for the thinking-mode switch.

Runs the SAME question under multiple EXECUTOR_THINKING values (e.g. none vs
high) and reports per-effort: status, iterations, elapsed, answer. Confirms the
executor_reasoning_effort → SearchAgent → build_chat_completion_kwargs chain
propagates without breaking the pipeline.

This is a behavioral smoke (does the pipeline still finish?), not a token-level
assertion — for token-level verification use `debug_llm_smoke.py --verify-thinking`.

Usage:
    python -m scripts.smoke.smoke_test_thinking --efforts none high
    python -m scripts.smoke.smoke_test_thinking --question "Who won the 2022 FIFA World Cup?" --efforts none low medium

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
_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_REPO_ROOT / ".env")

from pipeline.orchestrator import SearchHarnessPipelineV4  # noqa: E402

_VALID_EFFORTS = {"minimal", "low", "medium", "high", "max", "none"}  # none = minimal alias; max = GLM-5 native


def run_one(
    api_base: str,
    api_key: str,
    model_id: str,
    executor_model_id: str,
    question: str,
    effort: str,
    args: argparse.Namespace,
) -> dict:
    """Run the pipeline once with a given executor reasoning_effort."""
    t0 = time.time()
    pipeline = SearchHarnessPipelineV4(
        api_base=api_base,
        api_key=api_key,
        model_id=model_id,
        executor_model_id=executor_model_id,
        max_planner_searches=args.max_planner_searches,
        max_executor_searches=args.max_executor_searches,
        max_total_searches=args.max_total_searches,
        enable_query_critic=not args.disable_query_critic,
        executor_reasoning_effort=effort or None,
    )
    try:
        result = pipeline.run(
            question=question,
            max_iterations=args.max_iterations,
            max_crawl_calls=args.max_crawl_calls,
        )
    except Exception as e:
        return {"effort": effort, "status": "error", "error": repr(e), "elapsed": time.time() - t0}
    elapsed = time.time() - t0
    return {
        "effort": effort,
        "status": result.get("status", "unknown"),
        "iterations": result.get("iterations", -1),
        "answer": (result.get("answer") or "").strip(),
        "elapsed": elapsed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="End-to-end thinking-mode smoke test.")
    parser.add_argument("--question", default="What is the capital of France?")
    parser.add_argument(
        "--efforts",
        default="none high",
        help="Space-separated EXECUTOR_THINKING values to compare, e.g. 'none high'. "
             f"Valid: {sorted(_VALID_EFFORTS)}.",
    )
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

    efforts = [e for e in args.efforts.split() if e.strip()]
    if not efforts:
        print("ERROR: --efforts must specify at least one value", flush=True)
        return 2
    invalid = [e for e in efforts if e not in _VALID_EFFORTS]
    if invalid:
        print(f"ERROR: invalid efforts {invalid}; valid: {sorted(_VALID_EFFORTS)}", flush=True)
        return 2

    logger.remove()
    logger.add(sys.stdout, level=os.getenv("LOG_LEVEL", "INFO"),
               format="{time:HH:mm:ss} | {level:<7} | {message}")

    print("=" * 70, flush=True)
    print(f"[thinking-smoke] model={model_id} executor={executor_model_id}", flush=True)
    print(f"[thinking-smoke] api_base={api_base}", flush=True)
    print(f"[thinking-smoke] question={args.question!r}", flush=True)
    print(f"[thinking-smoke] efforts={efforts}", flush=True)
    print("=" * 70, flush=True)

    results = []
    for effort in efforts:
        print(f"\n--- effort={effort!r} ---", flush=True)
        r = run_one(api_base, api_key, model_id, executor_model_id, args.question, effort, args)
        results.append(r)
        print(f"[{effort}] status={r['status']} iterations={r.get('iterations', '?')} "
              f"elapsed={r['elapsed']:.1f}s answer={r.get('answer', '')!r}", flush=True)
        if r["status"] == "error":
            print(f"[{effort}] error={r.get('error')}", flush=True)

    print("\n" + "=" * 70, flush=True)
    print("[thinking-smoke] SUMMARY", flush=True)
    print(f"{'effort':<10} {'status':<12} {'iters':<6} {'elapsed':<10} {'answer':<30}", flush=True)
    print("-" * 70, flush=True)
    for r in results:
        ans = (r.get("answer") or "")[:30]
        print(f"{r['effort']:<10} {r['status']:<12} {str(r.get('iterations', '?')):<6} "
              f"{r['elapsed']:<10.1f} {ans!r}", flush=True)
    print("=" * 70, flush=True)

    # Verdict: all efforts should finish without error. (We do NOT assert equal
    # answers — trivial questions may produce identical answers regardless of
    # effort, and that's fine for a connectivity smoke. The point is: the pipeline
    # does not crash when reasoning_effort is injected.)
    all_finished = all(r["status"] in ("finished", "completed") for r in results)
    any_error = any(r["status"] == "error" for r in results)
    if all_finished and not any_error:
        print("[thinking-smoke] RESULT = PASS (all efforts finished)", flush=True)
        return 0
    if any_error:
        print("[thinking-smoke] RESULT = FAIL (one or more efforts errored)", flush=True)
        return 1
    print("[thinking-smoke] RESULT = CHECK (no errors, but not all 'finished')", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
