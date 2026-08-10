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

import os
import sys
from types import SimpleNamespace

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from search_harness_pipeline_v4 import SearchHarnessPipelineV4  # noqa: E402
from search_agent_v3 import SearchAgentV3  # noqa: E402
from llm_error_utils import classify_infra_error  # noqa: E402


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
