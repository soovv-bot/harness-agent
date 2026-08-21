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
from trajectory.recorder import TrajectoryRecorder
from llm.compat import chat_completion_with_structuring
from llm.factory import build_openai_client

from query_history import QueryHistoryMemory
from query_critic import QueryCritic
from search_crawl_controller import SearchCrawlController
from tools.search_tools import authoritative_domains_in, high_weight_sources_in  # type: ignore

from pipeline import candidates as _candidates
from pipeline import feedback as _feedback
from pipeline import finish as _finish
from pipeline import stages as _stages
from pipeline import tracing as _tracing
from pipeline import verification as _verification


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

    # RD step4b: pure helpers extracted into pipeline/{tracing, finish, ...}.
    # Re-bound as class attributes to keep private-name call sites working.
    _record_candidate_snapshot_for_trajectory = _tracing.record_candidate_snapshot_for_trajectory
    _record_event_for_trajectory = _tracing.record_event_for_trajectory
    _record_iteration_summary_for_trajectory = _tracing.record_iteration_summary_for_trajectory

    _finish_with_answer = _finish.finish_with_answer
    _best_effort_finish = _finish.best_effort_finish
    _build_wrap_up_state_excerpt = _finish.build_wrap_up_state_excerpt
    _try_protocol_wrap_up = _finish.try_protocol_wrap_up
    _looks_solved = _finish.looks_solved

    _stage_context = _stages.stage_context
    _workflow_stage_from_plan = _stages.workflow_stage_from_plan
    _sync_workflow_stage_from_plan = _stages.sync_workflow_stage_from_plan
    _prepare_plan_for_stage = _stages.prepare_plan_for_stage
    _normalize_plan_steps_for_stage = _stages.normalize_plan_steps_for_stage
    _should_advance_stage = _stages.should_advance_stage
    _advance_stage = _stages.advance_stage
    _build_stage_transition_feedback = _stages.build_stage_transition_feedback
    _maybe_advance_stage = _stages.maybe_advance_stage

    _build_stagnation_feedback = _feedback.build_stagnation_feedback
    _build_gap_summary = _feedback.build_gap_summary
    _direction_critic_context = _feedback.direction_critic_context
    _reflect_on_elimination = _feedback.reflect_on_elimination
    _assess_subtask_relevance = _feedback.assess_subtask_relevance
    _apply_direction_critic_action = _feedback.apply_direction_critic_action

    _force_pool_rebuild = _candidates.force_pool_rebuild
    _mark_candidate_eliminated = _candidates.mark_candidate_eliminated
    _fallback_answer_from_pool = _candidates.fallback_answer_from_pool
    _all_candidate_records = _candidates.all_candidate_records
    _viable_candidate_records = _candidates.viable_candidate_records
    _current_candidate_record = _candidates.current_candidate_record
    _should_rotate_active_candidate = _candidates.should_rotate_active_candidate
    _rotate_active_candidate = _candidates.rotate_active_candidate
    _should_rebuild_candidate_pool = _candidates.should_rebuild_candidate_pool
    _infer_candidate_type_hints = _candidates.infer_candidate_type_hints
    _infer_question_answer_type = _candidates.infer_question_answer_type
    _check_pool_health = _candidates.check_pool_health

    _consume_stage_answer = _verification.consume_stage_answer
    _pipeline_status_for_answer = _verification.pipeline_status_for_answer
    _verify_planner_answer = _verification.verify_planner_answer
    _gate_verification_short_circuit = _verification.gate_verification_short_circuit
    _initialize_verification_queue = _verification.initialize_verification_queue
    _rank_verification_queue_by_question = _verification.rank_verification_queue_by_question
    _verified_candidate_early_stop = _verification.verified_candidate_early_stop
    _tied_candidate_blocks_early_stop = _verification.tied_candidate_blocks_early_stop
    _authoritative_consensus_early_stop = _verification.authoritative_consensus_early_stop

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
