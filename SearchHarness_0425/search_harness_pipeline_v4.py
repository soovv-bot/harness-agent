"""Search harness pipeline v4.

Adds a bounded stopping policy and best-effort finalization on unresolved runs.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from loguru import logger

from search_memory import SearchStateStore
from planning_agent_v3 import PlanningAgentV3
from search_agent_v3 import SearchAgentV3
from search_finalizer import SearchFinalizer
from subtask_critic import SubtaskCritic
from planning_direction_critic import DirectionCritic
from trajectory_recorder import TrajectoryRecorder

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from query_history import QueryHistoryMemory
from query_critic import QueryCritic
from search_crawl_controller import SearchCrawlController


class SearchHarnessPipelineV4:
    CANDIDATE_GENERATION = "candidate_generation"
    CANDIDATE_VERIFICATION = "candidate_verification"
    FINAL_CHECK = "final_check"

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model_id: str,
        trajectory_recorder: TrajectoryRecorder = None,
        max_planner_searches: int = 10,
        max_executor_searches: int = 30,
        max_total_searches: int = 80,
        executor_model_id: Optional[str] = None,
        enable_query_critic: bool = True,
        enable_direction_critic: bool = False,
    ):
        self.state_store = SearchStateStore(keep_recent_observations=3)
        self._api_base = api_base
        self._api_key = api_key
        self._model_id = model_id
        self._executor_model_id = executor_model_id or model_id
        self.enable_query_critic = enable_query_critic
        self.enable_direction_critic = enable_direction_critic
        self.query_memory = QueryHistoryMemory()
        self.query_critic = QueryCritic(self.query_memory, api_base=api_base, api_key=api_key, model_id=model_id)
        self.crawl_controller = SearchCrawlController(self.query_memory, api_base=api_base, api_key=api_key, model_id=model_id)
        self.planner = PlanningAgentV3(api_base=api_base, api_key=api_key, model_id=model_id, search_budget=max_planner_searches)
        self.executor = SearchAgentV3(
            api_base=api_base,
            api_key=api_key,
            model_id=self._executor_model_id,
            state_store=self.state_store,
            query_memory=self.query_memory,
            query_critic=self.query_critic,
            crawl_controller=self.crawl_controller,
            search_budget=max_executor_searches,
            enable_query_critic=self.enable_query_critic,
        )
        self.finalizer = SearchFinalizer(api_base=api_base, api_key=api_key, model_id=model_id)
        self.subtask_critic = SubtaskCritic(api_base=api_base, api_key=api_key, model_id=model_id)
        self.direction_critic = DirectionCritic(api_base=api_base, api_key=api_key, model_id=model_id)
        self.trajectory_recorder = trajectory_recorder
        self.max_total_searches = max_total_searches
        self.max_candidate_generation_rounds = 2
        self._stage_answer: Optional[str] = None

    def run(
        self,
        question: str,
        max_iterations: int = 6,
        max_crawl_calls: int = 12,
    ) -> Dict[str, Any]:
        # Reset all state for a new task
        self.state_store = SearchStateStore(keep_recent_observations=self.state_store.keep_recent_observations)
        self.state_store.set_question(question)
        self.executor.state_store = self.state_store
        self.subtask_critic.records = []
        self.query_memory = QueryHistoryMemory()
        self.query_critic = QueryCritic(self.query_memory, api_base=self._api_base, api_key=self._api_key, model_id=self._model_id)
        self.crawl_controller = SearchCrawlController(self.query_memory, api_base=self._api_base, api_key=self._api_key, model_id=self._model_id)
        self.executor.query_memory = self.query_memory
        self.executor.query_critic = self.query_critic
        self.executor.enable_query_critic = self.enable_query_critic
        self.executor.crawl_controller = self.crawl_controller
        self.workflow_stage = self.CANDIDATE_GENERATION
        self.stage_round_counts = {
            self.CANDIDATE_GENERATION: 0,
            self.CANDIDATE_VERIFICATION: 0,
            self.FINAL_CHECK: 0,
        }
        self.verification_queue: List[str] = []
        self.completed_verification_candidates: List[str] = []
        self.active_candidate: Optional[str] = None
        self.active_candidate_rounds: int = 0
        self._plan_history: List[Dict[str, Any]] = []
        self._stage_answer = None
        pipeline_config = {"max_iterations": max_iterations, "max_planner_searches": self.planner.search_budget, "max_executor_searches": self.executor.search_budget, "max_total_searches": self.max_total_searches, "max_crawl_calls": max_crawl_calls}
        if self.trajectory_recorder:
            self.trajectory_recorder.start(question=question, pipeline_config=pipeline_config)

        planner_result = self.planner.run(
            question=question,
            compact_state=self.state_store.export_compact_state(),
            workflow_stage=self.workflow_stage,
            stage_context=self._stage_context(),
        )
        if self.trajectory_recorder:
            self.trajectory_recorder.record_planner(messages=self.planner.messages, iteration=0)
        if planner_result.get("answer"):
            return self._finish_with_answer(planner_result["answer"], iterations=0)

        plan = planner_result.get("plan") or {}
        plan = self._prepare_plan_for_stage(plan)
        self._plan_history.append(plan)
        phase_changed = self.state_store.add_plan(plan)
        if phase_changed:
            self.state_store.create_snapshot()
        plan = self._maybe_advance_stage(question, plan, iteration=0)
        solved = self._consume_stage_answer(iterations=0)
        if solved:
            return solved

        for iteration in range(max_iterations):
            stop = self._check_stop(iteration, max_iterations, max_crawl_calls)
            if stop:
                wrapped = self._try_protocol_wrap_up(question, iteration)
                if wrapped:
                    return wrapped
                return self._best_effort_finish(question, plan, iteration, stop)

            subtask = self._next_subtask_from_plan(plan)
            if not subtask:
                # If candidate is resolved but planner didn't output <answer>, nudge it
                cand_status = (plan.get("candidate_status") or {}).get("state", "")
                if cand_status == "resolved":
                    logger.info("[Pipeline] candidate_status=resolved but no <answer> — nudging planner")
                    nudge = {"role": "user", "content": (
                        "Your plan shows candidate_status as 'resolved' with all steps completed. "
                        "If the original question is sufficiently solved, output the final answer now using exactly one <answer>...</answer> block. "
                        "Answer the original question directly rather than naming an intermediate candidate unless the candidate name itself is the answer. "
                        "If you still believe a final answer cannot yet be given, output exactly one <planning>...</planning> block with the minimal remaining verification work. "
                        "If you continue planning, prefer to refine or finalize the strongest currently supported candidate or answer path rather than introducing a completely new candidate, unless the current strongest path has been clearly disproven by the existing evidence."
                    )}
                    planner_result = self.planner.run(
                        question=question,
                        feedback_history=[nudge],
                        compact_state=self.state_store.export_compact_state(),
                        workflow_stage=self.workflow_stage,
                        stage_context=self._stage_context(),
                    )
                    if self.trajectory_recorder:
                        self.trajectory_recorder.record_planner(messages=self.planner.messages, iteration=iteration + 1)
                    if planner_result.get("answer"):
                        return self._finish_with_answer(planner_result["answer"], iterations=iteration + 1)
                recovered = self._recover_missing_subtask(question, plan, iteration)
                if recovered:
                    if recovered.get("answer"):
                        return recovered
                    plan = recovered.get("plan") or plan
                    subtask = self._next_subtask_from_plan(plan)
                if subtask:
                    pass
                else:
                    stop = {"trigger": "no_subtask", "details": {"iteration": iteration}}
                    return self._best_effort_finish(question, plan, iteration, stop)

            critic_result = self._settle_subtask_with_critic(
                question=question,
                plan=plan,
                subtask=subtask,
                iteration=iteration,
            )
            if critic_result.get("answer"):
                return self._finish_with_answer(critic_result["answer"], iterations=iteration + 1)
            plan = critic_result.get("plan") or plan
            subtask = critic_result.get("subtask") or subtask
            if not subtask:
                stop = {"trigger": "no_subtask_after_critic", "details": {"iteration": iteration}}
                return self._best_effort_finish(question, plan, iteration, stop)

            executor_result = self.executor.run(
                question=question,
                overall_plan=plan,
                subtask=subtask,
                executor_state=self.state_store.export_executor_state(),
            )
            if self.trajectory_recorder:
                self.trajectory_recorder.record_executor(messages=self.executor.messages, iteration=iteration)
            findings = executor_result.get("findings") or self._fallback_findings(subtask, executor_result)
            self.state_store.add_findings(findings)
            self.state_store.record_subtask_execution(
                iteration=iteration + 1,
                plan=plan,
                subtask=subtask,
                findings=findings,
            )

            # Record subtask result for future critic evaluations
            self.subtask_critic.record(
                name=subtask.get("subtask") or subtask.get("name", ""),
                status=findings.get("status", "unknown"),
                summary=findings.get("summary", "")[:300],
            )
            self.stage_round_counts[self.workflow_stage] = self.stage_round_counts.get(self.workflow_stage, 0) + 1
            if self.workflow_stage == self.CANDIDATE_VERIFICATION and self.active_candidate:
                self.active_candidate_rounds += 1

            self.state_store.set_controller_signals(self.crawl_controller.evaluate(
                phase=plan.get("phase", "unknown"),
                pending_urls=self.state_store.pending_urls,
                current_candidates=self.state_store.current_candidates,
                active_sources=self._plan_source_recommendations(plan),
                use_llm=False,
            ).to_dict())

            if self._should_snapshot(plan):
                self.state_store.create_snapshot()

            # Direction critic: every 2 completed subtasks, check for stagnation
            stagnation_msg = None
            if self.enable_direction_critic and len(self._plan_history) >= 2 and len(self._plan_history) % 2 == 0:
                verdict = self.direction_critic.evaluate(
                    question=question,
                    plan_history=self._plan_history[-4:],
                    findings_history=self.state_store.findings_history[-4:],
                    context=self._direction_critic_context(),
                )
                if verdict.is_stagnant:
                    stagnation_msg = self._build_stagnation_feedback(verdict)
                    logger.warning(f"[Pipeline] Direction stagnation: {verdict.reason[:120]}")
                    forced_plan = self._apply_direction_critic_action(question, verdict, iteration, plan)
                    if forced_plan is not None:
                        plan = forced_plan

            feedback_messages = self.state_store.build_planner_feedback(max_findings=3)
            if stagnation_msg:
                feedback_messages.append(stagnation_msg)
            # Old soft-only critic behavior kept for easy rollback:
            # feedback_messages = self.state_store.build_planner_feedback(max_findings=3)
            # if stagnation_msg:
            #     feedback_messages.append(stagnation_msg)
            planner_result = self.planner.run(
                question=question,
                feedback_history=feedback_messages,
                compact_state=self.state_store.export_compact_state(),
                workflow_stage=self.workflow_stage,
                stage_context=self._stage_context(),
            )
            if self.trajectory_recorder:
                self.trajectory_recorder.record_planner(messages=self.planner.messages, iteration=iteration + 1)
            if planner_result.get("answer"):
                return self._finish_with_answer(planner_result["answer"], iterations=iteration + 1)
            plan = self._prepare_plan_for_stage(planner_result.get("plan") or plan)
            self._plan_history.append(plan)
            phase_changed = self.state_store.add_plan(plan)
            if phase_changed:
                self.state_store.create_snapshot()
            plan = self._maybe_advance_stage(question, plan, iteration=iteration + 1)
            solved = self._consume_stage_answer(iterations=iteration + 1)
            if solved:
                return solved

        stop = {"trigger": "max_iterations_reached", "details": {"max_iterations": max_iterations}}
        wrapped = self._try_protocol_wrap_up(question, max_iterations)
        if wrapped:
            return wrapped
        return self._best_effort_finish(question, plan, max_iterations, stop)

    def _stage_context(self) -> Dict[str, Any]:
        return {
            "workflow_stage": self.workflow_stage,
            "generation_round": self.stage_round_counts.get(self.CANDIDATE_GENERATION, 0) + 1,
            "generation_budget": self.max_candidate_generation_rounds,
            "current_candidate_count": len(self.state_store.current_candidates),
            "viable_candidate_count": len(self._viable_candidate_records()),
            "active_candidate": self.active_candidate,
            "candidate_verification_round": self.active_candidate_rounds + 1 if self.active_candidate else 0,
            "verification_queue_remaining": len(self.verification_queue),
            "completed_verification_candidates": self.completed_verification_candidates[-10:],
        }

    def _workflow_stage_from_plan(self, plan: Dict[str, Any]) -> Optional[str]:
        phase = str(plan.get("phase") or "").strip().lower()
        if phase in {"source_identification", self.CANDIDATE_GENERATION}:
            return self.CANDIDATE_GENERATION
        if phase in {"candidate_narrowing", "verification", self.CANDIDATE_VERIFICATION}:
            return self.CANDIDATE_VERIFICATION
        if phase == self.FINAL_CHECK:
            return self.FINAL_CHECK

        for step in plan.get("steps", []) or []:
            if not isinstance(step, dict):
                continue
            if step.get("status") not in ("pending", "in_progress"):
                continue
            subtask_type = str(step.get("subtask_type") or step.get("type") or "").strip().lower()
            if subtask_type == "candidate_expansion":
                return self.CANDIDATE_GENERATION
            if subtask_type == "candidate_verification":
                return self.CANDIDATE_VERIFICATION
            if subtask_type == "final_check":
                return self.FINAL_CHECK
        return None

    def _sync_workflow_stage_from_plan(self, plan: Dict[str, Any]) -> None:
        target_stage = self._workflow_stage_from_plan(plan)
        if not target_stage or target_stage == self.workflow_stage:
            return

        previous_stage = self.workflow_stage
        self.workflow_stage = target_stage
        if target_stage == self.CANDIDATE_VERIFICATION:
            if previous_stage != self.CANDIDATE_VERIFICATION or not (self.active_candidate or self.verification_queue):
                self._initialize_verification_queue()
        elif target_stage == self.CANDIDATE_GENERATION:
            self.active_candidate = None
            self.active_candidate_rounds = 0
            self.verification_queue = []

    def _consume_stage_answer(self, iterations: int) -> Optional[Dict[str, Any]]:
        if not self._stage_answer:
            return None
        answer = self._stage_answer
        self._stage_answer = None
        return self._finish_with_answer(answer, iterations=iterations)

    def _pipeline_status_for_answer(self, answer: str) -> str:
        text = (answer or "").strip()
        if not text:
            return "unfinished"
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            answer_text = str(payload.get("answer", "")).strip()
            answer_status = str(payload.get("status", "")).strip().lower()
            if answer_status == "infra_error":
                return "infra_error"
            if answer_status and answer_status != "solved":
                return "unfinished"
            text = answer_text or text
        if text.strip().lower() in {"unknown", "unk", "n/a", "none", "null"}:
            return "unfinished"
        return "finished"

    def _finish_with_answer(self, answer: str, iterations: int) -> Dict[str, Any]:
        status = self._pipeline_status_for_answer(answer)
        if self.trajectory_recorder:
            self.trajectory_recorder.finalize(status=status, iterations=iterations)
        return {
            "answer": answer,
            "state": self.state_store.export_compact_state(),
            "iterations": iterations,
            "status": status,
        }

    def _prepare_plan_for_stage(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        if not plan:
            return plan
        prepared = dict(plan)
        self._sync_workflow_stage_from_plan(prepared)
        prepared["workflow_stage"] = self.workflow_stage
        prepared.setdefault("stage_status", "continue")
        if self.workflow_stage == self.CANDIDATE_GENERATION:
            if not prepared.get("phase"):
                prepared["phase"] = self.CANDIDATE_GENERATION
            prepared.setdefault("pool_assessment", {
                "coverage_status": "partial",
                "gaps": [],
            })
        elif self.workflow_stage == self.CANDIDATE_VERIFICATION:
            if not prepared.get("phase"):
                prepared["phase"] = "verification"
            if self.active_candidate:
                prepared["active_candidate"] = self.active_candidate
        elif self.workflow_stage == self.FINAL_CHECK:
            if not prepared.get("phase"):
                prepared["phase"] = "final_check"
        self._normalize_plan_steps_for_stage(prepared)
        return prepared

    def _normalize_plan_steps_for_stage(self, plan: Dict[str, Any]) -> None:
        steps = plan.get("steps")
        if not isinstance(steps, list):
            return
        if len(steps) > 6:
            actionable = [
                step for step in steps
                if isinstance(step, dict) and step.get("status") in ("pending", "in_progress")
            ]
            non_actionable = [
                step for step in steps
                if not (isinstance(step, dict) and step.get("status") in ("pending", "in_progress"))
            ]
            plan["steps"] = (actionable + non_actionable)[:6]
            steps = plan["steps"]
        default_stage = self._workflow_stage_from_plan(plan) or self.workflow_stage
        if default_stage == self.CANDIDATE_GENERATION:
            default_type = "candidate_expansion"
        elif default_stage == self.CANDIDATE_VERIFICATION:
            default_type = "candidate_verification"
        else:
            default_type = "final_check"
        for step in steps:
            if not isinstance(step, dict):
                continue
            if step.get("name") and not step.get("subtask"):
                step["subtask"] = step.get("name")
            if step.get("status") in ("pending", "in_progress") and not step.get("subtask_type"):
                step["subtask_type"] = default_type

    def _all_candidate_records(self) -> List[Dict[str, Any]]:
        return [
            record for record in self.state_store.candidate_records.values()
            if isinstance(record, dict)
        ]

    def _viable_candidate_records(self, compact_state: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        records = self._all_candidate_records()
        return [
            record for record in records
            if isinstance(record, dict) and record.get("status") != "eliminated" and not record.get("hard_conflicts")
        ]

    def _should_advance_stage(self, plan: Dict[str, Any], compact_state: Dict[str, Any]) -> bool:
        stage_status = (plan.get("stage_status") or "continue").strip().lower()
        if self.workflow_stage == self.CANDIDATE_GENERATION:
            return stage_status == "ready_to_advance"
        if self.workflow_stage == self.CANDIDATE_VERIFICATION:
            viable_records = self._viable_candidate_records()
            verification_queue_exhausted = not self.active_candidate and not self.verification_queue
            return stage_status == "ready_to_advance" and verification_queue_exhausted and len(viable_records) == 1
        return False

    def _advance_stage(self) -> bool:
        if self.workflow_stage == self.CANDIDATE_GENERATION:
            self.workflow_stage = self.CANDIDATE_VERIFICATION
            self._initialize_verification_queue()
            return True
        if self.workflow_stage == self.CANDIDATE_VERIFICATION:
            self.workflow_stage = self.FINAL_CHECK
            return True
        return False

    def _initialize_verification_queue(self) -> None:
        candidate_records = self._all_candidate_records()
        ordered: List[str] = []
        for record in candidate_records:
            if not isinstance(record, dict):
                continue
            name = str(record.get("name", "")).strip()
            if not name or record.get("status") == "eliminated":
                continue
            if name not in ordered:
                ordered.append(name)
        for name in self.state_store.current_candidates:
            if name and name not in ordered:
                ordered.append(name)
        self.verification_queue = ordered
        self.completed_verification_candidates = []
        self.active_candidate = self.verification_queue.pop(0) if self.verification_queue else None
        self.active_candidate_rounds = 0

    def _current_candidate_record(self, compact_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.active_candidate:
            return None
        for record in self._all_candidate_records():
            if isinstance(record, dict) and str(record.get("name", "")).strip() == self.active_candidate:
                return record
        return None

    def _should_rotate_active_candidate(self, plan: Dict[str, Any], compact_state: Dict[str, Any]) -> bool:
        if self.workflow_stage != self.CANDIDATE_VERIFICATION or not self.active_candidate:
            return False
        stage_status = (plan.get("stage_status") or "continue").strip().lower()
        if stage_status == "ready_to_advance":
            return True
        record = self._current_candidate_record(compact_state)
        if record and record.get("hard_conflicts"):
            return True
        return self.active_candidate_rounds >= 2

    def _rotate_active_candidate(self, compact_state: Dict[str, Any]) -> bool:
        if not self.active_candidate:
            return False
        if self.active_candidate not in self.completed_verification_candidates:
            self.completed_verification_candidates.append(self.active_candidate)
        remaining = []
        for name in self.verification_queue:
            if name and name not in self.completed_verification_candidates:
                remaining.append(name)
        self.verification_queue = remaining
        viable_names = {
            str(record.get("name", "")).strip()
            for record in self._viable_candidate_records()
            if isinstance(record, dict)
        }
        next_candidate = None
        while self.verification_queue:
            candidate = self.verification_queue.pop(0)
            if candidate in viable_names:
                next_candidate = candidate
                break
        self.active_candidate = next_candidate
        self.active_candidate_rounds = 0
        return next_candidate is not None

    def _should_rebuild_candidate_pool(self, compact_state: Dict[str, Any]) -> bool:
        if self.workflow_stage != self.CANDIDATE_VERIFICATION:
            return False
        if self.active_candidate or self.verification_queue:
            return False
        viable_records = self._viable_candidate_records()
        if viable_records:
            return False
        candidate_records = self._all_candidate_records()
        damaged_records = [
            record for record in candidate_records
            if isinstance(record, dict) and record.get("hard_conflicts")
        ]
        return bool(damaged_records)

    def _build_stage_transition_feedback(self, previous_stage: str, compact_state: Dict[str, Any]) -> Dict[str, str]:
        if self.workflow_stage == self.CANDIDATE_VERIFICATION:
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
                    f"The first candidate to verify is: {json.dumps(self.active_candidate, ensure_ascii=False)}. "
                    f"Verify candidates one by one, record hard conflicts aggressively, and remember that a candidate may be an upstream entity rather than the final answer string. "
                    f"Do not restart broad candidate generation unless the current pool clearly collapses."
                    f"{pool_note}"
                ),
            }
        if self.workflow_stage == self.FINAL_CHECK:
            viable = [r.get("name", "") for r in self._viable_candidate_records()]
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

    def _maybe_advance_stage(self, question: str, plan: Dict[str, Any], iteration: int) -> Dict[str, Any]:
        compact_state = self.state_store.export_compact_state()
        if self.workflow_stage == self.CANDIDATE_VERIFICATION and self._should_rotate_active_candidate(plan, compact_state):
            if self._rotate_active_candidate(compact_state):
                transition_feedback = [{
                    "role": "user",
                    "content": (
                        "Candidate verification loop update: the previous candidate has been checked enough for now. "
                        f"Switch to the next candidate: {self.active_candidate}. "
                        "Stay within candidate_verification and focus the next plan on this candidate only."
                    ),
                }]
                planner_result = self.planner.run(
                    question=question,
                    feedback_history=transition_feedback,
                    compact_state=compact_state,
                    workflow_stage=self.workflow_stage,
                    stage_context=self._stage_context(),
                )
                if self.trajectory_recorder:
                    self.trajectory_recorder.record_planner(messages=self.planner.messages, iteration=iteration)
                if planner_result.get("answer"):
                    self._stage_answer = planner_result["answer"]
                    return plan
                rotated_plan = self._prepare_plan_for_stage(planner_result.get("plan") or plan)
                self._plan_history.append(rotated_plan)
                phase_changed = self.state_store.add_plan(rotated_plan)
                if phase_changed:
                    self.state_store.create_snapshot()
                return rotated_plan
            plan = dict(plan)
            plan["stage_status"] = "ready_to_advance"
        if self._should_rebuild_candidate_pool(compact_state):
            self.workflow_stage = self.CANDIDATE_GENERATION
            self.stage_round_counts[self.CANDIDATE_GENERATION] = 0
            self.active_candidate = None
            self.active_candidate_rounds = 0
            self.verification_queue = []
            rebuild_feedback = [{
                "role": "user",
                "content": (
                    "Candidate verification loop update: the current candidate paths have accumulated hard conflicts. "
                    "Return to candidate_generation and rebuild the pool from alternative interpretations. "
                    "Do not continue refining the same damaged path."
                ),
            }]
            planner_result = self.planner.run(
                question=question,
                feedback_history=rebuild_feedback,
                compact_state=compact_state,
                workflow_stage=self.workflow_stage,
                stage_context=self._stage_context(),
            )
            if self.trajectory_recorder:
                self.trajectory_recorder.record_planner(messages=self.planner.messages, iteration=iteration)
            if planner_result.get("answer"):
                self._stage_answer = planner_result["answer"]
                return plan
            rebuilt_plan = self._prepare_plan_for_stage(planner_result.get("plan") or plan)
            self._plan_history.append(rebuilt_plan)
            phase_changed = self.state_store.add_plan(rebuilt_plan)
            if phase_changed:
                self.state_store.create_snapshot()
            return rebuilt_plan
        if not self._should_advance_stage(plan, compact_state):
            return plan
        previous_stage = self.workflow_stage
        if not self._advance_stage():
            return plan
        transition_feedback = [self._build_stage_transition_feedback(previous_stage, compact_state)]
        planner_result = self.planner.run(
            question=question,
            feedback_history=transition_feedback,
            compact_state=compact_state,
            workflow_stage=self.workflow_stage,
            stage_context=self._stage_context(),
        )
        if self.trajectory_recorder:
            self.trajectory_recorder.record_planner(messages=self.planner.messages, iteration=iteration)
        if planner_result.get("answer"):
            self._stage_answer = planner_result["answer"]
            return plan
        next_plan = self._prepare_plan_for_stage(planner_result.get("plan") or plan)
        self._plan_history.append(next_plan)
        phase_changed = self.state_store.add_plan(next_plan)
        if phase_changed:
            self.state_store.create_snapshot()
        return next_plan

    def _settle_subtask_with_critic(
        self,
        question: str,
        plan: Dict[str, Any],
        subtask: Optional[Dict[str, Any]],
        iteration: int,
        max_rewrites: int = 3,
    ) -> Dict[str, Any]:
        rewrites = 0
        current_plan = plan
        current_subtask = subtask

        while current_subtask:
            verdict = self.subtask_critic.evaluate(
                subtask_name=current_subtask.get("subtask") or current_subtask.get("name", ""),
                subtask_guidance=self._subtask_guidance_for_critic(current_subtask),
                overall_plan=current_plan,
            )
            logger.info(f"[SubtaskCritic] verdict={verdict.decision} | reason={verdict.reason[:120]}")
            if verdict.is_allowed:
                return {"plan": current_plan, "subtask": current_subtask}

            self.subtask_critic.record(
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
            planner_result = self.planner.run(
                question=question,
                feedback_history=feedback_messages,
                compact_state=self.state_store.export_compact_state(),
                workflow_stage=self.workflow_stage,
                stage_context=self._stage_context(),
            )
            if self.trajectory_recorder:
                self.trajectory_recorder.record_planner(messages=self.planner.messages, iteration=iteration + 1)
            if planner_result.get("answer"):
                return {"answer": planner_result["answer"]}

            current_plan = self._prepare_plan_for_stage(planner_result.get("plan") or current_plan)
            self._plan_history.append(current_plan)
            phase_changed = self.state_store.add_plan(current_plan)
            if phase_changed:
                self.state_store.create_snapshot()
            current_plan = self._maybe_advance_stage(question, current_plan, iteration=iteration + 1)
            solved = self._consume_stage_answer(iterations=iteration + 1)
            if solved:
                return {"answer": solved.get("answer", "")}
            current_subtask = self._next_subtask_from_plan(current_plan)
            if not current_subtask:
                recovered = self._recover_missing_subtask(question, current_plan, iteration)
                if recovered:
                    if recovered.get("answer"):
                        return {"answer": recovered["answer"]}
                    current_plan = recovered.get("plan") or current_plan
                    current_subtask = self._next_subtask_from_plan(current_plan)

        return {"plan": current_plan, "subtask": None}

    def _recover_missing_subtask(self, question: str, plan: Dict[str, Any], iteration: int) -> Optional[Dict[str, Any]]:
        recovery_feedback = [{
            "role": "user",
            "content": (
                f"Your current workflow stage is {self.workflow_stage}, but the latest plan has no executable pending step. "
                "Output exactly one <planning>...</planning> block with at least one concrete pending step for this stage, "
                "or output exactly one <answer>...</answer> block if the original question is already sufficiently solved. "
                "Do not leave the plan with zero actionable steps."
            ),
        }]
        planner_result = self.planner.run(
            question=question,
            feedback_history=recovery_feedback,
            compact_state=self.state_store.export_compact_state(),
            workflow_stage=self.workflow_stage,
            stage_context=self._stage_context(),
        )
        if self.trajectory_recorder:
            self.trajectory_recorder.record_planner(messages=self.planner.messages, iteration=iteration + 1)
        if planner_result.get("answer"):
            return self._finish_with_answer(planner_result["answer"], iterations=iteration + 1)
        recovered_plan = self._prepare_plan_for_stage(planner_result.get("plan") or {})
        if not recovered_plan:
            return None
        self._plan_history.append(recovered_plan)
        phase_changed = self.state_store.add_plan(recovered_plan)
        if phase_changed:
            self.state_store.create_snapshot()
        return {"plan": self._maybe_advance_stage(question, recovered_plan, iteration=iteration + 1)}

    def _check_stop(
        self,
        iteration: int,
        max_iterations: int,
        max_crawl_calls: int,
    ) -> Optional[Dict[str, Any]]:
        total_search_calls = len(self.query_memory.records)
        crawl_calls = sum(len(r.crawl_urls) for r in self.query_memory.records)
        if iteration >= max_iterations:
            return {"trigger": "max_iterations_reached", "details": {"iteration": iteration, "max_iterations": max_iterations}}
        if total_search_calls >= self.max_total_searches:
            return {"trigger": "max_total_searches_reached", "details": {"total_search_calls": total_search_calls, "max_total_searches": self.max_total_searches}}
        if crawl_calls >= max_crawl_calls:
            return {"trigger": "max_crawl_calls_reached", "details": {"crawl_calls": crawl_calls, "max_crawl_calls": max_crawl_calls}}
        return None

    def _best_effort_finish(self, question: str, plan: Dict[str, Any], iteration: int, stop: Dict[str, Any]) -> Dict[str, Any]:
        compact_state = self.state_store.export_compact_state()
        mode = "solved" if self._looks_solved(compact_state) else "best_effort"
        final = self.finalizer.finalize(question=question, compact_state=compact_state, budget_status=stop, mode=mode)
        if final.status == "infra_error":
            pipeline_status = "infra_error"
        elif final.error_type == "protocol_error":
            # Explicit protocol_error: finalizer LLM output was unparseable.
            # Still emit the local fallback answer, but mark the pipeline so it is
            # distinguishable from a genuine best_effort "Unknown".
            pipeline_status = "protocol_error"
        else:
            pipeline_status = "finished" if final.status == "solved" and final.answer.strip().lower() != "unknown" else "unfinished"
        if self.trajectory_recorder:
            self.trajectory_recorder.record_pipeline_state(
                query_history=self.query_memory.to_dict(),
                snapshots=[s.to_dict() for s in self.state_store.snapshots],
                state_summary={k: compact_state.get(k) for k in ("current_candidates", "eliminated_candidates", "confirmed_wrong_candidates", "candidate_records", "visited_domains", "pending_urls", "crawled_urls")},
            )
            self.trajectory_recorder.finalize(status=pipeline_status, iterations=iteration, stop=stop)
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

    def _build_wrap_up_state_excerpt(self, compact_state: Dict[str, Any]) -> str:
        latest_snapshot = compact_state.get("latest_snapshot") or {}
        current_plan = compact_state.get("current_plan") or {}
        excerpt = {
            "workflow_stage": self.workflow_stage,
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

    def _try_protocol_wrap_up(self, question: str, iteration: int) -> Optional[Dict[str, Any]]:
        compact_state = self.state_store.export_compact_state()
        state_excerpt = self._build_wrap_up_state_excerpt(compact_state)
        nudge = {
            "role": "user",
            "content": (
                "You have reached the execution limit for this run. Do not call any more tools. "
                "Based on all the information gathered so far, output exactly one <answer>...</answer> block now. "
                "Answer the original question directly rather than naming an intermediate candidate unless the candidate name itself is the answer. "
                "If the evidence is insufficient to answer the original question directly, return an explicit best-effort answer such as Unknown inside the <answer> block rather than continuing to plan. "
                "Do not output any <planning> block. "
                "Base your wrap-up on the current tracked state excerpt below rather than re-guessing from scratch.\n"
                f"CURRENT_TRACKED_STATE={state_excerpt}"
            ),
        }
        planner_result = self.planner.run(
            question=question,
            feedback_history=[nudge],
            compact_state=compact_state,
            workflow_stage=self.workflow_stage,
            stage_context=self._stage_context(),
        )
        if self.trajectory_recorder:
            self.trajectory_recorder.record_planner(messages=self.planner.messages, iteration=iteration + 1)
        if planner_result.get("answer"):
            return self._finish_with_answer(planner_result["answer"], iterations=iteration + 1)
        return None

    def _looks_solved(self, compact_state: Dict[str, Any]) -> bool:
        plan = compact_state.get("current_plan") or {}
        phase = plan.get("phase", "")
        cand = self.state_store.current_candidates
        viable_records = self._viable_candidate_records()
        if self.workflow_stage == self.FINAL_CHECK and phase == "final_check" and len(cand) == 1:
            return len(viable_records) <= 1
        cand_status = (plan.get("candidate_status") or {}).get("state", "")
        return self.workflow_stage == self.FINAL_CHECK and cand_status == "resolved" and len(cand) >= 1 and len(viable_records) == 1

    def _is_progress(self, findings: Dict[str, Any]) -> bool:
        evidence = findings.get("evidence") or []
        updates = findings.get("candidate_updates") or {}
        new_candidates = updates.get("new_candidates", []) or []
        source_feedback = findings.get("source_feedback") or {}
        promising = source_feedback.get("promising_sources", []) or []
        summary = (findings.get("summary") or "").strip()
        if new_candidates or promising:
            return True
        if evidence:
            return True
        if summary and len(summary) > 40 and "no useful" not in summary.lower():
            return True
        return False

    def _next_subtask_from_plan(self, plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for idx, step in enumerate(plan.get("steps", []) or []):
            if step.get("status") in ("pending", "in_progress"):
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
                source_recommendations = self._plan_source_recommendations(plan)
                if source_recommendations:
                    subtask["source_recommendations"] = source_recommendations
                return subtask
        return None

    def _plan_source_recommendations(self, plan: Dict[str, Any]) -> List[str]:
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

    def _subtask_guidance_for_critic(self, subtask: Dict[str, Any]) -> List[str]:
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

    def _should_snapshot(self, plan: Dict[str, Any]) -> bool:
        phase = plan.get("phase", "unknown")
        return phase in {"candidate_generation", "candidate_narrowing", "verification", "final_check"}

    def _fallback_findings(self, subtask: Dict[str, Any], executor_result: Dict[str, Any]) -> Dict[str, Any]:
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

    def _build_stagnation_feedback(self, verdict) -> Dict[str, str]:
        suggestions_text = "\n".join(f"- {s}" for s in verdict.suggestions) if verdict.suggestions else ""
        return {
            "role": "user",
            "content": (
                f"DIRECTION STAGNATION WARNING\n\n"
                f"The direction critic has determined that your planning direction has been stagnant.\n\n"
                f"Reason: {verdict.reason}\n\n"
                f"The executor has not produced useful results under the current direction for multiple rounds. "
                f"You MUST change your approach.\n\n"
                f"Consider:\n"
                f"1. Re-read the original question carefully — you may be misinterpreting a key constraint or clue\n"
                f"2. Consider alternative interpretations of ambiguous terms (slang, nicknames, abbreviations, homophones)\n"
                f"3. Try a simpler, more concrete subtask that can produce definitive results before tackling the full question\n"
                f"4. Switch to a completely different source family or search angle\n"
                f"5. If you've been searching forward from a hypothesis, try working backwards from known facts instead\n"
                f"{suggestions_text}"
            ),
        }

    def _direction_critic_context(self) -> Dict[str, Any]:
        compact_state = self.state_store.export_compact_state()
        return {
            "workflow_stage": self.workflow_stage,
            "active_candidate": self.active_candidate,
            "verification_queue_remaining": len(self.verification_queue),
            "completed_verification_candidates": self.completed_verification_candidates[-10:],
            "current_candidates": self.state_store.current_candidates,
            "viable_candidate_count": len(self._viable_candidate_records()),
            "remaining_uncertainties": (compact_state.get("latest_snapshot") or {}).get("remaining_uncertainties") or [],
        }

    def _apply_direction_critic_action(
        self,
        question: str,
        verdict,
        iteration: int,
        current_plan: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        action = (getattr(verdict, "force_action", "none") or "none").strip().lower()
        if action == "none":
            return None

        compact_state = self.state_store.export_compact_state()
        feedback_text: Optional[str] = None

        if action == "rebuild_candidate_pool":
            self.workflow_stage = self.CANDIDATE_GENERATION
            self.stage_round_counts[self.CANDIDATE_GENERATION] = 0
            self.active_candidate = None
            self.active_candidate_rounds = 0
            self.verification_queue = []
            feedback_text = (
                "HARNESS ACTION: direction critic forced a rebuild of the candidate pool. "
                "Return to candidate_generation immediately. "
                "Drop the current search frame and rebuild from a materially different angle, source family, or interpretation."
            )
        elif action == "rotate_active_candidate" and self.workflow_stage == self.CANDIDATE_VERIFICATION:
            rotated = self._rotate_active_candidate(compact_state)
            if rotated and self.active_candidate:
                feedback_text = (
                    "HARNESS ACTION: direction critic forced a candidate rotation. "
                    f"Stop over-investing in the previous candidate and switch to: {self.active_candidate}. "
                    "Stay in candidate_verification and focus on this candidate only."
                )
            else:
                return None
        elif action == "force_final_check":
            self.workflow_stage = self.FINAL_CHECK
            feedback_text = (
                "HARNESS ACTION: direction critic forced final_check. "
                "Do not broaden the pool. Determine whether the surviving path is actually sufficient."
            )
        else:
            return None

        logger.warning(f"[Pipeline] Applying direction-critic action: {action}")
        planner_result = self.planner.run(
            question=question,
            feedback_history=[{"role": "user", "content": feedback_text}],
            compact_state=self.state_store.export_compact_state(),
            workflow_stage=self.workflow_stage,
            stage_context=self._stage_context(),
        )
        if self.trajectory_recorder:
            self.trajectory_recorder.record_planner(messages=self.planner.messages, iteration=iteration)
        forced_plan = self._prepare_plan_for_stage(planner_result.get("plan") or current_plan)
        self._plan_history.append(forced_plan)
        phase_changed = self.state_store.add_plan(forced_plan)
        if phase_changed:
            self.state_store.create_snapshot()
        return forced_plan


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    api_base = os.getenv("OPENAI_BASE_URL")
    api_key = os.getenv("OPENAI_API_KEY")
    model_id = os.getenv("MODEL_NAME", "GLM-5.2")
    recorder = TrajectoryRecorder(model_id=model_id, output_dir="logs/trajectories")
    pipeline = SearchHarnessPipelineV4(api_base=api_base, api_key=api_key, model_id=model_id, trajectory_recorder=recorder,
                                       max_planner_searches=5, max_executor_searches=15, max_total_searches=30)
    result = pipeline.run(
        "In which arid high plateau region did Walther Penck conduct geological fieldwork?",
        max_iterations=4,
        max_crawl_calls=6,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
