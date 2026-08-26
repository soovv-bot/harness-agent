"""Subtask scheduling and concurrent execution helpers.

Pure functions extracted from ``SearchHarnessPipelineV4`` (RD §5.2 step4b).
Each takes the pipeline as its first parameter; the class rebinds the private
methods to these helpers so existing behaviour and private API names are
preserved.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger

from critics.query_critic import QueryCritic
from agents.search_agent_v3 import SearchAgentV3
from memory.search_crawl_controller import SearchCrawlController

if TYPE_CHECKING:
    from pipeline.orchestrator import SearchHarnessPipelineV4


def settle_subtask_with_critic(pipeline: "SearchHarnessPipelineV4", question: str, plan: Dict[str, Any], subtask: Optional[Dict[str, Any]], iteration: int, max_rewrites: int = 2, ) -> Dict[str, Any]:
    rewrites = 0
    current_plan = plan
    current_subtask = subtask

    while current_subtask:
        _t_critic = __import__("time").time()
        verdict = pipeline.subtask_critic.evaluate(
            subtask_name=current_subtask.get("subtask") or current_subtask.get("name", ""),
            subtask_guidance=subtask_guidance_for_critic(pipeline, current_subtask),
            overall_plan=current_plan,
        )
        logger.info(f"[SubtaskCritic] verdict={verdict.decision} in {__import__('time').time()-_t_critic:.1f}s | reason={verdict.reason[:120]}")
        if verdict.is_allowed:
            return {"plan": current_plan, "subtask": current_subtask}

        pipeline.subtask_critic.record(
            name=current_subtask.get("subtask") or current_subtask.get("name", ""),
            status="rejected",
            summary=f"Rejected by critic: {verdict.reason}",
        )
        if rewrites >= max_rewrites:
            logger.warning("[SubtaskCritic] rewrite limit reached; executing latest proposed subtask with warning")
            return {"plan": current_plan, "subtask": current_subtask}

        rewrites += 1
        feedback_messages = [{
            "role": "user",
            "content": (
                f"Your proposed subtask \"{current_subtask.get('subtask') or current_subtask.get('name')}\" was rejected by the subtask critic.\n"
                f"Reason: {verdict.reason}\n\n"
                "Revise the current plan now, but keep this as the same pipeline iteration. "
                "Output a substantially different executable subtask. Consider:\n"
                "- Breaking the problem into a simpler, more concrete subtask\n"
                "- Approaching from a different source family\n"
                "- Relaxing one constraint to broaden the search space before re-narrowing\n"
                "- Switching between candidate_expansion and candidate_verification if the current pool state justifies it"
            ),
        }]
        _t_rewrite = __import__("time").time()
        logger.info(f"[Pipeline] planner.start rewrite #{rewrites} (critic rejected subtask)")
        planner_result = pipeline.planner.run(
            question=question,
            feedback_history=feedback_messages,
            compact_state=pipeline.state_store.export_compact_state(),
            workflow_stage=pipeline.workflow_stage,
            stage_context=pipeline._stage_context(),
        )
        logger.info(f"[Pipeline] planner.done rewrite #{rewrites} in {__import__('time').time()-_t_rewrite:.1f}s")
        if pipeline.trajectory_recorder:
            pipeline.trajectory_recorder.record_planner(messages=pipeline.planner.messages, iteration=iteration + 1, latency_ms=(time.time() - _t_rewrite) * 1000.0)
        if planner_result.get("answer"):
            return {"answer": planner_result["answer"]}

        current_plan = pipeline._prepare_plan_for_stage(planner_result.get("plan") or current_plan)
        pipeline._plan_history.append(current_plan)
        phase_changed = pipeline.state_store.add_plan(current_plan)
        if phase_changed:
            pipeline.state_store.create_snapshot()
        current_plan = pipeline._maybe_advance_stage(question, current_plan, iteration=iteration + 1)
        solved = pipeline._consume_stage_answer(iterations=iteration + 1)
        if solved:
            return {"answer": solved.get("answer", "")}
        current_subtask = next_subtask_from_plan(pipeline, current_plan)
        if not current_subtask:
            recovered = recover_missing_subtask(pipeline, question, current_plan, iteration)
            if recovered:
                if recovered.get("answer"):
                    return {"answer": recovered["answer"]}
                current_plan = recovered.get("plan") or current_plan
                current_subtask = next_subtask_from_plan(pipeline, current_plan)

    return {"plan": current_plan, "subtask": None}


def recover_missing_subtask(pipeline: "SearchHarnessPipelineV4", question: str, plan: Dict[str, Any], iteration: int) -> Optional[Dict[str, Any]]:
    recovery_feedback = [{
        "role": "user",
        "content": (
            f"Your current workflow stage is {pipeline.workflow_stage}, but the latest plan has no executable pending step. "
            "Output exactly one <planning>...</planning> block with at least one concrete pending step for this stage, "
            "or output exactly one <answer>...</answer> block if the original question is already sufficiently solved. "
            "Do not leave the plan with zero actionable steps."
        ),
    }]
    # P1-A concurrent path: if the pool health check fired during the
    # concurrent executor path and invalidated the plan, include that
    # feedback here so the planner knows to search for the correct
    # entity type (e.g., "person" instead of "institution").
    _pending_phf = getattr(pipeline, "_pending_pool_health_feedback", None)
    if _pending_phf:
        recovery_feedback.insert(0, _pending_phf)
        pipeline._pending_pool_health_feedback = None
    _t_rec = __import__("time").time()
    logger.info("[Pipeline] planner.start recovery (no subtask)")
    planner_result = pipeline.planner.run(
        question=question,
        feedback_history=recovery_feedback,
        compact_state=pipeline.state_store.export_compact_state(),
        workflow_stage=pipeline.workflow_stage,
        stage_context=pipeline._stage_context(),
    )
    logger.info(f"[Pipeline] planner.done recovery in {__import__('time').time()-_t_rec:.1f}s answer={'yes' if planner_result.get('answer') else 'no'}")
    if pipeline.trajectory_recorder:
        pipeline.trajectory_recorder.record_planner(messages=pipeline.planner.messages, iteration=iteration + 1, latency_ms=(time.time() - _t_rec) * 1000.0)
    if planner_result.get("answer"):
        # pos6 fix: gate recovery-path answers through the same top-2
        # verification short-circuit gate as the main loop. Without this,
        # a recovery planner that immediately commits an answer (observed:
        # "Opium" committed at iter 3 while 13 siblings remain unverified)
        # bypasses the top-2 gate and the tie-gate entirely.
        if pipeline.workflow_stage == pipeline.CANDIDATE_VERIFICATION:
            blocked_answer = pipeline._gate_verification_short_circuit(
                planner_result["answer"], iteration + 1
            )
            if blocked_answer is not None:
                pipeline._stage_answer = None
                logger.info(
                    f"[Pipeline] recovery answer blocked by top-2 gate — "
                    f"injecting verification subtask for next candidate "
                    f"in queue"
                )
                # Inject a verification subtask for the next unverified
                # candidate so the main loop has something to execute
                # instead of re-entering recovery infinitely.
                next_cand = pipeline.active_candidate or ""
                if not next_cand and pipeline.verification_queue:
                    next_cand = pipeline.verification_queue[0]
                if next_cand:
                    injected_plan = {
                        "phase": "candidate_verification",
                        "stage_status": "continue",
                        "steps": [{
                            "id": 1,
                            "subtask": f"Verify whether '{next_cand}' satisfies ALL constraints in the question. Search for evidence and use update_candidate to set verification_status to verified or contradicted.",
                            "subtask_type": "candidate_verification",
                            "status": "pending",
                        }],
                    }
                    recovered_plan = pipeline._prepare_plan_for_stage(injected_plan)
                    pipeline._plan_history.append(recovered_plan)
                    phase_changed = pipeline.state_store.add_plan(recovered_plan)
                    if phase_changed:
                        pipeline.state_store.create_snapshot()
                    return {"plan": pipeline._maybe_advance_stage(question, recovered_plan, iteration=iteration + 1)}
                # Fall through to plan recovery if no next candidate
            else:
                _r = pipeline._finish_with_answer(planner_result["answer"], iterations=iteration + 1)
                if _r is not None:
                    return _r
        else:
            _r = pipeline._finish_with_answer(planner_result["answer"], iterations=iteration + 1)
            if _r is not None:
                return _r
    recovered_plan = pipeline._prepare_plan_for_stage(planner_result.get("plan") or {})
    if not recovered_plan:
        return None
    pipeline._plan_history.append(recovered_plan)
    phase_changed = pipeline.state_store.add_plan(recovered_plan)
    if phase_changed:
        pipeline.state_store.create_snapshot()
    return {"plan": pipeline._maybe_advance_stage(question, recovered_plan, iteration=iteration + 1)}


def is_progress(pipeline: "SearchHarnessPipelineV4", findings: Dict[str, Any]) -> bool:
    evidence = findings.get("evidence") or []
    updates = findings.get("candidate_updates") or {}
    new_candidates = updates.get("new_candidates", []) or []
    source_feedback = findings.get("source_feedback") or {}
    # Reasoning models may emit source_feedback as a string; coerce to dict for safe access.
    if not isinstance(source_feedback, dict):
        source_feedback = {}
    promising = source_feedback.get("promising_sources", []) or []
    summary = (findings.get("summary") or "").strip()
    if new_candidates or promising:
        return True
    if evidence:
        return True
    if summary and len(summary) > 40 and "no useful" not in summary.lower():
        return True
    return False


def subtask_from_step(pipeline: "SearchHarnessPipelineV4", step: Dict[str, Any], plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    status = step.get("status")
    if status not in (None, "pending", "in_progress"):
        return None
    subtask = {
        "subtask": step.get("subtask") or step.get("name", "unnamed step"),
    }
    subtask_type = step.get("subtask_type") or step.get("type") or step.get("mode")
    if not subtask_type:
        phase = str(plan.get("phase") or "").lower()
        if phase in {"candidate_generation", "source_identification"}:
            subtask_type = "candidate_expansion"
        elif phase in {"candidate_narrowing", "verification"}:
            subtask_type = "candidate_verification"
    if subtask_type:
        subtask["subtask_type"] = subtask_type
    guidance_items: List[str] = []
    step_guidance = step.get("guidance") or step.get("executor_guidance")
    if isinstance(step_guidance, list):
        guidance_items.extend(str(item) for item in step_guidance if item)
    elif step_guidance:
        guidance_items.append(str(step_guidance))
    if guidance_items:
        subtask["guidance"] = guidance_items
    source_recommendations = plan_source_recommendations(pipeline, plan)
    if source_recommendations:
        subtask["source_recommendations"] = source_recommendations
    return subtask


def next_subtask_from_plan(pipeline: "SearchHarnessPipelineV4", plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for step in plan.get("steps", []) or []:
        st = subtask_from_step(pipeline, step, plan)
        if st:
            return st
    return None


def next_subtasks_batch(pipeline: "SearchHarnessPipelineV4", plan: Dict[str, Any], k: int) -> List[Dict[str, Any]]:
    """Return up to k pending subtasks from the plan (concurrent execution)."""
    out: List[Dict[str, Any]] = []
    for step in plan.get("steps", []) or []:
        st = subtask_from_step(pipeline, step, plan)
        if st:
            out.append(st)
            if len(out) >= k:
                break
    return out


def decide_concurrency(pipeline: "SearchHarnessPipelineV4", question: str, plan: Dict[str, Any]) -> int:
    """Decide how many subtasks to run in parallel this iteration.

    Default 2; bump to 3 for complex questions (long question or >=4
    pending steps). Capped by EXECUTOR_MAX_SUBTASK_CONCURRENCY and by
    the number of pending steps. Returns 1 for the serial zero-regression
    path (env EXECUTOR_SUBTASK_CONCURRENCY=1 or only one pending step).
    """
    k = pipeline._subtask_concurrency
    if k <= 1:
        return 1
    steps = plan.get("steps", []) or []
    pending = [s for s in steps if s.get("status") in (None, "pending", "in_progress")]
    n_pending = len(pending)
    if n_pending <= 1:
        return 1
    long_question = len(question) > 200
    many_steps = n_pending >= 4
    if long_question or many_steps:
        k = min(pipeline._max_subtask_concurrency, k + 1)
    k = max(1, min(k, pipeline._max_subtask_concurrency, n_pending))
    return k


def build_executor_pool(pipeline: "SearchHarnessPipelineV4", k: int) -> List["SearchAgentV3"]:
    """Create k independent executor instances for concurrent subtasks.

    Each gets its own query_critic/crawl_controller (isolated caches and
    _current_question), but shares state_store + query_memory (both
    lock-protected) and the OpenAI client (connection pool reuse).
    """
    shared_client = getattr(pipeline.executor, "client", None)
    pool: List["SearchAgentV3"] = []
    _rec = pipeline.trajectory_recorder
    _current_iter = pipeline._trajectory_current_iter
    for i in range(k):
        qc = QueryCritic(pipeline.query_memory, api_base=pipeline._api_base, api_key=pipeline._api_key, model_id=pipeline._model_id)
        cc = SearchCrawlController(pipeline.query_memory, api_base=pipeline._api_base, api_key=pipeline._api_key, model_id=pipeline._model_id)
        exec_ = SearchAgentV3(
            api_base=pipeline._api_base, api_key=pipeline._api_key, model_id=pipeline._executor_model_id,
            state_store=pipeline.state_store, query_memory=pipeline.query_memory,
            query_critic=qc, crawl_controller=cc,
            search_budget=pipeline.executor.search_budget,
            enable_query_critic=pipeline.enable_query_critic,
            reasoning_effort=pipeline._executor_reasoning_effort,
            openai_client=shared_client,
            temperature=pipeline.executor.temperature,
        )
        if _rec is not None and _current_iter is not None:
            _idx = i
            exec_._event_callback = lambda et, data, _i=_idx: _rec.record_event(et, iteration=_current_iter[0], agent=f"executor#{_i}", data=data)
        pool.append(exec_)
    return pool


def run_subtasks_concurrent(pipeline: "SearchHarnessPipelineV4", question: str, plan: Dict[str, Any], subtasks: List[Dict[str, Any]], iteration: int, ) -> List[Dict[str, Any]]:
    """Run N subtasks in parallel with independent executor instances.

    Returns the list of executor results (one per subtask, in input order).
    If any subtask triggers a fact_confirmed/authority_consensus early stop,
    a threading.Event signals the others to wind down promptly.
    """
    k = len(subtasks)
    pool = pipeline._build_executor_pool(k)
    stop_event = threading.Event()
    results: List[Optional[Dict[str, Any]]] = [None] * k
    def run_one(i: int, exec_: "SearchAgentV3", st: Dict[str, Any]) -> None:
        try:
            state = pipeline.state_store.export_executor_state()
            res = exec_.run(question=question, overall_plan=plan, subtask=st, executor_state=state, stop_event=stop_event)
            results[i] = res
            if getattr(exec_, "_authority_consensus_done", False):
                stop_event.set()
        except Exception as e:  # noqa: BLE001
            logger.error(f"[Pipeline] concurrent executor#{i} failed: {e}")
            results[i] = {"metadata": {"status": "error", "error": str(e)}, "findings": {}, "messages": []}
    with ThreadPoolExecutor(max_workers=k) as ex:
        futs = [ex.submit(run_one, i, e, s) for i, (e, s) in enumerate(zip(pool, subtasks))]
        for f in as_completed(futs):
            f.result()
    return [r for r in results if r is not None]


def plan_source_recommendations(pipeline: "SearchHarnessPipelineV4", plan: Dict[str, Any]) -> List[str]:
    raw = plan.get("source_recommendations")
    if raw is None:
        raw = plan.get("source_hypotheses")
    recommendations: List[str] = []
    for item in raw or []:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(item.get("source_family") or item.get("source_type") or item.get("site") or "").strip()
        else:
            text = str(item).strip()
        if text:
            recommendations.append(text)
    return recommendations


def subtask_guidance_for_critic(pipeline: "SearchHarnessPipelineV4", subtask: Dict[str, Any]) -> List[str]:
    guidance: List[str] = []
    subtask_type = subtask.get("subtask_type")
    if subtask_type:
        guidance.append(f"subtask_type={subtask_type}")
    raw_guidance = subtask.get("guidance")
    if isinstance(raw_guidance, list):
        guidance.extend(str(item) for item in raw_guidance if item)
    elif raw_guidance:
        guidance.append(str(raw_guidance))
    return guidance


def should_snapshot(pipeline: "SearchHarnessPipelineV4", plan: Dict[str, Any]) -> bool:
    phase = plan.get("phase", "unknown")
    return phase in {"candidate_generation", "candidate_narrowing", "verification", "final_check"}


def fallback_findings(pipeline: "SearchHarnessPipelineV4", subtask: Dict[str, Any], executor_result: Dict[str, Any]) -> Dict[str, Any]:
    metadata = executor_result.get("metadata", {})
    return {
        "subtask": subtask.get("subtask") or subtask.get("name", "unknown"),
        "status": metadata.get("status", "unknown"),
        "summary": "Executor stopped without structured findings.",
        "evidence": [],
        "candidate_updates": {"new_candidates": [], "eliminated_candidates": [], "notes": "No structured findings produced."},
        "source_feedback": {"promising_sources": [], "unhelpful_sources": []},
        "suggestion_for_planner": "Revise the plan and tighten the current subtask.",
    }

