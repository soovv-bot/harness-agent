"""Trajectory recorder for SearchHarness.

Records complete planner + executor conversation trajectories with pipeline
state and metadata. Output format is compatible with the existing
convert_trajectory_to_offseeker_format.py converter.

Usage:
    recorder = TrajectoryRecorder(model_id="GLM-5.2", output_dir="logs/trajectories")
    recorder.start(question="...", task_index=0, pipeline_config={...})
    recorder.record_planner(messages=planner.messages, iteration=0)
    recorder.record_executor(messages=executor.messages, iteration=0)
    ...
    recorder.finalize(status="solved", iterations=3, stop=None)
    recorder.update_grading(correct=True, extracted_answer="...", reasoning="...")
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


class TrajectoryRecorder:
    """Records a single SearchHarness pipeline run as a trajectory."""

    def __init__(
        self,
        model_id: str,
        output_dir: str = "logs/trajectories",
        task_index: int = 0,
    ):
        self.model_id = model_id
        self.output_dir = output_dir
        self.task_index = task_index

        # Collected data
        self._metadata: Dict[str, Any] = {}
        self._planner_turns: List[Dict[str, Any]] = []   # [{iteration, messages}, ...]
        self._executor_turns: List[Dict[str, Any]] = []   # [{iteration, messages}, ...]
        self._pipeline_state: Dict[str, Any] = {}
        self._started: bool = False
        self._partial_write_enabled: bool = True

    def start(
        self,
        question: str,
        task_index: Optional[int] = None,
        pipeline_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Begin recording a new task."""
        if task_index is not None:
            self.task_index = task_index

        self._metadata = {
            "task_index": self.task_index,
            "question": question,
            "model": self.model_id,
            "started_at": datetime.now().isoformat(),
            "finished_at": None,
            "status": None,
            "iterations": 0,
            "stop_reason": None,
            "is_correct": None,
            "pipeline_config": pipeline_config or {},
            "grading": None,
        }
        self._planner_turns.clear()
        self._executor_turns.clear()
        self._pipeline_state.clear()
        self._started = True
        self._write_partial_snapshot(status="running")

    def record_planner(self, messages: List[Dict[str, Any]], iteration: int) -> None:
        """Record planner conversation for one iteration."""
        if not self._started:
            return
        self._planner_turns.append({
            "iteration": iteration,
            "messages": deepcopy(messages),
        })
        self._write_partial_snapshot(status="running")

    def record_executor(self, messages: List[Dict[str, Any]], iteration: int) -> None:
        """Record executor conversation for one iteration."""
        if not self._started:
            return
        self._executor_turns.append({
            "iteration": iteration,
            "messages": deepcopy(messages),
        })
        self._write_partial_snapshot(status="running")

    def record_pipeline_state(
        self,
        query_history: Optional[Dict[str, Any]] = None,
        snapshots: Optional[List[Dict[str, Any]]] = None,
        state_summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record the final pipeline state for analysis."""
        self._pipeline_state = {
            "query_history": query_history or {},
            "snapshots": snapshots or [],
            "state_summary": state_summary or {},
        }
        if self._started:
            self._write_partial_snapshot(status="running")

    def finalize(
        self,
        status: str,
        iterations: int,
        stop: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Finalize recording and save to disk."""
        if not self._started:
            return

        self._metadata["finished_at"] = datetime.now().isoformat()
        self._metadata["status"] = status
        self._metadata["iterations"] = iterations
        self._metadata["stop_reason"] = stop

        trajectory = {
            "metadata": self._metadata,
            "pipeline_state": self._pipeline_state,
            "messages": self._build_merged_messages(),
        }

        output_path = self._output_path()
        self._write_json(output_path, trajectory)

        logger.info(f"[TrajectoryRecorder] Saved trajectory to {output_path}")

        partial_path = self._partial_output_path()
        if partial_path.exists():
            try:
                partial_path.unlink()
            except OSError:
                logger.warning(f"[TrajectoryRecorder] Failed to remove partial trajectory {partial_path}")

    def update_grading(
        self,
        correct: bool,
        extracted_answer: str = "",
        reasoning: str = "",
    ) -> None:
        """Update metadata with grading result (call after finalize if needed)."""
        self._metadata["is_correct"] = correct
        self._metadata["grading"] = {
            "correct": correct,
            "extracted_answer": extracted_answer,
            "reasoning": reasoning,
        }
        # Re-save the file with updated grading
        if self._metadata.get("finished_at"):
            trajectory = {
                "metadata": self._metadata,
                "pipeline_state": self._pipeline_state,
                "messages": self._build_merged_messages(),
            }
            output_path = self._output_path()
            self._write_json(output_path, trajectory)

    def _build_merged_messages(self) -> List[Dict[str, Any]]:
        """Merge planner and executor messages into a single conversation.

        Strategy: interleave by iteration with separator messages.
        Iteration 0: planner -> separator -> executor
        Iteration 1: separator -> planner -> separator -> executor
        ...
        """
        merged: List[Dict[str, Any]] = []

        # Build lookup: iteration -> messages
        planner_by_iter = {t["iteration"]: t["messages"] for t in self._planner_turns}
        executor_by_iter = {t["iteration"]: t["messages"] for t in self._executor_turns}

        all_iterations = sorted(
            set(planner_by_iter.keys()) | set(executor_by_iter.keys())
        )

        for i, iteration in enumerate(all_iterations):
            # Planner turn
            if iteration in planner_by_iter:
                if i > 0:
                    merged.append({
                        "role": "user",
                        "content": f"[Iteration {iteration} — Planning Phase]",
                    })
                for msg in planner_by_iter[iteration]:
                    merged.append(deepcopy(msg))

            # Executor turn
            if iteration in executor_by_iter:
                merged.append({
                    "role": "user",
                    "content": f"[Iteration {iteration} — Execution Phase]",
                })
                for msg in executor_by_iter[iteration]:
                    merged.append(deepcopy(msg))

        return merged

    def _output_path(self) -> Path:
        return Path(self.output_dir) / self.model_id / f"task_{self.task_index:06d}.json"

    def _partial_output_path(self) -> Path:
        return Path(self.output_dir) / self.model_id / f"task_{self.task_index:06d}.partial.json"

    def _snapshot_payload(self, status: str, partial: bool) -> Dict[str, Any]:
        metadata = deepcopy(self._metadata)
        metadata["status"] = metadata.get("status") or status
        metadata["partial"] = partial
        metadata["updated_at"] = datetime.now().isoformat()
        metadata["planner_turns_recorded"] = len(self._planner_turns)
        metadata["executor_turns_recorded"] = len(self._executor_turns)
        return {
            "metadata": metadata,
            "pipeline_state": deepcopy(self._pipeline_state),
            "messages": self._build_merged_messages(),
        }

    def _write_json(self, output_path: Path, payload: Dict[str, Any]) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        try:
            os.replace(tmp_path, output_path)
        except PermissionError:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    def _write_partial_snapshot(self, status: str) -> None:
        if not self._partial_write_enabled:
            return
        payload = self._snapshot_payload(status=status, partial=True)
        self._write_json(self._partial_output_path(), payload)
