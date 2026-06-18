"""
Batch Trajectory Generation Script with Resume Support
Generate trajectories for multiple tasks concurrently using ThreadPoolExecutor.

Features:
- Resume from previous runs (skips completed tasks)
- Save each trajectory immediately after completion
- Progress tracking and summary

Tasks are loaded from source_oriented_data_systhesis/data/mixed_domains_qa_with_enhance.jsonl
Trajectories are saved to data/trajectories/{model}/task_000001.json
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Dict, List, Optional, Set
from datetime import datetime
import argparse

from trajectory_agent import TrajectoryRecordingAgent
from openai import OpenAI


# Thread-safe file writing lock
file_lock = Lock()


def judge_answer_semantic_match(
    ground_truth: str,
    model_answer: str,
    api_base: str,
    api_key: str,
    judge_model: str
) -> bool:
    """
    Use LLM to judge if model answer is semantically equivalent to ground truth.

    Args:
        ground_truth: The expected correct answer
        model_answer: The answer produced by the model
        api_base: API base URL
        api_key: API key
        judge_model: Model to use for judging

    Returns:
        True if semantically equivalent, False otherwise
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
        client = OpenAI(base_url=api_base, api_key=api_key)
        response = client.chat.completions.create(
            model=judge_model,
            messages=[{"role": "user", "content": judge_prompt}],
            temperature=0,
            max_tokens=10,
        )
        result = response.choices[0].message.content.strip().upper()
        return "YES" in result
    except Exception as e:
        logger.warning(f"Judge API call failed: {e}, falling back to string match")
        # Fallback to simple string match
        return ground_truth.lower() in model_answer.lower()


# Dedicated trajectory directory
TRAJECTORY_DIR = Path("data/trajectories")

# Maximum retry attempts per task
MAX_RETRIES = 3

# Metadata file path will be set per model in main()
# Each model has its own generation_metadata.json in its trajectory directory


def get_completed_tasks(trajectory_dir: Path) -> Set[int]:
    """
    Scan trajectory directory (including subdirectories) to find already completed tasks.

    Subdirectories:
    - no_answer/: Tasks without answers
    - answer_wrong/: Tasks with wrong answers
    - answer_correct/: Tasks with correct answers

    Args:
        trajectory_dir: Path to trajectory directory

    Returns:
        Set of completed task indices
    """
    completed = set()
    if not trajectory_dir.exists():
        return completed

    # Scan root directory and all subdirectories
    subdirs = ["no_answer", "answer_wrong", "answer_correct"]
    search_paths = [trajectory_dir] + [trajectory_dir / d for d in subdirs]

    for search_path in search_paths:
        if not search_path.exists():
            continue
        for file_path in search_path.glob("task_*.json"):
            try:
                # Extract index from filename like task_000001.json
                filename = file_path.stem  # remove .json
                if filename.startswith("task_"):
                    index = int(filename.split("_")[1])
                    completed.add(index)
            except (ValueError, IndexError) as e:
                logger.warning(f"Could not parse index from {file_path}: {e}")

    return completed


def load_generation_metadata(metadata_file: Path) -> Dict[int, Dict]:
    """
    Load generation metadata from file.

    Args:
        metadata_file: Path to metadata file

    Returns:
        Dict mapping task_index to metadata dict
    """
    if not metadata_file.exists():
        return {}

    try:
        with open(metadata_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load metadata: {e}, starting fresh")
        return {}


def save_generation_metadata(metadata: Dict[int, Dict], metadata_file: Path):
    """
    Save generation metadata to file.

    Args:
        metadata: Dict mapping task_index to metadata dict
        metadata_file: Path to metadata file
    """
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    with file_lock:
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)


