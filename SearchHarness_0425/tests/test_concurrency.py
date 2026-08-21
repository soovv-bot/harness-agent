"""Unit tests for subtask concurrent execution in pipeline.orchestrator.

Covers:
  - ``_decide_concurrency`` — default 2, bump to 3 for complex questions,
    serial fallback when only one pending step or env override.
  - ``_next_subtasks_batch`` — pick k pending subtasks in order.
  - ``_run_subtasks_concurrent`` — ThreadPoolExecutor parallel run, results in
    input order, early-stop ``threading.Event`` propagation when an executor
    sets ``_authority_consensus_done``.

Pure/deterministic — no network, no LLM. Executors are mocked.
"""

from __future__ import annotations

import threading

import pytest

import pipeline.orchestrator as pipe  # type: ignore


# ── _decide_concurrency ───────────────────────────────────────────────────────


def _make_pipeline_for_concurrency():
    class _Stub:
        _subtask_concurrency = 2
        _max_subtask_concurrency = 3
        _decide_concurrency = pipe.SearchHarnessPipelineV4._decide_concurrency
        _next_subtasks_batch = pipe.SearchHarnessPipelineV4._next_subtasks_batch
        _subtask_from_step = pipe.SearchHarnessPipelineV4._subtask_from_step
        _plan_source_recommendations = pipe.SearchHarnessPipelineV4._plan_source_recommendations

    return _Stub()


def test_decide_concurrency_default_two():
    stub = _make_pipeline_for_concurrency()
    plan = {"steps": [{"subtask": "a"}, {"subtask": "b"}]}
    assert stub._decide_concurrency("short question", plan) == 2


def test_decide_concurrency_long_question_bumps_to_three():
    stub = _make_pipeline_for_concurrency()
    plan = {"steps": [{"subtask": "a"}, {"subtask": "b"}, {"subtask": "c"}]}
    long_q = "x" * 250  # >200 chars → bump k+1
    # k+1=3, n_pending=3 → min(3, max=3, 3) = 3
    assert stub._decide_concurrency(long_q, plan) == 3


def test_decide_concurrency_many_steps_bumps_to_three():
    stub = _make_pipeline_for_concurrency()
    plan = {"steps": [{"subtask": f"s{i}"} for i in range(4)]}
    # 4 pending → many_steps → k+1=3, min(3,3,4)=3
    assert stub._decide_concurrency("short", plan) == 3


def test_decide_concurrency_one_pending_returns_one():
    stub = _make_pipeline_for_concurrency()
    plan = {"steps": [{"subtask": "a"}]}
    assert stub._decide_concurrency("q", plan) == 1


def test_decide_concurrency_env_serial_forces_one():
    stub = _make_pipeline_for_concurrency()
    stub._subtask_concurrency = 1  # env EXECUTOR_SUBTASK_CONCURRENCY=1
    plan = {"steps": [{"subtask": "a"}, {"subtask": "b"}]}
    assert stub._decide_concurrency("q", plan) == 1


def test_decide_concurrency_capped_by_pending():
    stub = _make_pipeline_for_concurrency()
    # long question but only 2 pending → k+1=3 capped to 2
    plan = {"steps": [{"subtask": "a"}, {"subtask": "b"}]}
    long_q = "y" * 300
    assert stub._decide_concurrency(long_q, plan) == 2


# ── _next_subtasks_batch ──────────────────────────────────────────────────────


def test_next_subtasks_batch_returns_k():
    stub = _make_pipeline_for_concurrency()
    plan = {"steps": [{"subtask": f"s{i}"} for i in range(5)]}
    batch = stub._next_subtasks_batch(plan, 3)
    assert len(batch) == 3
    assert [b["subtask"] for b in batch] == ["s0", "s1", "s2"]


def test_next_subtasks_batch_skips_non_pending():
    stub = _make_pipeline_for_concurrency()
    plan = {
        "steps": [
            {"subtask": "done1", "status": "done"},
            {"subtask": "a"},
            {"subtask": "skipped", "status": "skipped"},
            {"subtask": "b"},
        ]
    }
    batch = stub._next_subtasks_batch(plan, 3)
    assert len(batch) == 2
    assert [b["subtask"] for b in batch] == ["a", "b"]


def test_next_subtasks_batch_fewer_than_k():
    stub = _make_pipeline_for_concurrency()
    plan = {"steps": [{"subtask": "a"}, {"subtask": "b"}]}
    batch = stub._next_subtasks_batch(plan, 5)
    assert len(batch) == 2


