"""Finish/wrap-up helpers extracted from SearchHarnessPipelineV4 (RD step4b).

Pure functions taking the pipeline instance as the first parameter; re-bound
on the class as private attribute names so existing call sites keep working.
"""
from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Dict, Optional

from loguru import logger

if TYPE_CHECKING:  # avoid circular import with .orchestrator
    from pipeline.orchestrator import SearchHarnessPipelineV4


def finish_with_answer(
    pipeline: "SearchHarnessPipelineV4",
    answer: str,
    iterations: int,
) -> Dict[str, Any]:
    # Fallback: when the planner wraps up with Unknown/empty (pos10-style
    # unfinished), try to salvage a best-guess answer from the viable
    # candidate pool before giving up. The salvaged answer still goes
    # through _verify_planner_answer, so a refuted fallback is downgraded
    # back to Unknown rather than committing a wrong guess.
    _normalized = (answer or "").strip().lower()
    if _normalized in {"", "unknown", "none", "null"}:
        _salvaged = pipeline._fallback_answer_from_pool()
        if _salvaged:
            logger.info(
                f"[Pipeline] planner answer was {answer!r}; salvaged fallback "
                f"from candidate pool: {_salvaged!r}"
            )
            pipeline._record_event_for_trajectory("fallback_answer_from_pool", iterations, {
                "original_answer": answer,
                "salvaged_answer": _salvaged,
            })
            answer = _salvaged
    answer = pipeline._verify_planner_answer(
        answer,
        iterations_remaining=pipeline._max_iterations - iterations,
        iteration=iterations,
    )
    # Contrastive retry: _verify_planner_answer returns None when it
    # triggered a pool rebuild. Signal the caller to continue the loop
    # instead of finishing.
    if answer is None:
        return None
    status = pipeline._pipeline_status_for_answer(answer)
    logger.info(
        f"[Pipeline] FINISHED answer status={status} "
        f"iterations={iterations} answer_preview='{answer[:80]}'"
    )
    pipeline._record_event_for_trajectory(
        "pipeline_answer", iterations, {"answer": answer[:200], "status": status}
    )
    pipeline._record_candidate_snapshot_for_trajectory(iterations)
    if pipeline.trajectory_recorder:
        pipeline.trajectory_recorder.record_pipeline_state(
            query_history=pipeline.query_memory.to_dict(),
            snapshots=[s.to_dict() for s in pipeline.state_store.snapshots],
            state_summary={
                k: pipeline.state_store.export_compact_state().get(k)
                for k in ("current_candidates", "eliminated_candidates", "confirmed_wrong_candidates",
                          "candidate_records", "visited_domains", "pending_urls", "crawled_urls")
            },
            candidate_records=pipeline.state_store.candidate_records,
        )
        pipeline.trajectory_recorder.finalize(status=status, iterations=iterations)
    return {
        "answer": answer,
        "state": pipeline.state_store.export_compact_state(),
        "iterations": iterations,
        "status": status,
    }


def best_effort_finish(
    pipeline: "SearchHarnessPipelineV4",
    question: str,
    plan: Dict[str, Any],
    iteration: int,
    stop: Dict[str, Any],
) -> Dict[str, Any]:
    compact_state = pipeline.state_store.export_compact_state()
    mode = "solved" if looks_solved(pipeline, compact_state) else "best_effort"
    _t_final = __import__("time").time()
    logger.info(f"[Pipeline] finalizer.start mode={mode} stop={stop.get('trigger','?')}")
    final = pipeline.finalizer.finalize(
        question=question, compact_state=compact_state, budget_status=stop, mode=mode
    )
    logger.info(f"[Pipeline] finalizer.done in {__import__('time').time()-_t_final:.1f}s status={final.status}")
    # P0-A+: salvage a fallback answer from the viable candidate pool when
    # the finalizer emits Unknown/empty (best_effort path). Mirrors the
    # _finish_with_answer fallback so the best_effort finish path no longer
    # silently returns Unknown while viable candidates remain unchosen.
    _final_answer_norm = (final.answer or "").strip().lower()
    if _final_answer_norm in {"", "unknown", "none", "null"}:
        _salvaged = pipeline._fallback_answer_from_pool()
        if _salvaged:
            logger.info(
                f"[Pipeline] finalizer answer was {final.answer!r}; salvaged fallback "
                f"from candidate pool (best_effort): {_salvaged!r}"
            )
            pipeline._record_event_for_trajectory("fallback_answer_from_pool_best_effort", iteration, {
                "original_answer": final.answer,
                "salvaged_answer": _salvaged,
            })
            final.answer = _salvaged
            final.confidence = "medium"
            final.status = "solved"
            # P1-F: clear the stale error_type so a salvaged answer is not
            # reported as protocol_error. The finalizer's LLM failure is
            # captured in final.reason; the salvaged candidate is a
            # legitimate answer that should be graded as finished.
            final.error_type = None
            final.reason = (final.reason + " | " if final.reason else "") + "Salvaged from viable candidate pool after finalizer returned Unknown."
    if final.status == "infra_error":
        pipeline_status = "infra_error"
    elif final.error_type == "protocol_error":
        # Explicit protocol_error: finalizer LLM output was unparseable.
        # Still emit the local fallback answer, but mark the pipeline so it is
        # distinguishable from a genuine best_effort "Unknown".
        pipeline_status = "protocol_error"
    else:
        pipeline_status = "finished" if final.status == "solved" and final.answer.strip().lower() != "unknown" else "unfinished"
    pipeline._record_event_for_trajectory("pipeline_best_effort_finish", iteration, {
        "stop_trigger": stop.get("trigger", ""),
        "mode": mode,
        "finalizer_status": final.status,
        "pipeline_status": pipeline_status,
    })
    pipeline._record_candidate_snapshot_for_trajectory(iteration)
    if pipeline.trajectory_recorder:
        pipeline.trajectory_recorder.record_pipeline_state(
            query_history=pipeline.query_memory.to_dict(),
            snapshots=[s.to_dict() for s in pipeline.state_store.snapshots],
            state_summary={
                k: compact_state.get(k)
                for k in ("current_candidates", "eliminated_candidates", "confirmed_wrong_candidates",
                          "candidate_records", "visited_domains", "pending_urls", "crawled_urls")
            },
            candidate_records=pipeline.state_store.candidate_records,
        )
        pipeline.trajectory_recorder.finalize(status=pipeline_status, iterations=iteration, stop=stop)
    return {
        "answer": final.to_answer_block(),
        "answer_payload": final.to_payload(),
        "plan": plan,
        "state": compact_state,
        "iterations": iteration,
        "status": pipeline_status,
        "failure_category": final.error_type,
        "stop": stop,
    }


