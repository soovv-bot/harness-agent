"""Stage 状态机 helper (RD step4b).

管理 candidate_generation → candidate_verification → final_check 三阶段
推进、stage_context、阶段切换时的 plan 整形及 top-2 verification gate。
纯函数 `(pipeline, ...)` 首参；orchestrator 类属性重绑定保留私有名可达。
"""
from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger

if TYPE_CHECKING:  # avoid circular import with .orchestrator
    from pipeline.orchestrator import SearchHarnessPipelineV4


def stage_context(pipeline: "SearchHarnessPipelineV4") -> Dict[str, Any]:
    return {
        "workflow_stage": pipeline.workflow_stage,
        "generation_round": pipeline.stage_round_counts.get(pipeline.CANDIDATE_GENERATION, 0) + 1,
        "generation_budget": pipeline.max_candidate_generation_rounds,
        "current_candidate_count": len(pipeline.state_store.current_candidates),
        "viable_candidate_count": len(pipeline._viable_candidate_records()),
        "active_candidate": pipeline.active_candidate,
        "candidate_verification_round": pipeline.active_candidate_rounds + 1 if pipeline.active_candidate else 0,
        "verification_queue_remaining": len(pipeline.verification_queue),
        "completed_verification_candidates": pipeline.completed_verification_candidates[-10:],
    }


def workflow_stage_from_plan(
    pipeline: "SearchHarnessPipelineV4", plan: Dict[str, Any]
) -> Optional[str]:
    phase = str(plan.get("phase") or "").strip().lower()
    if phase in {"source_identification", pipeline.CANDIDATE_GENERATION}:
        return pipeline.CANDIDATE_GENERATION
    if phase in {"candidate_narrowing", "verification", pipeline.CANDIDATE_VERIFICATION}:
        return pipeline.CANDIDATE_VERIFICATION
    if phase == pipeline.FINAL_CHECK:
        return pipeline.FINAL_CHECK

    for step in plan.get("steps", []) or []:
        if not isinstance(step, dict):
            continue
        if step.get("status") not in (None, "pending", "in_progress"):
            continue
        subtask_type = str(step.get("subtask_type") or step.get("type") or "").strip().lower()
        if subtask_type == "candidate_expansion":
            return pipeline.CANDIDATE_GENERATION
        if subtask_type == "candidate_verification":
            return pipeline.CANDIDATE_VERIFICATION
        if subtask_type == "final_check":
            return pipeline.FINAL_CHECK
    return None


def sync_workflow_stage_from_plan(pipeline: "SearchHarnessPipelineV4", plan: Dict[str, Any]) -> None:
    target_stage = workflow_stage_from_plan(pipeline, plan)
    if not target_stage or target_stage == pipeline.workflow_stage:
        return

    # pos6 fix: enforce monotonic stage progression. The planner must not
    # skip candidate_verification and jump straight from candidate_generation
    # to final_check — that bypasses the top-2 verification gate in
    # _should_advance_stage and lets a weak "partial" candidate be selected
    # over an unverified-but-stronger sibling (pos6 root cause). If the
    # planner tries to jump, force it into verification first.
    stage_order = {
        pipeline.CANDIDATE_GENERATION: 0,
        pipeline.CANDIDATE_VERIFICATION: 1,
        pipeline.FINAL_CHECK: 2,
    }
    current_rank = stage_order.get(pipeline.workflow_stage, 0)
    target_rank = stage_order.get(target_stage, 0)
    if target_rank > current_rank + 1:
        logger.info(
            f"[Pipeline] stage-jump guard: planner tried to jump "
            f"{pipeline.workflow_stage} -> {target_stage}; forcing "
            f"{pipeline.CANDIDATE_VERIFICATION} first"
        )
        target_stage = pipeline.CANDIDATE_VERIFICATION
    # pos6 fix: do NOT let the planner skip verification by jumping
    # from candidate_verification to final_check before ANY verification
    # subtask has run. Without this, a transition planner that immediately
    # emits phase=final_check (observed: planner_conv 3 after the
    # generation->verification force-advance) bypasses the top-2 gate in
    # _should_advance_stage and lets a single verified-but-weak candidate
    # (e.g. "Opium") win over 48 unverified siblings (e.g. "In the Arms of
    # Morpheus"). Require at least one completed verification pass.
    if (
        pipeline.workflow_stage == pipeline.CANDIDATE_VERIFICATION
        and target_stage == pipeline.FINAL_CHECK
        and not pipeline.completed_verification_candidates
        and pipeline.active_candidate_rounds == 0
    ):
        logger.info(
            f"[Pipeline] stage-jump guard: planner tried to advance "
            f"candidate_verification -> final_check before ANY "
            f"verification subtask ran (completed=[], "
            f"active_rounds=0) — forcing back to "
            f"{pipeline.CANDIDATE_VERIFICATION}"
        )
        target_stage = pipeline.CANDIDATE_VERIFICATION

    previous_stage = pipeline.workflow_stage
    pipeline.workflow_stage = target_stage
    if target_stage == pipeline.CANDIDATE_VERIFICATION:
        if previous_stage != pipeline.CANDIDATE_VERIFICATION or not (pipeline.active_candidate or pipeline.verification_queue):
            pipeline._initialize_verification_queue()
    elif target_stage == pipeline.CANDIDATE_GENERATION:
        pipeline.active_candidate = None
        pipeline.active_candidate_rounds = 0
        pipeline.verification_queue = []


