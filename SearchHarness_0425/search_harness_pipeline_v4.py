"""Search harness pipeline v4.

Adds a bounded stopping policy and best-effort finalization on unresolved runs.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from loguru import logger

from search_memory import SearchStateStore
from planning_agent_v3 import PlanningAgentV3
from search_agent_v3 import SearchAgentV3
from config import settings
from search_finalizer import SearchFinalizer
from subtask_critic import SubtaskCritic
from planning_direction_critic import DirectionCritic
from trajectory_recorder import TrajectoryRecorder
from trajectory_recorder_enhanced import TrajectoryRecorderEnhanced
from llm_reasoning_compat import chat_completion_with_structuring
from openai_client_factory import build_openai_client

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from query_history import QueryHistoryMemory
from query_critic import QueryCritic
from search_crawl_controller import SearchCrawlController
from tools.search_tools import authoritative_domains_in, high_weight_sources_in  # type: ignore


class SearchHarnessPipelineV4:
    CANDIDATE_GENERATION = "candidate_generation"
    CANDIDATE_VERIFICATION = "candidate_verification"
    FINAL_CHECK = "final_check"

    VERIFICATION_RANKING_PROMPT = """You are ranking candidate answers for a research question.

Rank the candidates by how likely each is to be the CORRECT answer, considering the question's SPECIFIC constraints — not just the broad criteria that generated the list.

The broad criteria (e.g., "300+ centuries") may be satisfied by many candidates. The SPECIFIC constraints (e.g., "highest break more than 3 times", a specific match score, a specific year) are what discriminate the correct answer. Use your knowledge to identify which candidates best satisfy the MOST DISCRIMINATING constraints.

## Question

{question}

## Candidates (in no particular order)

{candidates}

## Output

JSON only (no markdown, no extra text):
{{"ranked_indices": [most_likely_idx, second_most_likely_idx, ...], "reasoning": "brief explanation of why the top-ranked candidate best fits the question's specific constraints"}}

