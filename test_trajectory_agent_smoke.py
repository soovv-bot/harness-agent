"""Smoke test for TrajectoryRecordingAgent: context compression + parallel tools.

Validates the two upgrades added to trajectory_agent.py:
  1. Context compression via _build_llm_context() (aggressive settings to trigger early)
  2. Parallel tool execution via ThreadPoolExecutor

Run with:
  LLM_THINKING_BUDGET_TOKENS=1000 python test_trajectory_agent_smoke.py
"""
import json
import os
import time
from dotenv import load_dotenv
from loguru import logger

from trajectory_agent import TrajectoryRecordingAgent


def main():
    load_dotenv()
    api_base = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE")
    api_key = os.getenv("OPENAI_API_KEY")
    model_id = os.getenv("MODEL_NAME", "GLM-5.2")
    logger.info(f"model={model_id} base={api_base}")

    # Load first task from dataset
    data_file = "source_oriented_data_systhesis/data/mixed_domains_qa_with_enhance.jsonl"
    with open(data_file, encoding="utf-8") as f:
        task_data = json.loads(f.readline())
    task = task_data["question"]
    ground_truth = task_data["answer"]
    print("=" * 60)
    print(f"Task: {task[:200]}...")
    print(f"Ground truth: {ground_truth}")
    print("=" * 60)

    agent = TrajectoryRecordingAgent(
        api_base=api_base,
        api_key=api_key,
        model_id=model_id,
        temperature=0.6,
        enable_hint=True,
        max_turns=3,
        log_dir="logs/test_trajectories_smoke",
        # Aggressive compression to trigger within 3 turns
        max_context_tokens=4000,
        keep_recent_messages=4,
        max_tool_result_chars=800,
        max_assistant_chars=500,
        max_tool_workers=4,
        enable_parallel_tools=True,
    )

    t0 = time.time()
    result = agent.run_with_trajectory(task, save_trajectory=True)
    elapsed = time.time() - t0

    md = result["metadata"]
    print("\n" + "=" * 60)
    print(f"status={md.get('status')} turns={md.get('turns')} elapsed={elapsed:.1f}s")
    print(f"answer={result.get('answer')!r}")

    # Check context compression
    compressions = md.get("context_compressions", [])
    print(f"context_compressions={len(compressions)}")
    for c in compressions[-3:]:
        print(f"  - {c}")

    msgs = result["trajectory"]
    print(f"total_messages={len(msgs)}")
    tool_msgs = [m for m in msgs if m.get("role") == "tool"]
    print(f"tool_results={len(tool_msgs)}")

    # Check for parallel tool execution (multiple tool calls in one assistant turn)
    assistant_msgs = [m for m in msgs if m.get("role") == "assistant"]
    multi_tool_turns = [m for m in assistant_msgs if len(m.get("tool_calls", [])) > 1]
    print(f"multi_tool_call_turns={len(multi_tool_turns)}")
    if multi_tool_turns:
        for m in multi_tool_turns:
            names = [tc.get("function", {}).get("name", "?") for tc in m["tool_calls"]]
            print(f"  parallel tools: {names}")

    # Verify full trajectory preserved (not compressed in storage)
    total_chars = sum(len(str(m.get("content", ""))) for m in msgs)
    print(f"total_trajectory_chars={total_chars}")
    print("=" * 60)


if __name__ == "__main__":
    main()