def prepare_plan_for_stage(
    pipeline: "SearchHarnessPipelineV4", plan: Dict[str, Any]
) -> Dict[str, Any]:
    if not plan:
        return plan
    prepared = dict(plan)
    sync_workflow_stage_from_plan(pipeline, prepared)
    prepared["workflow_stage"] = pipeline.workflow_stage
    prepared.setdefault("stage_status", "continue")
    if pipeline.workflow_stage == pipeline.CANDIDATE_GENERATION:
        if not prepared.get("phase"):
            prepared["phase"] = pipeline.CANDIDATE_GENERATION
        prepared.setdefault("pool_assessment", {
            "coverage_status": "partial",
            "gaps": [],
        })
    elif pipeline.workflow_stage == pipeline.CANDIDATE_VERIFICATION:
        if not prepared.get("phase"):
            prepared["phase"] = "verification"
        if pipeline.active_candidate:
            prepared["active_candidate"] = pipeline.active_candidate
    elif pipeline.workflow_stage == pipeline.FINAL_CHECK:
        if not prepared.get("phase"):
            prepared["phase"] = "final_check"
    normalize_plan_steps_for_stage(pipeline, prepared)
    return prepared


def normalize_plan_steps_for_stage(pipeline: "SearchHarnessPipelineV4", plan: Dict[str, Any]) -> None:
    steps = plan.get("steps")
    if not isinstance(steps, list):
        return
    if len(steps) > 6:
        actionable = [
            step for step in steps
            if not (isinstance(step, dict) and step.get("status") in (None, "pending", "in_progress"))
        ]
        non_actionable = [
            step for step in steps
            if not (isinstance(step, dict) and step.get("status") in (None, "pending", "in_progress"))
        ]
        plan["steps"] = (actionable + non_actionable)[:6]
        steps = plan["steps"]
    default_stage = workflow_stage_from_plan(pipeline, plan) or pipeline.workflow_stage
    if default_stage == pipeline.CANDIDATE_GENERATION:
        default_type = "candidate_expansion"
    elif default_stage == pipeline.CANDIDATE_VERIFICATION:
        default_type = "candidate_verification"
    else:
        default_type = "final_check"
    for step in steps:
        if not isinstance(step, dict):
            continue
        if step.get("name") and not step.get("subtask"):
            step["subtask"] = step.get("name")
        if step.get("status") in (None, "pending", "in_progress") and not step.get("subtask_type"):
            step["subtask_type"] = default_type