The ranked_indices MUST be a permutation of [0, 1, ..., {n_minus_one}], with the most likely candidate first."""

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model_id: str,
        trajectory_recorder=None,
        max_planner_searches: int = 10,
        max_executor_searches: int = 30,
        max_total_searches: int = 80,
        executor_model_id: Optional[str] = None,
        executor_reasoning_effort: Optional[str] = None,
        enable_query_critic: bool = True,
        enable_direction_critic: bool = False,
    ):
        self.state_store = SearchStateStore(keep_recent_observations=3)
        self._api_base = api_base
        self._api_key = api_key
        self._model_id = model_id
        self._executor_model_id = executor_model_id or model_id
        # Per-role reasoning control: executor can disable thinking (root fix
        # for reasoning-model tool-call starvation). Falls back to EXECUTOR_THINKING env.
        if executor_reasoning_effort is None:
            executor_reasoning_effort = (os.getenv("EXECUTOR_THINKING") or "").strip().lower() or None
        self._executor_reasoning_effort = executor_reasoning_effort
        self.enable_query_critic = enable_query_critic
        self.enable_direction_critic = enable_direction_critic
        self.query_memory = QueryHistoryMemory()
        self.query_critic = QueryCritic(self.query_memory, api_base=api_base, api_key=api_key, model_id=model_id)
        self.crawl_controller = SearchCrawlController(self.query_memory, api_base=api_base, api_key=api_key, model_id=model_id)
        self.planner = PlanningAgentV3(
            api_base=api_base,
            api_key=api_key,
            model_id=model_id,
            search_budget=max_planner_searches,
            reasoning_effort=executor_reasoning_effort,
            temperature=float(os.getenv("PLANNER_TEMPERATURE", "0.4") or "0.4"),
        )
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
            reasoning_effort=executor_reasoning_effort,
            temperature=float(os.getenv("EXECUTOR_TEMPERATURE", "0.4") or "0.4"),
        )
        self.finalizer = SearchFinalizer(api_base=api_base, api_key=api_key, model_id=model_id)
        self.subtask_critic = SubtaskCritic(api_base=api_base, api_key=api_key, model_id=model_id)
        self.direction_critic = DirectionCritic(api_base=api_base, api_key=api_key, model_id=model_id)
        self._rank_client = build_openai_client(api_base, api_key)
        self._rank_enabled = (os.getenv("VERIFY_RANK_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"})
        # Reflexion (Shinn et al., 2023) + CRAG (Yan et al., 2024) hooks.
        # Reflexion: extract verbal lesson after each eliminated candidate,
        #            feed it back to the next planner turn.
        # CRAG:      assess retrieval relevance after each subtask,
        #            trigger a corrective hint when results are off-topic.
        self._reflexion_enabled = (os.getenv("REFLEXION_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"})
        self._crag_enabled = (os.getenv("CRAG_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"})
        self._reflection_notes: List[Dict[str, str]] = []
        self._relevance_notes: List[Dict[str, str]] = []
        self._max_reflection_notes = 5
        self._max_relevance_notes = 3
        self.trajectory_recorder = trajectory_recorder
        self.max_total_searches = max_total_searches
        self._max_iterations = 6  # default; updated by run()
        # Subtask concurrency: run up to N subtasks in parallel per iteration.
        # Default 2 (balanced), capped by EXECUTOR_MAX_SUBTASK_CONCURRENCY (3).
        # Set EXECUTOR_SUBTASK_CONCURRENCY=1 to force the original serial path.
        self._subtask_concurrency = int(os.getenv("EXECUTOR_SUBTASK_CONCURRENCY", "2") or "2")
        self._max_subtask_concurrency = int(os.getenv("EXECUTOR_MAX_SUBTASK_CONCURRENCY", "3") or "3")
        self.max_candidate_generation_rounds = 3
        self._stage_answer: Optional[str] = None
        self._trajectory_current_iter: Optional[list] = None
        # Default workflow stage so _check_stop / early-stop helpers work even
        # before run() is called (unit tests call _check_stop directly).
        self.workflow_stage = self.CANDIDATE_GENERATION

    def run(
        self,
        question: str,
        max_iterations: int = 6,
        max_crawl_calls: int = 12,
    ) -> Dict[str, Any]:
        # Reset all state for a new task
        self.state_store = SearchStateStore(keep_recent_observations=self.state_store.keep_recent_observations)
        self.state_store.set_question(question)
        self._question = question  # cached for full-path self-verification (Plan A)
        self._max_iterations = max_iterations
        self._contrastive_retry_done = False  # reset retry flag per task
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
        # Reset Reflexion / CRAG hook state for a fresh task.
        self._reflection_notes = []
        self._relevance_notes = []
        pipeline_config = {"max_iterations": max_iterations, "max_planner_searches": self.planner.search_budget, "max_executor_searches": self.executor.search_budget, "max_total_searches": self.max_total_searches, "max_crawl_calls": max_crawl_calls}
        if self.trajectory_recorder:
            self.trajectory_recorder.start(question=question, pipeline_config=pipeline_config)
            # Wire event callbacks so agents push structured events to the recorder.
            # Use a mutable container so the callback always reports the *current*
            # pipeline iteration (updated at the top of each loop pass). This is
            # important for concurrent runs: each pipeline owns its own container,
            # so there is no cross-task leakage.
            _rec = self.trajectory_recorder
            _current_iter = [0]
            self._trajectory_current_iter = _current_iter
            self.planner._event_callback = lambda et, data: _rec.record_event(et, iteration=_current_iter[0], agent="planner", data=data)
            self.executor._event_callback = lambda et, data: _rec.record_event(et, iteration=_current_iter[0], agent="executor", data=data)

        _t_plan0 = __import__("time").time()
        logger.info("[Pipeline] planner.start initial")
        planner_result = self.planner.run(
            question=question,
            compact_state=self.state_store.export_compact_state(),
            workflow_stage=self.workflow_stage,
            stage_context=self._stage_context(),
        )
        _plan_lat = (__import__("time").time() - _t_plan0) * 1000.0
        if self.trajectory_recorder:
            self.trajectory_recorder.record_planner(
                messages=self.planner.messages, iteration=0,
                plan=planner_result.get("plan"), answer=planner_result.get("answer"),
                latency_ms=_plan_lat,
            )
        logger.info(f"[Pipeline] planner.done initial in {__import__('time').time()-_t_plan0:.1f}s answer={'yes' if planner_result.get('answer') else 'no'}")
        if planner_result.get("answer"):
            _r = self._finish_with_answer(planner_result["answer"], iterations=0)
            if _r is not None:
                return _r

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
            logger.info(f"[Pipeline] === iteration={iteration}/{max_iterations} phase={self.workflow_stage} ===")
            if self._trajectory_current_iter is not None:
                self._trajectory_current_iter[0] = iteration
            stop = self._check_stop(iteration, max_iterations, max_crawl_calls)
            if stop:
                wrapped = self._try_protocol_wrap_up(question, iteration)
                if wrapped:
                    return wrapped
                return self._best_effort_finish(question, plan, iteration, stop)

            subtask = self._next_subtask_from_plan(plan)
            if subtask:
                self._record_event_for_trajectory("subtask_selected", iteration, {
                    "subtask": (subtask.get("subtask") or subtask.get("name", ""))[:120],
                    "subtask_type": subtask.get("subtask_type", ""),
                    "phase": plan.get("phase", ""),
                })
            if not subtask:
                # If candidate is resolved but planner didn't output <answer>, nudge it
                cand_status = (plan.get("candidate_status") or {}).get("state", "")
                if cand_status == "resolved":
                    logger.info("[Pipeline] candidate_status=resolved but no <answer> — nudging planner")
                    _t_nudge = __import__("time").time()
                    self._record_event_for_trajectory("planner_nudge", iteration, {"reason": "candidate_status=resolved but no answer"})
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
                    _nudge_lat = (__import__("time").time() - _t_nudge) * 1000.0
                    logger.info(f"[Pipeline] planner.done nudge in {_nudge_lat/1000:.1f}s answer={'yes' if planner_result.get('answer') else 'no'}")
                    if self.trajectory_recorder:
                        self.trajectory_recorder.record_planner(
                            messages=self.planner.messages, iteration=iteration + 1,
                            plan=planner_result.get("plan"), answer=planner_result.get("answer"),
                            latency_ms=_nudge_lat,
                        )
                    if planner_result.get("answer"):
                        # pos6 fix: apply the same top-2 verification gate to
                        # nudge-path answers as to followup-path answers.
                        if self.workflow_stage == self.CANDIDATE_VERIFICATION:
                            blocked_answer = self._gate_verification_short_circuit(
                                planner_result["answer"], iteration + 1
                            )
                            if blocked_answer is not None:
                                self._stage_answer = None
                                plan = self._prepare_plan_for_stage(planner_result.get("plan") or {"phase": "verification"})
                            else:
                                _r = self._finish_with_answer(planner_result["answer"], iterations=iteration + 1)
                                if _r is not None:
                                    return _r
                        else:
                            _r = self._finish_with_answer(planner_result["answer"], iterations=iteration + 1)
                            if _r is not None:
                                return _r
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

            skip_serial_critic = False
            k = self._decide_concurrency(question, plan)
            if k >= 2 and subtask is not None:
                batch = self._next_subtasks_batch(plan, k)
                if len(batch) >= 2:
                    settled: List[Dict[str, Any]] = []
                    for st in batch:
                        cr = self._settle_subtask_with_critic(question=question, plan=plan, subtask=st, iteration=iteration)
                        if cr.get("answer"):
                            _r = self._finish_with_answer(cr["answer"], iterations=iteration + 1)
                            if _r is not None:
                                return _r
                        plan = cr.get("plan") or plan
                        settled.append(cr.get("subtask") or st)
                    if len(settled) >= 2:
                        _t_exec = time.time()
                        self._record_event_for_trajectory("executor_start", iteration, {"subtask": f"[batch:{len(settled)}]", "concurrency": len(settled)})
                        results = self._run_subtasks_concurrent(question, plan, settled, iteration)
                        _exec_lat = (time.time() - _t_exec) * 1000.0
                        logger.info(f"[Pipeline] concurrent executor.done in {_exec_lat/1000:.1f}s batch={len(settled)} results={len(results)}")
                        if self.trajectory_recorder:
                            for idx, res in enumerate(results):
                                st = settled[idx] if idx < len(settled) else {}
                                self.trajectory_recorder.record_executor(
                                    messages=(res or {}).get("messages") or [], iteration=iteration,
                                    findings=(res or {}).get("findings"), subtask=st,
                                    latency_ms=_exec_lat / max(1, len(results)),
                                )
                        for idx, res in enumerate(results):
                            try:
                                st = settled[idx] if idx < len(settled) else {}
                                findings = (res or {}).get("findings") or self._fallback_findings(st, res or {})
                                cu = (findings or {}).get("candidate_updates", {}) or {}
                                nc = cu.get("new_candidates", []) or []
                                logger.info(f"[Pipeline] iter={iteration} concurrent idx={idx} new_candidates={nc}")
                                self.state_store.add_findings(findings)
                                self.state_store.record_subtask_execution(iteration=iteration + 1, plan=plan, subtask=st, findings=findings)
                            except Exception as _find_err:
                                logger.error(
                                    f"[Pipeline] concurrent findings processing error idx={idx} (non-fatal): "
                                    f"{_find_err} | type={type(_find_err).__name__}",
                                    exc_info=True,
                                )
                        try:
                            self._record_iteration_summary_for_trajectory(iteration, settled[0] if settled else {}, (results[0] or {}).get("findings") if results else None)
                        except Exception:
                            pass
                        # Pool health check: mirrors the serial path (line ~508).
                        # MUST run BEFORE the stage-advancement logic below,
                        # because _maybe_advance_stage calls planner.run() which
                        # can take 30+ seconds (or hang). If the pool health check
                        # fires, it resets the stage to CANDIDATE_GENERATION and
                        # invalidates the plan, so the stage-advancement logic
                        # below sees the reset stage and skips the planner call.
                        # Without this, type mismatch detection never fires when
                        # the concurrent executor is used (EXECUTOR_SUBTASK_CONCURRENCY>=2),
                        # which was the root cause of pos8's wrong-type candidate
                        # pool never being caught and rebuilt.
                        pool_health_msg = self._check_pool_health(question, iteration)
                        if pool_health_msg:
                            self._pending_pool_health_feedback = pool_health_msg
                            plan = {}
                            # Skip stage-advancement entirely: the pool health
                            # check already reset the stage to CANDIDATE_GENERATION.
                            # Running _maybe_advance_stage now would call
                            # planner.run() (which can hang for 30+ seconds) and
                            # potentially re-advance to the wrong stage.
                            continue
                        # P1-D fix + rotation fix: wrap stage-advancement logic
                        # in try/except so a bug in _maybe_advance_stage (e.g.
                        # the pos8 "slice(None, 3, None)" crash) degrades to
                        # continuing the next iteration instead of killing the
                        # whole pipeline. The serial path already calls
                        # _maybe_advance_stage every iteration; the concurrent
                        # path previously skipped it entirely (P1-D root cause).
                        try:
                            for _st in settled:
                                self.stage_round_counts[self.workflow_stage] = self.stage_round_counts.get(self.workflow_stage, 0) + 1
                            # pos6 fix: increment active_candidate_rounds and
                            # check for candidate rotation (mirrors serial path
                            # L435+L570). Without this, _should_rotate_active_candidate
                            # never fires and the planner loops on the same
                            # candidate indefinitely (observed: 9 iterations all
                            # verifying "Shaun Murphy" while "Ding Junhui"
                            # never got a turn in the verification queue).
                            if self.workflow_stage == self.CANDIDATE_VERIFICATION and self.active_candidate:
                                self.active_candidate_rounds += 1
                                logger.info(
                                    f"[Pipeline] concurrent verification: "
                                    f"active_candidate={self.active_candidate!r} "
                                    f"rounds={self.active_candidate_rounds} "
                                    f"queue_remaining={len(self.verification_queue)}"
                                )
                                plan = self._maybe_advance_stage(question, plan, iteration)
                                solved = self._consume_stage_answer(iterations=iteration + 1)
                                if solved:
                                    return solved
                            # P1-D: force-advance from candidate_generation to
                            # candidate_verification when the generation budget
                            # is exhausted with enough viable candidates.
                            if self.workflow_stage == self.CANDIDATE_GENERATION:
                                gen_round = self.stage_round_counts.get(self.CANDIDATE_GENERATION, 0)
                                viable_n = len(self._viable_candidate_records())
                                logger.info(
                                    f"[Pipeline] concurrent advance check: gen_round={gen_round} "
                                    f"max={self.max_candidate_generation_rounds} viable_n={viable_n}"
                                )
                                if gen_round > self.max_candidate_generation_rounds and viable_n >= 2:
                                    logger.info(
                                        f"[Pipeline] generation budget exhausted (concurrent) "
                                        f"round {gen_round} > {self.max_candidate_generation_rounds}, "
                                        f"viable={viable_n} — forcing advance to verification"
                                    )
                                    plan = dict(plan)
                                    plan["stage_status"] = "ready_to_advance"
                                    plan = self._maybe_advance_stage(question, plan, iteration)
                                    solved = self._consume_stage_answer(iterations=iteration + 1)
                                    if solved:
                                        return solved
                        except Exception as _stage_err:
                            logger.error(
                                f"[Pipeline] concurrent post-batch stage logic error (non-fatal): "
                                f"{_stage_err} | type={type(_stage_err).__name__}",
                                exc_info=True,
                            )
                        continue
                    if settled:
                        subtask = settled[0]
                        skip_serial_critic = True
            if not skip_serial_critic:
                critic_result = self._settle_subtask_with_critic(
                    question=question,
                    plan=plan,
                    subtask=subtask,
                    iteration=iteration,
                )
                if critic_result.get("answer"):
                    _r = self._finish_with_answer(critic_result["answer"], iterations=iteration + 1)
                    if _r is not None:
                        return _r
                plan = critic_result.get("plan") or plan
                subtask = critic_result.get("subtask") or subtask
            if not subtask:
                stop = {"trigger": "no_subtask_after_critic", "details": {"iteration": iteration}}
                return self._best_effort_finish(question, plan, iteration, stop)

            _t_exec = __import__("time").time()
            subtask_name = (subtask.get("subtask") or subtask.get("name") or "unknown")[:60]
            logger.info(f"[Pipeline] executor.start subtask='{subtask_name}' iter={iteration}")
            self._record_event_for_trajectory("executor_start", iteration, {"subtask": subtask_name})
            executor_result = self.executor.run(
                question=question,
                overall_plan=plan,
                subtask=subtask,
                executor_state=self.state_store.export_executor_state(),
            )
            _exec_lat = (__import__("time").time() - _t_exec) * 1000.0
            logger.info(f"[Pipeline] executor.done in {_exec_lat/1000:.1f}s subtask='{subtask_name}' status={executor_result.get('metadata',{}).get('status','?')}")
            if self.trajectory_recorder:
                self.trajectory_recorder.record_executor(
                    messages=self.executor.messages, iteration=iteration,
                    findings=executor_result.get("findings"), subtask=subtask,
                    latency_ms=_exec_lat,
                )
            findings = executor_result.get("findings") or self._fallback_findings(subtask, executor_result)
            # Debug: log findings extraction
            raw_findings = executor_result.get("findings")
            cu = (findings or {}).get("candidate_updates", {}) or {}
            nc = cu.get("new_candidates", []) or []
            logger.info(f"[Pipeline] iteration={iteration} raw_findings={'present' if raw_findings else 'None'} fallback={'yes' if not raw_findings else 'no'} new_candidates={nc}")
            self.state_store.add_findings(findings)
            self.state_store.record_subtask_execution(
                iteration=iteration + 1,
                plan=plan,
                subtask=subtask,
                findings=findings,
            )

            # Record iteration summary and candidate snapshot for trajectory
            self._record_iteration_summary_for_trajectory(iteration, subtask, findings)
            self._record_candidate_snapshot_for_trajectory(iteration)

            # Record candidate changes from findings
            cu = (findings or {}).get("candidate_updates", {}) or {}
            for nc in (cu.get("new_candidates", []) or []):
                cname = nc if isinstance(nc, str) else (nc.get("name", "") if isinstance(nc, dict) else "")
                if cname:
                    self._record_event_for_trajectory("candidate_change", iteration, {
                        "name": cname, "change_type": "added",
                    })
            for ec in (cu.get("eliminated_candidates", []) or []):
                ename = ec if isinstance(ec, str) else (ec.get("name", "") if isinstance(ec, dict) else "")
                if ename:
                    self._record_event_for_trajectory("candidate_change", iteration, {
                        "name": ename, "change_type": "eliminated",
                    })

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

            # Pool health check: detect type mismatch or domain monoculture
            # that the direction critic might miss. This is a lightweight
            # heuristic that runs every iteration without an LLM call.
            pool_health_msg = self._check_pool_health(question, iteration)

            # Reflexion (Shinn et al., 2023): when a candidate is eliminated,
            # extract a verbal lesson and feed it back to the next planner turn.
            # CRAG (Yan et al., 2024): when the just-completed subtask's findings
            # look off-topic, emit a corrective hint so the planner rewrites the
            # next search query. Both hooks are LLM-backed and gated by env
            # flags; they degrade to no-ops on any error.
            eliminated_names_this_iter = [
                (ec.get("name", "") if isinstance(ec, dict) else str(ec))
                for ec in (cu.get("eliminated_candidates", []) or [])
            ]
            eliminated_names_this_iter = [n for n in eliminated_names_this_iter if n]
            eliminated_records = []
            for ename in eliminated_names_this_iter:
                rec = self.state_store.candidate_records.get(self.state_store._candidate_key(ename))
                if rec:
                    eliminated_records.append(rec)
            reflexion_msg = self._reflect_on_elimination(
                eliminated_records, subtask_name, findings, iteration,
            ) if eliminated_records else None
            crag_msg = self._assess_subtask_relevance(subtask, findings, iteration)

            feedback_messages = self.state_store.build_planner_feedback(max_findings=3)
            if stagnation_msg:
                feedback_messages.append(stagnation_msg)
            if pool_health_msg:
                feedback_messages.append(pool_health_msg)
            # P1-A concurrent path: pick up pool health feedback stored by the
            # concurrent executor path (which skips this serial feedback builder).
            _pending_phf = getattr(self, "_pending_pool_health_feedback", None)
            if _pending_phf:
                feedback_messages.append(_pending_phf)
                self._pending_pool_health_feedback = None
            if reflexion_msg:
                feedback_messages.append(reflexion_msg)
            if crag_msg:
                feedback_messages.append(crag_msg)
            # P1-3A: Inject iteration gap summary so the planner sees what
            # constraints have been addressed vs. what gaps remain.
            gap_msg = self._build_gap_summary(iteration)
            if gap_msg:
                feedback_messages.append(gap_msg)
            # Old soft-only critic behavior kept for easy rollback:
            # feedback_messages = self.state_store.build_planner_feedback(max_findings=3)
            # if stagnation_msg:
            #     feedback_messages.append(stagnation_msg)
            _t_followup = __import__("time").time()
            planner_result = self.planner.run(
                question=question,
                feedback_history=feedback_messages,
                compact_state=self.state_store.export_compact_state(),
                workflow_stage=self.workflow_stage,
                stage_context=self._stage_context(),
            )
            _followup_lat = (__import__("time").time() - _t_followup) * 1000.0
            if self.trajectory_recorder:
                self.trajectory_recorder.record_planner(
                    messages=self.planner.messages, iteration=iteration + 1,
                    plan=planner_result.get("plan"), answer=planner_result.get("answer"),
                    latency_ms=_followup_lat,
                )
            if planner_result.get("answer"):
                # pos6 fix: top-2 verification gate for planner short-circuit.
                # When the planner tries to commit an answer while still in
                # candidate_verification, only allow it if the answer candidate
                # is already verification_status=verified. If it is only
                # partial/unverified, OR if there are other viable candidates
                # that have not yet been verified at all, block the short-circuit
                # and force one more verification subtask. This prevents the
                # planner from committing a weak "Opium" (partial) over an
                # unverified "In the Arms of Morpheus" that never got its turn
                # in the verification queue (pos6 root cause).
                if self.workflow_stage == self.CANDIDATE_VERIFICATION:
                    blocked_answer = self._gate_verification_short_circuit(
                        planner_result["answer"], iteration + 1
                    )
                    if blocked_answer is not None:
                        # Gate blocked: keep the answer aside but do not finish;
                        # fall through to _maybe_advance_stage which will emit a
                        # re-verify subtask via the top-2 gate logic.
                        self._stage_answer = None
                        plan = self._prepare_plan_for_stage(planner_result.get("plan") or {"phase": "verification"})
                    else:
                        _r = self._finish_with_answer(planner_result["answer"], iterations=iteration + 1)
                        if _r is not None:
                            return _r
                else:
                    _r = self._finish_with_answer(planner_result["answer"], iterations=iteration + 1)
                    if _r is not None:
                        return _r
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
            if step.get("status") not in (None, "pending", "in_progress"):
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

        # pos6 fix: enforce monotonic stage progression. The planner must not
        # skip candidate_verification and jump straight from candidate_generation
        # to final_check — that bypasses the top-2 verification gate in
        # _should_advance_stage and lets a weak "partial" candidate be selected
        # over an unverified-but-stronger sibling (pos6 root cause). If the
        # planner tries to jump, force it into verification first.
        stage_order = {
            self.CANDIDATE_GENERATION: 0,
            self.CANDIDATE_VERIFICATION: 1,
            self.FINAL_CHECK: 2,
        }
        current_rank = stage_order.get(self.workflow_stage, 0)
        target_rank = stage_order.get(target_stage, 0)
        if target_rank > current_rank + 1:
            logger.info(
                f"[Pipeline] stage-jump guard: planner tried to jump "
                f"{self.workflow_stage} -> {target_stage}; forcing "
                f"{self.CANDIDATE_VERIFICATION} first"
            )
            target_stage = self.CANDIDATE_VERIFICATION
        # pos6 fix: do NOT let the planner skip verification by jumping
        # from candidate_verification to final_check before ANY verification
        # subtask has run. Without this, a transition planner that immediately
        # emits phase=final_check (observed: planner_conv 3 after the
        # generation->verification force-advance) bypasses the top-2 gate in
        # _should_advance_stage and lets a single verified-but-weak candidate
        # (e.g. "Opium") win over 48 unverified siblings (e.g. "In the Arms of
        # Morpheus"). Require at least one completed verification pass.
        if (
            self.workflow_stage == self.CANDIDATE_VERIFICATION
            and target_stage == self.FINAL_CHECK
            and not self.completed_verification_candidates
            and self.active_candidate_rounds == 0
        ):
            logger.info(
                f"[Pipeline] stage-jump guard: planner tried to advance "
                f"candidate_verification -> final_check before ANY "
                f"verification subtask ran (completed=[], "
                f"active_rounds=0) — forcing back to "
                f"{self.CANDIDATE_VERIFICATION}"
            )
            target_stage = self.CANDIDATE_VERIFICATION

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
        _r = self._finish_with_answer(answer, iterations=iterations)
        return _r  # may be None if contrastive retry triggered

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

    def _verify_planner_answer(self, answer: str, *, iterations_remaining: int = 0, iteration: int = 0) -> Optional[str]:
        """Full-path self-verification for planner-committed answers.

        Two-stage verification (mirrors SearchFinalizer._maybe_verify):
        1. Contrastive verification: if multiple candidates exist, compare them
           to select the one matching the question's required answer type + all
           constraints. Fixes question-misreading (answering wrong dimension)
           and candidate bias (wrong strong candidate). If no candidate matches
           the required type, downgrade to Unknown.
        2. Grounded single-candidate verification (Plan A): verify the chosen
           answer against fresh web evidence. Refuted -> Unknown.

        The planner can short-circuit with a direct ``<answer>`` via
        ``_finish_with_answer``, bypassing ``SearchFinalizer``. To give
        verification coverage over *every* committed answer — matching the
