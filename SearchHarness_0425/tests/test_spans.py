"""Span-derivation tests (M3 ④) — trajectory/timeline invariants.

Invariant being tested: span derivation is offline, deterministic, and
graceful under partial enrichment (no events / no llm_calls / no timing).
"""

import json

import pytest

from trajectory.spans import (
    SPAN_SCHEMA_VERSION,
    build_spans,
    main as spans_main,
    render_timeline,
    to_otel_json,
)


def _rich_trajectory():
    return {
        "metadata": {
            "task_index": 3,
            "model": "m1",
            "status": "completed",
            "iterations": 2,
            "total_elapsed_ms": 10000.0,
            "is_correct": True,
        },
        "events": [
            {"event_type": "iteration_started", "iteration": 1, "elapsed_ms": 0,
             "data": {"workflow_stage": "plan"}},
            {"event_type": "search_query", "iteration": 1, "elapsed_ms": 500},
            {"event_type": "executor_start", "iteration": 1, "elapsed_ms": 1000},
            {"event_type": "visit_urls_executed", "iteration": 1, "elapsed_ms": 2000},
            {"event_type": "executor_end", "iteration": 1, "elapsed_ms": 4000},
            {"event_type": "iteration_started", "iteration": 2, "elapsed_ms": 5000, "data": {}},
        ],
        "llm_calls": [
            {"agent": "planner", "phase": "plan", "iteration": 1, "latency_ms": 800,
             "input_tokens": 100, "output_tokens": 50, "has_tool_calls": False},
            {"agent": "executor", "phase": "act", "iteration": 2, "latency_ms": 1500,
             "input_tokens": 200, "output_tokens": 100, "has_tool_calls": True},
        ],
    }


class TestBuildSpans:
    def test_span_forest_structure(self):
        tid, spans = build_spans(_rich_trajectory())
        assert len(spans) == 8
        d = {s["name"]: s for s in spans}
        # interval closed by end event
        assert d["executor (interval)"]["startTimeUnixMs"] == 1000.0
        assert d["executor (interval)"]["endTimeUnixMs"] == 4000.0
        # unclosed iteration span extended to task end
        assert d["iteration 1"]["endTimeUnixMs"] == 10000.0
        # llm span parented under its iteration and anchored at iteration start
        assert d["llm:executor:act"]["parentSpanId"] == d["iteration 2"]["spanId"]
        assert d["llm:executor:act"]["startTimeUnixMs"] == d["iteration 2"]["startTimeUnixMs"]
        assert d["llm:executor:act"]["endTimeUnixMs"] - d["llm:executor:act"]["startTimeUnixMs"] == 1500.0
        # single trace id throughout
        assert set(s["traceId"] for s in spans) == {tid}

    def test_sorted_by_start(self):
        _, spans = build_spans(_rich_trajectory())
        keys = [(s["startTimeUnixMs"], s["endTimeUnixMs"]) for s in spans]
        assert keys == sorted(keys)

    def test_deterministic(self):
        assert build_spans(_rich_trajectory()) == build_spans(_rich_trajectory())

    def test_attributes_otel_shapes(self):
        _, spans = build_spans(_rich_trajectory())
        d = {s["name"]: s for s in spans}
        attrs = {a["key"]: a["value"] for a in d["task completed"]["attributes"]}
        assert attrs["task_index"] == {"intValue": 3}
        assert attrs["is_correct"] == {"boolValue": True}
        assert attrs["model"] == {"stringValue": "m1"}
        attrs = {a["key"]: a["value"] for a in d["llm:planner:plan"]["attributes"]}
        assert attrs["output_tokens"] == {"intValue": 50}
        assert attrs["has_tool_calls"] == {"boolValue": False}

    def test_root_attrs_mark_sparse_payloads(self):
        _, spans = build_spans({"metadata": {"task_index": 1, "model": "m"}})
        root = spans[0]
        attrs = {a["key"]: a["value"] for a in root["attributes"]}
        assert attrs["has_events"] == {"boolValue": False}
        assert attrs["has_llm_calls"] == {"boolValue": False}


class TestFallbackTiming:
    def test_finished_at_fallback(self):
        t = {
            "metadata": {
                "task_index": 1,
                "model": "m",
                "started_at": "2026-04-13T08:00:00",
                "finished_at": "2026-04-13T08:10:00",
            }
        }
        _, spans = build_spans(t)
        assert spans[0]["endTimeUnixMs"] - spans[0]["startTimeUnixMs"] == pytest.approx(600_000.0)

    def test_no_timing_at_all(self):
        _, spans = build_spans({"metadata": {}})
        assert spans[0]["startTimeUnixMs"] == spans[0]["endTimeUnixMs"] == 0.0

    def test_garbage_event_timestamps_become_zero(self):
        t = {"metadata": {"task_index": 1, "model": "m"},
             "events": [{"event_type": "weird", "elapsed_ms": "oops"}]}
        _, spans = build_spans(t)
        weird = next(s for s in spans if s["name"] == "weird")
        assert weird["startTimeUnixMs"] == 0.0


class TestOtelWrapper:
    def test_resource_envelope(self):
        tid, spans = build_spans(_rich_trajectory())
        otel = to_otel_json(tid, spans)
        assert otel["schema_version"] == SPAN_SCHEMA_VERSION
        assert otel["trace_id"] == tid
        rs = otel["resourceSpans"][0]
        svc = rs["resource"]["attributes"][0]
        assert svc == {"key": "service.name", "value": {"stringValue": "search-harness"}}
        assert rs["scopeSpans"][0]["spans"] == spans


class TestTimeline:
    def test_contains_hierarchy_and_bar(self):
        tid, spans = build_spans(_rich_trajectory())
        tl = render_timeline(tid, spans)
        assert "trace:" in tl
        assert "iteration 1" in tl and "llm:planner:plan" in tl
        assert "█" in tl

    def test_empty(self):
        assert render_timeline("t", []) == "(no spans)"


class TestCli:
    def test_cli_writes_otel_and_timeline(self, tmp_path, capsys):
        traj = tmp_path / "task_000003.json"
        traj.write_text(json.dumps(_rich_trajectory()), encoding="utf-8")
        out = tmp_path / "spans.json"
        rc = spans_main([str(traj), "--out", str(out), "--timeline"])
        assert rc == 0
        otel = json.loads(out.read_text(encoding="utf-8"))
        assert otel["trace_id"] == "task-000003-m1"
        assert len(otel["resourceSpans"][0]["scopeSpans"][0]["spans"]) == 8
        captured = capsys.readouterr()
        assert "wrote 8 spans" in captured.out
        assert "iteration 1" in captured.err  # timeline to stderr when --out
