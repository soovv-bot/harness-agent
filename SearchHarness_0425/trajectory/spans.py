"""Span-level tracing from enriched trajectory JSON (M3 ④).

Converts a recorded trajectory (events + llm_calls + latency fields) into a
span tree with OTEL-compatible JSON output, so单任务时间线 can be visualized
or ingested by downstream tooling. Live instrumentation is unchanged — spans
are derived offline from already-recorded events, keeping the hot path free
of tracing overhead and replay-stable.

Usage as CLI:
    python -m trajectory.spans logs/trajectories/<model>/task_000001.json \
        --out spans_otel.json --timeline
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SPAN_SCHEMA_VERSION = 1

# Events that delimit meaningful work units. Unknown event types still
# become instant spans so nothing disappears from the timeline.
_ITERATION_MARKERS = {"iteration_started", "subtask_selected", "executor_start"}


def _ms(elapsed: Any) -> float:
    try:
        return float(elapsed)
    except (TypeError, ValueError):
        return 0.0


def _attr(key: str, value: Any) -> Dict[str, Any]:
    if isinstance(value, bool):
        v: Dict[str, Any] = {"boolValue": value}
    elif isinstance(value, int):
        v = {"intValue": value}
    elif isinstance(value, float):
        v = {"doubleValue": value}
    else:
        v = {"stringValue": str(value)}
    return {"key": key, "value": v}


def _span(
    *,
    trace_id: str,
    span_id: str,
    parent: Optional[str],
    name: str,
    start_ms: float,
    end_ms: float,
    attrs: Iterable[Tuple[str, Any]] = (),
) -> Dict[str, Any]:
    """One OTEL-shape span (times in Unix epoch ms, like OTLP nanos but ms)."""
    return {
        "traceId": trace_id,
        "spanId": span_id,
        "parentSpanId": parent or "",
        "name": name,
        "startTimeUnixMs": round(start_ms, 3),
        "endTimeUnixMs": round(end_ms, 3),
        "attributes": [_attr(k, v) for k, v in attrs],
    }


class _Ids:
    def __init__(self) -> None:
        self._n = 0

    def next(self) -> str:
        self._n += 1
        return f"{self._n:08x}"


def build_spans(trajectory: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    """Derive a span forest from one trajectory payload. Offline & pure.

    Hierarchy: task ─┬─ iteration_i ─┬─ llm_call / search / executor / planner
                      └─ events (instant or interval via known begin/end pairs)
    """
    meta = trajectory.get("metadata") or {}
    trace_id = f"task-{meta.get('task_index', 0):06d}-{meta.get('model', 'unknown')}"
    ids = _Ids()

    start_iso = meta.get("started_at")
    # Absolute anchor: events carry only monotonic elapsed_ms; anchor to
    # started_at when parseable, else 0 (relative timeline).
    t0 = 0.0
    start_dt = None
    from datetime import datetime

    if isinstance(start_iso, str):
        try:
            start_dt = datetime.fromisoformat(start_iso)
            t0 = start_dt.timestamp() * 1000.0
        except ValueError:
            start_dt, t0 = None, 0.0

    spans: List[Dict[str, Any]] = []
    total_ms = _ms(meta.get("total_elapsed_ms"))
    if not total_ms:
        # Fallback chains: finish−start delta, then last event's elapsed_ms
        fin = meta.get("finished_at")
        if start_dt and isinstance(fin, str):
            try:
                total_ms = (datetime.fromisoformat(fin) - start_dt).total_seconds() * 1000.0
            except ValueError:
                total_ms = 0.0
        if not total_ms:
            total_ms = max(
                (_ms(e.get("elapsed_ms")) for e in trajectory.get("events") or []),
                default=0.0,
            )
    root_id = ids.next()
    spans.append(_span(
        trace_id=trace_id, span_id=root_id, parent=None,
        name=f"task {meta.get('status', '')}".strip(),
        start_ms=t0, end_ms=t0 + total_ms,
        attrs=[
            ("task_index", int(meta.get("task_index", 0))),
            ("model", meta.get("model", "")),
            ("iterations", int(meta.get("iterations") or 0)),
            ("is_correct", bool(meta.get("is_correct"))),
            ("has_events", bool(trajectory.get("events"))),
            ("has_llm_calls", bool(trajectory.get("llm_calls"))),
        ],
    ))

    # Iteration parents keyed by iteration number
    iteration_span: Dict[int, str] = {}

    events: List[Dict[str, Any]] = list(trajectory.get("events") or [])
    started_stack: Dict[str, str] = {}  # event_type→span_id for begin/end pairs

    def parent_for(iteration: int) -> Tuple[str, float]:
        """Return (parent_span_id, anchor_start_ms) for one iteration level."""
        sid = iteration_span.get(iteration)
        if iteration and sid:
            start = next(
                (s["startTimeUnixMs"] for s in spans if s["spanId"] == sid), t0
            )
            return sid, start
        return root_id, t0

    for ev in events:
        et = str(ev.get("event_type", ""))
        it = int(ev.get("iteration") or 0)
        at = t0 + _ms(ev.get("elapsed_ms"))

        if et == "iteration_started":
            sid = ids.next()
            iteration_span[it] = sid
            # Close at next iteration_started or task end (patched later)
            spans.append(_span(
                trace_id=trace_id, span_id=sid, parent=root_id,
                name=f"iteration {it}", start_ms=at, end_ms=at,  # patched below
                attrs=[("iteration", it),
                       ("workflow_stage", (ev.get("data") or {}).get("workflow_stage", ""))],
            ))
            continue

        parent, _ = parent_for(it)
        et_lower = et.lower()
        if et_lower.endswith(("_started", "_start")):
            stem = et_lower.rsplit("_start", 1)[0].rstrip("ed") or et_lower
            sid = ids.next()
            started_stack[stem] = sid
            spans.append(_span(
                trace_id=trace_id, span_id=sid, parent=parent,
                name=et, start_ms=at, end_ms=at,
                attrs=[("event_type", et)],
            ))
            continue
        if et_lower.endswith(("_ended", "_end")):
            stem = et_lower.rsplit("_end", 1)[0].rstrip("e") or et_lower
            sid = started_stack.pop(stem, None)
            if sid:
                for sp in spans:
                    if sp["spanId"] == sid:
                        sp["endTimeUnixMs"] = at
                        sp["name"] = f"{stem} (interval)"
                        break
                continue

        spans.append(_span(
            trace_id=trace_id, span_id=ids.next(), parent=parent,
            name=et or "event", start_ms=at, end_ms=at,
            attrs=[("event_type", et), ("agent", ev.get("agent", "")), ("iteration", it)],
        ))

    # Close iteration spans at task end
    for it, sid in iteration_span.items():
        for sp in spans:
            if sp["spanId"] == sid and sp["endTimeUnixMs"] == sp["startTimeUnixMs"]:
                sp["endTimeUnixMs"] = t0 + total_ms

    # LLM calls: interval spans anchored at their parent iteration's start
    # (llm_calls entries carry latency only, so absolute placement reuses the
    # iteration anchor — indicative of duration, not wall-clock position).
    for call in trajectory.get("llm_calls") or []:
        it = int(call.get("iteration") or 0)
        parent, anchor = parent_for(it)
        latency = _ms(call.get("latency_ms"))
        spans.append(_span(
            trace_id=trace_id, span_id=ids.next(), parent=parent,
            name=f"llm:{call.get('agent', '?')}:{call.get('phase', '?')}",
            start_ms=anchor, end_ms=anchor + latency,
            attrs=[
                ("agent", call.get("agent", "")),
                ("phase", call.get("phase", "")),
                ("iteration", it),
                ("input_tokens", int(call.get("input_tokens") or 0)),
                ("output_tokens", int(call.get("output_tokens") or 0)),
                ("has_tool_calls", bool(call.get("has_tool_calls"))),
            ],
        ))

    spans.sort(key=lambda s: (s["startTimeUnixMs"], s["endTimeUnixMs"]))
    return trace_id, spans


def to_otel_json(trace_id: str, spans: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Wrap spans in OTLP-JSON resource wrapper (ingest-friendly)."""
    return {
        "schema_version": SPAN_SCHEMA_VERSION,
        "trace_id": trace_id,
        "resourceSpans": [{
            "resource": {"attributes": [_attr("service.name", "search-harness")]},
            "scopeSpans": [{
                "scope": {"name": "trajectory.spans", "version": str(SPAN_SCHEMA_VERSION)},
                "spans": spans,
            }],
        }],
    }


