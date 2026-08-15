"""Enhanced trajectory recorder for SearchHarness.

Records rich, structured trajectory data for model training and log
debugging. Builds on TrajectoryRecorder with:

1. Structured event stream — every key decision point (search called,
   candidate added/eliminated, plan generated, answer produced) is a
   typed event with timestamp, agent, iteration, and payload.
2. Per-agent conversations — planner and executor conversations kept
   separate with metadata tags (agent, phase, iteration) on each message,
   so training pipelines can reconstruct the exact context each agent saw.
3. Candidate pool evolution — snapshot of the candidate pool after every
   iteration showing add/verify/eliminate transitions.
4. LLM call metadata — latency, token usage, and model params captured
   per assistant message.
5. Backward compatible — keeps the flat `messages` field for the existing
   convert_trajectory_to_offseeker_format.py converter.

Usage:
    recorder = TrajectoryRecorderEnhanced(model_id="<model_name>", output_dir="logs/trajectories")
    recorder.start(question="...", task_index=0, pipeline_config={...})
    recorder.record_planner(messages=planner.messages, iteration=0, plan=plan_dict)
    recorder.record_event("subtask_selected", iteration=0, agent="pipeline", data={...})
    recorder.record_executor(messages=executor.messages, iteration=0, findings=findings_dict)
    recorder.record_candidate_snapshot(iteration=0, candidates=[...])
    recorder.finalize(status="solved", iterations=3, stop=None)
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


def _now_ms() -> float:
    """Monotonic-ish timestamp in milliseconds (float)."""
    import time
    return time.time() * 1000.0


class TrajectoryRecorderEnhanced:
    """Records a single SearchHarness pipeline run as an enriched trajectory."""

    def __init__(
        self,
        model_id: str,
        output_dir: str = "logs/trajectories",
        task_index: int = 0,
    ):
        self.model_id = model_id
        self.output_dir = output_dir
        self.task_index = task_index

        # Core collected data
        self._metadata: Dict[str, Any] = {}
        self._planner_turns: List[Dict[str, Any]] = []
        self._executor_turns: List[Dict[str, Any]] = []
        self._pipeline_state: Dict[str, Any] = {}
        self._started: bool = False
        self._partial_write_enabled: bool = True

        # Enriched data
        self._events: List[Dict[str, Any]] = []
        self._candidate_snapshots: List[Dict[str, Any]] = []
        self._search_log: List[Dict[str, Any]] = []
        self._llm_calls: List[Dict[str, Any]] = []
        self._iteration_summaries: List[Dict[str, Any]] = []
        self._t_start: Optional[float] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(
        self,
        question: str,
        task_index: Optional[int] = None,
        pipeline_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Begin recording a new task."""
        if task_index is not None:
            self.task_index = task_index

        self._t_start = _now_ms()
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
            # Enriched counters (filled during run)
            "total_events": 0,
            "total_searches": 0,
            "total_crawls": 0,
            "total_llm_calls": 0,
            "total_candidates_ever": 0,
        }
        self._planner_turns.clear()
        self._executor_turns.clear()
        self._pipeline_state.clear()
        self._events.clear()
        self._candidate_snapshots.clear()
        self._search_log.clear()
        self._llm_calls.clear()
        self._iteration_summaries.clear()
        self._started = True
        self._record_event("trajectory_started", agent="recorder", iteration=0,
                          data={"question": question[:200]})
        self._write_partial_snapshot(status="running")

    # ------------------------------------------------------------------
    # Agent conversation recording (enriched with metadata)
    # ------------------------------------------------------------------

    def record_planner(
        self,
        messages: List[Dict[str, Any]],
        iteration: int,
        plan: Optional[Dict[str, Any]] = None,
        answer: Optional[str] = None,
        latency_ms: Optional[float] = None,
    ) -> None:
        """Record planner conversation for one iteration.

        Args:
            messages: planner's full message list (deep-copied)
            iteration: 0 for initial plan, 1+ for follow-up rounds
            plan: the parsed <planning> JSON block (if any)
            answer: the extracted <answer> (if planner produced a final answer)
            latency_ms: wall-clock time for this planner call
        """
        if not self._started:
            return
        tagged = self._tag_messages(messages, agent="planner", iteration=iteration)
        self._planner_turns.append({
            "iteration": iteration,
            "messages": tagged,
            "plan": deepcopy(plan) if plan else None,
            "answer": answer,
            "latency_ms": latency_ms,
            "message_count": len(tagged),
        })
        if plan:
            self._record_event(
                "plan_generated", agent="planner", iteration=iteration,
                data={
                    "phase": plan.get("phase"),
                    "workflow_stage": plan.get("workflow_stage"),
                    "stage_status": plan.get("stage_status"),
                    "num_steps": len(plan.get("steps") or []),
                    "subtask_types": [s.get("subtask_type", "?") for s in (plan.get("steps") or [])],
                },
            )
        if answer:
            self._record_event(
                "answer_produced", agent="planner", iteration=iteration,
                data={"answer": answer[:200]},
            )
        self._write_partial_snapshot(status="running")

    def record_executor(
        self,
        messages: List[Dict[str, Any]],
        iteration: int,
        findings: Optional[Dict[str, Any]] = None,
        subtask: Optional[Dict[str, Any]] = None,
        latency_ms: Optional[float] = None,
    ) -> None:
        """Record executor conversation for one iteration.

        Args:
            messages: executor's full message list (deep-copied)
            iteration: pipeline iteration index
            findings: parsed <findings> JSON block (if any)
            subtask: the subtask dict that was executed
            latency_ms: wall-clock time for this executor call
        """
        if not self._started:
            return
        tagged = self._tag_messages(messages, agent="executor", iteration=iteration)
        cu = (findings or {}).get("candidate_updates", {}) or {}
        new_cands = cu.get("new_candidates", []) or []
        self._executor_turns.append({
            "iteration": iteration,
            "messages": tagged,
            "findings": deepcopy(findings) if findings else None,
            "subtask": deepcopy(subtask) if subtask else None,
            "subtask_text": (subtask or {}).get("subtask") or (subtask or {}).get("name", ""),
            "subtask_type": (subtask or {}).get("subtask_type", ""),
            "status": (findings or {}).get("status", ""),
            "latency_ms": latency_ms,
            "message_count": len(tagged),
            "new_candidates": new_cands,
        })
        self._record_event(
            "executor_completed", agent="executor", iteration=iteration,
            data={
                "subtask": (subtask or {}).get("subtask", "")[:120],
                "status": (findings or {}).get("status", ""),
                "summary": ((findings or {}).get("summary", "") or "")[:200],
                "new_candidates": new_cands,
                "num_messages": len(tagged),
            },
        )
        self._write_partial_snapshot(status="running")

    # ------------------------------------------------------------------
    # Structured event stream
    # ------------------------------------------------------------------

    def record_event(
        self,
        event_type: str,
        iteration: int,
        agent: str = "pipeline",
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a structured event. Public API for the pipeline."""
        self._record_event(event_type, agent=agent, iteration=iteration, data=data)

    def _record_event(
        self,
        event_type: str,
        agent: str = "pipeline",
        iteration: int = 0,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self._started:
            return
        event = {
            "seq": len(self._events) + 1,
            "event_type": event_type,
            "agent": agent,
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
            "elapsed_ms": _now_ms() - (self._t_start or _now_ms()),
            "data": data or {},
        }
        self._events.append(event)
        self._metadata["total_events"] = len(self._events)

    # ------------------------------------------------------------------
    # Search log (structured record of every search query)
    # ------------------------------------------------------------------

    def record_search(
        self,
        iteration: int,
        agent: str,
        query: str,
        verdict: str = "allow",
        critic_reason: str = "",
        result_summary: str = "",
        result_count: int = 0,
        domains: Optional[List[str]] = None,
        latency_ms: Optional[float] = None,
    ) -> None:
        """Record a single search query and its outcome."""
        if not self._started:
            return
        entry = {
            "seq": len(self._search_log) + 1,
            "iteration": iteration,
            "agent": agent,
            "query": query,
            "verdict": verdict,
            "critic_reason": critic_reason[:200] if critic_reason else "",
            "result_summary": result_summary[:200] if result_summary else "",
            "result_count": result_count,
            "domains": (domains or [])[:5],
            "latency_ms": latency_ms,
        }
        self._search_log.append(entry)
        if verdict == "allow":
            self._metadata["total_searches"] = len([
                s for s in self._search_log if s["verdict"] == "allow"
            ])
        self._record_event(
            "search_query", agent=agent, iteration=iteration,
            data={
                "query": query[:120],
                "verdict": verdict,
                "result_count": result_count,
                "domains": (domains or [])[:3],
            },
        )

    # ------------------------------------------------------------------
    # LLM call metadata
    # ------------------------------------------------------------------

    def record_llm_call(
        self,
        iteration: int,
        agent: str,
        phase: str,
        latency_ms: float,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        reasoning_tokens: Optional[int] = None,
        content_chars: int = 0,
        reasoning_chars: int = 0,
        model_params: Optional[Dict[str, Any]] = None,
        has_tool_calls: bool = False,
    ) -> None:
        """Record metadata for a single LLM API call."""
        if not self._started:
            return
        entry = {
            "seq": len(self._llm_calls) + 1,
            "iteration": iteration,
            "agent": agent,
            "phase": phase,
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "reasoning_tokens": reasoning_tokens,
            "content_chars": content_chars,
            "reasoning_chars": reasoning_chars,
            "model_params": model_params or {},
            "has_tool_calls": has_tool_calls,
        }
        self._llm_calls.append(entry)
        self._metadata["total_llm_calls"] = len(self._llm_calls)

    # ------------------------------------------------------------------
    # Candidate pool evolution
    # ------------------------------------------------------------------

    def record_candidate_snapshot(
        self,
        iteration: int,
        candidates: List[Dict[str, Any]],
        active_candidate: Optional[str] = None,
    ) -> None:
        """Record a snapshot of the candidate pool at a point in time."""
        if not self._started:
            return
        snapshot = {
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
            "active_candidate": active_candidate,
            "total": len(candidates),
            "candidates": deepcopy(candidates),
        }
        self._candidate_snapshots.append(snapshot)
        # Track max candidate count
        if len(candidates) > self._metadata.get("total_candidates_ever", 0):
            self._metadata["total_candidates_ever"] = len(candidates)
        self._record_event(
            "candidate_snapshot", agent="pipeline", iteration=iteration,
            data={
                "total": len(candidates),
                "names": [c.get("name", "?") for c in candidates[:10]],
                "active": active_candidate,
            },
        )

    def record_candidate_change(
        self,
        iteration: int,
        name: str,
        change_type: str,
        confidence: Optional[float] = None,
        reason: str = "",
        constraints: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a single candidate add/verify/eliminate/confirm event.

        change_type: added | verified | eliminated | confirmed | confidence_updated
        """
        self._record_event(
            "candidate_change", agent="pipeline", iteration=iteration,
            data={
                "name": name,
                "change_type": change_type,
                "confidence": confidence,
                "reason": reason[:200],
                "constraints": constraints or {},
            },
        )

    # ------------------------------------------------------------------
    # Iteration summary
    # ------------------------------------------------------------------

    def record_iteration_summary(
        self,
        iteration: int,
        phase: str,
        subtask: Optional[str] = None,
        searches_this_iter: int = 0,
        crawls_this_iter: int = 0,
        new_candidates: Optional[List[str]] = None,
        eliminated_candidates: Optional[List[str]] = None,
        plan_phase: Optional[str] = None,
    ) -> None:
        """Record a summary of what happened in one pipeline iteration."""
        if not self._started:
            return
        self._iteration_summaries.append({
            "iteration": iteration,
            "phase": phase,
            "subtask": (subtask or "")[:120],
            "searches": searches_this_iter,
            "crawls": crawls_this_iter,
            "new_candidates": new_candidates or [],
            "eliminated_candidates": eliminated_candidates or [],
            "plan_phase": plan_phase,
        })

    # ------------------------------------------------------------------
    # Pipeline state
    # ------------------------------------------------------------------

    def record_pipeline_state(
        self,
        query_history: Optional[Dict[str, Any]] = None,
        snapshots: Optional[List[Dict[str, Any]]] = None,
        state_summary: Optional[Dict[str, Any]] = None,
        candidate_records: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record the pipeline state for analysis."""
        self._pipeline_state = {
            "query_history": query_history or {},
            "snapshots": snapshots or [],
            "state_summary": state_summary or {},
            "candidate_records": candidate_records or {},
        }
        if self._started:
            self._write_partial_snapshot(status="running")

    # ------------------------------------------------------------------
    # Finalize
    # ------------------------------------------------------------------

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
        self._metadata["total_elapsed_ms"] = _now_ms() - (self._t_start or _now_ms())

        self._record_event(
            "trajectory_finalized", agent="recorder", iteration=iterations,
            data={"status": status, "iterations": iterations},
        )

        trajectory = self._build_trajectory()

        output_path = self._output_path()
        self._write_json(output_path, trajectory)

        logger.info(f"[TrajectoryRecorder] Saved enriched trajectory to {output_path}")

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
        if self._metadata.get("finished_at"):
            trajectory = self._build_trajectory()
            output_path = self._output_path()
            self._write_json(output_path, trajectory)

    # ------------------------------------------------------------------
    # Build helpers
    # ------------------------------------------------------------------

    def _tag_messages(
        self,
        messages: List[Dict[str, Any]],
        agent: str,
        iteration: int,
    ) -> List[Dict[str, Any]]:
        """Deep-copy messages and add agent/iteration tags to each."""
        tagged = []
        for msg in messages:
            m = deepcopy(msg)
            # Don't override existing tags; add ours
            m.setdefault("_agent", agent)
            m.setdefault("_iteration", iteration)
            tagged.append(m)
        return tagged

    def _build_merged_messages(self) -> List[Dict[str, Any]]:
        """Merge planner and executor messages into a single conversation.

        Backward-compatible with the existing converter. Adds _agent and
        _iteration tags so downstream consumers can distinguish origins.
        """
        merged: List[Dict[str, Any]] = []

        planner_by_iter = {t["iteration"]: t["messages"] for t in self._planner_turns}
        executor_by_iter = {t["iteration"]: t["messages"] for t in self._executor_turns}

        all_iterations = sorted(
            set(planner_by_iter.keys()) | set(executor_by_iter.keys())
        )

        for i, iteration in enumerate(all_iterations):
            if iteration in planner_by_iter:
                if i > 0:
                    merged.append({
                        "role": "user",
                        "content": f"[Iteration {iteration} — Planning Phase]",
                        "_agent": "system_marker",
                        "_iteration": iteration,
                    })
                merged.extend(deepcopy(planner_by_iter[iteration]))

            if iteration in executor_by_iter:
                merged.append({
                    "role": "user",
                    "content": f"[Iteration {iteration} — Execution Phase]",
                    "_agent": "system_marker",
                    "_iteration": iteration,
                })
                merged.extend(deepcopy(executor_by_iter[iteration]))

        return merged

    def _derive_search_log_from_events(self) -> List[Dict[str, Any]]:
        """Derive search_log from search_query/search_executed events.

        Correlates critic verdicts (search_query) with execution results
        (search_executed) by matching query text within the same iteration.
        Used as a fallback when record_search() was never called directly.
        """
        if not self._events:
            return []
        # Collect verdicts per query (last verdict wins — a query may be
        # critiqued in candidate_generation and again in verification)
        verdicts: Dict[str, Dict[str, Any]] = {}
        executed: Dict[str, Dict[str, Any]] = {}
        for ev in self._events:
            if ev.get("event_type") not in ("search_query", "search_executed"):
                continue
            d = ev.get("data", {})
            q = (d.get("query") or "").strip()
            if not q:
                continue
            if ev["event_type"] == "search_query":
                verdicts[q] = {
                    "verdict": d.get("verdict", ""),
                    "critic_reason": d.get("critic_reason", ""),
                    "phase": d.get("phase", ""),
                    "subtask": d.get("subtask", ""),
                    "iteration": ev.get("iteration", 0),
                }
            else:  # search_executed
                executed[q] = {
                    "result_count": d.get("result_count", 0),
                    "domains": d.get("domains", []),
                    "latency_ms": d.get("latency_ms"),
                    "phase": d.get("phase", ""),
                    "subtask": d.get("subtask", ""),
                    "iteration": ev.get("iteration", 0),
                }
        # Build entries: every critiqued query, enriched with execution data
        all_queries = list(verdicts.keys())
        # Also include queries that were executed but somehow not critiqued
        for q in executed:
            if q not in verdicts:
                all_queries.append(q)
        log: List[Dict[str, Any]] = []
        for seq, q in enumerate(all_queries, 1):
            v = verdicts.get(q, {})
            ex = executed.get(q, {})
            log.append({
                "seq": seq,
                "iteration": v.get("iteration", ex.get("iteration", 0)),
                "agent": "executor",
                "query": q[:200],
                "verdict": v.get("verdict", "allow"),
                "critic_reason": (v.get("critic_reason") or "")[:200],
                "result_count": ex.get("result_count", 0),
                "domains": (ex.get("domains") or [])[:5],
                "latency_ms": ex.get("latency_ms"),
                "phase": v.get("phase") or ex.get("phase", ""),
                "subtask": (v.get("subtask") or ex.get("subtask") or "")[:200],
            })
        return log

    @staticmethod
    def _extract_reasoning_excerpt(
        assistant_msgs: List[Dict[str, Any]],
        *,
        max_chars: int = 2000,
    ) -> str:
        """Concatenate reasoning_content from assistant messages, truncated.

        P1-4A: This preserves the model's chain-of-thought in the llm_calls
        summary so distillation pipelines and log inspection can access the
        reasoning without scanning the full conversation messages. We join
        per-message reasoning with a separator and truncate to max_chars.
        """
        parts: List[str] = []
        for m in assistant_msgs:
            rc = m.get("reasoning_content")
            if rc:
                parts.append(str(rc))
        if not parts:
            return ""
        joined = "\n[...]\n".join(parts)
        if len(joined) <= max_chars:
            return joined
        # Keep the head; append an ellipsis marker so truncation is visible.
        return joined[:max_chars] + "...[truncated]"

    def _derive_llm_calls_from_conversations(self) -> List[Dict[str, Any]]:
        """Derive llm_calls from planner/executor conversations.

        Each planner/executor turn is one LLM call chain. We record one
        entry per turn with its latency and a count of assistant messages
        (which correspond to individual completions within the turn).
        """
        calls: List[Dict[str, Any]] = []
        seq = 0
        for t in self._planner_turns:
            seq += 1
            msgs = t.get("messages", [])
            assistant_msgs = [m for m in msgs if m.get("role") == "assistant"]
            content_chars = sum(len(m.get("content") or "") for m in assistant_msgs)
            reasoning_chars = sum(
                len(m.get("reasoning_content") or "") for m in assistant_msgs
            )
            # P1-4A: Save a reasoning excerpt (truncated) so distillation and
            # log inspection can see the model's chain-of-thought without
            # digging into the full conversation messages.
            reasoning_excerpt = self._extract_reasoning_excerpt(assistant_msgs)
            calls.append({
                "seq": seq,
                "iteration": t["iteration"],
                "agent": "planner",
                "phase": "planning",
                "latency_ms": t.get("latency_ms"),
                "assistant_messages": len(assistant_msgs),
                "content_chars": content_chars,
                "reasoning_chars": reasoning_chars,
                "reasoning_excerpt": reasoning_excerpt,
                "has_tool_calls": any(
                    m.get("tool_calls") for m in assistant_msgs
                ),
            })
        for t in self._executor_turns:
            seq += 1
            msgs = t.get("messages", [])
            assistant_msgs = [m for m in msgs if m.get("role") == "assistant"]
            content_chars = sum(len(m.get("content") or "") for m in assistant_msgs)
            reasoning_chars = sum(
                len(m.get("reasoning_content") or "") for m in assistant_msgs
            )
            reasoning_excerpt = self._extract_reasoning_excerpt(assistant_msgs)
            calls.append({
                "seq": seq,
                "iteration": t["iteration"],
                "agent": "executor",
                "phase": t.get("subtask_type", "execution"),
                "latency_ms": t.get("latency_ms"),
                "assistant_messages": len(assistant_msgs),
                "content_chars": content_chars,
                "reasoning_chars": reasoning_chars,
                "reasoning_excerpt": reasoning_excerpt,
                "has_tool_calls": any(
                    m.get("tool_calls") for m in assistant_msgs
                ),
            })
        return calls

    def _build_trajectory(self) -> Dict[str, Any]:
        """Build the full enriched trajectory payload."""
        # Derive search_log and llm_calls from events/conversations if the
        # dedicated record methods were never called (fallback path)
        search_log = self._search_log or self._derive_search_log_from_events()
        llm_calls = self._llm_calls or self._derive_llm_calls_from_conversations()
        # Keep metadata counters in sync with derived data
        self._metadata["total_searches"] = len([
            s for s in search_log if s.get("verdict") == "allow"
        ])
        # Count crawl events: visit_urls observations in pipeline_state or events
        _crawl_count = len([
            e for e in self._events
            if e.get("event_type") == "visit_urls_executed"
            or (e.get("event_type") == "tool_observation" and e.get("data", {}).get("tool_name") == "visit_urls")
        ])
        # Also count from pipeline_state candidate_records if events are empty
        if _crawl_count == 0 and self._pipeline_state:
            _ps = self._pipeline_state if isinstance(self._pipeline_state, dict) else {}
            _state_summary = _ps.get("state_summary") or {}
            _crawl_count = _state_summary.get("crawl_count", 0) if isinstance(_state_summary, dict) else 0
        self._metadata["total_crawls"] = _crawl_count
        self._metadata["total_llm_calls"] = len(llm_calls)
        return {
            "metadata": deepcopy(self._metadata),
            # Enriched structured data
            "events": deepcopy(self._events),
            "search_log": deepcopy(search_log),
            "llm_calls": deepcopy(llm_calls),
            "candidate_snapshots": deepcopy(self._candidate_snapshots),
            "iteration_summaries": deepcopy(self._iteration_summaries),
            # Per-agent conversations (training-friendly)
            "planner_conversations": [
                {
                    "iteration": t["iteration"],
                    "plan": t.get("plan"),
                    "answer": t.get("answer"),
                    "latency_ms": t.get("latency_ms"),
                    "message_count": t.get("message_count"),
                    "messages": deepcopy(t["messages"]),
                }
                for t in self._planner_turns
            ],
            "executor_conversations": [
                {
                    "iteration": t["iteration"],
                    "subtask": t.get("subtask"),
                    "subtask_text": t.get("subtask_text"),
                    "subtask_type": t.get("subtask_type"),
                    "findings": t.get("findings"),
                    "status": t.get("status"),
                    "latency_ms": t.get("latency_ms"),
                    "message_count": t.get("message_count"),
                    "new_candidates": t.get("new_candidates"),
                    "messages": deepcopy(t["messages"]),
                }
                for t in self._executor_turns
            ],
            # Pipeline state
            "pipeline_state": deepcopy(self._pipeline_state),
            # Backward-compatible merged messages
            "messages": self._build_merged_messages(),
        }

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
        return self._build_trajectory()

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
