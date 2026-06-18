"""Export planner-only SFT data from SearchHarness trajectories.

The first training target is deliberately narrow: imitate successful planner
decisions from stronger model trajectories. Each exported example contains the
planner-visible system/user messages and one canonical assistant target:
either a <planning> JSON block or an <answer> block.
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import string
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd


PLANNING_PHASE_RE = re.compile(r"\[Iteration\s+(\d+).*?Planning Phase\]", re.IGNORECASE)
EXECUTION_PHASE_RE = re.compile(r"\[Iteration\s+(\d+).*?Execution Phase\]", re.IGNORECASE)
ANSWER_RE = re.compile(r"<answer>(.*?)</answer>", re.IGNORECASE | re.DOTALL)
PLANNING_RE = re.compile(r"<planning>(.*?)</planning>", re.IGNORECASE | re.DOTALL)
CURRENT_SYSTEM_SUFFIX = """

You have no tools. Do not call tools, browse, search, or update the candidate pool yourself.
All search, browsing, candidate expansion, and candidate verification must be assigned to the executor through concrete subtasks.
Keep every plan compact: at most 6 steps, no large candidate dumps, and no long enumerations.

If the task is not solved, output exactly one <planning>...</planning> block with valid JSON only.
If the task is solved, output exactly one <answer>...</answer> block.
"""


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_answer(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip()).lower()
    return text.strip(string.whitespace + string.punctuation)


def _extract_answer(content: str) -> Optional[str]:
    matches = ANSWER_RE.findall(content or "")
    if not matches:
        return None
    return matches[-1].strip()


def _repair_json_candidates(raw: str) -> Iterable[str]:
    text = (raw or "").strip()
    if not text:
        return []
    candidates = [text]
    fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    if fenced and fenced not in candidates:
        candidates.append(fenced)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        obj = text[start : end + 1]
        if obj not in candidates:
            candidates.append(obj)
    return candidates


def _extract_plan(content: str) -> Optional[Dict[str, Any]]:
    planning_blocks = PLANNING_RE.findall(content or "")
    raw_candidates = list(reversed(planning_blocks)) if planning_blocks else [content or ""]
    for raw in raw_candidates:
        for candidate in _repair_json_candidates(raw):
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    return None


def _canonical_assistant_content(content: str) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    answer = _extract_answer(content)
    if answer is not None:
        return "answer", f"<answer>{answer}</answer>", None

    plan = _extract_plan(content)
    if plan is not None:
        plan_json = json.dumps(plan, ensure_ascii=False, indent=2)
        return "planning", f"<planning>\n{plan_json}\n</planning>", plan

    return None, None, None


def _is_current_planning_schema(plan: Dict[str, Any]) -> bool:
    """Keep SFT targets aligned with the current planner-output interface."""
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        return False
    if "source_recommendations" not in plan:
        return False
    if not isinstance(plan.get("candidate_status"), dict):
        return False
    actionable_steps = [
        step
        for step in steps
        if isinstance(step, dict) and str(step.get("status", "")).lower() in {"pending", "in_progress"}
    ]
    if not actionable_steps:
        actionable_steps = [step for step in steps if isinstance(step, dict)]
    return any(step.get("subtask") and step.get("subtask_type") for step in actionable_steps)


def _clean_message(msg: Dict[str, Any]) -> Optional[Dict[str, str]]:
    role = msg.get("role")
    content = msg.get("content")
    if role not in {"system", "user", "assistant"}:
        return None
    if not isinstance(content, str) or not content.strip():
        return None
    return {"role": role, "content": content}


def _is_phase_separator(msg: Dict[str, Any], pattern: re.Pattern[str]) -> bool:
    content = msg.get("content")
    return msg.get("role") == "user" and isinstance(content, str) and bool(pattern.search(content))


def _split_planner_segments(messages: List[Dict[str, Any]]) -> List[Tuple[int, List[Dict[str, Any]]]]:
    """Return (iteration, planner_messages) segments from merged trajectory messages."""
    segments: List[Tuple[int, List[Dict[str, Any]]]] = []
    current: List[Dict[str, Any]] = []
    current_iteration = 0
    in_planner = True

    for msg in messages:
        content = msg.get("content")
        if _is_phase_separator(msg, PLANNING_PHASE_RE):
            if current:
                segments.append((current_iteration, current))
            match = PLANNING_PHASE_RE.search(content or "")
            current_iteration = int(match.group(1)) if match else current_iteration + 1
            current = []
            in_planner = True
            continue

        if _is_phase_separator(msg, EXECUTION_PHASE_RE):
            if current:
                segments.append((current_iteration, current))
            current = []
            in_planner = False
            continue

        if in_planner:
            cleaned = _clean_message(msg)
            if cleaned:
                current.append(cleaned)

    if current:
        segments.append((current_iteration, current))

    return segments


def _load_gold_answers(answer_file: Optional[Path]) -> Dict[int, str]:
    if not answer_file or not answer_file.exists():
        return {}
    data = _read_json(answer_file)
    answers: Dict[int, str] = {}
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "sample_position" in item and "answer" in item:
                answers[int(item["sample_position"])] = str(item["answer"])
    return answers


def _load_current_system_prompt(system_prompt_file: Optional[Path]) -> Optional[str]:
    if not system_prompt_file:
        return None
    if not system_prompt_file.exists():
        raise FileNotFoundError(f"System prompt file not found: {system_prompt_file}")
    return system_prompt_file.read_text(encoding="utf-8") + CURRENT_SYSTEM_SUFFIX


def _trajectory_success(
    trajectory: Dict[str, Any],
    gold_answers: Dict[int, str],
    success_policy: str,
) -> Tuple[bool, str]:
    metadata = trajectory.get("metadata") or {}
    if success_policy == "all":
        return True, "all"

    status = str(metadata.get("status") or "").lower()
    if metadata.get("partial") is True or status == "running":
        return False, "partial_or_running"

    if metadata.get("is_correct") is True:
        return True, "metadata_is_correct"

    task_index = metadata.get("task_index")
    final_answer = None
    for msg in reversed(trajectory.get("messages") or []):
        if msg.get("role") == "assistant":
            final_answer = _extract_answer(msg.get("content") or "")
            if final_answer:
                break

    if success_policy in {"answer_match_or_correct", "answer_match"}:
        if task_index is not None and int(task_index) in gold_answers and final_answer:
            gold = gold_answers[int(task_index)]
            if _normalize_answer(final_answer) == _normalize_answer(gold):
                return True, "final_answer_matches_gold"
        if success_policy == "answer_match":
            return False, "no_gold_answer_match"

    if success_policy == "status_or_correct":
        if status in {"finished", "solved"} and final_answer:
            return True, f"status_{status}_with_final_answer"

    return False, "not_successful"


def _examples_from_trajectory(
    path: Path,
    trajectory: Dict[str, Any],
    success_reason: str,
    current_system_prompt: Optional[str],
    replace_system_prompt: bool,
    require_current_schema: bool,
) -> List[Dict[str, Any]]:
    metadata = trajectory.get("metadata") or {}
    examples: List[Dict[str, Any]] = []

    for iteration, segment in _split_planner_segments(trajectory.get("messages") or []):
        assistant_positions = [i for i, msg in enumerate(segment) if msg.get("role") == "assistant"]
        if not assistant_positions:
            continue
        target_idx = assistant_positions[-1]
        target_type, target_content, plan = _canonical_assistant_content(segment[target_idx].get("content") or "")
        if not target_type or not target_content:
            continue
        if require_current_schema and target_type == "planning" and not _is_current_planning_schema(plan or {}):
            continue

        # Keep only planner-visible instructions/state before the target.
        # Dropping earlier assistant messages avoids teaching malformed retry outputs.
        prefix = [msg for msg in segment[:target_idx] if msg.get("role") in {"system", "user"}]
        if not prefix:
            continue
        if replace_system_prompt and current_system_prompt:
            first_system_idx = next((i for i, msg in enumerate(prefix) if msg.get("role") == "system"), None)
            if first_system_idx is None:
                prefix.insert(0, {"role": "system", "content": current_system_prompt})
            else:
                prefix[first_system_idx] = {"role": "system", "content": current_system_prompt}

        messages = prefix + [{"role": "assistant", "content": target_content}]
        examples.append(
            {
                "messages": messages,
                "source_trajectory": str(path),
                "task_index": metadata.get("task_index"),
                "iteration": iteration,
                "target_type": target_type,
                "success_reason": success_reason,
                "trajectory_status": metadata.get("status"),
                "model": metadata.get("model"),
                "question": metadata.get("question"),
            }
        )

    return examples


def export_planner_sft(
    trajectory_glob: str,
    output_jsonl: Path,
    output_parquet: Optional[Path],
    answer_file: Optional[Path],
    success_policy: str,
    system_prompt_file: Optional[Path],
    replace_system_prompt: bool,
    require_current_schema: bool,
) -> Dict[str, Any]:
    gold_answers = _load_gold_answers(answer_file)
    current_system_prompt = _load_current_system_prompt(system_prompt_file) if replace_system_prompt else None
    paths = sorted(Path(p) for p in glob.glob(trajectory_glob, recursive=True))
    records: List[Dict[str, Any]] = []
    skipped: Dict[str, int] = {}

    for path in paths:
        try:
            trajectory = _read_json(path)
        except Exception:
            skipped["read_error"] = skipped.get("read_error", 0) + 1
            continue

        ok, reason = _trajectory_success(trajectory, gold_answers, success_policy)
        if not ok:
            skipped[reason] = skipped.get(reason, 0) + 1
            continue

        examples = _examples_from_trajectory(
            path,
            trajectory,
            success_reason=reason,
            current_system_prompt=current_system_prompt,
            replace_system_prompt=replace_system_prompt,
            require_current_schema=require_current_schema,
        )
        if not examples:
            skipped["no_planner_examples"] = skipped.get("no_planner_examples", 0) + 1
            continue
        records.extend(examples)

    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with output_jsonl.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    if output_parquet:
        output_parquet.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(records).to_parquet(output_parquet, index=False)

    return {
        "trajectory_glob": trajectory_glob,
        "trajectories_scanned": len(paths),
        "examples_exported": len(records),
        "output_jsonl": str(output_jsonl),
        "output_parquet": str(output_parquet) if output_parquet else None,
        "success_policy": success_policy,
        "gold_answers_loaded": len(gold_answers),
        "replace_system_prompt": replace_system_prompt,
        "system_prompt_file": str(system_prompt_file) if system_prompt_file else None,
        "require_current_schema": require_current_schema,
        "skipped": skipped,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export planner-only SFT data from SearchHarness trajectories.")
    parser.add_argument("--trajectory-glob", default="training_trajectories/**/task_*.json")
    parser.add_argument("--output-jsonl", default="training/data/planner_sft.jsonl")
    parser.add_argument("--output-parquet", default="training/data/planner_sft.parquet")
    parser.add_argument("--answer-file", default="docs/seed123_k10_full.json")
    parser.add_argument("--system-prompt-file", default="planning_agent_prompt_v3.md")
    parser.add_argument("--keep-original-system-prompt", action="store_true")
    parser.add_argument("--allow-legacy-planning-schema", action="store_true")
    parser.add_argument(
        "--success-policy",
        choices=["answer_match_or_correct", "answer_match", "metadata_correct", "status_or_correct", "all"],
        default="answer_match_or_correct",
        help=(
            "answer_match_or_correct uses gold answer matches when available and falls back to metadata.is_correct. "
            "metadata_correct only trusts trajectory grading. status_or_correct also accepts finished/solved with a final answer."
        ),
    )
    args = parser.parse_args()

    success_policy = args.success_policy
    answer_file = Path(args.answer_file) if args.answer_file and success_policy != "metadata_correct" else None

    summary = export_planner_sft(
        trajectory_glob=args.trajectory_glob,
        output_jsonl=Path(args.output_jsonl),
        output_parquet=Path(args.output_parquet) if args.output_parquet else None,
        answer_file=answer_file,
        success_policy=success_policy,
        system_prompt_file=Path(args.system_prompt_file) if args.system_prompt_file else None,
        replace_system_prompt=not args.keep_original_system_prompt,
        require_current_schema=not args.allow_legacy_planning_schema,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