def should_advance_stage(
    pipeline: "SearchHarnessPipelineV4",
    plan: Dict[str, Any],
    compact_state: Dict[str, Any],
) -> bool:
    stage_status = (plan.get("stage_status") or "continue").strip().lower()
    if pipeline.workflow_stage == pipeline.CANDIDATE_GENERATION:
        if stage_status == "ready_to_advance":
            return True
        # Force advance when the generation budget is exhausted but the
        # planner keeps returning "continue". Without this the planner can
        # loop on candidate_expansion indefinitely (observed: 8 identical
        # expansion subtasks, 191 searches, never entering verification),
        # which starves the verification crawl nudge and leaves the
        # finalizer to guess. Only force when there are enough viable
        # candidates to actually verify.
        gen_round = pipeline.stage_round_counts.get(pipeline.CANDIDATE_GENERATION, 0) + 1
        viable_n = len(pipeline._viable_candidate_records())
        # Diagnostic: log why force-advance is/isn't triggering
        logger.info(
            f"[Pipeline] _should_advance_stage(gen): gen_round={gen_round} "
            f"max_rounds={pipeline.max_candidate_generation_rounds} "
            f"viable_n={viable_n} stage_status={stage_status!r}"
        )
        if gen_round > pipeline.max_candidate_generation_rounds and viable_n >= 2:
            logger.info(
                f"[Pipeline] generation budget exhausted "
                f"(round {gen_round} > {pipeline.max_candidate_generation_rounds}) "
                f"with {viable_n} viable candidates — forcing advance to "
                f"verification (planner stage_status={stage_status!r})"
            )
            return True
        return False
    if pipeline.workflow_stage == pipeline.CANDIDATE_VERIFICATION:
        viable_records = pipeline._viable_candidate_records()
        verification_queue_exhausted = not pipeline.active_candidate and not pipeline.verification_queue
        if not (stage_status == "ready_to_advance" and verification_queue_exhausted and len(viable_records) == 1):
            return False
        # Top-2 verification gate (Fix for pos6-style selection errors):
        # Do NOT advance to final_check if the sole surviving viable
        # candidate is still only "partial" (unresolved constraints remain)
        # AND it has not yet exhausted its verification rounds. This forces
        # one more candidate_verification subtask to either confirm it
        # (verified) or surface a hard_conflict, preventing a weaker
        # partial candidate from being selected over an unverified-but-
        # higher-confidence sibling. The active_candidate_rounds >= 2
        # guard ensures we never block indefinitely.
        sole = viable_records[0] if viable_records else None
        if sole and str(sole.get("verification_status", "")).lower() not in {"verified", "contradicted"}:
            # Still partial/unverified: block advance unless we have
            # already spent the full verification round budget on it.
            if pipeline.active_candidate_rounds < 2:
                logger.info(
                    f"[Pipeline] top-2 gate: sole viable candidate "
                    f"{sole.get('name', '')!r} is "
                    f"verification_status={sole.get('verification_status')!r} "
                    f"(rounds={pipeline.active_candidate_rounds}) — blocking "
                    f"advance to final_check for one more verification pass"
                )
                return False
        return True
    return False


def advance_stage(pipeline: "SearchHarnessPipelineV4") -> bool:
    if pipeline.workflow_stage == pipeline.CANDIDATE_GENERATION:
        pipeline.workflow_stage = pipeline.CANDIDATE_VERIFICATION
        pipeline._initialize_verification_queue()
        return True
    if pipeline.workflow_stage == pipeline.CANDIDATE_VERIFICATION:
        pipeline.workflow_stage = pipeline.FINAL_CHECK
        return True
    return False


def build_stage_transition_feedback(
    pipeline: "SearchHarnessPipelineV4",
    previous_stage: str,
    compact_state: Dict[str, Any],
) -> Dict[str, str]:
    if pipeline.workflow_stage == pipeline.CANDIDATE_VERIFICATION:
        candidates = compact_state.get("current_candidates") or []
        candidate_records = compact_state.get("candidate_records") or []
        incomplete_pool = not candidates or len(candidate_records) < 2
        pool_note = (
            " The current pool may still be incomplete, so keep track of that uncertainty while you verify."
            if incomplete_pool else
            ""
        )
        return {
            "role": "user",
            "content": (
                f"Workflow transition: candidate generation is finished for now. "
                f"You are now entering candidate_verification. "
                f"Use the current pool as your starting point: {json.dumps(candidates, ensure_ascii=False)}. "
                f"The first candidate to verify is: {json.dumps(pipeline.active_candidate, ensure_ascii=False)}. "
                f"Verify candidates one by one, record hard conflicts aggressively, and remember that a candidate may be an upstream entity rather than the final answer string. "
                f"Do not restart broad candidate generation unless the current pool clearly collapses."
                f"{pool_note}"
            ),
        }
    if pipeline.workflow_stage == pipeline.FINAL_CHECK:
        viable = [r.get("name", "") for r in pipeline._viable_candidate_records()]
        return {
            "role": "user",
            "content": (
                f"Workflow transition: candidate verification is sufficiently complete. "
                f"You are now entering final_check. "
                f"The surviving candidate paths are: {json.dumps(viable, ensure_ascii=False)}. "
                f"Do not broaden the pool. Decide whether the surviving path is sufficient for the final answer; if not, explain the exact remaining gap."
            ),
        }
    return {"role": "user", "content": f"Workflow transition from {previous_stage} complete."}