def render_timeline(trace_id: str, spans: List[Dict[str, Any]], *, width: int = 72) -> str:
    """ASCII waterfall of the spans, for terminal debugging."""
    if not spans:
        return "(no spans)"
    t0 = min(s["startTimeUnixMs"] for s in spans)
    t1 = max(s["endTimeUnixMs"] for s in spans) or t0 + 1
    span_ids = {s["spanId"] for s in spans}

    def depth(s: Dict[str, Any]) -> int:
        d, seen, cur = 0, set(), s
        while cur.get("parentSpanId") and cur["parentSpanId"] in span_ids:
            if cur["spanId"] in seen:
                break  # cycle guard
            seen.add(cur["spanId"])
            nxt = next((x for x in spans if x["spanId"] == cur["parentSpanId"]), None)
            if not nxt:
                break
            cur, d = nxt, d + 1
        return d

    lines = [f"trace: {trace_id}  span={t1 - t0:.0f}ms"]
    for s in spans:
        lo = (s["startTimeUnixMs"] - t0) / max(t1 - t0, 1)
        hi = max(lo, (s["endTimeUnixMs"] - t0) / max(t1 - t0, 1))
        a, b = int(lo * width), max(int(hi * width), int(lo * width) + 1)
        bar = " " * a + "█" * (b - a)
        lines.append(f"{'  ' * depth(s)}{s['name'][:28]:28s} |{bar:<{width}s}| +{s['startTimeUnixMs'] - t0:8.0f}ms")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Derive span traces from a trajectory JSON")
    parser.add_argument("trajectory", type=Path, help="Path to task_XXXXXXXX.json")
    parser.add_argument("--out", type=Path, default=None, help="Write OTEL JSON here (default: stdout)")
    parser.add_argument("--timeline", action="store_true", help="Print ASCII timeline")
    args = parser.parse_args(argv)

    trajectory = json.loads(args.trajectory.read_text(encoding="utf-8"))
    trace_id, spans = build_spans(trajectory)
    otel = to_otel_json(trace_id, spans)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(otel, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {len(spans)} spans → {args.out}")
    else:
        print(json.dumps(otel, ensure_ascii=False, indent=2) if not args.timeline else "")
    if args.timeline:
        print(render_timeline(trace_id, spans), file=sys.stderr if args.out else sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
