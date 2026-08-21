"""Regression smoke tests for P0/P1 subtask-behavior optimizations.

Covers the five optimization passes that fixed pos5 (Ding Junhui) regressions:
- P0-A: _fallback_answer_from_pool salvages a candidate when planner emits Unknown
- P0-B: classify_infra_error routes transient errors to retry
- P1-B: _tied_candidate_blocks_early_stop prevents premature convergence
- P1-C: build_subtask_prompt forces page-evidence crawl in verification
- P1-D: _should_advance_stage force-advances when generation budget exhausted

Run: pytest tests/test_subtask_optimizations.py -v

These are fast (no real LLM) unit tests — run after every code change to catch
regressions before the ~45min pos5 end-to-end test.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from search_harness_pipeline_v4 import SearchHarnessPipelineV4  # noqa: E402
from search_agent_v3 import SearchAgentV3  # noqa: E402
from llm.errors import classify_infra_error  # noqa: E402


def _make_pipeline(fake_llm, responder=None):
    if responder is None:
        responder = lambda kwargs: SimpleNamespace(
            role="assistant", content="", reasoning_content=None, tool_calls=[])
    fake_llm(responder)
    p = SearchHarnessPipelineV4(
        api_base="x", api_key="y", model_id="GLM-5.2",
        max_planner_searches=2, max_executor_searches=4, max_total_searches=8,
    )
    # stage_round_counts is initialized inside run(), not __init__; set it
    # explicitly so unit tests on _should_advance_stage can exercise the
    # force-advance branch without driving a full pipeline run().
    p.stage_round_counts = {
        p.CANDIDATE_GENERATION: 0,
        p.CANDIDATE_VERIFICATION: 0,
        p.FINAL_CHECK: 0,
    }
    # completed_verification_candidates is also initialized in run(), not __init__
    p.completed_verification_candidates = []
    return p


def _add_candidate(p, name, verification_status="unverified", support=None,
                   hard_conflicts=None, evidence=None, unresolved=None):
    """Insert a candidate record directly into the state store."""
    p.state_store.set_question("Q?")
    key = p.state_store._candidate_key(name)
    p.state_store.candidate_records[key] = {
        "candidate": name,
        "name": name,
        "status": "eliminated" if hard_conflicts else "active",
        "verification_status": verification_status,
        "supporting_constraints": support or [],
        "hard_conflicts": hard_conflicts or [],
        "evidence": evidence or [],
        "unresolved_constraints": unresolved or [],
    }
    if not hard_conflicts:
        if name not in p.state_store.current_candidates:
            p.state_store.current_candidates.append(name)


# ════════════════════════════════════════════════════════════════════════════
# P0-A: _fallback_answer_from_pool
# ════════════════════════════════════════════════════════════════════════════

class TestFallbackAnswerFromPool:
    def test_no_viable_returns_none(self, fake_llm):
        p = _make_pipeline(fake_llm)
        assert p._fallback_answer_from_pool() is None

    def test_returns_best_viable(self, fake_llm):
        p = _make_pipeline(fake_llm)
        _add_candidate(p, "Alpha", verification_status="unverified")
        _add_candidate(p, "Beta", verification_status="verified", support=["c1"])
        assert p._fallback_answer_from_pool() == "Beta"

    def test_verified_beats_partial_beats_unverified(self, fake_llm):
        p = _make_pipeline(fake_llm)
        _add_candidate(p, "Unverified", verification_status="unverified", support=["c1"])
        _add_candidate(p, "Partial", verification_status="partial", support=["c1"])
        _add_candidate(p, "Verified", verification_status="verified", support=["c1"])
        assert p._fallback_answer_from_pool() == "Verified"

    def test_skips_eliminated(self, fake_llm):
        p = _make_pipeline(fake_llm)
        _add_candidate(p, "Good", verification_status="partial")
        _add_candidate(p, "Bad", verification_status="verified",
                       hard_conflicts=["contradiction"])
        assert p._fallback_answer_from_pool() == "Good"

    def test_higher_support_wins_when_same_status(self, fake_llm):
        p = _make_pipeline(fake_llm)
        _add_candidate(p, "Less", verification_status="partial", support=["c1"])
        _add_candidate(p, "More", verification_status="partial", support=["c1", "c2", "c3"])
        assert p._fallback_answer_from_pool() == "More"


# ════════════════════════════════════════════════════════════════════════════
# P0-B: classify_infra_error
# ════════════════════════════════════════════════════════════════════════════

class TestClassifyInfraError:
    def test_rate_limit_429(self):
        assert classify_infra_error("Error code: 429 — too many requests") == "rate_limit"

    def test_network_timeout(self):
        assert classify_infra_error("Connection timed out") == "network_error"

    def test_service_503(self):
        assert classify_infra_error("Error code: 503 service unavailable") == "service_error"

    def test_auth_401_not_retriable(self):
        # auth errors must NOT be classified as network/service/rate_limit
        # (P0-B only retries transient infra errors, not auth)
        assert classify_infra_error("Error code: 401 invalid api key") == "auth_error"

    def test_unknown_returns_none(self):
        assert classify_infra_error("some random message") is None

    def test_empty_returns_none(self):
        assert classify_infra_error("") is None
        assert classify_infra_error(None) is None


# ════════════════════════════════════════════════════════════════════════════
# P1-B: _tied_candidate_blocks_early_stop
# ════════════════════════════════════════════════════════════════════════════

class TestTiedCandidateBlocksEarlyStop:
    def test_single_viable_no_block(self, fake_llm):
        p = _make_pipeline(fake_llm)
        rec = {"candidate": "Solo", "verification_status": "verified", "supporting_constraints": ["c1"]}
        assert p._tied_candidate_blocks_early_stop(rec, [rec], iteration=3, max_iterations=10) is False

    def test_unverified_sibling_blocks(self, fake_llm):
        p = _make_pipeline(fake_llm)
        trigger = {"candidate": "A", "verification_status": "verified", "supporting_constraints": ["c1"]}
        sibling = {"candidate": "B", "verification_status": "unverified", "supporting_constraints": ["c1"]}
        assert p._tied_candidate_blocks_early_stop(trigger, [trigger, sibling], iteration=3, max_iterations=10) is True

    def test_budget_release_when_all_siblings_verified(self, fake_llm):
        p = _make_pipeline(fake_llm)
        trigger = {"candidate": "A", "verification_status": "verified", "supporting_constraints": ["c1"]}
        sibling = {"candidate": "B", "verification_status": "contradicted", "supporting_constraints": ["c1"]}
        # near budget cap (iteration 9 of 10), sibling contradicted → release
        assert p._tied_candidate_blocks_early_stop(trigger, [trigger, sibling], iteration=9, max_iterations=10) is False

    def test_budget_holds_when_sibling_unverified(self, fake_llm):
        p = _make_pipeline(fake_llm)
        trigger = {"candidate": "A", "verification_status": "verified", "supporting_constraints": ["c1"]}
        sibling = {"candidate": "B", "verification_status": "unverified", "supporting_constraints": ["c1"]}
        # near budget cap BUT unverified sibling remains → top-2 gate holds
        assert p._tied_candidate_blocks_early_stop(trigger, [trigger, sibling], iteration=9, max_iterations=10) is True

    def test_tied_support_with_unresolved_blocks(self, fake_llm):
        p = _make_pipeline(fake_llm)
        trigger = {"candidate": "A", "verification_status": "partial",
                    "supporting_constraints": ["c1", "c2"], "unresolved_constraints": ["c3"]}
        sibling = {"candidate": "B", "verification_status": "verified",
                   "supporting_constraints": ["c1", "c2"], "unresolved_constraints": ["c3"]}
        # trigger partial + unresolved, sibling comparable support + unresolved → block
        assert p._tied_candidate_blocks_early_stop(trigger, [trigger, sibling], iteration=4, max_iterations=10) is True


# ════════════════════════════════════════════════════════════════════════════
# P1-C: build_subtask_prompt crawl nudge
# ════════════════════════════════════════════════════════════════════════════

class TestBuildSubtaskPromptCrawlNudge:
    def _make_agent(self, fake_llm):
        # build_subtask_prompt is a pure text method — create an
        # uninitialized instance so we don't need the full dependency graph
        # (state_store, query_critic, crawl_controller, ...).
        agent = object.__new__(SearchAgentV3)
        return agent

    def test_verification_prompt_has_page_evidence_rule(self, fake_llm):
        agent = self._make_agent(fake_llm)
        subtask = {"subtask": "Verify Ding Junhui's maximum breaks", "subtask_type": "candidate_verification"}
        prompt = agent.build_subtask_prompt("Q?", {"phase": "candidate_verification"}, subtask)
        assert "Page evidence required" in prompt
        assert "visit_urls" in prompt

    def test_verification_prompt_lists_subtask_urls(self, fake_llm):
        agent = self._make_agent(fake_llm)
        subtask = {"subtask": "Verify https://en.wikipedia.org/wiki/Ding_Junhui career",
                   "subtask_type": "candidate_verification"}
        prompt = agent.build_subtask_prompt("Q?", {"phase": "candidate_verification"}, subtask)
        assert "Required URLs to visit" in prompt
        assert "en.wikipedia.org/wiki/Ding_Junhui" in prompt

    def test_expansion_prompt_no_page_evidence_rule(self, fake_llm):
        agent = self._make_agent(fake_llm)
        subtask = {"subtask": "Search for snooker players", "subtask_type": "candidate_expansion"}
        prompt = agent.build_subtask_prompt("Q?", {"phase": "candidate_generation"}, subtask)
        assert "Page evidence required" not in prompt


# ════════════════════════════════════════════════════════════════════════════
# P1-F: anti-premature-elimination planner prompt (pos4 Coverdale regression)
# ════════════════════════════════════════════════════════════════════════════

class TestPlannerAntiPrematureElimination:
    """P1-F: the candidate_generation stage message must instruct the planner
    not to silently exclude candidates from reasoning (the pos4 v2 root cause:
    planner reasoned 'David Coverdale: not art college' without a search and
    never issued a verification subtask, dropping the correct answer)."""

    def _make_planner(self):
        from planning_agent_v3 import PlanningAgentV3
        return object.__new__(PlanningAgentV3)

    def test_generation_message_has_anti_elimination_directive(self):
        planner = self._make_planner()
        msg = planner._build_workflow_stage_message(
            "candidate_generation",
            {"generation_round": 1, "generation_budget": 2, "current_candidate_count": 3},
        )
        content = msg["content"]
        assert "anti-premature-elimination" in content.lower()
        assert "Do NOT silently exclude" in content

    def test_generation_message_requires_per_member_enumeration(self):
        planner = self._make_planner()
        msg = planner._build_workflow_stage_message(
            "candidate_generation",
            {"generation_round": 1, "generation_budget": 2, "current_candidate_count": 3},
        )
        content = msg["content"]
        assert "per-member" in content.lower() or "enumerate its members" in content.lower()

    def test_verification_message_unchanged(self):
        """The anti-elimination directive is only on candidate_generation;
        candidate_verification message should not carry it."""
        planner = self._make_planner()
        msg = planner._build_workflow_stage_message(
            "candidate_verification",
            {"viable_candidate_count": 2, "active_candidate": "X",
             "candidate_verification_round": 1, "verification_queue_remaining": 1},
        )
        assert "anti-premature-elimination" not in msg["content"].lower()


# ════════════════════════════════════════════════════════════════════════════
# P1-F: salvage clears stale error_type (protocol_error cleanup)
# ════════════════════════════════════════════════════════════════════════════

class TestSalvageClearsErrorType:
    """P1-F: when _best_effort_finish salvages a candidate from the pool after
    the finalizer returned Unknown (e.g. due to a transient LLM NameError), the
    stale error_type must be cleared so the pipeline reports finished, not
    protocol_error. The salvaged answer is graded on its own merits."""

    def test_salvage_clears_protocol_error(self, fake_llm):
        from search_finalizer import FinalizationResult
        from unittest.mock import MagicMock
        p = _make_pipeline(fake_llm)
        _add_candidate(p, "Whitesnake", verification_status="verified", support=["c1"])
        # Mock finalizer returns Unknown with protocol_error (simulating the
        # NameError path), then salvage should recover "Whitesnake" and clear
        # the error_type.
        fake_final = FinalizationResult(
            status="best_effort", answer="Unknown", confidence="none",
            reason="Finalizer LLM failed: name 'logger' is not defined",
            remaining_uncertainty="", supporting_evidence=[],
            error_type="protocol_error",
        )
        p.finalizer = MagicMock()
        p.finalizer.finalize.return_value = fake_final
        # Minimal stubs to keep _best_effort_finish from touching real infra
        p._looks_solved = lambda state: False
        p._record_event_for_trajectory = lambda *a, **k: None
        p._record_candidate_snapshot_for_trajectory = lambda *a, **k: None
        p.trajectory_recorder = None
        result = p._best_effort_finish("Q?", {}, 10, {"trigger": "max_iterations_reached"})
        # Salvaged answer recovered
        assert "Whitesnake" in result["answer"]
        # error_type cleared so pipeline_status is finished, not protocol_error
        assert result["status"] == "finished"
        assert result["failure_category"] != "protocol_error"


# ════════════════════════════════════════════════════════════════════════════
# P1-F: finalizer _infer_uncertainty defensive guards
# ════════════════════════════════════════════════════════════════════════════

class TestFinalizerUncertaintyGuards:
    """P1-F: _infer_uncertainty crashed with AttributeError when
    pool_assessment was a string (planner emitted text instead of dict),
    which cascaded through finalize()'s except block and killed the task.
    The fix guards plan/latest_snapshot/pool_assessment/findings with
    isinstance checks."""

    def _make_finalizer(self):
        from search_finalizer import SearchFinalizer
        return object.__new__(SearchFinalizer)

    def test_string_pool_assessment(self):
        f = self._make_finalizer()
        state = {"current_plan": {"pool_assessment": "insufficient candidates"}}
        assert isinstance(f._infer_uncertainty(state), str)

    def test_string_current_plan(self):
        f = self._make_finalizer()
        state = {"current_plan": "no plan yet"}
        assert isinstance(f._infer_uncertainty(state), str)

    def test_string_latest_snapshot(self):
        f = self._make_finalizer()
        state = {"latest_snapshot": "snapshot text"}
        assert isinstance(f._infer_uncertainty(state), str)

    def test_string_finding_in_recent_findings(self):
        f = self._make_finalizer()
        state = {"recent_findings": ["finding string not dict"]}
        assert isinstance(f._infer_uncertainty(state), str)


# ════════════════════════════════════════════════════════════════════════════
# P1-D: _should_advance_stage force-advance
# ════════════════════════════════════════════════════════════════════════════

class TestShouldAdvanceStageForceAdvance:
    def test_ready_to_advance_always_returns_true(self, fake_llm):
        p = _make_pipeline(fake_llm)
        p.workflow_stage = p.CANDIDATE_GENERATION
        plan = {"stage_status": "ready_to_advance"}
        assert p._should_advance_stage(plan, {}) is True

    def test_continue_under_budget_returns_false(self, fake_llm):
        p = _make_pipeline(fake_llm)
        p.workflow_stage = p.CANDIDATE_GENERATION
        p.stage_round_counts[p.CANDIDATE_GENERATION] = 1  # round 2 of 2
        _add_candidate(p, "A"); _add_candidate(p, "B"); _add_candidate(p, "C")
        plan = {"stage_status": "continue"}
        assert p._should_advance_stage(plan, {}) is False

    def test_force_advance_when_budget_exhausted(self, fake_llm):
        p = _make_pipeline(fake_llm)
        p.workflow_stage = p.CANDIDATE_GENERATION
        p.stage_round_counts[p.CANDIDATE_GENERATION] = 3  # round 4 > max 2
        _add_candidate(p, "A"); _add_candidate(p, "B"); _add_candidate(p, "C")
        plan = {"stage_status": "continue"}
        assert p._should_advance_stage(plan, {}) is True

    def test_no_force_advance_when_too_few_viable(self, fake_llm):
        p = _make_pipeline(fake_llm)
        p.workflow_stage = p.CANDIDATE_GENERATION
        p.stage_round_counts[p.CANDIDATE_GENERATION] = 5  # way over budget
        _add_candidate(p, "A")  # only 1 viable < 2
        plan = {"stage_status": "continue"}
        assert p._should_advance_stage(plan, {}) is False


# ════════════════════════════════════════════════════════════════════════════
# P1-E: Candidate rotation in concurrent verification path
# ════════════════════════════════════════════════════════════════════════════

class TestCandidateRotation:
    """Regression tests for the concurrent-path rotation fix.

    Root cause: the concurrent batch path incremented active_candidate_rounds
    but never called _maybe_advance_stage, so _should_rotate_active_candidate
    never fired — the planner looped on the same candidate for all remaining
    iterations (pos5: 9 iterations all on "Shaun Murphy", Ding Junhui never
    verified).
    """

    def test_should_rotate_after_two_rounds(self, fake_llm):
        p = _make_pipeline(fake_llm)
        p.workflow_stage = p.CANDIDATE_VERIFICATION
        p.active_candidate = "Shaun Murphy"
        p.active_candidate_rounds = 2
        _add_candidate(p, "Shaun Murphy")
        plan = {"stage_status": "continue"}
        assert p._should_rotate_active_candidate(plan, {}) is True

    def test_should_not_rotate_after_one_round(self, fake_llm):
        p = _make_pipeline(fake_llm)
        p.workflow_stage = p.CANDIDATE_VERIFICATION
        p.active_candidate = "Shaun Murphy"
        p.active_candidate_rounds = 1
        _add_candidate(p, "Shaun Murphy")
        plan = {"stage_status": "continue"}
        assert p._should_rotate_active_candidate(plan, {}) is False

    def test_should_rotate_on_hard_conflicts(self, fake_llm):
        p = _make_pipeline(fake_llm)
        p.workflow_stage = p.CANDIDATE_VERIFICATION
        p.active_candidate = "Shaun Murphy"
        p.active_candidate_rounds = 0
        _add_candidate(p, "Shaun Murphy", hard_conflicts=["not_a_snooker_player"])
        compact = p.state_store.export_compact_state()
        plan = {"stage_status": "continue"}
        assert p._should_rotate_active_candidate(plan, compact) is True

    def test_should_rotate_on_ready_to_advance(self, fake_llm):
        p = _make_pipeline(fake_llm)
        p.workflow_stage = p.CANDIDATE_VERIFICATION
        p.active_candidate = "Shaun Murphy"
        p.active_candidate_rounds = 0
        _add_candidate(p, "Shaun Murphy")
        plan = {"stage_status": "ready_to_advance"}
        assert p._should_rotate_active_candidate(plan, {}) is True

    def test_rotate_moves_to_next_in_queue(self, fake_llm):
        p = _make_pipeline(fake_llm)
        p.workflow_stage = p.CANDIDATE_VERIFICATION
        p.active_candidate = "Shaun Murphy"
        p.active_candidate_rounds = 2
        _add_candidate(p, "Shaun Murphy")
        _add_candidate(p, "Ding Junhui")
        p.verification_queue = ["Ding Junhui"]
        compact = p.state_store.export_compact_state()
        rotated = p._rotate_active_candidate(compact)
        assert rotated is True
        assert p.active_candidate == "Ding Junhui"
        assert p.active_candidate_rounds == 0

    def test_rotate_returns_false_when_queue_empty(self, fake_llm):
        p = _make_pipeline(fake_llm)
        p.workflow_stage = p.CANDIDATE_VERIFICATION
        p.active_candidate = "Shaun Murphy"
        p.active_candidate_rounds = 2
        _add_candidate(p, "Shaun Murphy")
        p.verification_queue = []
        compact = p.state_store.export_compact_state()
        rotated = p._rotate_active_candidate(compact)
        assert rotated is False

    def test_rotate_skips_completed_candidates(self, fake_llm):
        p = _make_pipeline(fake_llm)
        p.workflow_stage = p.CANDIDATE_VERIFICATION
        p.active_candidate = "Shaun Murphy"
        p.active_candidate_rounds = 2
        _add_candidate(p, "Shaun Murphy")
        _add_candidate(p, "Judd Trump")
        _add_candidate(p, "Ding Junhui")
        p.completed_verification_candidates = ["Judd Trump"]
        p.verification_queue = ["Judd Trump", "Ding Junhui"]
        compact = p.state_store.export_compact_state()
        rotated = p._rotate_active_candidate(compact)
        assert rotated is True
        assert p.active_candidate == "Ding Junhui"