def update_attempt_metadata(
    task_index: int,
    answer: Optional[str],
    status: str,
    attempts: int,
    metadata: Dict,
    metadata_file: Path
) -> Dict:
    """
    Update attempt metadata for a task (thread-safe).

    Args:
        task_index: Task index
        answer: The answer from this attempt (can be None if failed)
        status: Status of this attempt (completed, max_turns_reached, error)
        attempts: Number of attempts so far
        metadata: Existing metadata dict
        metadata_file: Path to metadata file

    Returns:
        Updated metadata dict
    """
    with file_lock:
        if task_index not in metadata:
            metadata[task_index] = {
                "task_index": task_index,
                "attempts": [],
            }

        attempt_record = {
            "attempt_number": attempts,
            "answer": answer,
            "status": status,
            "timestamp": datetime.now().isoformat(),
        }

        metadata[task_index]["attempts"].append(attempt_record)
        metadata[task_index]["latest_answer"] = answer
        metadata[task_index]["latest_status"] = status
        metadata[task_index]["total_attempts"] = attempts

        # Save immediately (already inside lock)
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    return metadata


def process_single_task(
    task_index: int,
    task_data: Dict,
    agent_config: Dict,
    judge_config: Dict,
    trajectory_dir: str,
    generation_metadata: Dict[int, Dict],
    metadata_file: Path,
    save_trajectory: bool = True,
    verbose: bool = False
) -> Optional[Dict]:
    """
    Process a single task with retry support.

    Args:
        task_index: Sequential index of the task (for file naming)
        task_data: Task data from dataset
        agent_config: Agent configuration dict
        judge_config: Judge configuration dict for semantic matching
        trajectory_dir: Directory to save trajectories
        generation_metadata: Shared metadata dict across all tasks
        metadata_file: Path to metadata file
        save_trajectory: Whether to save trajectory to file
        verbose: Whether to print detailed output

    Returns:
        Result dict with answer, trajectory, metadata, or None on failure
    """
    task = task_data["question"]
    ground_truth = task_data.get("answer", "")
    domain = task_data.get("domain", "unknown")
    difficulty = task_data.get("difficulty_level", "unknown")

    # Get current attempt count
    task_meta = generation_metadata.get(task_index, {})
    current_attempts = task_meta.get("total_attempts", 0)

    # Generate sequential filename: task_000001.json, task_000002.json, etc.
    filename = f"task_{task_index:06d}.json"

    # Retry loop
    for attempt in range(current_attempts + 1, MAX_RETRIES + 1):
        try:
            # Create agent for this task
            agent = TrajectoryRecordingAgent(
                api_base=agent_config["api_base"],
                api_key=agent_config["api_key"],
                model_id=agent_config["model_id"],
                temperature=agent_config.get("temperature", 0.6),
                enable_hint=agent_config.get("enable_hint", True),
                max_turns=agent_config.get("max_turns", 20),
                log_dir=trajectory_dir,
            )

            # Run the agent
            result = agent.run_with_trajectory(task, save_trajectory=False)

            status = result.get("metadata", {}).get("status", "unknown")
            answer = result.get("answer")

            # Update metadata with this attempt
            generation_metadata = update_attempt_metadata(
                task_index, answer, status, attempt, generation_metadata, metadata_file
            )

            # Determine if we need to retry
            should_retry = False

            if status == "completed":
                # Task completed successfully - no retry needed
                should_retry = False
            elif status == "max_turns_reached":
                # No answer but hit max turns - this is a failure case
                if attempt < MAX_RETRIES:
                    should_retry = True
                    logger.info(f"Task {task_index:06d} attempt {attempt}/{MAX_RETRIES} reached max turns, will retry...")
                else:
                    logger.warning(f"Task {task_index:06d} failed after {MAX_RETRIES} attempts (max turns)")
            else:
                # Error status
                if attempt < MAX_RETRIES:
                    should_retry = True
                    logger.warning(f"Task {task_index:06d} attempt {attempt}/{MAX_RETRIES} had error: {status}, will retry...")
                else:
                    logger.error(f"Task {task_index:06d} failed after {MAX_RETRIES} attempts (error)")

            if not should_retry:
                # Save trajectory (including failed ones)
                if save_trajectory and result:
                    # Check if answer matches ground truth using semantic judge
                    if answer and ground_truth:
                        answer_match = judge_answer_semantic_match(
                            ground_truth=ground_truth,
                            model_answer=answer,
                            api_base=judge_config["api_base"],
                            api_key=judge_config["api_key"],
                            judge_model=judge_config["model"],
                        )
                    else:
                        answer_match = False

                    # Determine subdirectory based on answer status
                    if not answer:
                        subdir = "no_answer"
                    elif answer_match:
                        subdir = "answer_correct"
                    else:
                        subdir = "answer_wrong"

                    # Create subdirectory if not exists
                    subdir_path = Path(trajectory_dir) / subdir
                    subdir_path.mkdir(parents=True, exist_ok=True)

                    # Prepare trajectory data with additional metadata
                    trajectory_data = {
                        "task_index": task_index,
                        "domain": domain,
                        "difficulty_level": difficulty,
                        "ground_truth": ground_truth,
                        "question": task,
                        "answer": answer,
                        "answer_match": answer_match,
                        "metadata": result.get("metadata", {}),
                        "trajectory": result.get("trajectory", []),
                        "generation_metadata": generation_metadata.get(task_index, {}),
                    }

                    # Save to subdirectory
                    final_trajectory_path = subdir_path / filename

                    # Thread-safe file write
                    with file_lock:
                        with open(final_trajectory_path, "w", encoding="utf-8") as f:
                            json.dump(trajectory_data, f, ensure_ascii=False, indent=2)

                    logger.info(f"Saved: {subdir}/{filename}")

                    result["trajectory_file"] = str(final_trajectory_path)

                # Add task metadata to result
                result["task_index"] = task_index
                result["filename"] = filename
                result["ground_truth"] = ground_truth
                result["domain"] = domain
                result["difficulty_level"] = difficulty
                result["skipped"] = False
                result["total_attempts"] = attempt
                result["answer_match"] = answer_match  # Use already computed value

                if verbose:
                    print(f"\n[Task {task_index:06d}]")
                    print(f"  File: {filename}")
                    print(f"  Domain: {domain}, Difficulty: {difficulty}")
                    print(f"  Answer: {result['answer'][:100] if result['answer'] else 'None'}...")
                    print(f"  Ground Truth: {ground_truth}")
                    print(f"  Match: {'✓' if result['answer_match'] else '✗'}")
                    print(f"  Turns: {result['metadata'].get('turns', 'N/A')}")
                    print(f"  Status: {result['metadata'].get('status', 'N/A')}")
                    print(f"  Attempts: {attempt}/{MAX_RETRIES}")

                return result

        except Exception as e:
            logger.error(f"Error processing task {task_index} attempt {attempt}: {e}")
            import traceback
            traceback.print_exc()

            # Update metadata with failed attempt
            generation_metadata = update_attempt_metadata(
                task_index, None, f"error: {str(e)}", attempt, generation_metadata, metadata_file
            )

            # If this is the last attempt and still failed, save failure record
            if attempt >= MAX_RETRIES:
                if save_trajectory:
                    # Failed tasks go to no_answer directory
                    subdir = "no_answer"
                    subdir_path = Path(trajectory_dir) / subdir
                    subdir_path.mkdir(parents=True, exist_ok=True)

                    failure_data = {
                        "task_index": task_index,
                        "domain": domain,
                        "difficulty_level": difficulty,
                        "ground_truth": ground_truth,
                        "question": task,
                        "answer": None,
                        "answer_match": False,
                        "metadata": {"status": "failed", "error": str(e)},
                        "trajectory": [],
                        "generation_metadata": generation_metadata.get(task_index, {}),
                    }

                    final_trajectory_path = subdir_path / filename

                    with file_lock:
                        with open(final_trajectory_path, "w", encoding="utf-8") as f:
                            json.dump(failure_data, f, ensure_ascii=False, indent=2)

                    logger.info(f"Saved failure record: {subdir}/{filename}")

                return {
                    "task_index": task_index,
                    "filename": filename,
                    "ground_truth": ground_truth,
                    "domain": domain,
                    "difficulty_level": difficulty,
                    "answer": None,
                    "metadata": {"status": "failed", "error": str(e)},
                    "trajectory_file": str(final_trajectory_path),
                    "skipped": False,
                    "answer_match": False,
                    "total_attempts": MAX_RETRIES,
                }

    # Should not reach here
    return None


