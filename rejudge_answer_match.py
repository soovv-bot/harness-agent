"""
临时脚本：重新用 LLM judge 判断 answer_match=false 的任务

流程：
1. 遍历所有 task JSON 文件，添加 answer_match 字段
2. 对有答案但 answer_match=false 的任务用 LLM judge 重新判断
3. 更新 batch_summary.json
4. 更新 generation_metadata.json
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from loguru import logger
from tqdm import tqdm


def judge_answer_semantic_match(
    ground_truth: str,
    model_answer: str,
    client: OpenAI,
    judge_model: str
) -> bool:
    """
    Use LLM to judge if model answer is semantically equivalent to ground truth.
    """
    if not model_answer or not ground_truth:
        return False

    judge_prompt = f"""You are a judge that determines if two answers are semantically equivalent.

Ground Truth Answer: {ground_truth}

Model's Answer: {model_answer}

Question: Are these two answers semantically equivalent? Consider:
- They should convey the same core information
- Minor formatting differences, extra context, or partial matches are acceptable
- The model answer should contain the essential information from the ground truth

Answer ONLY with "YES" or "NO"."""

    try:
        response = client.chat.completions.create(
            model=judge_model,
            messages=[{"role": "user", "content": judge_prompt}],
            temperature=0,
            max_tokens=10,
        )
        result = response.choices[0].message.content.strip().upper()
        return "YES" in result
    except Exception as e:
        logger.warning(f"Judge API call failed: {e}")
        # Fallback to simple string match
        return ground_truth.lower() in model_answer.lower()


def main():
    load_dotenv()

    # Configuration
    api_base = os.getenv("OPENAI_BASE_URL")
    api_key = os.getenv("OPENAI_API_KEY")
    judge_model = os.getenv("ANSWER_JUDGE_MODEL", "deepseek-chat")

    if not api_base or not api_key:
        logger.error("Please set OPENAI_BASE_URL and OPENAI_API_KEY in .env file")
        return

    client = OpenAI(base_url=api_base, api_key=api_key)

    # Paths
    trajectory_dir = Path("data/trajectories/deepseek-chat")
    batch_summary_path = Path("data/trajectories/batch_summary.json")
    metadata_path = Path("data/trajectories/generation_metadata.json")

    # Step 1: Process all task JSON files
    logger.info(f"Step 1: Processing task files in {trajectory_dir}")
    task_files = list(trajectory_dir.glob("task_*.json"))
    logger.info(f"Found {len(task_files)} task files")

    tasks_data = {}
    for task_file in tqdm(task_files, desc="Reading task files"):
        with open(task_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        task_index = data.get("task_index")
        if task_index:
            tasks_data[task_index] = data

    # Step 2: Find tasks that need rejudging (have answer but no answer_match or answer_match=false)
    tasks_to_rejudge = []
    for task_index, data in tasks_data.items():
        answer = data.get("answer")
        ground_truth = data.get("ground_truth")
        current_match = data.get("answer_match")

        # Only rejudge if has answer and ground_truth, and either no answer_match or answer_match=false
        if answer and ground_truth and (current_match is None or current_match == False):
            tasks_to_rejudge.append({
                "task_index": task_index,
                "answer": answer,
                "ground_truth": ground_truth,
                "current_match": current_match
            })

    logger.info(f"Tasks to rejudge: {len(tasks_to_rejudge)}")

    if not tasks_to_rejudge:
        logger.info("No tasks to rejudge!")
        return

    # Step 3: Rejudge with LLM
    logger.info("Step 2: Rejudging with LLM...")
    changed_count = 0
    for task_info in tqdm(tasks_to_rejudge, desc="Rejudging"):
        new_match = judge_answer_semantic_match(
            ground_truth=task_info["ground_truth"],
            model_answer=task_info["answer"],
            client=client,
            judge_model=judge_model,
        )

        task_info["new_match"] = new_match

        if new_match and not task_info.get("current_match", False):
            changed_count += 1
            logger.info(f"Task {task_info['task_index']}: False -> True")
            logger.info(f"  Ground truth: {task_info['ground_truth']}")
            logger.info(f"  Answer: {task_info['answer'][:100]}...")

    logger.info(f"Changed {changed_count} tasks from false to true")

    # Step 4: Update task JSON files
    logger.info("Step 3: Updating task JSON files...")
    for task_info in tqdm(tasks_to_rejudge, desc="Updating task files"):
        task_index = task_info["task_index"]
        task_file = trajectory_dir / f"task_{task_index:06d}.json"

        if task_file.exists():
            with open(task_file, "r", encoding="utf-8") as f:
                task_data = json.load(f)

            # Update answer_match field
            task_data["answer_match"] = task_info["new_match"]

            with open(task_file, "w", encoding="utf-8") as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2)

    # Step 5: Update batch_summary.json
    logger.info("Step 4: Updating batch_summary.json...")
    with open(batch_summary_path, "r", encoding="utf-8") as f:
        batch_summary = json.load(f)

    results = batch_summary.get("results", [])

    # Update answer_match in results
    for task_info in tasks_to_rejudge:
        task_index = task_info["task_index"]
        for r in results:
            if r and r.get("task_index") == task_index:
                r["answer_match"] = task_info["new_match"]
                break

    # Recalculate statistics
    total_tasks = len(results)
    matches = sum(1 for r in results if r and r.get("answer_match", False))
    batch_summary["answer_matches"] = matches
    batch_summary["match_rate"] = matches / total_tasks * 100 if total_tasks else 0

    with open(batch_summary_path, "w", encoding="utf-8") as f:
        json.dump(batch_summary, f, ensure_ascii=False, indent=2)

    logger.info(f"Updated batch_summary.json: answer_matches={matches}, match_rate={batch_summary['match_rate']:.1f}%")

    # Step 6: Update generation_metadata.json
    if metadata_path.exists():
        logger.info("Step 5: Updating generation_metadata.json...")
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        for task_info in tasks_to_rejudge:
            task_idx = str(task_info["task_index"])
            if task_idx in metadata:
                metadata[task_idx]["answer_match"] = task_info["new_match"]

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(f"Updated generation_metadata.json")

    print("\n" + "=" * 60)
    print("REJUDGE SUMMARY")
    print("=" * 60)
    print(f"Total task files: {len(task_files)}")
    print(f"Tasks rejudged: {len(tasks_to_rejudge)}")
    print(f"Changed to match=true: {changed_count}")
    print(f"Final answer_matches: {matches}")
    print(f"Final match_rate: {batch_summary['match_rate']:.1f}%")
    print("=" * 60)


if __name__ == "__main__":
    main()
