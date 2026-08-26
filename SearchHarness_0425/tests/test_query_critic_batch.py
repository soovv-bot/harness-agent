"""Unit tests for QueryCritic.batch_evaluate.

Covers the P0 latency optimization: judging multiple queries in ONE LLM call
instead of N sequential calls. Verifies:
- All-rule-decided batch makes ZERO LLM calls.
- Cache hits make ZERO LLM calls.
- Ordering is preserved 1:1 with input queries.
- LLM-decided batch makes exactly ONE call and parses a JSON array.
- Mixed batches (some rule-decided, some LLM) only LLM the undecided ones.
- Verdicts are cached so a repeat batch skips LLM.
- Graceful degradation on LLM failure / malformed response (fail-open).

Run: pytest tests/test_query_critic_batch.py -v
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from critics.query_critic import (  # noqa: E402
    ALLOW,
    ALLOW_WITH_WARNING,
    REJECT_AS_REDUNDANT,
    SUGGEST_PIVOT,
    QueryCritic,
)
from memory.query_history import QueryHistoryMemory  # noqa: E402


def _responder_with_count(responses):
    """Build a responder returning scripted content + tracking call count.

    ``responses`` is a list of content strings; each LLM call pops the next.
    Returns (responder_fn, call_count_dict).
    """
    if isinstance(responses, str):
        responses = [responses]
    queue = list(responses)
    call_count = {"n": 0}

    def responder(kwargs):
        idx = min(call_count["n"], len(queue) - 1)
        content = queue[idx] if queue else ""
        call_count["n"] += 1
        return SimpleNamespace(role="assistant", content=content,
                                reasoning_content=None, tool_calls=[])

    return responder, call_count


def _make_critic(fake_llm, responses):
    """Install fake LLM with given responses; return (critic, call_count)."""
    responder, call_count = _responder_with_count(responses)
    fake_client = fake_llm(responder)
    memory = QueryHistoryMemory()
    critic = QueryCritic(memory=memory, api_base="x", api_key="y", model_id="GLM-5.2")
    critic._call_count = call_count  # type: ignore[attr-defined]
    critic._fake_client = fake_client  # type: ignore[attr-defined]
    return critic, call_count


def _prime(critic, query="prime"):
    critic.memory.record(query=query, phase="candidate_generation", subtask="s",
                          results_summary="", new_source_families=[],
                          new_candidates=[], result_quality="medium",
                          led_to_crawl=False, crawl_urls=[])


class TestBatchAllRuleDecided:
    def test_no_llm_when_all_decided_by_rules(self, fake_llm):
        critic, calls = _make_critic(fake_llm, ["[]"])
        verdicts = critic.batch_evaluate(
            queries=["alpha beta", "gamma delta"],
            phase="candidate_generation", subtask="find candidates", question="Q?",
        )
        assert len(verdicts) == 2
        assert all(v.decision == ALLOW for v in verdicts)
        assert calls["n"] == 0

    def test_literal_duplicate_rejected_by_rule(self, fake_llm):
        # The dup is rejected by rule (no LLM). The non-dup has history, so it
        # goes to LLM -> exactly 1 LLM call for the non-dup only.
        critic, calls = _make_critic(fake_llm, ['[{"decision": "allow", "reason": "ok"}]'])
        critic.memory.record(query="red apples", phase="candidate_generation",
                             subtask="s", results_summary="", new_source_families=[],
                             new_candidates=[], result_quality="high",
                             led_to_crawl=False, crawl_urls=[])
        verdicts = critic.batch_evaluate(
            queries=["red apples", "green apples"],
            phase="candidate_generation", subtask="s", question="Q?",
        )
        assert verdicts[0].decision == REJECT_AS_REDUNDANT  # rule, no LLM
        assert verdicts[1].decision == ALLOW  # via LLM
        assert calls["n"] == 1  # only the non-dup hit LLM


class TestBatchCacheHits:
    def test_second_batch_reuses_cache_no_llm(self, fake_llm):
        critic, calls = _make_critic(fake_llm, [
            '[{"decision": "allow", "reason": "first"}, '
            '{"decision": "reject_as_redundant", "reason": "dup"}]',
        ])
        _prime(critic)
        first = critic.batch_evaluate(
            queries=["novel alpha", "novel beta"],
            phase="candidate_generation", subtask="s", question="Q?",
        )
        assert calls["n"] == 1
        assert first[0].decision == ALLOW
        assert first[1].decision == REJECT_AS_REDUNDANT

        before = calls["n"]
        second = critic.batch_evaluate(
            queries=["novel alpha", "novel beta"],
            phase="candidate_generation", subtask="s", question="Q?",
        )
        assert calls["n"] == before
        assert second[0].decision == ALLOW
        assert second[1].decision == REJECT_AS_REDUNDANT


class TestBatchLlmDecided:
    def test_one_llm_call_for_multiple_queries(self, fake_llm):
        critic, calls = _make_critic(fake_llm, [
            '[{"decision": "allow", "reason": "a"}, '
            '{"decision": "reject_as_redundant", "reason": "b"}, '
            '{"decision": "suggest_pivot", "reason": "c", "alternative_queries": ["x"]}]',
        ])
        _prime(critic)
        verdicts = critic.batch_evaluate(
            queries=["q1", "q2", "q3"],
            phase="candidate_generation", subtask="s", question="Q?",
        )
        assert calls["n"] == 1
        assert verdicts[0].decision == ALLOW
        assert verdicts[1].decision == REJECT_AS_REDUNDANT
        assert verdicts[2].decision == SUGGEST_PIVOT
        assert verdicts[2].alternative_queries == ["x"]

    def test_order_preserved(self, fake_llm):
        critic, calls = _make_critic(fake_llm, [
            '[{"decision": "allow", "reason": "0"}, '
            '{"decision": "reject_as_redundant", "reason": "1"}, '
            '{"decision": "allow_with_warning", "reason": "2"}]',
        ])
        _prime(critic)
        verdicts = critic.batch_evaluate(
            queries=["first", "second", "third"],
            phase="p", subtask="s", question="Q?",
        )
        assert [v.reason for v in verdicts] == ["0", "1", "2"]


class TestBatchMixed:
    def test_only_undecided_go_to_llm(self, fake_llm):
        critic, calls = _make_critic(fake_llm, [
            '[{"decision": "allow", "reason": "llm-a"}, '
            '{"decision": "reject_as_redundant", "reason": "llm-b"}]',
        ])
        critic.memory.record(query="the dup", phase="p", subtask="s", results_summary="",
                             new_source_families=[], new_candidates=[], result_quality="high",
                             led_to_crawl=False, crawl_urls=[])
        critic.memory.record(query="other prime", phase="p", subtask="s", results_summary="",
                             new_source_families=[], new_candidates=[], result_quality="medium",
                             led_to_crawl=False, crawl_urls=[])
        verdicts = critic.batch_evaluate(
            queries=["the dup", "needs llm a", "needs llm b"],
            phase="p", subtask="s", question="Q?",
        )
        assert calls["n"] == 1
        assert verdicts[0].decision == REJECT_AS_REDUNDANT
        assert verdicts[1].decision == ALLOW
        assert verdicts[2].decision == REJECT_AS_REDUNDANT


class TestBatchDegradation:
    def test_malformed_response_fails_open(self, fake_llm):
        critic, calls = _make_critic(fake_llm, ["this is not json at all"])
        _prime(critic)
        verdicts = critic.batch_evaluate(
            queries=["q1", "q2"], phase="p", subtask="s", question="Q?",
        )
        assert all(v.decision == ALLOW_WITH_WARNING for v in verdicts)

    def test_count_mismatch_fills_with_safe_default(self, fake_llm):
        critic, calls = _make_critic(fake_llm, ['[{"decision": "allow", "reason": "only one"}]'])
        _prime(critic)
        verdicts = critic.batch_evaluate(
            queries=["q1", "q2", "q3"], phase="p", subtask="s", question="Q?",
        )
        assert len(verdicts) == 3
        assert verdicts[0].decision == ALLOW
        assert verdicts[1].decision == ALLOW_WITH_WARNING
        assert verdicts[2].decision == ALLOW_WITH_WARNING

    def test_unknown_decision_coerced(self, fake_llm):
        critic, calls = _make_critic(fake_llm, [
            '[{"decision": "definitely_maybe", "reason": "weird"}]',
        ])
        _prime(critic)
        verdicts = critic.batch_evaluate(
            queries=["q1"], phase="p", subtask="s", question="Q?",
        )
        assert verdicts[0].decision == ALLOW_WITH_WARNING


class TestBatchEmpty:
    def test_empty_input_returns_empty(self, fake_llm):
        critic, calls = _make_critic(fake_llm, [])
        verdicts = critic.batch_evaluate([], phase="p", subtask="s", question="Q?")
        assert verdicts == []
        assert calls["n"] == 0

    def test_empty_string_query_rejected_without_llm(self, fake_llm):
        critic, calls = _make_critic(fake_llm, [])
        verdicts = critic.batch_evaluate(["", "  "], phase="p", subtask="s", question="Q?")
        assert len(verdicts) == 2
        assert all(v.decision == REJECT_AS_REDUNDANT for v in verdicts)
        assert calls["n"] == 0


class TestBatchNoLlmFlag:
    def test_use_llm_false_skips_llm(self, fake_llm):
        critic, calls = _make_critic(fake_llm, ["[]"])
        _prime(critic)
        verdicts = critic.batch_evaluate(
            queries=["q1", "q2"], phase="p", subtask="s", question="Q?", use_llm=False,
        )
        assert all(v.decision == ALLOW for v in verdicts)
        assert calls["n"] == 0
