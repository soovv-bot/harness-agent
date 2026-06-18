"""
Test script for running a single task from the dataset
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

from trajectory_agent import TrajectoryRecordingAgent


def main():
    # Load environment variables
    load_dotenv()

    # Check required environment variables
    api_base = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE") or os.getenv("API_BASE")
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY")
    model_id = os.getenv("MODEL_NAME") or os.getenv("MODEL_ID", "deepseek-chat")

    if not api_base or not api_key:
        logger.error("Please set OPENAI_API_BASE and OPENAI_API_KEY in .env file")
        return

    logger.info(f"Using API: {api_base}")
    logger.info(f"Using model: {model_id}")

    # Load the task from dataset
    data_file = "source_oriented_data_systhesis/data/mixed_domains_qa_with_enhance.jsonl"
    with open(data_file, "r", encoding="utf-8") as f:
        first_line = f.readline()
        task_data = json.loads(first_line)

    task = task_data["question"]
    ground_truth = task_data["answer"]
    domain = task_data.get("domain", "unknown")
    difficulty = task_data.get("difficulty_level", "unknown")

    print("\n" + "=" * 80)
    print(f"DOMAIN: {domain.upper()}")
    print(f"DIFFICULTY: {difficulty}")
    print("=" * 80)
    print(f"TASK:\n{task}")
    print("\n" + "=" * 80)
    print(f"GROUND TRUTH ANSWER: {ground_truth}")
    print("=" * 80 + "\n")

    # Create agent
    agent = TrajectoryRecordingAgent(
        api_base=api_base,
        api_key=api_key,
        model_id=model_id,
        temperature=0.6,
        enable_hint=True,
        max_turns=20,
        log_dir="logs/test_trajectories",
    )

    # Run the agent
    logger.info("Starting task execution...")
    result = agent.run_with_trajectory(task, save_trajectory=True)

    # Display results
    print("\n" + "=" * 80)
    print("FINAL ANSWER:")
    print("=" * 80)
    print(result["answer"])
    print("\n" + "=" * 80)
    print("GROUND TRUTH:")
    print("=" * 80)
    print(ground_truth)
    print("\n" + "=" * 80)
    print("METADATA:")
    print("=" * 80)
    for key, value in result["metadata"].items():
        print(f"  {key}: {value}")

    # Compare with ground truth
    if result["answer"]:
        # Simple check: is ground truth mentioned in the answer?
        if ground_truth.lower() in result["answer"].lower():
            print("\n" + "=" * 80)
            print("✓ ANSWER MATCHES GROUND TRUTH!")
            print("=" * 80)
        else:
            print("\n" + "=" * 80)
            print("✗ ANSWER MAY NOT MATCH GROUND TRUTH")
            print("=" * 80)

    # Save trajectory info
    print("\n" + "=" * 80)
    print("TRAJECTORY INFO:")
    print("=" * 80)
    messages = result["trajectory"]
    print(f"Total messages: {len(messages)}")
    role_counts = {}
    for msg in messages:
        role = msg.get("role", "unknown")
        role_counts[role] = role_counts.get(role, 0) + 1
    for role, count in role_counts.items():
        print(f"  - {role}: {count}")

    # Show first few messages
    print("\n" + "=" * 80)
    print("FIRST FEW MESSAGES:")
    print("=" * 80)
    for i, msg in enumerate(messages[:4]):
        print(f"\n--- Message {i+1} ({msg.get('role', 'unknown')}) ---")
        if msg.get("role") == "system":
            print(f"Content: {msg.get('content', '')[:300]}...")
        elif msg.get("role") == "user":
            print(f"Content: {msg.get('content', '')}")
        elif msg.get("role") == "assistant":
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])
            print(f"Content: {content[:300] if content else '(no content)'}...")
            if tool_calls:
                print(f"Tool calls: {len(tool_calls)}")
                for tc in tool_calls:
                    func = tc.get("function", {})
                    print(f"  - {func.get('name', 'unknown')}")
        elif msg.get("role") == "tool":
            print(f"Tool: {msg.get('name', 'unknown')}")
            print(f"Result: {msg.get('content', '')[:300]}...")

    if len(messages) > 4:
        print(f"\n... and {len(messages) - 4} more messages")

    # Save trajectory path
    print("\n" + "=" * 80)
    print("SAVED FILES:")
    print("=" * 80)
    if result["metadata"].get("status") == "completed":
        timestamp = result["metadata"].get("finished_at", "").replace(":", "-").replace(".", "-")
        model_name = model_id.replace("/", "_").replace(":", "_")
        trajectory_path = f"logs/test_trajectories/{model_name}/task_{timestamp}.json"
        print(f"Trajectory: {trajectory_path}")

        # Also save a pretty-printed version for inspection
        pretty_path = Path("logs/test_trajectories") / model_name / "latest_trajectory_pretty.json"
        pretty_path.parent.mkdir(parents=True, exist_ok=True)
        with open(pretty_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Pretty version: {pretty_path}")


if __name__ == "__main__":
    main()