def maybe_advance_stage(
    pipeline: "SearchHarnessPipelineV4",
    question: str,
    plan: Dict[str, Any],
    iteration: int,
) -> Dict[str, Any]:
    compact_state = pipeline.state_store.export_compact_state()
    if pipeline.workflow_stage == pipeline.CANDIDATE_VERIFICATION and pipeline._should_rotate_active_candidate(plan, compact_state):
        if pipeline._rotate_active_candidate(compact_state):
            transition_feedback = [{
                "role": "user",
                "content": (
                    "Candidate verification loop update: the previous candidate has been checked enough for now. "
                    f"Switch to the next candidate: {pipeline.active_candidate}. "
                    "Stay within candidate_verification and focus the next plan on this candidate only."
                ),
            }]
            _t_pr = time.time()
            planner_result = pipeline.planner.run(
                question=question,
                feedback_history=transition_feedback,
                compact_state=compact_state,
                workflow_stage=pipeline.workflow_stage,
                stage_context=stage_context(pipeline),
            )
            if pipeline.trajectory_recorder:
                pipeline.trajectory_recorder.record_planner(messages=pipeline.planner.messages, iteration=iteration, latency_ms=(time.time() - _t_pr) * 1000.0)
            if planner_result.get("answer"):
                # pos6 v15 fix: apply the top-2 verification gate to answers
                # produced during candidate rotation inside _maybe_advance_stage.
                # Previously, the planner could commit an answer here (e.g.
                # "Opium: A Portrait of the Heavenly Demon") while viable
                # unverified siblings remained, bypassing the gate that
                # the serial followup and nudge paths already enforce.
                if pipeline.workflow_stage == pipeline.CANDIDATE_VERIFICATION:
                    blocked_answer = pipeline._gate_verification_short_circuit(
                        planner_result["answer"], iteration
                    )
                    if blocked_answer is not None:
                        # Gate blocked: discard the answer and fall through
                        # to the rotation subtask below.
                        pass
                    else:
                        pipeline._stage_answer = planner_result["answer"]
                        return plan
                else:
                    pipeline._stage_answer = planner_result["answer"]
                    return plan
            rotated_plan = prepare_plan_for_stage(pipeline, planner_result.get("plan") or plan)
            pipeline._plan_history.append(rotated_plan)
            phase_changed = pipeline.state_store.add_plan(rotated_plan)
            if phase_changed:
                pipeline.state_store.create_snapshot()
            return rotated_plan
        plan = dict(plan)
        plan["stage_status"] = "ready_to_advance"
    if pipeline._should_rebuild_candidate_pool(compact_state):
        pipeline.workflow_stage = pipeline.CANDIDATE_GENERATION
        pipeline.stage_round_counts[pipeline.CANDIDATE_GENERATION] = 0
        pipeline.active_candidate = None
        pipeline.active_candidate_rounds = 0
        pipeline.verification_queue = []
        rebuild_feedback = [{
            "role": "user",
            "content": (
                "Candidate verification loop update: the current candidate paths have accumulated hard conflicts. "
                "Return to candidate_generation and rebuild the pool from alternative interpretations. "
                "Do not continue refining the same damaged path."
            ),
        }]
        _t_pr = time.time()
        planner_result = pipeline.planner.run(
            question=question,
            feedback_history=rebuild_feedback,
            compact_state=compact_state,
            workflow_stage=pipeline.workflow_stage,
            stage_context=stage_context(pipeline),
        )
        if pipeline.trajectory_recorder:
            pipeline.trajectory_recorder.record_planner(messages=pipeline.planner.messages, iteration=iteration, latency_ms=(time.time() - _t_pr) * 1000.0)
        if planner_result.get("answer"):
            # pos6 v15 fix: apply the top-2 verification gate to answers
            # produced during pool rebuild inside _maybe_advance_stage.
            if pipeline.workflow_stage == pipeline.CANDIDATE_VERIFICATION:
                blocked_answer = pipeline._gate_verification_short_circuit(
                    planner_result["answer"], iteration
                )
                if blocked_answer is not None:
                    pass
                else:
                    pipeline._stage_answer = planner_result["answer"]
                    return plan
            else:
                pipeline._stage_answer = planner_result["answer"]
                return plan
        rebuilt_plan = prepare_plan_for_stage(pipeline, planner_result.get("plan") or plan)
        pipeline._plan_history.append(rebuilt_plan)
        phase_changed = pipeline.state_store.add_plan(rebuilt_plan)
        if phase_changed:
            pipeline.state_store.create_snapshot()
        return rebuilt_plan
    # Top-2 verification gate (pos6 fix): if the only thing blocking advance
    # to final_check is that the sole viable candidate is still "partial",
    # re-queue it for another verification pass instead of returning a
    # plan with no actionable subtask (which would deadlock or mis-select).
    if (
        pipeline.workflow_stage == pipeline.CANDIDATE_VERIFICATION
        and not pipeline.active_candidate
        and not pipeline.verification_queue
    ):
        viable_records = pipeline._viable_candidate_records()
        if len(viable_records) == 1:
            sole = viable_records[0]
            sole_vs = str(sole.get("verification_status", "")).lower()
            if sole_vs not in {"verified", "contradicted"} and pipeline.active_candidate_rounds < 2:
                pipeline.active_candidate = str(sole.get("name", "")).strip()
                pipeline.active_candidate_rounds = 0
                if pipeline.active_candidate in pipeline.completed_verification_candidates:
                    pipeline.completed_verification_candidates.remove(pipeline.active_candidate)
                logger.info(
                    f"[Pipeline] top-2 gate: re-queuing sole viable "
                    f"{pipeline.active_candidate!r} (verification_status={sole_vs}) "
                    f"for one more verification pass"
                )
                reverify_feedback = [{
                    "role": "user",
                    "content": (
                        f"Top-2 verification gate: the sole surviving viable candidate "
                        f"{pipeline.active_candidate!r} is still only verification_status="
                        f"{sole_vs!r} with unresolved constraints. Before finalizing, "
                        f"run one focused candidate_verification subtask to either "
                        f"confirm it (mark verification_status=verified with evidence) "
                        f"or surface a hard_conflict that eliminates it. Do not broaden "
                        f"the candidate pool; focus only on resolving this candidate."
                    ),
                }]
                _t_pr = time.time()
                planner_result = pipeline.planner.run(
                    question=question,
                    feedback_history=reverify_feedback,
                    compact_state=compact_state,
                    workflow_stage=pipeline.workflow_stage,
                    stage_context=stage_context(pipeline),
                )
                if pipeline.trajectory_recorder:
                    pipeline.trajectory_recorder.record_planner(messages=pipeline.planner.messages, iteration=iteration, latency_ms=(time.time() - _t_pr) * 1000.0)
                if planner_result.get("answer"):
                    # pos6 v15 fix: gate re-verify answers too.
                    if pipeline.workflow_stage == pipeline.CANDIDATE_VERIFICATION:
                        blocked_answer = pipeline._gate_verification_short_circuit(
                            planner_result["answer"], iteration
                        )
                        if blocked_answer is not None:
                            pass
                        else:
                            pipeline._stage_answer = planner_result["answer"]
                            return plan
                    else:
                        pipeline._stage_answer = planner_result["answer"]
                        return plan
                reverify_plan = prepare_plan_for_stage(pipeline, planner_result.get("plan") or plan)
                pipeline._plan_history.append(reverify_plan)
                phase_changed = pipeline.state_store.add_plan(reverify_plan)
                if phase_changed:
                    pipeline.state_store.create_snapshot()
                return reverify_plan
    if not should_advance_stage(pipeline, plan, compact_state):
        return plan
    previous_stage = pipeline.workflow_stage
    if not advance_stage(pipeline):
        return plan
    transition_feedback = [build_stage_transition_feedback(pipeline, previous_stage, compact_state)]
    _t_pr = time.time()
    planner_result = pipeline.planner.run(
        question=question,
        feedback_history=transition_feedback,
        compact_state=compact_state,
        workflow_stage=pipeline.workflow_stage,
        stage_context=stage_context(pipeline),
    )
    if pipeline.trajectory_recorder:
        pipeline.trajectory_recorder.record_planner(messages=pipeline.planner.messages, iteration=iteration, latency_ms=(time.time() - _t_pr) * 1000.0)
    if planner_result.get("answer"):
        # pos6 v15 fix: gate stage-transition answers when still in
        # candidate_verification (the gate is a no-op for final_check).
        if pipeline.workflow_stage == pipeline.CANDIDATE_VERIFICATION:
            blocked_answer = pipeline._gate_verification_short_circuit(
                planner_result["answer"], iteration
            )
            if blocked_answer is not None:
                pass
            else:
                pipeline._stage_answer = planner_result["answer"]
                return plan
        else:
            pipeline._stage_answer = planner_result["answer"]
            return plan
    next_plan = prepare_plan_for_stage(pipeline, planner_result.get("plan") or plan)
    pipeline._plan_history.append(next_plan)
    phase_changed = pipeline.state_store.add_plan(next_plan)
    if phase_changed:
        pipeline.state_store.create_snapshot()
    return next_plan
