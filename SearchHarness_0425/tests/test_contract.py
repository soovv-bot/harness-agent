"""Contract-layer tests (RD §6, M2 contract step).

Locks in two things:
1. Behavior parity for the migrated classes (QueryRecord, QueryVerdict,
   ToolObservation→ToolResult) — field defaults, post-init normalization,
   to_dict() output identical to the legacy implementations.
2. R1 purity — the contract package must never import other project modules.
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contract import (  # noqa: E402
    CandidateRecord,
    Findings,
    Message,
    Plan,
    PlanStep,
    QueryRecord,
    QueryVerdict,
    RunResult,
    GradeResult,
    Subtask,
    SubtaskResult,
    PipelineOptions,
    TaskResult,
    ToolResult,
    TrajectoryDoc,
    TrajectoryEvent,
)
from contract.candidate import (  # noqa: E402
    ALLOW,
    ALLOW_WITH_WARNING,
    REJECT_AS_REDUNDANT,
    SUGGEST_PIVOT,
)


# ----------------------------------------------------------------------
# Migration aliases: original import paths still expose the same objects
# ----------------------------------------------------------------------

def test_query_record_alias_identity():
    from memory.query_history import QueryRecord as LegacyQR
    assert LegacyQR is QueryRecord


def test_query_verdict_alias_and_constants():
    import critics.query_critic as query_critic
    assert query_critic.QueryVerdict is QueryVerdict
    assert query_critic.ALLOW == ALLOW
    assert query_critic.ALLOW_WITH_WARNING == ALLOW_WITH_WARNING
    assert query_critic.REJECT_AS_REDUNDANT == REJECT_AS_REDUNDANT
    assert query_critic.SUGGEST_PIVOT == SUGGEST_PIVOT


def test_tool_observation_alias_identity():
    from memory.search_memory import ToolObservation
    assert ToolObservation is ToolResult


# ----------------------------------------------------------------------
# QueryRecord parity (legacy semantics: `or []` normalization, mutability)
# ----------------------------------------------------------------------

def test_query_record_none_containers_normalize():
    r = QueryRecord(query="q", phase="p", subtask="s")
    assert r.new_source_families == []
    assert r.new_candidates == []
    assert r.crawl_urls == []
    assert r.metadata == {}
    assert r.results_summary == ""
    assert r.result_quality == "unknown"
    assert r.led_to_crawl is False
    assert r.turn_index is None
    assert isinstance(r.timestamp, str) and r.timestamp


def test_query_record_post_init_mutation_supported():
    """QueryHistoryMemory.update_last_record mutates the last record — the
    dataclass must stay non-frozen."""
    r = QueryRecord(query="q", phase="p", subtask="s", new_candidates=["A"])
    r.results_summary = "updated"
    r.new_candidates.append("B")
    r.led_to_crawl = True
    r.crawl_urls = ["https://example.org"]
    r.turn_index = 3
    assert r.new_candidates == ["A", "B"] and r.turn_index == 3


def test_query_record_to_dict_keys_and_turn_index_pattern():
    """Mirror of QueryHistoryMemory.record()/load() usage."""
    from memory.query_history import QueryHistoryMemory
    mem = QueryHistoryMemory()
    entry = mem.record(query="albrecht penck", phase="source_identification",
                       subtask="identify scientist", new_candidates=["Albrecht Penck"])
    assert entry.turn_index == 0
    mem.update_last_record(result_quality="high", crawl_urls=["https://en.wikipedia.org/wiki/Albrecht_Penck"])
    mem.add_candidates_to_last_record(["Albrecht Penck", "penck, albrecht "])
    d = entry.to_dict()
    assert d["query"] == "albrecht penck"
    assert d["result_quality"] == "high"
    assert d["crawl_urls"] == ["https://en.wikipedia.org/wiki/Albrecht_Penck"]
    assert d["new_candidates"] == ["Albrecht Penck", "penck, albrecht"]
    assert set(d) == {
        "query", "phase", "subtask", "results_summary", "new_source_families",
        "new_candidates", "result_quality", "led_to_crawl", "crawl_urls",
        "metadata", "timestamp", "turn_index",
    }


# ----------------------------------------------------------------------
# QueryVerdict parity
# ----------------------------------------------------------------------

def test_verdict_decisions_and_is_allowed():
    assert QueryVerdict(ALLOW, "ok").is_allowed
    assert QueryVerdict(ALLOW_WITH_WARNING, "ok").is_allowed
    assert not QueryVerdict(REJECT_AS_REDUNDANT, "dup").is_allowed
    assert not QueryVerdict(SUGGEST_PIVOT, "pivot").is_allowed


def test_verdict_to_dict_omits_empty_alternatives():
    v = QueryVerdict(ALLOW, "fine")
    assert "alternative_queries" not in v.to_dict()
    v2 = QueryVerdict(SUGGEST_PIVOT, "pivot", alternative_queries=["other"])
    assert v2.to_dict()["alternative_queries"] == ["other"]
    assert "ALLOW" not in repr(v2)  # repr format preserved from legacy class
    assert repr(v2).startswith("QueryVerdict(suggest_pivot, reason='pivot...')")


def test_verdict_none_containers_normalize():
    v = QueryVerdict(ALLOW, "r", checks=None, alternative_queries=None)
    assert v.checks == {} and v.alternative_queries == []


# ----------------------------------------------------------------------
# ToolResult (ToolObservation) parity
# ----------------------------------------------------------------------

def test_tool_result_to_dict_include_raw_switch():
    obs = ToolResult(tool_name="search", arguments={"q": "x"},
                     raw_result="RAW", compact_summary="sum")
    full = obs.to_dict()
    assert full["raw_result"] == "RAW"
    redacted = obs.to_dict(include_raw=False)
    assert "raw_result" not in redacted and redacted["compact_summary"] == "sum"
    assert isinstance(obs.created_at, str) and obs.created_at


# ----------------------------------------------------------------------
# Trajectory contracts
# ----------------------------------------------------------------------

def test_trajectory_doc_validate():
    doc = {k: [] for k in TrajectoryDoc.REQUIRED_KEYS}
    doc["metadata"] = {"task": "t", "model": "m", "status": "completed"}
    doc["pipeline_state"] = {}
    assert TrajectoryDoc.validate(doc) == []
    bad = {"metadata": {"task": "t"}, "messages": "not-a-list"}
    violations = TrajectoryDoc.validate(bad)
    assert any("missing top-level key" in v for v in violations)
    assert any("missing metadata key" in v for v in violations)
    assert any("messages is not a list" in v for v in violations)


def test_trajectory_event_and_message_roundtrip():
    ev = TrajectoryEvent(event_type="tool_observation", iteration=2, data={"tool_name": "search"})
    assert TrajectoryEvent.from_dict(ev.to_dict()).event_type == "tool_observation"
    msg = Message(role="assistant", content=None, tool_calls=[{"id": "c1"}])
    d = msg.to_dict()
    assert d == {"role": "assistant", "content": None, "tool_calls": [{"id": "c1"}]}
    assert Message.from_dict(d).tool_calls == [{"id": "c1"}]


# ----------------------------------------------------------------------
# Agent / run contracts (tolerant dict adapters)
# ----------------------------------------------------------------------

def test_plan_roundtrip_from_dict_shape():
    plan = Plan.from_dict({
        "phase": "candidate_generation",
        "steps": [{"subtask": "expand", "type": "candidate_expansion", "guidance": ["g1"]}],
    })
    assert plan.steps[0].subtask_type == "candidate_expansion"
    assert plan.steps[0].guidance == ["g1"]
    assert Plan.from_dict(plan.to_dict()).steps[0].subtask == "expand"


def test_subtask_result_and_findings_roundtrip():
    sr = SubtaskResult.from_dict({
        "subtask": "verify X", "status": "completed",
        "findings": {"summary": "ok", "new_candidates": ["X"]},
    })
    assert sr.findings.new_candidates == ["X"]
    assert Subtask(**Subtask.from_dict({"subtask": "s", "guidance": ["a"]}).to_dict()).guidance == ["a"]


def test_candidate_record_defaults_match_state_store_shape():
    rec = CandidateRecord(name="X")
    d = rec.to_dict()
    assert d["status"] == "active"
    assert d["verification_status"] == "unverified"
    assert d["confidence"] == "low"
    for k in ("supporting_constraints", "unresolved_constraints", "hard_conflicts", "evidence"):
        assert d[k] == []
    assert CandidateRecord.from_dict(d).name == "X"


def test_run_contracts_roundtrip():
    opts = PipelineOptions.from_dict({"max_iterations": 8, "custom_flag": True})
    assert opts.max_iterations == 8 and opts.flags["custom_flag"] is True
    rr = RunResult.from_dict({"answer": "a", "status": "completed", "iterations": 3})
    assert rr.to_dict()["iterations"] == 3
    gr = GradeResult.from_dict({"correct": True, "extracted_answer": "x", "reasoning": "why"})
    assert gr.correct and gr.reasoning == "why"
    tr = TaskResult.from_dict({"task_index": 7, "answer": "a", "unknown_key": 1})
    assert tr.task_index == 7 and tr.to_dict()["unknown_key"] == 1


# ----------------------------------------------------------------------
# R1 purity: contract must not import project modules
# ----------------------------------------------------------------------

def test_contract_layer_r1_purity():
    project_modules = {
        "config", "llm",
        "search_memory", "query_history", "query_critic", "subtask_critic",
        "pipeline", "trajectory",
        "planning_agent_v3", "search_agent_v3",
    }
    # AST-level check: no `import <project_module>` / `from <project_module>` in contract sources.
    # (A sys.modules heuristic is unreliable — e.g. the contract package legitimately
    # owns a `trajectory` submodule attribute while a top-level `trajectory` package exists.)
    import ast
    contract_dir = Path(__file__).resolve().parent.parent / "contract"
    for py in contract_dir.glob("*.py"):
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in project_modules, f"{py.name} imports {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                mod = (node.module or "").split(".")[0]
                assert mod not in project_modules, f"{py.name} imports from {mod}"