def load_dataset(data_file: str, num_samples: Optional[int] = None) -> List[Dict]:
    """
    Load tasks from dataset file while preserving order.

    Args:
        data_file: Path to JSONL file
        num_samples: Maximum number of samples to load (None = all)

    Returns:
        List of task dicts with sequential index
    """
    tasks = []
    with open(data_file, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if num_samples and i >= num_samples:
                break
            try:
                task_data = json.loads(line.strip())
                tasks.append(task_data)
            except Exception as e:
                logger.warning(f"Failed to parse line {i}: {e}")
                continue

    logger.info(f"Loaded {len(tasks)} tasks from {data_file}")
    return tasks


def save_summary(results: List[Dict], output_file: str):
    """
    Save execution summary to file.

    Note: This function is deprecated - summary is now saved in main().
    Kept for backward compatibility.
    """
    logger.warning("save_summary() is deprecated, summary is now saved in main()")


def main():
    # Load environment variables first
    load_dotenv()

    # Read config from environment variables (defaults)
    env_query_file = os.getenv("DISTILLED_QUERY_FILE", "source_oriented_data_systhesis/data/mixed_domains_qa_with_enhance.jsonl")
    env_num_samples = os.getenv("DISTILLED_NUM_SAMPLES")
    env_max_workers = int(os.getenv("DISTILLED_MAX_WORKERS", "4"))
    env_summary_file = os.getenv("DISTILLED_SUMMARY_FILE", "data/trajectories/batch_summary.json")
    env_model = os.getenv("DISTILLED_MODEL") or os.getenv("MODEL_NAME", "deepseek-chat")
    env_force = os.getenv("DISTILLED_FORCE", "false").lower() == "true"

    parser = argparse.ArgumentParser(
        description="Batch generate trajectories using concurrent execution with resume support"
    )
    parser.add_argument(
        "--query-file", "-f",
        default=env_query_file,
        help=f"Path to query JSONL file (default: {env_query_file})"
    )
    parser.add_argument(
        "--num-samples", "-n",
        type=int,
        default=int(env_num_samples) if env_num_samples else None,
        help="Number of samples to process (default: all)"
    )
    parser.add_argument(
        "--max-workers", "-w",
        type=int,
        default=env_max_workers,
        help=f"Maximum number of concurrent workers (default: {env_max_workers})"
    )
    parser.add_argument(
        "--summary-file", "-s",
        default=env_summary_file,
        help=f"Output file for execution summary (default: {env_summary_file})"
    )
    parser.add_argument(
        "--model",
        default=env_model,
        help=f"Model name (default: {env_model})"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=env_force,
        help="Force re-run all tasks, ignoring completed ones (default: from DISTILLED_FORCE)"
    )

    args = parser.parse_args()

    api_base = os.getenv("OPENAI_BASE_URL")
    api_key = os.getenv("OPENAI_API_KEY")
    model_id = args.model

    if not api_base or not api_key:
        logger.error("Please set OPENAI_BASE_URL and OPENAI_API_KEY in .env file")
        return

    # Load queries
    logger.info(f"Loading queries from: {args.query_file}")
    tasks = load_dataset(args.query_file, args.num_samples)

    if not tasks:
        logger.error("No tasks to process")
        return

    # Create trajectory directory
    trajectory_dir = TRAJECTORY_DIR / model_id.replace("/", "_").replace(":", "_")

    # Check for completed tasks (resume support)
    if not args.force:
        completed_tasks = get_completed_tasks(trajectory_dir)
        logger.info(f"Found {len(completed_tasks)} already completed tasks in {trajectory_dir}")
    else:
        completed_tasks = set()
        logger.info("Force mode: will process all tasks")

    # Filter out completed tasks
    pending_indices = []
    for idx in range(1, len(tasks) + 1):
        if idx not in completed_tasks:
            pending_indices.append(idx)

    logger.info(f"Pending tasks: {len(pending_indices)} / {len(tasks)}")

    if not pending_indices:
        logger.info("All tasks already completed! Use --force to re-run.")
        return

    logger.info(f"Trajectory directory: {trajectory_dir}")
    logger.info(f"Processing {len(pending_indices)} tasks with {args.max_workers} workers...")

    # Create trajectory directory
    trajectory_dir.mkdir(parents=True, exist_ok=True)

    # Set metadata file path (per model)
    metadata_file = trajectory_dir / "generation_metadata.json"

    # Load or initialize generation metadata
    generation_metadata = load_generation_metadata(metadata_file)
    logger.info(f"Loaded metadata for {len(generation_metadata)} tasks")

    # Reset total_attempts for all tasks if --force mode
    if args.force:
        for task_idx in generation_metadata:
            generation_metadata[task_idx]["total_attempts"] = 0
        logger.info("Force mode: reset total_attempts for all tasks")

    # Agent configuration (from environment variables)
    agent_config = {
        "api_base": api_base,
        "api_key": api_key,
        "model_id": model_id,
        "temperature": float(os.getenv("DISTILLED_TEMPERATURE", "0.6")),
        "enable_hint": os.getenv("DISTILLED_ENABLE_HINT", "true").lower() == "true",
        "max_turns": int(os.getenv("DISTILLED_MAX_TURNS", "30")),
    }

    logger.info(f"Agent config: model={model_id}, temperature={agent_config['temperature']}, "
                f"enable_hint={agent_config['enable_hint']}, max_turns={agent_config['max_turns']}")

    # Judge config for semantic answer matching
    judge_model = os.getenv("ANSWER_JUDGE_MODEL", "deepseek-chat")
    judge_config = {
        "api_base": api_base,
        "api_key": api_key,
        "model": judge_model,
    }
    logger.info(f"Judge config: model={judge_model}")

    # Process tasks concurrently
    results = [None] * len(tasks)  # Pre-allocate to preserve order

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        # Submit only pending tasks
        futures = {}
        for task_index in pending_indices:
            task_data = tasks[task_index - 1]  # Convert to 0-based index
            future = executor.submit(
                process_single_task,
                task_index,
                task_data,
                agent_config,
                judge_config,
                str(trajectory_dir),
                generation_metadata,  # Pass metadata dict for tracking
                metadata_file,  # Pass metadata file path
                True,
                args.verbose
            )
            futures[future] = task_index

        # Process completed tasks with progress bar
        with tqdm(total=len(pending_indices), desc="Generating trajectories") as pbar:
            for future in as_completed(futures):
                task_index = futures[future]
                try:
                    result = future.result(timeout=600)  # 10 minutes timeout per task
                    results[task_index - 1] = result  # Store at correct position

                    # Update progress bar description with stats
                    completed_count = sum(1 for r in results if r and r.get("metadata", {}).get("status") == "completed")
                    matches_count = sum(1 for r in results if r and r.get("answer_match", False))
                    skipped_count = sum(1 for r in results if r and r.get("skipped", False))
                    pbar.set_postfix({
                        f"done": f"{completed_count}/{len(results)}",
                        f"match": f"{matches_count}",
                        f"skip": f"{skipped_count}"
                    })

                except Exception as e:
                    logger.error(f"Task {task_index} failed: {e}")
                    results[task_index - 1] = None

                pbar.update(1)

    # Collect all results (including previously completed)
    all_results = []
    for idx, task_data in enumerate(tasks, start=1):
        if idx in completed_tasks:
            # Load previously completed result - search in subdirectories
            filename = f"task_{idx:06d}.json"
            trajectory_path = None

            # Search in subdirectories first, then root
            for subdir in ["no_answer", "answer_wrong", "answer_correct", ""]:
                search_path = trajectory_dir / subdir / filename if subdir else trajectory_dir / filename
                if search_path.exists():
                    trajectory_path = search_path
                    break

            if trajectory_path and trajectory_path.exists():
                with open(trajectory_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)

                # Use existing answer_match if available, otherwise judge
                answer = existing_data.get("answer")
                ground_truth = task_data.get("answer", "")
                answer_match = existing_data.get("answer_match")

                if answer_match is None and answer and ground_truth:
                    answer_match = judge_answer_semantic_match(
                        ground_truth=ground_truth,
                        model_answer=answer,
                        api_base=api_base,
                        api_key=api_key,
                        judge_model=judge_config["model"],
                    )
                elif answer_match is None:
                    answer_match = False

                all_results.append({
                    "task_index": idx,
                    "filename": filename,
                    "ground_truth": ground_truth,
                    "domain": task_data.get("domain", "unknown"),
                    "difficulty_level": task_data.get("difficulty_level", "unknown"),
                    "answer": answer,
                    "metadata": existing_data.get("metadata", {}),
                    "skipped": True,
                    "answer_match": answer_match
                })
        else:
            all_results.append(results[idx - 1])

    # Print summary
    successful = sum(1 for r in all_results if r and r.get("metadata", {}).get("status") == "completed")
    failed = sum(1 for r in all_results if not r or r.get("metadata", {}).get("status") != "completed")
    matches = sum(1 for r in all_results if r and r.get("answer_match", False))
    skipped = sum(1 for r in all_results if r and r.get("skipped", False))

    print("\n" + "=" * 80)
    print("BATCH EXECUTION SUMMARY")
    print("=" * 80)
    print(f"Total tasks: {len(all_results)}")
    print(f"Previously completed: {skipped}")
    print(f"Newly completed: {successful - skipped}")
    print(f"Failed: {failed}")
    print(f"Answer matches: {matches}")
    print(f"Success rate: {successful / len(all_results) * 100:.1f}%")
    print(f"Match rate: {matches / len(all_results) * 100:.1f}%")
    print(f"\nTrajectory directory: {trajectory_dir}")
    print("=" * 80)

    # Save summary (without detailed results - those are in individual trajectory files)
    summary_data = {
        "timestamp": datetime.now().isoformat(),
        "trajectory_dir": str(trajectory_dir),
        "total_tasks": len(all_results),
        "previously_completed": skipped,
        "newly_completed": successful - skipped,
        "failed": failed,
        "answer_matches": matches,
        "success_rate": successful / len(all_results) * 100 if all_results else 0,
        "match_rate": matches / len(all_results) * 100 if all_results else 0,
        "domains": {},
        "difficulties": {}
    }

    # Collect statistics
    for r in all_results:
        if not r:
            continue
        domain = r.get("domain", "unknown")
        difficulty = r.get("difficulty_level", "unknown")
        summary_data["domains"][domain] = summary_data["domains"].get(domain, 0) + 1
        summary_data["difficulties"][difficulty] = summary_data["difficulties"].get(difficulty, 0) + 1

    # Save summary
    summary_path = Path(args.summary_file)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved summary to: {summary_path}")
    logger.info("Batch execution completed!")
    logger.info(f"Generation metadata saved to: {metadata_file}")


if __name__ == "__main__":
    main()