outer-verification-loop design of AREX-style agents — we run both checks here
too. Failure-safe: any error keeps the original answer.
        """
        verifier = getattr(self.finalizer, "verifier", None)
        if verifier is None:
            return answer
        a = (answer or "").strip()
        if not a or a.lower() in {"unknown", "none", "null"}:
            return answer

        question = getattr(self, "_question", "")
        compact_state = self.state_store.export_compact_state()

        # --- Stage 1: contrastive verification ---
        try:
            candidates = self.finalizer._collect_candidates_for_contrast(compact_state, a)
            if len(candidates) >= 2:
                type_hint = self._infer_question_answer_type(question)
                cr = verifier.contrastive_verify(
                    question, candidates, answer_type_hint=type_hint
                )
                if cr.winner is None:
                    # Contrastive verify rejected all candidates. Do NOT
                    # trigger a pool rebuild — the rebuild is destructive: it
                    # clears the candidate pool (including the correct
                    # candidate the planner chose) and the finalizer then
                    # salvages a wrong candidate from stale message context
                    # (pos2 regression: planner chose correct "Marguerite
                    # Smith", contrastive_verify rejected both candidates,
                    # rebuild cleared the pool, finalizer salvaged wrong
                    # "Alma Lutz"). Instead keep the planner's answer and fall
                    # through to Stage 2 grounded verification, which will
                    # downgrade to Unknown only if fresh web evidence
                    # refutes the answer. The planner already chose based on
                    # all gathered evidence; a noisy contrastive verdict
                    # should not override it.
                    logger.info(
                        f"[Pipeline] contrastive_verify rejected all candidates "
                        f"(answer_type={cr.answer_type!r}); keeping original "
                        f"planner answer {a!r} (not triggering rebuild — Stage 2 "
                        f"grounded verification will still refute if wrong)"
                    )
                    # Fall through to Stage 2 grounded verification
                if cr.winner is not None and cr.winner.strip().lower() != a.lower():
                    logger.info(
                        f"[Pipeline] contrastive_verify replaced answer: "
                        f"{a!r} -> {cr.winner!r} (answer_type={cr.answer_type})"
                    )
                    a = cr.winner
                    answer = cr.winner
        except Exception as exc:
            logger.warning(f"[Pipeline] contrastive_verify failed (kept original): {exc}")

        # --- Stage 2: grounded single-candidate verification (Plan A) ---
        try:
            candidate_record = self.finalizer._pick_candidate_record(compact_state, a)
            vr = verifier.verify(question, a, candidate_record)
            if vr.is_refuted:
                logger.info(
                    f"[Pipeline] planner answer REFUTED by grounded verification: "
                    f"{a!r} -> Unknown | reason={vr.reason[:120]}"
                )
                # Mark the matching candidate record as eliminated so the
                # fallback salvage can't reselect it (pos6 v13 root cause:
                # refuted "Kazuo Ishiguro" was salvaged from the pool because
                # its record status was never updated).
                self._mark_candidate_eliminated(a, vr.reason)
                return "Unknown"
            logger.info(
                f"[Pipeline] planner answer verification: {a!r} -> {vr.verdict}"
            )
        except Exception as exc:
            logger.warning(f"[Pipeline] planner-answer verification failed (kept original): {exc}")
        return answer

    def _force_pool_rebuild(self, iteration: int, answer_type: str) -> None:
        """Force the pipeline back to candidate_generation after a contrastive
        rejection, so the planner searches for entities of the correct type.
        Also allocates extra search budget so the rebuild can actually search
        and clears old wrong-type candidates so the fallback can't reselect them."""
        self.workflow_stage = self.CANDIDATE_GENERATION
        self.stage_round_counts[self.CANDIDATE_GENERATION] = 0
        self.verification_queue = []
        self.active_candidate = None
        self.active_candidate_rounds = 0
        self._stage_answer = None
        # Clear old candidate records so the fallback_answer_from_pool can't
        # reselect wrong-type candidates (e.g. institutions when a person is
        # required). The rebuild's whole point is a fresh candidate search.
        old_count = len(self.state_store.candidate_records)
        self.state_store.candidate_records.clear()
        # Allocate extra search budget for the rebuild round. The pipeline may
        # have already used far more searches than the original limit (the stop
        # check only fires at iteration boundaries, not mid-subtask), so we
        # set the new ceiling relative to the current usage, not the old max.
        current_search_calls = len(self.query_memory.records)
        extra = 15
        self.max_total_searches = current_search_calls + extra
        self.planner.search_budget += 5
        self.executor.search_budget += 10
        logger.info(
            f"[Pipeline] Forced pool rebuild: CANDIDATE_GENERATION "
            f"(contrastive reject, answer_type={answer_type}, iter={iteration}, "
            f"cleared {old_count} old candidates, "
            f"+{extra} search budget -> total={self.max_total_searches} "
            f"(used={current_search_calls})"
        )
        self._record_event_for_trajectory("contrastive_reject_rebuild", iteration, {
            "answer_type": answer_type,
            "forced_stage": self.CANDIDATE_GENERATION,
            "extra_budget": extra,
            "cleared_candidates": old_count,
            "current_search_calls": current_search_calls,
        })

    def _mark_candidate_eliminated(self, answer: str, reason: str) -> None:
        """Mark a candidate record as eliminated when it is refuted by
        grounded verification. This prevents the fallback salvage from
        reselecting a refuted answer (pos6 v13 root cause)."""
        a_norm = (answer or "").strip().lower()
        if not a_norm:
            return
        for record in self.state_store.candidate_records:
            if not isinstance(record, dict):
                continue
            name = str(record.get("candidate") or record.get("name") or "").strip().lower()
            if name == a_norm:
                record["status"] = "eliminated"
                record["elimination_reason"] = f"refuted by grounded verification: {reason[:200]}"
                logger.info(
                    f"[Pipeline] Marked candidate {name!r} as eliminated "
                    f"(refuted by grounded verification)"
                )
                return

    def _fallback_answer_from_pool(self) -> Optional[str]:
        """Pick the strongest viable candidate as a fallback answer when the
        planner/finalizer emits Unknown. Ranks by verification_status and
        supporting-constraint count, so a verified/partial candidate beats a
        bare unverified one. Returns None when no viable candidate exists.

        This fixes pos10-style failures where the planner wraps up with
        ``<answer>Unknown</answer>`` even though the candidate pool still holds
        an active, unevaluated candidate. The salvaged answer still flows
        through ``_verify_planner_answer`` afterwards, so a fallback that is
        refuted by fresh web evidence is correctly downgraded back to Unknown.

        pos6 p1h2 fix: when the question's answer type is known (e.g.
        'book_title'), STRONGLY prefer candidates whose inferred type matches.
        Without this, the fallback picks the most-verified candidate of ANY
        type — e.g. an author ('Barbara Hodgson') when the question asks for a
        book title — and returns the wrong entity type as the answer. A
        type-matching candidate always beats a non-matching one regardless of
        verification score; only when no type-matching candidate exists do we
        fall back to the original verification-score ranking.
        """
        viable = self._viable_candidate_records()
        if not viable:
            return None
        vorder = {"verified": 0, "partial": 1, "unverified": 2, "contradicted": 3}

        qtype = (self._infer_question_answer_type(getattr(self, "_question", "") or "") or "").strip().lower()
        type_hints = self._infer_candidate_type_hints(viable) if qtype and qtype != "unknown" else []
        indexed_viable = list(enumerate(viable))

        def _score(rec: Dict[str, Any], idx: int) -> tuple:
            vs = str(rec.get("verification_status") or "unverified").lower()
            support_n = len(rec.get("supporting_constraints") or [])
            has_evidence = 1 if rec.get("evidence") else 0
            # Type-match preference: a candidate whose inferred type matches the
            # question's answer type ranks ahead of any non-matching candidate.
            type_match = 0
            if qtype and qtype != "unknown" and type_hints:
                ct = type_hints[idx] if idx < len(type_hints) else "unknown"
                type_match = 0 if ct == qtype else 1
            return (type_match, vorder.get(vs, 2), -support_n, -has_evidence)

        indexed_viable.sort(key=lambda pair: _score(pair[1], pair[0]))
        best = indexed_viable[0][1] if indexed_viable else None
        if best is None:
            return None
        name = str(best.get("candidate") or best.get("name") or "").strip()
        return name or None

    def _finish_with_answer(self, answer: str, iterations: int) -> Dict[str, Any]:
        # Fallback: when the planner wraps up with Unknown/empty (pos10-style
        # unfinished), try to salvage a best-guess answer from the viable
        # candidate pool before giving up. The salvaged answer still goes
        # through _verify_planner_answer, so a refuted fallback is downgraded
        # back to Unknown rather than committing a wrong guess.
        _normalized = (answer or "").strip().lower()
        if _normalized in {"", "unknown", "none", "null"}:
            _salvaged = self._fallback_answer_from_pool()
            if _salvaged:
                logger.info(
                    f"[Pipeline] planner answer was {answer!r}; salvaged fallback "
                    f"from candidate pool: {_salvaged!r}"
                )
                self._record_event_for_trajectory("fallback_answer_from_pool", iterations, {
                    "original_answer": answer,
                    "salvaged_answer": _salvaged,
                })
                answer = _salvaged
        answer = self._verify_planner_answer(
            answer,
            iterations_remaining=self._max_iterations - iterations,
            iteration=iterations,
        )
        # Contrastive retry: _verify_planner_answer returns None when it
        # triggered a pool rebuild. Signal the caller to continue the loop
        # instead of finishing.
        if answer is None:
            return None
        status = self._pipeline_status_for_answer(answer)
        logger.info(f"[Pipeline] FINISHED answer status={status} iterations={iterations} answer_preview='{answer[:80]}'")
        self._record_event_for_trajectory("pipeline_answer", iterations, {"answer": answer[:200], "status": status})
        self._record_candidate_snapshot_for_trajectory(iterations)
        if self.trajectory_recorder:
            self.trajectory_recorder.record_pipeline_state(
                query_history=self.query_memory.to_dict(),
                snapshots=[s.to_dict() for s in self.state_store.snapshots],
                state_summary={k: self.state_store.export_compact_state().get(k) for k in ("current_candidates", "eliminated_candidates", "confirmed_wrong_candidates", "candidate_records", "visited_domains", "pending_urls", "crawled_urls")},
                candidate_records=self.state_store.candidate_records,
            )
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
                if isinstance(step, dict) and step.get("status") in (None, "pending", "in_progress")
            ]
            non_actionable = [
                step for step in steps
                if not (isinstance(step, dict) and step.get("status") in (None, "pending", "in_progress"))
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
            if step.get("status") in (None, "pending", "in_progress") and not step.get("subtask_type"):
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
            if stage_status == "ready_to_advance":
                return True
            # Force advance when the generation budget is exhausted but the
            # planner keeps returning "continue". Without this the planner can
            # loop on candidate_expansion indefinitely (observed: 8 identical
            # expansion subtasks, 191 searches, never entering verification),
            # which starves the verification crawl nudge and leaves the
            # finalizer to guess. Only force when there are enough viable
            # candidates to actually verify.
            gen_round = self.stage_round_counts.get(self.CANDIDATE_GENERATION, 0) + 1
            viable_n = len(self._viable_candidate_records())
            # Diagnostic: log why force-advance is/isn't triggering
            logger.info(
                f"[Pipeline] _should_advance_stage(gen): gen_round={gen_round} "
                f"max_rounds={self.max_candidate_generation_rounds} "
                f"viable_n={viable_n} stage_status={stage_status!r}"
            )
            if gen_round > self.max_candidate_generation_rounds and viable_n >= 2:
                logger.info(
                    f"[Pipeline] generation budget exhausted "
                    f"(round {gen_round} > {self.max_candidate_generation_rounds}) "
                    f"with {viable_n} viable candidates — forcing advance to "
                    f"verification (planner stage_status={stage_status!r})"
                )
                return True
            return False
        if self.workflow_stage == self.CANDIDATE_VERIFICATION:
            viable_records = self._viable_candidate_records()
            verification_queue_exhausted = not self.active_candidate and not self.verification_queue
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
                if self.active_candidate_rounds < 2:
                    logger.info(
                        f"[Pipeline] top-2 gate: sole viable candidate "
                        f"{sole.get('name', '')!r} is "
                        f"verification_status={sole.get('verification_status')!r} "
                        f"(rounds={self.active_candidate_rounds}) — blocking "
                        f"advance to final_check for one more verification pass"
                    )
                    return False
            return True
        return False

    def _gate_verification_short_circuit(
        self, answer: str, iteration: int
    ) -> Optional[str]:
        """pos6 fix: gate the planner's direct <answer> short-circuit while
        still in candidate_verification.

        Returns None if the answer is allowed to commit (the candidate is
        already verified, or no further verification is possible). Returns a
        non-None sentinel (the blocked answer) if the short-circuit must be
        deferred so the pipeline can verify the answer candidate or one of its
        unverified viable siblings first.

        Conditions that block the short-circuit:
        1. The answer candidate exists in the pool but is not yet
           verification_status=verified (only partial/unverified).
        2. There are other viable candidates that have never been verified at
           all (verification_status=unverified) — they deserve a verification
           turn before the planner commits.
        A safety cap (active_candidate_rounds >= 3 or iteration >= 8) prevents
        indefinite blocking near the iteration budget.
        """
        if not answer or str(answer).strip().lower() in {"unknown", "none", "null"}:
            return None
        viable_records = self._viable_candidate_records()
        if not viable_records:
            return None
        answer_low = str(answer).strip().lower()
        # Locate the candidate record matching the answer (substring match,
        # since the answer may be a book title while the candidate name may
        # carry extra context).
        answer_record = None
        for rec in viable_records:
            rname = str(rec.get("name", "")).strip()
            if not rname:
                continue
            if rname.lower() in answer_low or answer_low in rname.lower():
                answer_record = rec
                break
        # Safety: near the iteration budget, let the planner commit.
        if iteration >= 8 or self.active_candidate_rounds >= 3:
            return None
        # Condition 1: answer candidate not yet verified.
        if answer_record is not None:
            vs = str(answer_record.get("verification_status", "")).lower()
            if vs not in {"verified", "contradicted"}:
                logger.info(
                    f"[Pipeline] top-2 gate (short-circuit): answer candidate "
                    f"{answer_record.get('name', '')!r} is verification_status="
                    f"{vs!r} — deferring planner answer for one more verification pass"
                )
                # Re-queue this candidate for verification.
                self.active_candidate = str(answer_record.get("name", "")).strip()
                self.active_candidate_rounds = 0
                if self.active_candidate in self.completed_verification_candidates:
                    self.completed_verification_candidates.remove(self.active_candidate)
                return answer
        # Condition 2: other viable candidates never verified at all.
        unverified_siblings = [
            rec for rec in viable_records
            if rec is not answer_record
            and str(rec.get("verification_status", "")).lower() == "unverified"
        ]
        if unverified_siblings:
            # Pick the first unverified sibling and re-queue it.
            sibling = unverified_siblings[0]
            sname = str(sibling.get("name", "")).strip()
            logger.info(
                f"[Pipeline] top-2 gate (short-circuit): "
                f"{len(unverified_siblings)} viable candidate(s) never verified "
                f"(e.g. {sname!r}) — deferring planner answer so they get a "
                f"verification turn"
            )
            self.active_candidate = sname
            self.active_candidate_rounds = 0
            if sname in self.completed_verification_candidates:
                self.completed_verification_candidates.remove(sname)
            return answer
        return None

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
        # Rank candidates by question-constraint relevance so the most
        # discriminating constraints are checked first. Falls back to
        # insertion order on any error (no regression).
        ranked = self._rank_verification_queue_by_question(ordered)
        self.verification_queue = ranked
        self.completed_verification_candidates = []
        self.active_candidate = self.verification_queue.pop(0) if self.verification_queue else None
        self.active_candidate_rounds = 0

    def _rank_verification_queue_by_question(self, candidates: List[str]) -> List[str]:
        """Reorder verification candidates by question-constraint relevance.

        Makes ONE lightweight LLM call asking the model to rank candidates by
        how well each satisfies the question's MOST DISCRIMINATING constraints
        (not just the broad criteria that generated the list). This ensures
        that the correct answer — which may not be the highest-scoring on the
        broad metric — is verified early enough within the iteration budget.

        Falls back to insertion order on any error, so existing behaviour is
        preserved when the ranking call is unavailable or disabled.
        """
        if not self._rank_enabled or len(candidates) <= 2:
            return candidates
        question = getattr(self, "_question", "") or ""
        if not question:
            return candidates
        try:
            candidates_text = "\n".join(
                f"{i}. {name}" for i, name in enumerate(candidates)
            )
            prompt = self.VERIFICATION_RANKING_PROMPT.format(
                question=question[:1500],
                candidates=candidates_text,
                n_minus_one=len(candidates) - 1,
            )
            _t_rank = time.time()
            message = chat_completion_with_structuring(
                self._rank_client,
                model_id=self._model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=1024,
                structurer_format_hint="Output the result as JSON.",
            )
            content = (getattr(message, "content", None) or "").strip()
            if not content:
                content = (getattr(message, "reasoning_content", None) or "").strip()
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if not match:
                logger.debug("[Pipeline] verify-ranking: no JSON in response, using insertion order")
                return candidates
            result = json.loads(match.group())
            ranked_indices = result.get("ranked_indices", [])
            if not isinstance(ranked_indices, list):
                return candidates
            # Build ranked list, validating indices
            ranked: List[str] = []
            seen = set()
            for idx in ranked_indices:
                if isinstance(idx, int) and 0 <= idx < len(candidates):
                    name = candidates[idx]
                    if name not in seen:
                        ranked.append(name)
                        seen.add(name)
            # Append any candidates not covered by the ranking
            for name in candidates:
                if name not in seen:
                    ranked.append(name)
            if len(ranked) != len(candidates):
                return candidates
            logger.info(
                f"[Pipeline] verify-ranking done in {time.time()-_t_rank:.1f}s "
                f"| top3={ranked[:3]}"
            )
            self._record_event_for_trajectory("verify_queue_ranked", 0, {
                "original_order": candidates[:5],
                "ranked_order": ranked[:5],
                "reasoning": str(result.get("reasoning", ""))[:300],
            })
            return ranked
        except Exception as e:
            logger.warning(f"[Pipeline] verify-ranking failed ({e}), using insertion order")
            return candidates

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
                _t_pr = time.time()
                planner_result = self.planner.run(
                    question=question,
                    feedback_history=transition_feedback,
                    compact_state=compact_state,
                    workflow_stage=self.workflow_stage,
                    stage_context=self._stage_context(),
                )
                if self.trajectory_recorder:
                    self.trajectory_recorder.record_planner(messages=self.planner.messages, iteration=iteration, latency_ms=(time.time() - _t_pr) * 1000.0)
                if planner_result.get("answer"):
                    # pos6 v15 fix: apply the top-2 verification gate to answers
                    # produced during candidate rotation inside _maybe_advance_stage.
                    # Previously, the planner could commit an answer here (e.g.
                    # "Opium: A Portrait of the Heavenly Demon") while viable
                    # unverified siblings remained, bypassing the gate that
                    # the serial followup and nudge paths already enforce.
                    if self.workflow_stage == self.CANDIDATE_VERIFICATION:
                        blocked_answer = self._gate_verification_short_circuit(
                            planner_result["answer"], iteration
                        )
                        if blocked_answer is not None:
                            # Gate blocked: discard the answer and fall through
                            # to the rotation subtask below.
                            pass
                        else:
                            self._stage_answer = planner_result["answer"]
                            return plan
                    else:
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
            _t_pr = time.time()
            planner_result = self.planner.run(
                question=question,
                feedback_history=rebuild_feedback,
                compact_state=compact_state,
                workflow_stage=self.workflow_stage,
                stage_context=self._stage_context(),
            )
            if self.trajectory_recorder:
                self.trajectory_recorder.record_planner(messages=self.planner.messages, iteration=iteration, latency_ms=(time.time() - _t_pr) * 1000.0)
            if planner_result.get("answer"):
                # pos6 v15 fix: apply the top-2 verification gate to answers
                # produced during pool rebuild inside _maybe_advance_stage.
                if self.workflow_stage == self.CANDIDATE_VERIFICATION:
                    blocked_answer = self._gate_verification_short_circuit(
                        planner_result["answer"], iteration
                    )
                    if blocked_answer is not None:
                        pass
                    else:
                        self._stage_answer = planner_result["answer"]
                        return plan
                else:
                    self._stage_answer = planner_result["answer"]
                    return plan
            rebuilt_plan = self._prepare_plan_for_stage(planner_result.get("plan") or plan)
            self._plan_history.append(rebuilt_plan)
            phase_changed = self.state_store.add_plan(rebuilt_plan)
            if phase_changed:
                self.state_store.create_snapshot()
            return rebuilt_plan
        # Top-2 verification gate (pos6 fix): if the only thing blocking advance
        # to final_check is that the sole viable candidate is still "partial",
        # re-queue it for another verification pass instead of returning a
        # plan with no actionable subtask (which would deadlock or mis-select).
        if (
            self.workflow_stage == self.CANDIDATE_VERIFICATION
            and not self.active_candidate
            and not self.verification_queue
        ):
            viable_records = self._viable_candidate_records()
            if len(viable_records) == 1:
                sole = viable_records[0]
                sole_vs = str(sole.get("verification_status", "")).lower()
                if sole_vs not in {"verified", "contradicted"} and self.active_candidate_rounds < 2:
                    self.active_candidate = str(sole.get("name", "")).strip()
                    self.active_candidate_rounds = 0
                    if self.active_candidate in self.completed_verification_candidates:
                        self.completed_verification_candidates.remove(self.active_candidate)
                    logger.info(
                        f"[Pipeline] top-2 gate: re-queuing sole viable "
                        f"{self.active_candidate!r} (verification_status={sole_vs}) "
                        f"for one more verification pass"
                    )
                    reverify_feedback = [{
                        "role": "user",
                        "content": (
                            f"Top-2 verification gate: the sole surviving viable candidate "
                            f"{self.active_candidate!r} is still only verification_status="
                            f"{sole_vs!r} with unresolved constraints. Before finalizing, "
                            f"run one focused candidate_verification subtask to either "
                            f"confirm it (mark verification_status=verified with evidence) "
                            f"or surface a hard_conflict that eliminates it. Do not broaden "
                            f"the candidate pool; focus only on resolving this candidate."
                        ),
                    }]
                    _t_pr = time.time()
                    planner_result = self.planner.run(
                        question=question,
                        feedback_history=reverify_feedback,
                        compact_state=compact_state,
                        workflow_stage=self.workflow_stage,
                        stage_context=self._stage_context(),
                    )
                    if self.trajectory_recorder:
                        self.trajectory_recorder.record_planner(messages=self.planner.messages, iteration=iteration, latency_ms=(time.time() - _t_pr) * 1000.0)
                    if planner_result.get("answer"):
                        # pos6 v15 fix: gate re-verify answers too.
                        if self.workflow_stage == self.CANDIDATE_VERIFICATION:
                            blocked_answer = self._gate_verification_short_circuit(
                                planner_result["answer"], iteration
                            )
                            if blocked_answer is not None:
                                pass
                            else:
                                self._stage_answer = planner_result["answer"]
                                return plan
                        else:
                            self._stage_answer = planner_result["answer"]
                            return plan
                    reverify_plan = self._prepare_plan_for_stage(planner_result.get("plan") or plan)
                    self._plan_history.append(reverify_plan)
                    phase_changed = self.state_store.add_plan(reverify_plan)
                    if phase_changed:
                        self.state_store.create_snapshot()
                    return reverify_plan
        if not self._should_advance_stage(plan, compact_state):
            return plan
        previous_stage = self.workflow_stage
        if not self._advance_stage():
            return plan
        transition_feedback = [self._build_stage_transition_feedback(previous_stage, compact_state)]
        _t_pr = time.time()
        planner_result = self.planner.run(
            question=question,
            feedback_history=transition_feedback,
            compact_state=compact_state,
            workflow_stage=self.workflow_stage,
            stage_context=self._stage_context(),
        )
        if self.trajectory_recorder:
            self.trajectory_recorder.record_planner(messages=self.planner.messages, iteration=iteration, latency_ms=(time.time() - _t_pr) * 1000.0)
        if planner_result.get("answer"):
            # pos6 v15 fix: gate stage-transition answers when still in
            # candidate_verification (the gate is a no-op for final_check).
            if self.workflow_stage == self.CANDIDATE_VERIFICATION:
                blocked_answer = self._gate_verification_short_circuit(
                    planner_result["answer"], iteration
                )
                if blocked_answer is not None:
                    pass
                else:
                    self._stage_answer = planner_result["answer"]
                    return plan
            else:
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
        max_rewrites: int = 2,
    ) -> Dict[str, Any]:
        rewrites = 0
        current_plan = plan
        current_subtask = subtask

        while current_subtask:
            _t_critic = __import__("time").time()
            verdict = self.subtask_critic.evaluate(
                subtask_name=current_subtask.get("subtask") or current_subtask.get("name", ""),
                subtask_guidance=self._subtask_guidance_for_critic(current_subtask),
                overall_plan=current_plan,
            )
            logger.info(f"[SubtaskCritic] verdict={verdict.decision} in {__import__('time').time()-_t_critic:.1f}s | reason={verdict.reason[:120]}")
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
            _t_rewrite = __import__("time").time()
            logger.info(f"[Pipeline] planner.start rewrite #{rewrites} (critic rejected subtask)")
            planner_result = self.planner.run(
                question=question,
                feedback_history=feedback_messages,
                compact_state=self.state_store.export_compact_state(),
                workflow_stage=self.workflow_stage,
                stage_context=self._stage_context(),
            )
            logger.info(f"[Pipeline] planner.done rewrite #{rewrites} in {__import__('time').time()-_t_rewrite:.1f}s")
            if self.trajectory_recorder:
                self.trajectory_recorder.record_planner(messages=self.planner.messages, iteration=iteration + 1, latency_ms=(time.time() - _t_rewrite) * 1000.0)
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
        # P1-A concurrent path: if the pool health check fired during the
        # concurrent executor path and invalidated the plan, include that
        # feedback here so the planner knows to search for the correct
        # entity type (e.g., "person" instead of "institution").
        _pending_phf = getattr(self, "_pending_pool_health_feedback", None)
        if _pending_phf:
            recovery_feedback.insert(0, _pending_phf)
            self._pending_pool_health_feedback = None
        _t_rec = __import__("time").time()
        logger.info("[Pipeline] planner.start recovery (no subtask)")
        planner_result = self.planner.run(
            question=question,
            feedback_history=recovery_feedback,
            compact_state=self.state_store.export_compact_state(),
            workflow_stage=self.workflow_stage,
            stage_context=self._stage_context(),
        )
        logger.info(f"[Pipeline] planner.done recovery in {__import__('time').time()-_t_rec:.1f}s answer={'yes' if planner_result.get('answer') else 'no'}")
        if self.trajectory_recorder:
            self.trajectory_recorder.record_planner(messages=self.planner.messages, iteration=iteration + 1, latency_ms=(time.time() - _t_rec) * 1000.0)
        if planner_result.get("answer"):
            # pos6 fix: gate recovery-path answers through the same top-2
            # verification short-circuit gate as the main loop. Without this,
            # a recovery planner that immediately commits an answer (observed:
            # "Opium" committed at iter 3 while 13 siblings remain unverified)
            # bypasses the top-2 gate and the tie-gate entirely.
            if self.workflow_stage == self.CANDIDATE_VERIFICATION:
                blocked_answer = self._gate_verification_short_circuit(
                    planner_result["answer"], iteration + 1
                )
                if blocked_answer is not None:
                    self._stage_answer = None
                    logger.info(
                        f"[Pipeline] recovery answer blocked by top-2 gate — "
                        f"injecting verification subtask for next candidate "
                        f"in queue"
                    )
                    # Inject a verification subtask for the next unverified
                    # candidate so the main loop has something to execute
                    # instead of re-entering recovery infinitely.
                    next_cand = self.active_candidate or ""
                    if not next_cand and self.verification_queue:
                        next_cand = self.verification_queue[0]
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
                        recovered_plan = self._prepare_plan_for_stage(injected_plan)
                        self._plan_history.append(recovered_plan)
                        phase_changed = self.state_store.add_plan(recovered_plan)
                        if phase_changed:
                            self.state_store.create_snapshot()
                        return {"plan": self._maybe_advance_stage(question, recovered_plan, iteration=iteration + 1)}
                    # Fall through to plan recovery if no next candidate
                else:
                    _r = self._finish_with_answer(planner_result["answer"], iterations=iteration + 1)
                    if _r is not None:
                        return _r
            else:
                _r = self._finish_with_answer(planner_result["answer"], iterations=iteration + 1)
                if _r is not None:
                    return _r
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
        # Plan C: adaptive early stop. If a candidate is fully verified and
        # carries no unresolved hard conflicts, the task is effectively solved
        # and extra search budget is wasted. This converts the stop policy
        # from a pure budget gate into an anytime/adaptive stop, producing a
        # Pareto-style accuracy-vs-search-count curve in ablations.
        early = self._verified_candidate_early_stop(iteration)
        if early:
            return early
        # Authority-consensus early stop: >=N independent authoritative sources
        # back one candidate. Fires even before the executor self-reports
        # verification_status=verified, saving iterations on well-corroborated
        # answers (query-efficiency optimization).
        auth = self._authoritative_consensus_early_stop(iteration, max_iterations)
        if auth:
            return auth
        return None

    def _verified_candidate_early_stop(self, iteration: int) -> Optional[Dict[str, Any]]:
        """Return an early-stop dict when a candidate is verified & conflict-free."""
        # pos6 fix: only allow verified-candidate early stop during the
        # candidate_verification stage. During candidate_generation the
        # executor may self-report verification_status=verified, but that
        # should NOT trigger an early stop — the candidate must go through
        # the formal verification queue first, and other viable candidates
        # deserve a verification turn (top-2 principle).
        if self.workflow_stage != self.CANDIDATE_VERIFICATION:
            return None
        records = (self.state_store.export_compact_state().get("candidate_records") or [])
        viable_records = self._viable_candidate_records()
        # top-2 gate: do not early-stop if there are other viable candidates
        # that have not yet been verified or contradicted. They must get a
        # verification turn before we commit.
        unverified_siblings = [
            rec for rec in viable_records
            if str(rec.get("verification_status", "")).lower() not in {"verified", "contradicted"}
        ]
        for record in records:
            if not isinstance(record, dict):
                continue
            name = str(record.get("candidate") or record.get("name") or "").strip()
            if not name or name.lower() in {"unknown", "none", "null"}:
                continue
            vs = str(record.get("verification_status") or "").strip().lower()
            hard_conflicts = record.get("hard_conflicts") or []
            unresolved = record.get("unresolved_constraints") or []
            if vs == "verified" and not hard_conflicts and not unresolved:
                if unverified_siblings:
                    logger.info(
                        f"[Pipeline] top-2 gate (early-stop): candidate {name!r} "
                        f"is verified, but {len(unverified_siblings)} viable "
                        f"sibling(s) remain unverified — deferring early stop"
                    )
                    return None
                return {
                    "trigger": "verified_candidate_early_stop",
                    "details": {
                        "iteration": iteration,
                        "candidate": name,
                        "verification_status": vs,
                    },
                }
        return None

    def _tied_candidate_blocks_early_stop(
        self,
        record: Dict[str, Any],
        viable_records: List[Dict[str, Any]],
        iteration: int,
        max_iterations: int,
    ) -> bool:
        """P1-B: Block early-stop when viable candidates are tied and a
        distinguishing constraint remains unresolved.

        Prevents premature convergence when the trigger candidate hits an
        authority/verified early-stop condition but other viable candidates
        have comparable support with unresolved constraints — the
        differentiating constraint has not been verified for any of them,
        so committing now risks picking the wrong tied candidate.

        Budget-aware: when iteration is within the last 25% of the budget,
        the gate releases (returns False) so the pipeline can commit the
        best-supported candidate instead of exhausting the budget and
        falling through to a blind best-effort finish. This preserves the
        early-iteration anti-convergence benefit without the 3x latency
        regression seen when constraints can never be resolved (e.g. when
        the executor never crawls).

        Returns True to defer the early-stop (the caller should ``continue``
        to the next candidate or fall through to the normal iteration loop).
        """
        if len(viable_records) <= 1:
            return False
        # Budget-aware release: near the iteration cap, let the pipeline
        # commit rather than burning the remaining budget on verification
        # that the executor has already shown it cannot complete.
        # pos6 fix: even near budget cap, do NOT release if there is a
        # viable sibling that has NEVER been verified or contradicted. The
        # top-2 principle still applies — committing a verified-but-wrong
        # candidate over an unverified-but-correct sibling is the exact
        # failure mode pos6 exposed (planner picked "Opium" because the
        # executor never verified "In the Arms of Morpheus"). Force at
        # least one verification turn on the top unverified sibling before
        # allowing the release.
        near_cap = max_iterations > 0 and iteration >= max_iterations - max(2, max_iterations // 4)
        trigger_name = str(record.get("candidate") or record.get("name") or "").strip()
        if near_cap:
            unverified_siblings = [
                sib for sib in viable_records
                if str(sib.get("candidate") or sib.get("name") or "").strip() != trigger_name
                and str(sib.get("verification_status") or "").strip().lower() not in {"verified", "contradicted"}
            ]
            if unverified_siblings:
                logger.info(
                    f"[Pipeline] tied gate: near budget cap at iteration="
                    f"{iteration}/{max_iterations}, but {len(unverified_siblings)} "
                    f"viable sibling(s) remain unverified (e.g. "
                    f"{str(unverified_siblings[0].get('candidate') or unverified_siblings[0].get('name',''))!r}) "
                    f"— top-2 gate holds; deferring release for a verification pass"
                )
                return True
            logger.info(
                f"[Pipeline] tied gate: releasing at iteration={iteration}/"
                f"{max_iterations} (near budget cap, all siblings verified/contradicted) — allowing early-stop "
                f"for candidate "
                f"{str(record.get('candidate') or record.get('name',''))!r}"
            )
            return False
        trigger_vs = str(record.get("verification_status") or "").strip().lower()
        trigger_support = len(record.get("supporting_constraints") or [])
        trigger_unresolved = record.get("unresolved_constraints") or []
        for sib in viable_records:
            sib_name = str(sib.get("candidate") or sib.get("name") or "").strip()
            if not sib_name or sib_name == trigger_name:
                continue
            sib_vs = str(sib.get("verification_status") or "").strip().lower()
            # Top-2 gate: an unverified viable sibling deserves a
            # verification turn before we commit (mirrors the gate in
            # _verified_candidate_early_stop).
            if sib_vs not in {"verified", "contradicted"}:
                logger.info(
                    f"[Pipeline] tied gate: candidate {trigger_name!r} hit "
                    f"early-stop, but viable sibling {sib_name!r} is still "
                    f"verification_status={sib_vs!r} — deferring for a "
                    f"verification pass"
                )
                return True
            # Tied-support gate: if the trigger is only partial (not fully
            # verified) and a sibling has comparable support AND carries
            # unresolved constraints, a distinguishing constraint likely
            # remains unverified for both → defer.
            if trigger_vs not in {"verified", "contradicted"} and trigger_unresolved:
                sib_support = len(sib.get("supporting_constraints") or [])
                sib_unresolved = sib.get("unresolved_constraints") or []
                if sib_support >= trigger_support - 1 and sib_unresolved:
                    logger.info(
                        f"[Pipeline] tied gate: candidate {trigger_name!r} "
                        f"(support={trigger_support}, vs={trigger_vs!r}) hit "
                        f"early-stop, but tied sibling {sib_name!r} "
                        f"(support={sib_support}) also has unresolved "
                        f"distinguishing constraints — deferring early stop"
                    )
                    return True
        return False

    def _authoritative_consensus_early_stop(self, iteration: int, max_iterations: int = 10) -> Optional[Dict[str, Any]]:
        """Early-stop when a candidate is backed by enough source weight.

        Two-tier decision (matches the "2 high-weight sources → fact confirmed"
        rule; weight=10 = official docs / academic / official financial reports,
        weight=2 = UGC / self-media):
          1. FACT-CONFIRMED: >=N independent weight-10 sources (default 2) agree
             on one candidate → fact established, stop the pipeline immediately.
             Trigger: ``fact_confirmed_early_stop``.
          2. AUTHORITATIVE CONSENSUS: >=N independent weight>=8 sources (tier>=4;
             default 2) agree → early-stop. Trigger:
             ``authoritative_consensus_early_stop``.

        Both complement ``_verified_candidate_early_stop`` (which waits for the
        executor to self-report verification_status=verified). FACT-CONFIRMED
        fires on objective source-weight counting — no need for the executor to
        self-report, saving iterations on well-corroborated answers. Disabled
        on contradicted/eliminated candidates. Gated by
        ``PIPELINE_AUTHORITY_EARLY_STOP`` (default on); thresholds via
        ``PIPELINE_FACT_CONFIRM_MIN_SOURCES`` (default 2) and
        ``PIPELINE_AUTHORITY_MIN_SOURCES`` (default 2).
        """
        if os.getenv("PIPELINE_AUTHORITY_EARLY_STOP", "1").strip().lower() not in {"1", "true", "yes"}:
            return None
        # pos6 fix: only allow authority-consensus early stop during the
        # candidate_verification stage. The same top-2 principle applies —
        # during candidate_generation a candidate may collect authoritative
        # sources, but other viable candidates must get a verification turn
        # before we commit to a single answer.
        if self.workflow_stage != self.CANDIDATE_VERIFICATION:
            return None
        fact_min = int(os.getenv("PIPELINE_FACT_CONFIRM_MIN_SOURCES", "2") or "2")
        auth_min = int(os.getenv("PIPELINE_AUTHORITY_MIN_SOURCES", "2") or "2")
        records = (self.state_store.export_compact_state().get("candidate_records") or [])
        viable_records = self._viable_candidate_records()
        for record in records:
            if not isinstance(record, dict):
                continue
            name = str(record.get("candidate") or record.get("name") or "").strip()
            if not name or name.lower() in {"unknown", "none", "null"}:
                continue
            status = str(record.get("status") or "").strip().lower()
            vs = str(record.get("verification_status") or "").strip().lower()
            if status == "eliminated" or vs == "contradicted":
                continue
            evidence = record.get("evidence") or []
            urls = []
            for ev in evidence:
                if not isinstance(ev, dict):
                    continue
                url_val = ev.get("source_url") or ev.get("source") or ""
                if isinstance(url_val, str) and url_val.strip().startswith("http"):
                    urls.append(url_val.strip())
            # P1-B: tied-candidate gate — if other viable candidates have
            # comparable support with unresolved distinguishing constraints,
            # defer the early-stop so the differentiating constraint gets
            # verified instead of committing to a tied candidate.
            if self._tied_candidate_blocks_early_stop(record, viable_records, iteration, max_iterations):
                continue
            # Tier 1: weight-10 sources (fact confirmed).
            high = high_weight_sources_in(urls, min_weight=10)
            if len(high) >= fact_min:
                return {
                    "trigger": "fact_confirmed_early_stop",
                    "details": {
                        "iteration": iteration,
                        "candidate": name,
                        "high_weight_domains": high,
                        "min_sources": fact_min,
                    },
                }
            # Tier 2: weight>=8 authoritative consensus.
            auth = authoritative_domains_in(urls)
            if len(auth) >= auth_min:
                return {
                    "trigger": "authoritative_consensus_early_stop",
                    "details": {
                        "iteration": iteration,
                        "candidate": name,
                        "authoritative_domains": auth,
                        "min_sources": auth_min,
                    },
                }
        return None

    def _record_candidate_snapshot_for_trajectory(self, iteration: int) -> None:
        """Snapshot the current candidate pool into the trajectory recorder."""
        if not self.trajectory_recorder:
            return
        records = self._all_candidate_records()
        try:
            self.trajectory_recorder.record_candidate_snapshot(
                iteration=iteration,
                candidates=records,
                active_candidate=self.active_candidate,
            )
        except Exception as e:
            logger.debug(f"[Pipeline] candidate snapshot record error: {e}")

    def _record_event_for_trajectory(self, event_type: str, iteration: int, data: Optional[Dict[str, Any]] = None) -> None:
        """Record a structured event into the trajectory recorder."""
        if not self.trajectory_recorder:
            return
        try:
            self.trajectory_recorder.record_event(event_type, iteration=iteration, agent="pipeline", data=data or {})
        except Exception as e:
            logger.debug(f"[Pipeline] event record error: {e}")

    def _record_iteration_summary_for_trajectory(
        self,
        iteration: int,
        subtask: Optional[Dict[str, Any]],
        findings: Optional[Dict[str, Any]],
    ) -> None:
        """Record an iteration summary into the trajectory recorder."""
        if not self.trajectory_recorder:
            return
        try:
            cu = (findings or {}).get("candidate_updates", {}) or {}
            self.trajectory_recorder.record_iteration_summary(
                iteration=iteration,
                phase=self.workflow_stage,
                subtask=(subtask or {}).get("subtask") or (subtask or {}).get("name", ""),
                searches_this_iter=getattr(self.executor, "_search_count", 0),
                new_candidates=cu.get("new_candidates", []) or [],
                plan_phase=(subtask or {}).get("subtask_type", ""),
            )
        except Exception as e:
            logger.debug(f"[Pipeline] iteration summary record error: {e}")


    def _best_effort_finish(self, question: str, plan: Dict[str, Any], iteration: int, stop: Dict[str, Any]) -> Dict[str, Any]:
        compact_state = self.state_store.export_compact_state()
        mode = "solved" if self._looks_solved(compact_state) else "best_effort"
        _t_final = __import__("time").time()
        logger.info(f"[Pipeline] finalizer.start mode={mode} stop={stop.get('trigger','?')}")
        final = self.finalizer.finalize(question=question, compact_state=compact_state, budget_status=stop, mode=mode)
        logger.info(f"[Pipeline] finalizer.done in {__import__('time').time()-_t_final:.1f}s status={final.status}")
        # P0-A+: salvage a fallback answer from the viable candidate pool when
        # the finalizer emits Unknown/empty (best_effort path). Mirrors the
        # _finish_with_answer fallback so the best_effort finish path no longer
        # silently returns Unknown while viable candidates remain unchosen.
        _final_answer_norm = (final.answer or "").strip().lower()
        if _final_answer_norm in {"", "unknown", "none", "null"}:
            _salvaged = self._fallback_answer_from_pool()
            if _salvaged:
                logger.info(
                    f"[Pipeline] finalizer answer was {final.answer!r}; salvaged fallback "
                    f"from candidate pool (best_effort): {_salvaged!r}"
                )
                self._record_event_for_trajectory("fallback_answer_from_pool_best_effort", iteration, {
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
        self._record_event_for_trajectory("pipeline_best_effort_finish", iteration, {
            "stop_trigger": stop.get("trigger", ""),
            "mode": mode,
            "finalizer_status": final.status,
            "pipeline_status": pipeline_status,
        })
        self._record_candidate_snapshot_for_trajectory(iteration)
        if self.trajectory_recorder:
            self.trajectory_recorder.record_pipeline_state(
                query_history=self.query_memory.to_dict(),
                snapshots=[s.to_dict() for s in self.state_store.snapshots],
                state_summary={k: compact_state.get(k) for k in ("current_candidates", "eliminated_candidates", "confirmed_wrong_candidates", "candidate_records", "visited_domains", "pending_urls", "crawled_urls")},
                candidate_records=self.state_store.candidate_records,
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
        planner_result = self.planner.run(
            question=question,
            feedback_history=[nudge],
            compact_state=compact_state,
            workflow_stage=self.workflow_stage,
            stage_context=self._stage_context(),
        )
        logger.info(f"[Pipeline] planner.done wrap-up in {__import__('time').time()-_t_wrap:.1f}s answer={'yes' if planner_result.get('answer') else 'no'}")
        if self.trajectory_recorder:
            self.trajectory_recorder.record_planner(messages=self.planner.messages, iteration=iteration + 1, latency_ms=(time.time() - _t_wrap) * 1000.0)
        if planner_result.get("answer"):
            _r = self._finish_with_answer(planner_result["answer"], iterations=iteration + 1)
            if _r is not None:
                return _r
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

    def _subtask_from_step(self, step: Dict[str, Any], plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
        source_recommendations = self._plan_source_recommendations(plan)
        if source_recommendations:
            subtask["source_recommendations"] = source_recommendations
        return subtask

    def _next_subtask_from_plan(self, plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for step in plan.get("steps", []) or []:
            st = self._subtask_from_step(step, plan)
            if st:
                return st
        return None

    def _next_subtasks_batch(self, plan: Dict[str, Any], k: int) -> List[Dict[str, Any]]:
        """Return up to k pending subtasks from the plan (concurrent execution)."""
        out: List[Dict[str, Any]] = []
        for step in plan.get("steps", []) or []:
            st = self._subtask_from_step(step, plan)
            if st:
                out.append(st)
                if len(out) >= k:
                    break
        return out

    def _decide_concurrency(self, question: str, plan: Dict[str, Any]) -> int:
        """Decide how many subtasks to run in parallel this iteration.

        Default 2; bump to 3 for complex questions (long question or >=4
        pending steps). Capped by EXECUTOR_MAX_SUBTASK_CONCURRENCY and by
        the number of pending steps. Returns 1 for the serial zero-regression
        path (env EXECUTOR_SUBTASK_CONCURRENCY=1 or only one pending step).
        """
        k = self._subtask_concurrency
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
            k = min(self._max_subtask_concurrency, k + 1)
        k = max(1, min(k, self._max_subtask_concurrency, n_pending))
        return k

    def _build_executor_pool(self, k: int) -> List["SearchAgentV3"]:
        """Create k independent executor instances for concurrent subtasks.

        Each gets its own query_critic/crawl_controller (isolated caches and
        _current_question), but shares state_store + query_memory (both
        lock-protected) and the OpenAI client (connection pool reuse).
        """
        shared_client = getattr(self.executor, "client", None)
        pool: List["SearchAgentV3"] = []
        _rec = self.trajectory_recorder
        _current_iter = self._trajectory_current_iter
        for i in range(k):
            qc = QueryCritic(self.query_memory, api_base=self._api_base, api_key=self._api_key, model_id=self._model_id)
            cc = SearchCrawlController(self.query_memory, api_base=self._api_base, api_key=self._api_key, model_id=self._model_id)
            exec_ = SearchAgentV3(
                api_base=self._api_base, api_key=self._api_key, model_id=self._executor_model_id,
                state_store=self.state_store, query_memory=self.query_memory,
                query_critic=qc, crawl_controller=cc,
                search_budget=self.executor.search_budget,
                enable_query_critic=self.enable_query_critic,
                reasoning_effort=self._executor_reasoning_effort,
                openai_client=shared_client,
                temperature=self.executor.temperature,
            )
            if _rec is not None and _current_iter is not None:
                _idx = i
                exec_._event_callback = lambda et, data, _i=_idx: _rec.record_event(et, iteration=_current_iter[0], agent=f"executor#{_i}", data=data)
            pool.append(exec_)
        return pool

    def _run_subtasks_concurrent(
        self, question: str, plan: Dict[str, Any], subtasks: List[Dict[str, Any]], iteration: int,
    ) -> List[Dict[str, Any]]:
        """Run N subtasks in parallel with independent executor instances.

        Returns the list of executor results (one per subtask, in input order).
        If any subtask triggers a fact_confirmed/authority_consensus early stop,
        a threading.Event signals the others to wind down promptly.
        """
        k = len(subtasks)
        pool = self._build_executor_pool(k)
        stop_event = threading.Event()
        results: List[Optional[Dict[str, Any]]] = [None] * k
        def run_one(i: int, exec_: "SearchAgentV3", st: Dict[str, Any]) -> None:
            try:
                state = self.state_store.export_executor_state()
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

    def _build_gap_summary(self, iteration: int) -> Optional[Dict[str, str]]:
        """P1-3A: Build a concise iteration gap summary for the planner.

        Lists what constraints have evidence, what candidates are active/eliminated,
        and what search directions have been tried. Helps the planner focus on
        unresolved gaps instead of re-trying exhausted directions.
        """
        try:
            compact_state = self.state_store.export_compact_state()
            candidate_records = compact_state.get("candidate_records", []) or []
            current_candidates = compact_state.get("current_candidates", []) or []
            eliminated = compact_state.get("eliminated_candidates", []) or []
            confirmed_wrong = compact_state.get("confirmed_wrong_candidates", []) or []
            executions = compact_state.get("current_plan_executions", []) or []
            visited_domains = compact_state.get("visited_domains", []) or []

            # Summarize verified vs. partial candidates with evidence
            verified = []
            partial = []
            for cr in candidate_records:
                if not isinstance(cr, dict):
                    continue
                name = cr.get("name", "?")
                vs = str(cr.get("verification_status", "")).lower()
                ev_count = len(cr.get("evidence", []) or [])
                if vs == "verified" and ev_count > 0:
                    verified.append(f"  ✓ {name} ({ev_count} evidence)")
                elif vs == "partial":
                    partial.append(f"  ? {name} ({ev_count} evidence)")

            # Summarize executed subtask types
            subtask_types = []
            for ex in executions[-10:]:
                st = (ex or {}).get("subtask_type", "") or (ex or {}).get("phase", "")
                if st and st not in subtask_types:
                    subtask_types.append(st)

            lines = [f"ITERATION GAP SUMMARY (after iteration {iteration})"]
            lines.append(f"Active candidates: {len(current_candidates)} | Eliminated: {len(eliminated)} | Confirmed wrong: {len(confirmed_wrong)}")
            if verified:
                lines.append("Verified (with evidence):")
                lines.extend(verified[:5])
            if partial:
                lines.append("Partial (needs more evidence):")
                lines.extend(partial[:5])
            if eliminated:
                lines.append(f"Eliminated: {', '.join(eliminated[:8])}")
            if subtask_types:
                lines.append(f"Subtask types tried: {', '.join(subtask_types)}")
            if visited_domains:
                lines.append(f"Domains visited ({len(visited_domains)}): {', '.join(visited_domains[:8])}")
            lines.append("Focus your next subtask on UNRESOLVED constraints. Do not repeat exhausted search directions.")

            return {"role": "user", "content": "\n".join(lines)}
        except Exception as e:
            logger.debug(f"[Pipeline] gap summary build error: {e}")
            return None

    def _direction_critic_context(self) -> Dict[str, Any]:
        compact_state = self.state_store.export_compact_state()
        all_records = self._all_candidate_records()
        viable_records = self._viable_candidate_records()
        eliminated_count = sum(
            1 for r in all_records
            if isinstance(r, dict) and (r.get("status") == "eliminated" or r.get("hard_conflicts"))
        )
        total_count = len(all_records)
        elimination_rate = (eliminated_count / total_count) if total_count else 0.0
        # Infer candidate "types" from names to detect type mismatch.
        # e.g., if the question asks for a university but all candidates are
        # person names, the pool has a type mismatch.
        candidate_type_hints = self._infer_candidate_type_hints(all_records)
        return {
            "workflow_stage": self.workflow_stage,
            "active_candidate": self.active_candidate,
            "verification_queue_remaining": len(self.verification_queue),
            "completed_verification_candidates": self.completed_verification_candidates[-10:],
            "current_candidates": self.state_store.current_candidates,
            "viable_candidate_count": len(viable_records),
            "remaining_uncertainties": (compact_state.get("latest_snapshot") or {}).get("remaining_uncertainties") or [],
            "total_candidate_count": total_count,
            "eliminated_count": eliminated_count,
            "elimination_rate": round(elimination_rate, 2),
            "candidate_type_hints": candidate_type_hints,
            "question_answer_type_hint": self._infer_question_answer_type(getattr(self, "_question", "") or ""),
        }

    def _infer_candidate_type_hints(self, records: List[Dict[str, Any]]) -> List[str]:
        """Infer the entity type of each candidate from its name/record.

        Returns a list of type labels (e.g., 'person', 'university',
        'organization', 'place', 'year', 'book_title') to help the direction
        critic detect type mismatches between the question's expected answer
        type and the candidate pool.
        """
        type_hints: List[str] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            name = str(record.get("name", "")).strip()
            # Strip parenthetical annotations like "(1330 centuries, CueTracker)"
            clean_name = re.sub(r'\s*\([^)]*\)\s*', '', name).strip()
            institutional_keywords = [
                "university", "institute", "college", "school", "academy",
                "hospital", "centre", "center", "foundation", "society",
                "association", "corporation", "company", "press", "library",
            ]
            name_lower = clean_name.lower()
            # pos6 v17 fix: detect book_title candidates. Book titles typically
            # contain " by <author>" or are long multi-word phrases that don't
            # match the 2-word person pattern, or contain lowercase articles
            # (the/a/an) + multiple words.
            if any(kw in name_lower for kw in [
                " by ", ": ", " a history of", " the tragic", " the story of",
            ]):
                type_hints.append("book_title")
                continue
            if any(kw in name_lower for kw in institutional_keywords):
                type_hints.append("institution")
            elif re.match(r'^\d{3,4}$', clean_name):
                type_hints.append("year")
            elif re.match(r'^[A-Z][a-zA-Z\'\.-]+\s+[A-Z]', clean_name):
                type_hints.append("person")
            else:
                type_hints.append("unknown")
        return type_hints

    def _infer_question_answer_type(self, question: str) -> str:
        """Infer what TYPE of entity the question asks for as the answer.

        BrowseComp questions often DESCRIBE a subject of one type in the body
        but ASK FOR a different type at the end. We check the last sentence
        (the actual question) first, then fall back to the full question.

        Common patterns: 'the name of the player' → person,
        'which university' → institution, 'what year' → year, etc.
        """
        q = (question or "").lower()
        # Split into sentences; the last clause is the actual question.
        # Common separators: '. ', '? '
        clauses = [c.strip() for c in re.split(r'[.?!]\s+', q) if c.strip()]
        ask_clause = clauses[-1] if clauses else q

        # Check the ASK clause (the actual question) first.
        # pos6 v16 fix: check book_title BEFORE person, because "name of the
        # book" and "full title of the book" contain "name of the" which would
        # otherwise match the person pattern and mis-classify as "person".
        if any(kw in ask_clause for kw in ["title of the book", "full title of the book", "title of", "name of the book", "what book", "which book"]):
            return "book_title"
        if any(kw in ask_clause for kw in [
            "the name of the player", "the name of the person", "who is", "who was",
            "the name of the author", "the name of the academic",
            "husband", "wife", "spouse", "full name of", "name of the",
            "the name of the", "whose", "who did", "who wrote", "who directed",
            "who painted", "who composed", "who founded", "who discovered",
        ]):
            return "person"
        if any(kw in ask_clause for kw in ["university", "college", "institute", "school", "academy"]):
            return "institution"
        if any(kw in ask_clause for kw in ["what year", "which year", "in what year", "what date"]):
            return "year"
        if any(kw in ask_clause for kw in ["which country", "what city", "what place", "which place", "where"]):
            return "place"

        # Fallback: scan the full question (description may contain the answer type).
        # But person keywords take priority over institution keywords, since
        # questions often describe institutions but ask for people.
        if any(kw in q for kw in ["title of the book", "full title of the book", "title of", "name of the book", "what book", "which book"]):
            return "book_title"
        if any(kw in q for kw in ["husband", "wife", "spouse", "full name of"]):
            return "person"
        if any(kw in q for kw in ["university", "college", "institute", "school", "academy"]):
            return "institution"
        if any(kw in q for kw in ["what year", "which year", "in what year", "what date"]):
            return "year"
        if any(kw in q for kw in ["which country", "what city", "what place", "which place", "where"]):
            return "place"
        return "unknown"

    def _check_pool_health(self, question: str, iteration: int) -> Optional[Dict[str, str]]:
        """Detect candidate-pool health issues the direction critic may miss.

        Two lightweight heuristic checks (no LLM call):

        1. **Type mismatch**: the question asks for entity type X (e.g.,
           "university") but all candidates are a different type (e.g.,
           "person"). This was the pos7 failure mode: the pool was all Spanish
           studies scholars but the answer was a university.

        2. **Domain monoculture + high elimination**: >60% of candidates
           eliminated and the remaining viable candidates are homogeneous
           (all same type/domain). Suggests the pool was built from a single
           source and needs to be rebuilt from a different angle.

        Returns a feedback message dict when an issue is detected, or None.
        Each issue type fires at most once per run to avoid nagging.
        """
        # Type mismatch check runs in BOTH candidate_generation and
        # candidate_verification: a pool built from wrong-type candidates
        # should be caught as early as possible, before the pipeline wastes
        # verification budget on candidates that can never be the answer.
        if self.workflow_stage not in (self.CANDIDATE_GENERATION, self.CANDIDATE_VERIFICATION):
            return None
        all_records = self._all_candidate_records()
        logger.info(
            f"[Pipeline] _check_pool_health: stage={self.workflow_stage} "
            f"records={len(all_records)} findings_history={len(self.state_store.findings_history)} "
            f"current_candidates={len(self.state_store.current_candidates)}"
        )
        if len(all_records) < 3:
            # Diagnostic: if we have findings but no candidate records,
            # the executor didn't call add_candidates tool. Log the
            # findings summaries to help diagnose.
            if len(self.state_store.findings_history) >= 1:
                for fh in self.state_store.findings_history[-3:]:
                    s = str((fh or {}).get("summary", ""))[:120]
                    nc = ((fh or {}).get("candidate_updates") or {}).get("new_candidates", [])
                    logger.info(f"[Pipeline] _check_pool_health: findings summary={s!r} new_cands={nc}")
            return None

        # Guard: each issue type fires at most once per run.
        if not hasattr(self, "_pool_health_fired"):
            self._pool_health_fired: set = set()

        question_type = self._infer_question_answer_type(question)
        candidate_types = self._infer_candidate_type_hints(all_records)
        viable_records = self._viable_candidate_records()
        eliminated_count = sum(
            1 for r in all_records
            if isinstance(r, dict) and (r.get("status") == "eliminated" or r.get("hard_conflicts"))
        )
        total_count = len(all_records)
        elimination_rate = (eliminated_count / total_count) if total_count else 0.0

        # Check 1: type mismatch (question asks for type X, all candidates are type Y)
        if (
            question_type != "unknown"
            and "type_mismatch" not in self._pool_health_fired
        ):
            non_matching = sum(
                1 for ct in candidate_types
                if ct != "unknown" and ct != question_type
            )
            matching = sum(1 for ct in candidate_types if ct == question_type)
            # If >70% of typed candidates are a different type and none match
            typed_count = sum(1 for ct in candidate_types if ct != "unknown")
            if typed_count >= 3 and matching == 0 and non_matching / typed_count >= 0.7:
                self._pool_health_fired.add("type_mismatch")
                viable_names = [r.get("name", "") for r in viable_records[:3]]
                logger.warning(
                    f"[Pipeline] POOL TYPE MISMATCH: question asks for '{question_type}' "
                    f"but all {typed_count} typed candidates are different types"
                )
                self._record_event_for_trajectory("pool_type_mismatch", iteration, {
                    "question_answer_type": question_type,
                    "candidate_types": candidate_types[:8],
                    "elimination_rate": round(elimination_rate, 2),
                    "forced_stage_rebuild": True,
                })
                # Force the pipeline back to candidate_generation so the
                # planner immediately sees the new stage and generates a
                # search plan targeting the correct entity type. This mirrors
                # the direction critic's rebuild_candidate_pool action but
                # uses a deterministic heuristic (no LLM call).
                self.workflow_stage = self.CANDIDATE_GENERATION
                self.stage_round_counts[self.CANDIDATE_GENERATION] = 0
                self.verification_queue = []
                self.active_candidate = None
                self.active_candidate_rounds = 0
                # pos6 v15: clear wrong-type candidate records so the executor
                # can't keep verifying them and the fallback can't reselect
                # them. The whole point of the rebuild is a fresh candidate
                # search of the CORRECT type. Without clearing, the executor
                # sees the stale wrong-type records and continues verifying
                # them (pos6 p1h: type mismatch fired at iter 0, planner
                # ignored the nudge and jumped to candidate_verification, and
                # the executor kept verifying authors instead of searching
                # for books).
                wrong_type_keys = []
                for key, rec in list(self.state_store.candidate_records.items()):
                    if not isinstance(rec, dict):
                        continue
                    # candidate_type is never persisted on records; infer it
                    # from the name using the same heuristic as
                    # _infer_candidate_type_hints so the clear actually fires.
                    hints = self._infer_candidate_type_hints([rec])
                    ct = hints[0] if hints else "unknown"
                    if ct and ct != "unknown" and ct != question_type:
                        wrong_type_keys.append(key)
                if wrong_type_keys:
                    for key in wrong_type_keys:
                        self.state_store.candidate_records.pop(key, None)
                    # Also prune them from the current/eliminated lists so the
                    # compact_state the planner sees is clean.
                    self.state_store.current_candidates = [
                        n for n in self.state_store.current_candidates
                        if self.state_store._candidate_key(n) not in set(wrong_type_keys)
                    ]
                    self.state_store.eliminated_candidates = [
                        n for n in self.state_store.eliminated_candidates
                        if self.state_store._candidate_key(n) not in set(wrong_type_keys)
                    ]
                logger.info(
                    f"[Pipeline] Forced stage: CANDIDATE_GENERATION reset "
                    f"(type mismatch, iter={iteration}, cleared {len(wrong_type_keys)} wrong-type candidates)"
                )
                return {
                    "role": "user",
                    "content": (
                        f"CANDIDATE POOL TYPE MISMATCH — STAGE RESET\n\n"
                        f"The original question appears to ask for a '{question_type}' as the answer, "
                        f"but ALL current candidates appear to be a different type of entity "
                        f"(persons, organizations, etc.). The correct answer may not be in the "
                        f"current pool at all.\n\n"
                        f"The pipeline has been FORCED back to candidate_generation. "
                        f"You MUST now search for '{question_type}' entities that satisfy the "
                        f"question's constraints. Do NOT propose verifying existing candidates "
                        f"of the wrong type.\n\n"
                        f"Previous viable candidates (wrong type): {json.dumps(viable_names, ensure_ascii=False)}\n"
                        f"Elimination rate: {elimination_rate:.0%} ({eliminated_count}/{total_count})\n\n"
                        f"Search strategy suggestions:\n"
                        f"1. Re-read the original question and identify what TYPE of entity the answer is\n"
                        f"2. Search for '{question_type}' entities matching the question's key constraints\n"
                        f"3. Use different search queries that would surface '{question_type}' results"
                        + (
                            f"\n4. The previous candidates were AUTHORS/PERSONS but the answer must be a "
                            f"BOOK TITLE. For each author previously found as a viable candidate, search "
                            f"explicitly for that author's published BOOKS (e.g. 'Barbara Hodgson books', "
                            f"'Barbara Hodgson bibliography', 'books by <author>') and add each book title "
                            f"as a candidate. A single author may have MULTIPLE books about the same topic — "
                            f"add ALL of them as separate candidates so they can be compared."
                            if question_type == "book_title"
                            else ""
                        )
                    ),
                }

        # Check 2: domain monoculture + high elimination
        # Lowered threshold from 0.6/≤2 to 0.4/≤4 so the rebuild fires earlier,
        # before the pipeline burns all its crawl budget verifying wrong
        # candidates (pos6 v13 root cause: 57% elimination with 3 viable
        # candidates never triggered the rebuild, pipeline ran out of budget
        # at iter 5 with all candidates wrong).
        if (
            "domain_monoculture" not in self._pool_health_fired
            and elimination_rate >= 0.4
            and len(viable_records) <= 4
        ):
            self._pool_health_fired.add("domain_monoculture")
            viable_names = [r.get("name", "") for r in viable_records[:3]]
            # Build elimination-aware feedback: list each eliminated
            # candidate and the reason it was eliminated so the planner
            # knows what didn't work and can search from a different angle.
            eliminated_info = []
            for r in all_records:
                if not isinstance(r, dict):
                    continue
                if r.get("status") == "eliminated" or r.get("hard_conflicts"):
                    ename = r.get("name", "")
                    ereason = str(r.get("elimination_reason") or r.get("supporting_constraints") or "contradicted")[:150]
                    eliminated_info.append(f"  - {ename}: {ereason}")
            eliminated_summary = "\n".join(eliminated_info[:5]) if eliminated_info else "  (no detailed reasons available)"
            logger.warning(
                f"[Pipeline] POOL DOMAIN MONOCULTURE: {elimination_rate:.0%} eliminated, "
                f"{len(viable_records)} viable remaining"
            )
            self._record_event_for_trajectory("pool_domain_monoculture", iteration, {
                "elimination_rate": round(elimination_rate, 2),
                "viable_count": len(viable_records),
                "total_count": total_count,
                "forced_stage_rebuild": True,
            })
            # Force the pipeline back to candidate_generation so the
            # planner searches from a completely different angle.
            self.workflow_stage = self.CANDIDATE_GENERATION
            self.stage_round_counts[self.CANDIDATE_GENERATION] = 0
            self.verification_queue = []
            self.active_candidate = None
            self.active_candidate_rounds = 0
            # Allocate extra search budget for the regeneration round so it
            # can actually search (mirrors _force_pool_rebuild).
            current_search_calls = len(self.query_memory.records)
            extra = 15
            self.max_total_searches = max(self.max_total_searches, current_search_calls + extra)
            self.planner.search_budget += 5
            self.executor.search_budget += 10
            logger.info(
                f"[Pipeline] Forced stage transition: CANDIDATE_VERIFICATION -> "
                f"CANDIDATE_GENERATION (domain monoculture, iter={iteration}, "
                f"+{extra} search budget -> total={self.max_total_searches})"
            )
            # Type-aware guidance: if the question asks for a specific type
            # (e.g. book_title) but candidates were a different type (e.g.
            # person), explicitly tell the planner to search for the correct
            # type.
            type_guidance = ""
            if question_type != "unknown":
                type_guidance = (
                    f"\n5. The answer should be a '{question_type}', but previous "
                    f"candidates were all a different type. Search for "
                    f"'{question_type}' entities directly, not the entities "
                    f"you've been verifying."
                )
            return {
                "role": "user",
                "content": (
                    f"CANDIDATE POOL COLLAPSE — STAGE RESET\n\n"
                    f"{eliminated_count} of {total_count} candidates have been eliminated "
                    f"({elimination_rate:.0%} elimination rate), and only {len(viable_records)} "
                    f"viable candidate(s) remain. The current pool was likely built from a "
                    f"single source or domain and may not contain the correct answer.\n\n"
                    f"ELIMINATED CANDIDATES AND REASONS:\n{eliminated_summary}\n\n"
                    f"The pipeline has been FORCED back to candidate_generation. "
                    f"You MUST search from a COMPLETELY DIFFERENT angle:\n"
                    f"1. Re-read the original question for alternative interpretations\n"
                    f"2. Search for a different TYPE of entity (e.g., institution instead of person)\n"
                    f"3. Use a different source family or search strategy\n"
                    f"4. Consider that the answer may be an upstream entity (publisher, employer, "
                    f"location) rather than the entities you've been verifying"
                    f"{type_guidance}\n\n"
                    f"Remaining viable: {json.dumps(viable_names, ensure_ascii=False)}"
                ),
            }

        return None

    # ------------------------------------------------------------------
    # Reflexion (Shinn et al., 2023) + CRAG (Yan et al., 2024) hooks.
    # ------------------------------------------------------------------
    REFLEXION_PROMPT = (
        "You are a research-agent reflection module. A candidate was just\n"
        "eliminated during verification. Produce ONE short lesson the planner\n"
        "should learn from this failure.\n\n"
        "Original question: {question}\n\n"
        "Eliminated candidate: {candidate_name}\n"
        "Hard conflicts (why it failed): {hard_conflicts}\n"
        "Subtask that produced the failure: {subtask_name}\n"
        "Subtask summary: {subtask_summary}\n\n"
        "Write <=3 sentences covering:\n"
        "1. WHICH constraint the pool is consistently failing on\n"
        "2. WHAT TYPE of entity (person / institution / year / place) is\n"
        "   more likely correct given this failure\n"
        "3. ONE concrete search-query suggestion for the next round\n\n"
        "Respond with plain text only — no JSON, no markdown headers."
    )

    CRAG_PROMPT = (
        "You are a retrieval-relevance assessor (CRAG style). Decide whether\n"
        "the executor's findings actually answer the subtask.\n\n"
        "Subtask goal: {subtask_name}\n"
        "Subtask type: {subtask_type}\n"
        "Findings summary: {findings_summary}\n"
        "Evidence count: {evidence_count}\n"
        "New candidates found: {new_candidate_count}\n"
        "Eliminated candidates: {eliminated_count}\n\n"
        "Output one line in this exact format:\n"
        "verdict=RELEVANT|IRRELEVANT|AMBIGUOUS | hint=<one short sentence, only if IRRELEVANT or AMBIGUOUS>\n\n"
        "RELEVANT means the findings meaningfully advance the subtask\n"
        "(new viable candidates, eliminated a wrong one, or gathered key evidence).\n"
        "IRRELEVANT means the executor looped without producing useful signal —\n"
        "in that case the hint must propose a different search angle."
    )

    def _reflect_on_elimination(
        self,
        eliminated_records: List[Dict[str, Any]],
        subtask_name: str,
        findings: Dict[str, Any],
        iteration: int,
    ) -> Optional[Dict[str, str]]:
        """Reflexion hook: extract a verbal lesson from eliminated candidates.

        Fires only when this iteration eliminated >=1 candidate. Makes ONE
        lightweight LLM call. On any error returns None (no regression).
        """
        if not self._reflexion_enabled or not eliminated_records:
            return None
        if len(self._reflection_notes) >= self._max_reflection_notes:
            return None
        question = getattr(self, "_question", "") or ""
        try:
            # Bundle up to 3 eliminated records into the prompt so a single
            # reflection covers a batch elimination round.
            sample_records = eliminated_records[:3]
            record_summaries = []
            for rec in sample_records:
                record_summaries.append(
                    f"- {rec.get('name', '?')}: "
                    f"conflicts={json.dumps(rec.get('hard_conflicts', [])[:2], ensure_ascii=False)}"
                )
            prompt = self.REFLEXION_PROMPT.format(
                question=question[:400],
                candidate_name="; ".join(r.get("name", "?") for r in sample_records),
                hard_conflicts="\n".join(record_summaries)[:600],
                subtask_name=subtask_name[:120],
                subtask_summary=str(findings.get("summary", ""))[:300],
            )
            resp = chat_completion_with_structuring(
                client=self._rank_client,
                model=self._model_id,
                system_prompt="You are a research reflection assistant.",
                user_prompt=prompt,
                max_tokens=220,
                temperature=0.3,
            )
            note_text = (resp or "").strip()
            if not note_text or len(note_text) < 20:
                return None
            self._reflection_notes.append({
                "iteration": iteration,
                "candidates": [r.get("name", "") for r in sample_records],
                "note": note_text[:300],
            })
            self._record_event_for_trajectory("elimination_reflection", iteration, {
                "candidates": [r.get("name", "") for r in sample_records],
                "note": note_text[:200],
            })
            logger.info(
                f"[Pipeline] REFLEXION iter={iteration} learned: {note_text[:100]}"
            )
            return {
                "role": "user",
                "content": (
                    f"REFLECTION FROM A PRIOR ELIMINATION (apply this lesson):\n"
                    f"{note_text}\n\n"
                    f"Use this when planning the next subtask: prefer the suggested "
                    f"entity type and search angle."
                ),
            }
        except Exception as exc:
            logger.debug(f"[Pipeline] reflexion hook failed (non-fatal): {exc}")
            return None

    def _assess_subtask_relevance(
        self,
        subtask: Dict[str, Any],
        findings: Dict[str, Any],
        iteration: int,
    ) -> Optional[Dict[str, str]]:
        """CRAG hook: assess whether the just-completed subtask's findings
        actually advanced the goal. Returns a corrective feedback message
        when the verdict is IRRELEVANT or AMBIGUOUS, otherwise None.
        """
        if not self._crag_enabled:
            return None
        if len(self._relevance_notes) >= self._max_relevance_notes:
            return None
        # Skip in final_check stage — at that point the executor is wrapping up
        # and "no new candidates" is the expected outcome.
        if self.workflow_stage == self.FINAL_CHECK:
            return None
        try:
            subtask_name = str(subtask.get("subtask") or subtask.get("name", ""))[:120]
            subtask_type = str(
                subtask.get("subtask_type") or subtask.get("type") or subtask.get("mode") or ""
            )[:40]
            cu = (findings or {}).get("candidate_updates", {}) or {}
            new_candidate_count = len(cu.get("new_candidates", []) or [])
            eliminated_count = len(cu.get("eliminated_candidates", []) or [])
            evidence_count = len((findings or {}).get("evidence", []) or [])
            findings_summary = str((findings or {}).get("summary", ""))[:300]
            # Skip the LLM call when findings are obviously useful —
            # new candidates or successful elimination = relevant by definition.
            if new_candidate_count > 0 and eliminated_count > 0:
                return None
            if new_candidate_count >= 2:
                return None
            prompt = self.CRAG_PROMPT.format(
                subtask_name=subtask_name,
                subtask_type=subtask_type,
                findings_summary=findings_summary,
                evidence_count=evidence_count,
                new_candidate_count=new_candidate_count,
                eliminated_count=eliminated_count,
            )
            resp = chat_completion_with_structuring(
                client=self._rank_client,
                model=self._model_id,
                system_prompt="You are a retrieval relevance assessor.",
                user_prompt=prompt,
                max_tokens=120,
                temperature=0.0,
            )
            verdict_line = (resp or "").strip().splitlines()[0] if resp else ""
            verdict = "AMBIGUOUS"
            hint = ""
            if "verdict=" in verdict_line.lower():
                parts = verdict_line.split("|", 1)
                verdict = parts[0].split("=", 1)[1].strip().upper()
                if len(parts) > 1 and "hint=" in parts[1].lower():
                    hint = parts[1].split("=", 1)[1].strip()
            if verdict not in {"IRRELEVANT", "AMBIGUOUS"}:
                return None
            if not hint:
                hint = "Rewrite the search query with more specific keywords."
            self._relevance_notes.append({
                "iteration": iteration,
                "subtask": subtask_name,
                "verdict": verdict,
                "hint": hint[:200],
            })
            self._record_event_for_trajectory("subtask_relevance", iteration, {
                "subtask": subtask_name,
                "verdict": verdict,
                "hint": hint[:200],
            })
            logger.warning(
                f"[Pipeline] CRAG verdict={verdict} iter={iteration} "
                f"subtask='{subtask_name[:60]}' hint='{hint[:80]}'"
            )
            return {
                "role": "user",
                "content": (
                    f"RETRIEVAL RELEVANCE WARNING (CRAG)\n\n"
                    f"The previous subtask '{subtask_name}' produced findings that "
                    f"do not appear to meaningfully advance the goal "
                    f"(verdict: {verdict}).\n\n"
                    f"Corrective hint: {hint}\n\n"
                    f"Rewrite the next search query to target a different angle. "
                    f"Do NOT repeat the same search that produced these findings."
                ),
            }
        except Exception as exc:
            logger.debug(f"[Pipeline] CRAG hook failed (non-fatal): {exc}")
            return None

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
        _t_pr = time.time()
        planner_result = self.planner.run(
            question=question,
            feedback_history=[{"role": "user", "content": feedback_text}],
            compact_state=self.state_store.export_compact_state(),
            workflow_stage=self.workflow_stage,
            stage_context=self._stage_context(),
        )
        if self.trajectory_recorder:
            self.trajectory_recorder.record_planner(messages=self.planner.messages, iteration=iteration, latency_ms=(time.time() - _t_pr) * 1000.0)
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
    model_id = settings().model_id
    recorder = TrajectoryRecorder(model_id=model_id, output_dir="logs/trajectories")
    pipeline = SearchHarnessPipelineV4(api_base=api_base, api_key=api_key, model_id=model_id, trajectory_recorder=recorder,
                                       max_planner_searches=5, max_executor_searches=15, max_total_searches=30)
    result = pipeline.run(
        "In which arid high plateau region did Walther Penck conduct geological fieldwork?",
        max_iterations=4,
        max_crawl_calls=6,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
