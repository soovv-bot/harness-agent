"""Pipeline-level tests for SearchHarnessPipelineV4.

Three tiers:
1. Pure-logic unit tests (no LLM): answer-status parsing, stop conditions,
   stage-aware plan preparation, finish return shape.
2. State-store tests: candidate elimination on hard_conflicts, promotion,
   and the finalizer bug fix (skip eliminated candidates).
3. Integration: a scripted LLM drives an early-answer run end-to-end.

Run: pytest tests/test_pipeline.py -v
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
from search_memory import SearchStateStore  # noqa: E402


def _make_pipeline(fake_llm, responder=None):
    """Build a pipeline whose agents all use the fake LLM client.

    ``responder`` defaults to an empty-content responder (safe no-op).
    """
    if responder is None:
        responder = lambda kwargs: SimpleNamespace(
            role="assistant", content="", reasoning_content=None, tool_calls=[])
    fake_llm(responder)
    return SearchHarnessPipelineV4(
        api_base="x", api_key="y", model_id="GLM-5.2",
        max_planner_searches=2, max_executor_searches=4, max_total_searches=8,
    )


# ──────────────────────────────────────────────────────────────────────────
# Tier 1: Pure-logic unit tests (no LLM calls)
# ──────────────────────────────────────────────────────────────────────────

class TestPipelineStatusForAnswer:
    def test_plain_text_finished(self, fake_llm):
        p = _make_pipeline(fake_llm)
        assert p._pipeline_status_for_answer("The answer is 42") == "finished"

    def test_empty_is_unfinished(self, fake_llm):
        p = _make_pipeline(fake_llm)
        assert p._pipeline_status_for_answer("") == "unfinished"
        assert p._pipeline_status_for_answer("   ") == "unfinished"

    def test_unknown_is_unfinished(self, fake_llm):
        p = _make_pipeline(fake_llm)
        for val in ["unknown", "Unknown", "UNK", "N/A", "none", "null"]:
            assert p._pipeline_status_for_answer(val) == "unfinished"

    def test_json_solved_is_finished(self, fake_llm):
        p = _make_pipeline(fake_llm)
        import json
        ans = json.dumps({"answer": "Albert Einstein", "status": "solved"})
        assert p._pipeline_status_for_answer(ans) == "finished"

    def test_json_unsolved_status_is_unfinished(self, fake_llm):
        p = _make_pipeline(fake_llm)
        import json
        ans = json.dumps({"answer": "maybe", "status": "needs_more_info"})
        assert p._pipeline_status_for_answer(ans) == "unfinished"

    def test_json_infra_error(self, fake_llm):
        p = _make_pipeline(fake_llm)
        import json
        ans = json.dumps({"answer": "", "status": "infra_error"})
        assert p._pipeline_status_for_answer(ans) == "infra_error"


class TestCheckStop:
    def test_max_iterations_reached(self, fake_llm):
        p = _make_pipeline(fake_llm)
        stop = p._check_stop(iteration=5, max_iterations=5, max_crawl_calls=12)
        assert stop is not None
        assert stop["trigger"] == "max_iterations_reached"

    def test_no_trigger_under_budget(self, fake_llm):
        p = _make_pipeline(fake_llm)
        stop = p._check_stop(iteration=0, max_iterations=6, max_crawl_calls=12)
        assert stop is None

    def test_max_total_searches_reached(self, fake_llm):
        p = _make_pipeline(fake_llm)
        p.max_total_searches = 2
        # Simulate 3 search records in query memory.
        for i in range(3):
            p.query_memory.record(
                query=f"q{i}", phase="candidate_generation", subtask="s",
                results_summary="", new_source_families=[], new_candidates=[],
                result_quality="medium", led_to_crawl=False, crawl_urls=[])
        stop = p._check_stop(iteration=0, max_iterations=6, max_crawl_calls=12)
        assert stop is not None
        assert stop["trigger"] == "max_total_searches_reached"

    def test_max_crawl_calls_reached(self, fake_llm):
        p = _make_pipeline(fake_llm)
        # One search record that led to 5 crawls.
        p.query_memory.record(
            query="q", phase="candidate_generation", subtask="s",
            results_summary="", new_source_families=[], new_candidates=[],
            result_quality="medium", led_to_crawl=False,
            crawl_urls=["u1", "u2", "u3", "u4", "u5"])
        stop = p._check_stop(iteration=0, max_iterations=6, max_crawl_calls=4)
        assert stop is not None
        assert stop["trigger"] == "max_crawl_calls_reached"


class TestPreparePlanForStage:
    def test_generation_sets_default_phase(self, fake_llm):
        p = _make_pipeline(fake_llm)
        p.workflow_stage = p.CANDIDATE_GENERATION
        # _prepare_plan_for_stage short-circuits on falsy plan, so pass non-empty.
        prepared = p._prepare_plan_for_stage({"steps": []})
        assert prepared["phase"] == p.CANDIDATE_GENERATION
        assert prepared["workflow_stage"] == p.CANDIDATE_GENERATION
        assert "pool_assessment" in prepared

    def test_verification_keeps_phase_and_active_candidate(self, fake_llm):
        p = _make_pipeline(fake_llm)
        p.workflow_stage = p.CANDIDATE_VERIFICATION
        p.active_candidate = "AlphaEntity"
        prepared = p._prepare_plan_for_stage({"phase": "verification"})
        assert prepared["phase"] == "verification"
        assert prepared["active_candidate"] == "AlphaEntity"

    def test_final_check_sets_phase(self, fake_llm):
        p = _make_pipeline(fake_llm)
        p.workflow_stage = p.FINAL_CHECK
        prepared = p._prepare_plan_for_stage({"steps": []})
        assert prepared["phase"] == "final_check"

    def test_empty_plan_short_circuits(self, fake_llm):
        p = _make_pipeline(fake_llm)
        # Falsy plan is returned as-is (no mutation).
        assert p._prepare_plan_for_stage({}) == {}


class TestFinishWithAnswer:
    def test_returns_expected_shape(self, fake_llm):
        p = _make_pipeline(fake_llm)
        result = p._finish_with_answer("The answer", iterations=3)
        assert result["answer"] == "The answer"
        assert result["iterations"] == 3
        assert result["status"] == "finished"
        assert "state" in result


# ──────────────────────────────────────────────────────────────────────────
# Tier 2: State-store candidate elimination + finalizer bug fix
# ──────────────────────────────────────────────────────────────────────────

class TestCandidateElimination:
    def test_hard_conflicts_eliminate_candidate(self, fake_llm):
        p = _make_pipeline(fake_llm)
        p.state_store.set_question("Q?")
        p.state_store._merge_candidate_assessment({
            "name": "AlphaEntity", "status": "active",
            "supporting_constraints": ["c1"], "hard_conflicts": [],
        })
        assert "AlphaEntity" in p.state_store.current_candidates
        p.state_store._merge_candidate_assessment({
            "name": "AlphaEntity", "status": "active",
            "hard_conflicts": ["contradicts constraint X"],
        })
        # hard_conflicts -> eliminated + removed from current_candidates.
        assert "AlphaEntity" in p.state_store.eliminated_candidates
        assert "AlphaEntity" not in p.state_store.current_candidates
        # candidate_records keys are lowercased via _candidate_key.
        rec = p.state_store.candidate_records.get("alphaentity")
        assert rec is not None
        assert rec["status"] == "eliminated"
        assert rec["verification_status"] == "contradicted"
        assert "contradicts constraint X" in rec["hard_conflicts"]

    def test_active_status_promotes_candidate(self, fake_llm):
        p = _make_pipeline(fake_llm)
        p.state_store.set_question("Q?")
        p.state_store._merge_candidate_assessment({
            "name": "BetaEntity", "status": "viable",
        })
        assert "BetaEntity" in p.state_store.current_candidates

    def test_hard_conflicts_accumulate_and_block_reactivation(self, fake_llm):
        # Once hard_conflicts are recorded they accumulate (never cleared),
        # so a later "active" assessment cannot revive the candidate.
        p = _make_pipeline(fake_llm)
        p.state_store.set_question("Q?")
        p.state_store._merge_candidate_assessment({
            "name": "GammaEntity", "status": "active", "hard_conflicts": ["bad"],
        })
        assert "GammaEntity" in p.state_store.eliminated_candidates
        p.state_store._merge_candidate_assessment({
            "name": "GammaEntity", "status": "active", "hard_conflicts": [],
        })
        assert "GammaEntity" in p.state_store.eliminated_candidates
        assert "GammaEntity" not in p.state_store.current_candidates

    def test_eliminated_status_without_conflicts_is_revived(self, fake_llm):
        # Quirk: passing status="eliminated" with NO hard_conflicts sets
        # eliminated then the elif branch immediately revives it to active.
        # The only durable elimination path is via hard_conflicts.
        p = _make_pipeline(fake_llm)
        p.state_store.set_question("Q?")
        p.state_store._merge_candidate_assessment({
            "name": "DeltaEntity", "status": "eliminated", "hard_conflicts": [],
        })
        # Net effect: revived to active (eliminate then elif-revive in one call).
        assert "DeltaEntity" in p.state_store.current_candidates
        assert "DeltaEntity" not in p.state_store.eliminated_candidates


class TestFinalizerSkipsEliminated:
    """Verify the bug fix: finalizer must not pick an eliminated candidate as the answer."""

    def test_build_prompt_uses_viable_candidate(self, fake_llm):
        from search_finalizer import SearchFinalizer
        f = SearchFinalizer(api_base="x", api_key="y", model_id="GLM-5.2")
        # Use the real state store so the exported shape matches production.
        store = SearchStateStore(keep_recent_observations=3)
        store.set_question("Q?")
        # Active candidate.
        store._merge_candidate_assessment({
            "name": "ActiveOne", "status": "active",
            "supporting_constraints": ["c1"], "hard_conflicts": [],
        })
        # Eliminated candidate (hard_conflict auto-eliminates).
        store._merge_candidate_assessment({
            "name": "BadOne", "status": "active",
            "hard_conflicts": ["contradicts constraint X"],
        })
        compact = store.export_compact_state()
        prompt = f._build_prompt(question="Who is the answer?", compact_state=compact,
                                  budget_status={"trigger": "max_iterations_reached"}, mode="best_effort")
        # The "Answer:" line must name the active candidate, not the eliminated one.
        assert "Answer: ActiveOne" in prompt
        assert "Answer: BadOne" not in prompt

    def test_all_eliminated_yields_unknown(self, fake_llm):
        from search_finalizer import SearchFinalizer
        f = SearchFinalizer(api_base="x", api_key="y", model_id="GLM-5.2")
        store = SearchStateStore(keep_recent_observations=3)
        store.set_question("Q?")
        store._merge_candidate_assessment({
            "name": "OnlyBad", "status": "active", "hard_conflicts": ["conflict"],
        })
        compact = store.export_compact_state()
        prompt = f._build_prompt(question="Q?", compact_state=compact,
                                  budget_status={"trigger": "max_iterations_reached"}, mode="best_effort")
        assert "Answer: Unknown" in prompt


# ──────────────────────────────────────────────────────────────────────────
# Tier 3: Integration — scripted LLM drives an early-answer run
# ──────────────────────────────────────────────────────────────────────────

class TestPipelineEarlyAnswer:
    def test_planner_answer_finishes_immediately(self, fake_llm):
        # Script the LLM to return an <answer> on the very first planner call.
        # chat_completion_with_structuring returns after one call when content
        # is populated, so only one LLM call is needed.
        def responder(kwargs):
            return SimpleNamespace(
                role="assistant",
                content="<answer>Albert Einstein</answer>",
                reasoning_content=None, tool_calls=[],
            )
        p = _make_pipeline(fake_llm, responder)
        result = p.run(question="Who developed the theory of relativity?", max_iterations=3)
        assert result["status"] == "finished"
        assert "Albert Einstein" in result["answer"]
        assert result["iterations"] == 0  # answered before the loop

    def test_planner_answer_with_json_payload(self, fake_llm):
        import json as _json
        payload = _json.dumps({"answer": "Paris", "status": "solved"})

        def responder(kwargs):
            return SimpleNamespace(
                role="assistant",
                content=f"<answer>{payload}</answer>",
                reasoning_content=None, tool_calls=[],
            )
        p = _make_pipeline(fake_llm, responder)
        result = p.run(question="What is the capital of France?", max_iterations=3)
        assert result["status"] == "finished"
        assert "Paris" in result["answer"]
