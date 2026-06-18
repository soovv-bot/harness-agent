import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def _run_once(
    run_index: int,
    seed: int,
    base_dir: Path,
    output_dir: Path,
    trajectory_root: Path,
    extra_args: List[str],
) -> Dict:
    run_output = output_dir / f"seed{seed}_run{run_index:02d}.json"
    run_trajectory_dir = trajectory_root / f"seed{seed}_run{run_index:02d}"

    cmd = [
        sys.executable,
        "run_browsecomp.py",
        "--num-examples",
        "1",
        "--max-workers",
        "1",
        "--seed",
        str(seed),
        "--output",
        str(run_output),
        "--trajectory-dir",
        str(run_trajectory_dir),
    ] + extra_args

    start = time.time()
    completed = subprocess.run(
        cmd,
        cwd=str(base_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    elapsed = time.time() - start

    result = {
        "run_index": run_index,
        "seed": seed,
        "command": cmd,
        "returncode": completed.returncode,
        "elapsed_seconds": round(elapsed, 1),
        "output_file": str(run_output),
        "trajectory_dir": str(run_trajectory_dir),
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }

    if completed.returncode == 0 and run_output.exists():
        payload = json.loads(run_output.read_text(encoding="utf-8"))
        first = (payload.get("results") or [{}])[0]
        result.update(
            {
                "accuracy": payload.get("accuracy"),
                "is_correct": first.get("is_correct", False),
                "extracted_answer": first.get("extracted_answer", ""),
                "pipeline_status": first.get("pipeline_status", ""),
                "grader_reasoning": first.get("grader_reasoning", ""),
            }
        )
    else:
        result.update(
            {
                "accuracy": 0.0,
                "is_correct": False,
                "extracted_answer": "",
                "pipeline_status": "unfinished",
                "grader_reasoning": "run failed before producing result file",
            }
        )

    return result


def main():
    parser = argparse.ArgumentParser(description="Repeat a single BrowseComp seed multiple times with bounded concurrency.")
    parser.add_argument("--seed", type=int, default=123, help="Seed passed to run_browsecomp.py")
    parser.add_argument("--repeats", type=int, default=10, help="How many repeated runs to execute")
    parser.add_argument("--parallelism", type=int, default=3, help="How many runs to execute concurrently")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="results/seed_repeats",
        help="Directory for per-run JSON outputs and aggregate summary",
    )
    parser.add_argument(
        "--trajectory-root",
        type=str,
        default="training_trajectories/seed_repeats",
        help="Root directory for per-run trajectory folders",
    )
    parser.add_argument(
        "--extra-arg",
        action="append",
        default=[],
        help="Extra argument passed through to run_browsecomp.py. Repeat as needed, e.g. --extra-arg=--max-iterations --extra-arg=6",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    output_dir = (base_dir / args.output_dir).resolve()
    trajectory_root = (base_dir / args.trajectory_root).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    trajectory_root.mkdir(parents=True, exist_ok=True)

    runs: List[Dict] = []
    overall_start = time.time()

    with ThreadPoolExecutor(max_workers=args.parallelism) as executor:
        futures = {
            executor.submit(
                _run_once,
                run_index,
                args.seed,
                base_dir,
                output_dir,
                trajectory_root,
                args.extra_arg,
            ): run_index
            for run_index in range(args.repeats)
        }

        for future in as_completed(futures):
            run_result = future.result()
            runs.append(run_result)
            mark = "OK" if run_result.get("is_correct") else "X "
            print(
                f"[{mark}] run={run_result['run_index']:02d} "
                f"status={run_result.get('pipeline_status')} "
                f"answer={run_result.get('extracted_answer', '')[:80]} "
                f"time={run_result['elapsed_seconds']:.1f}s"
            )

    runs.sort(key=lambda x: x["run_index"])
    total_elapsed = round(time.time() - overall_start, 1)
    correct = sum(1 for r in runs if r.get("is_correct"))
    accuracy = correct / len(runs) if runs else 0.0

    summary = {
        "timestamp": datetime.now().isoformat(),
        "seed": args.seed,
        "repeats": args.repeats,
        "parallelism": args.parallelism,
        "total_elapsed_seconds": total_elapsed,
        "correct_count": correct,
        "accuracy": accuracy,
        "runs": runs,
    }

    summary_path = output_dir / f"seed{args.seed}_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print("Repeated Seed Evaluation Summary")
    print("=" * 60)
    print(f"Seed:          {args.seed}")
    print(f"Repeats:       {args.repeats}")
    print(f"Parallelism:   {args.parallelism}")
    print(f"Correct:       {correct}")
    print(f"Accuracy:      {accuracy:.2%}")
    print(f"Total time:    {total_elapsed:.1f}s")
    print(f"Summary file:  {summary_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