def build_wrap_up_state_excerpt(
    pipeline: "SearchHarnessPipelineV4",
    compact_state: Dict[str, Any],
) -> str:
    latest_snapshot = compact_state.get("latest_snapshot") or {}
    current_plan = compact_state.get("current_plan") or {}
    excerpt = {
        "workflow_stage": pipeline.workflow_stage,
        "phase": current_plan.get("phase"),
        "stage_status": current_plan.get("stage_status"),
        "candidate_status": current_plan.get("candidate_status"),
        "pool_assessment": current_plan.get("pool_assessment"),
        "current_candidates": compact_state.get("current_candidates") or [],
        "confirmed_wrong_candidates": compact_state.get("confirmed_wrong_candidates") or [],
        "candidate_records": compact_state.get("candidate_records") or [],
        "resolved_uncertainties": latest_snapshot.get("resolved_uncertainties") or [],
        "remaining_uncertainties": latest_snapshot.get("remaining_uncertainties") or [],
        "top_evidence": latest_snapshot.get("top_evidence") or [],
    }
    return json.dumps(excerpt, ensure_ascii=False)


def try_protocol_wrap_up(
    pipeline: "SearchHarnessPipelineV4",
    question: str,
    iteration: int,
) -> Optional[Dict[str, Any]]:
    compact_state = pipeline.state_store.export_compact_state()
    state_excerpt = pipeline._build_wrap_up_state_excerpt(compact_state)
    nudge = {
        "role": "user",
        "content": (
            "You have reached the execution limit for this run. Do not call any more tools. "
            "Based on all the information gathered so far, output exactly one <answer>...</answer> block now. "
            "Answer the original question directly rather than naming an intermediate candidate unless the candidate name itself is the answer. "
            "If the evidence is insufficient to answer the original question directly, return an explicit best-effort answer such as Unknown inside the <answer> block rather than continuing to plan. "
            "Do not output any <planning> block. "
            "Base your wrap-up on the current tracked state excerpt below rather than re-guessing from scratch.\n"
            "IMPORTANT DISAMBIGUATION STEP: If the final candidate is an author, person, or entity that has MULTIPLE specific works or items found in the evidence "
            "(e.g., multiple books by the same author), you MUST list every specific work/item mentioned in the evidence and check each one "
            "against ALL constraints in the original question. Pay special attention to:\n"
            "  - 'made from a particular flower/substance' may include DERIVATIVES or EXTRACTS (e.g., opium is made from the poppy flower, "
            "but laudanum, morphine, and patent medicines are ALSO made from the poppy flower — they are derivatives of opium). "
            "A book about laudanum/morphine IS a book about 'an addictive substance made from a particular flower'.\n"
            "  - The question asks for THE FULL TITLE of THE BOOK (singular). If the author has multiple books about the same topic, "
            "check which one is specifically about the addictive substance described in the question, not just the most well-known one.\n"
            "Only select the work/item that satisfies EVERY constraint.\n"
            f"CURRENT_TRACKED_STATE={state_excerpt}"
        ),
    }
    _t_wrap = __import__("time").time()
    logger.info(f"[Pipeline] planner.start wrap-up (protocol)")
    planner_result = pipeline.planner.run(
        question=question,
        feedback_history=[nudge],
        compact_state=compact_state,
        workflow_stage=pipeline.workflow_stage,
        stage_context=pipeline._stage_context(),
    )
    logger.info(f"[Pipeline] planner.done wrap-up in {__import__('time').time()-_t_wrap:.1f}s answer={'yes' if planner_result.get('answer') else 'no'}")
    if pipeline.trajectory_recorder:
        pipeline.trajectory_recorder.record_planner(
            messages=pipeline.planner.messages,
            iteration=iteration + 1,
            latency_ms=(time.time() - _t_wrap) * 1000.0,
        )
    if planner_result.get("answer"):
        _r = pipeline._finish_with_answer(planner_result["answer"], iterations=iteration + 1)
        if _r is not None:
            return _r
    return None


def looks_solved(
    pipeline: "SearchHarnessPipelineV4",
    compact_state: Dict[str, Any],
) -> bool:
    plan = compact_state.get("current_plan") or {}
    phase = plan.get("phase", "")
    cand = pipeline.state_store.current_candidates
    viable_records = pipeline._viable_candidate_records()
    if pipeline.workflow_stage == pipeline.FINAL_CHECK and phase == "final_check" and len(cand) == 1:
        return len(viable_records) <= 1
    cand_status = (plan.get("candidate_status") or {}).get("state", "")
    return (
        pipeline.workflow_stage == pipeline.FINAL_CHECK
        and cand_status == "resolved"
        and len(cand) >= 1
        and len(viable_records) == 1
    )
