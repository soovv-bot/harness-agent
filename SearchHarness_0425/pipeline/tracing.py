"""Trajectory event helpers extracted from SearchHarnessPipelineV4 (RD step4b).

Pure functions taking the pipeline instance as the first parameter; no class
inheritance or mixin. Re-bound on the class as private attribute names so
existing external call sites (e.g. tests grabbing unbound methods) keep working.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from loguru import logger

if TYPE_CHECKING:  # avoid circular import with .orchestrator
    from pipeline.orchestrator import SearchHarnessPipelineV4


def record_candidate_snapshot_for_trajectory(
    pipeline: "SearchHarnessPipelineV4",
    iteration: int,
) -> None:
    """Snapshot the current candidate pool into the trajectory recorder."""
    if not pipeline.trajectory_recorder:
        return
    records = pipeline._all_candidate_records()
    try:
        pipeline.trajectory_recorder.record_candidate_snapshot(
            iteration=iteration,
            candidates=records,
            active_candidate=pipeline.active_candidate,
        )
    except Exception as e:
        logger.debug(f"[Pipeline] candidate snapshot record error: {e}")


def record_event_for_trajectory(
    pipeline: "SearchHarnessPipelineV4",
    event_type: str,
    iteration: int,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """Record a structured event into the trajectory recorder."""
    if not pipeline.trajectory_recorder:
        return
    try:
        pipeline.trajectory_recorder.record_event(
            event_type, iteration=iteration, agent="pipeline", data=data or {}
        )
    except Exception as e:
        logger.debug(f"[Pipeline] event record error: {e}")


def record_iteration_summary_for_trajectory(
    pipeline: "SearchHarnessPipelineV4",
    iteration: int,
    subtask: Optional[Dict[str, Any]],
    findings: Optional[Dict[str, Any]],
) -> None:
    """Record an iteration summary into the trajectory recorder."""
    if not pipeline.trajectory_recorder:
        return
    try:
        cu = (findings or {}).get("candidate_updates", {}) or {}
        pipeline.trajectory_recorder.record_iteration_summary(
            iteration=iteration,
            phase=pipeline.workflow_stage,
            subtask=(subtask or {}).get("subtask") or (subtask or {}).get("name", ""),
            searches_this_iter=getattr(pipeline.executor, "_search_count", 0),
            new_candidates=cu.get("new_candidates", []) or [],
            plan_phase=(subtask or {}).get("subtask_type", ""),
        )
    except Exception as e:
        logger.debug(f"[Pipeline] iteration summary record error: {e}")