# ── _run_subtasks_concurrent ─────────────────────────────────────────────────


class _MockExecutor:
    """Mock SearchAgentV3.run — records calls, optionally triggers early stop."""

    def __init__(self, idx, findings, triggers_stop=False, stop_event_holder=None):
        self._idx = idx
        self._findings = findings
        self._triggers_stop = triggers_stop
        self._stop_event_holder = stop_event_holder
        self._authority_consensus_done = False
        self.run_calls = 0
        self.client = None

    def run(self, question, overall_plan, subtask, executor_state, stop_event=None):
        self.run_calls += 1
        if self._triggers_stop:
            self._authority_consensus_done = True
        else:
            if self._stop_event_holder is not None:
                self._stop_event_holder.append(stop_event)
            if stop_event is not None:
                stop_event.wait(timeout=5.0)
        return {"messages": [f"msg-{self._idx}"], "findings": self._findings,
                "metadata": {"status": "completed"}}


class _FakeStateStore:
    def __init__(self):
        self.merged = []

    def export_executor_state(self):
        return {}

    def add_findings(self, findings):
        self.merged.append(findings)

    def record_subtask_execution(self, iteration, plan, subtask, findings):
        pass


def _make_pipeline_for_concurrent_run(pool):
    class _Stub:
        state_store = _FakeStateStore()
        trajectory_recorder = None
        _trajectory_current_iter = None
        _run_subtasks_concurrent = pipe.SearchHarnessPipelineV4._run_subtasks_concurrent

        def _build_executor_pool(self, k):
            return pool[:k]

    return _Stub()


def test_run_subtasks_concurrent_preserves_order():
    """Two executors run in parallel; results returned in input order."""
    stub = _make_pipeline_for_concurrent_run([
        _MockExecutor(0, {"subtask": "a", "candidate_updates": {"new_candidates": ["A"]}}),
        _MockExecutor(1, {"subtask": "b", "candidate_updates": {"new_candidates": ["B"]}}),
    ])
    subtasks = [{"subtask": "a"}, {"subtask": "b"}]
    results = stub._run_subtasks_concurrent("q", {"steps": subtasks}, subtasks, iteration=0)
    assert len(results) == 2
    assert results[0]["findings"]["subtask"] == "a"
    assert results[1]["findings"]["subtask"] == "b"


def test_run_subtasks_concurrent_calls_each_executor_once():
    pool = [_MockExecutor(0, {"subtask": "a"}), _MockExecutor(1, {"subtask": "b"})]
    stub = _make_pipeline_for_concurrent_run(pool)
    stub._run_subtasks_concurrent("q", {"steps": []}, [{"subtask": "a"}, {"subtask": "b"}], iteration=0)
    assert all(e.run_calls == 1 for e in pool)


def test_run_subtasks_concurrent_early_stop_event():
    """If one executor sets _authority_consensus_done, stop_event is set for the other."""
    stop_holder = []
    pool = [
        _MockExecutor(0, {"subtask": "a"}, triggers_stop=True),
        _MockExecutor(1, {"subtask": "b"}, triggers_stop=False, stop_event_holder=stop_holder),
    ]
    stub = _make_pipeline_for_concurrent_run(pool)
    subtasks = [{"subtask": "a"}, {"subtask": "b"}]
    results = stub._run_subtasks_concurrent("q", {"steps": subtasks}, subtasks, iteration=0)
    assert len(results) == 2
    assert pool[0]._authority_consensus_done is True
    assert len(stop_holder) == 1
    assert stop_holder[0].is_set() is True


def test_run_subtasks_concurrent_executor_failure_isolated():
    """One executor raising does not crash the others; error captured in result."""
    class _FailingExecutor(_MockExecutor):
        def run(self, question, overall_plan, subtask, executor_state, stop_event=None):
            self.run_calls += 1
            raise RuntimeError("boom")

    pool = [_FailingExecutor(0, {}), _MockExecutor(1, {"subtask": "b"})]
    stub = _make_pipeline_for_concurrent_run(pool)
    results = stub._run_subtasks_concurrent("q", {"steps": []}, [{"subtask": "a"}, {"subtask": "b"}], iteration=0)
    assert len(results) == 2
    assert results[0]["metadata"]["status"] == "error"
    assert "boom" in results[0]["metadata"]["error"]
    assert results[1]["findings"]["subtask"] == "b"
