"""Trajectory & message contracts (RD §6).

Pure data structures — no project imports (rule R1).

``ToolResult`` is the canonical home of what used to be
``search_memory.ToolObservation``. Field names are kept identical to the
legacy class so serialized output does not drift; ``search_memory`` keeps a
``ToolObservation`` alias for existing consumers.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Message:
    """A single chat message in OpenAI-style conversation format."""

    role: str
    content: Optional[str] = None
    reasoning_content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    name: Optional[str] = None
    tool_call_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"role": self.role, "content": self.content}
        if self.reasoning_content is not None:
            d["reasoning_content"] = self.reasoning_content
        if self.tool_calls is not None:
            d["tool_calls"] = self.tool_calls
        if self.name is not None:
            d["name"] = self.name
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Message":
        return cls(
            role=d.get("role", ""),
            content=d.get("content"),
            reasoning_content=d.get("reasoning_content"),
            tool_calls=d.get("tool_calls"),
            name=d.get("name"),
            tool_call_id=d.get("tool_call_id"),
        )


@dataclass
class ToolResult:
    """Canonical form of a recorded tool observation.

    Physically moved from ``search_memory.ToolObservation`` — fields and
    serialization are byte-for-byte compatible.
    """

    tool_name: str
    arguments: Dict[str, Any]
    raw_result: str
    compact_summary: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self, include_raw: bool = True) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "compact_summary": self.compact_summary,
            "created_at": self.created_at,
        }
        if include_raw:
            data["raw_result"] = self.raw_result
        return data

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ToolResult":
        return cls(
            tool_name=d.get("tool_name", ""),
            arguments=d.get("arguments") or {},
            raw_result=d.get("raw_result", ""),
            compact_summary=d.get("compact_summary", ""),
            created_at=d.get("created_at") or datetime.now().isoformat(),
        )


@dataclass
class TrajectoryEvent:
    """One structured event as recorded by ``TrajectoryRecorder.record_event``."""

    event_type: str
    iteration: int = 0
    agent: str = "pipeline"
    data: Dict[str, Any] = field(default_factory=dict)
    seq: int = 0
    timestamp: Optional[str] = None
    elapsed_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seq": self.seq,
            "event_type": self.event_type,
            "agent": self.agent,
            "iteration": self.iteration,
            "timestamp": self.timestamp,
            "elapsed_ms": self.elapsed_ms,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TrajectoryEvent":
        return cls(
            event_type=d.get("event_type", ""),
            iteration=d.get("iteration", 0),
            agent=d.get("agent", "pipeline"),
            data=d.get("data") or {},
            seq=d.get("seq", 0),
            timestamp=d.get("timestamp"),
            elapsed_ms=d.get("elapsed_ms"),
        )


class TrajectoryDoc:
    """Schema constants + lightweight validation for the trajectory JSON doc.

    The authoritative producer is ``trajectory_recorder_enhanced._build_trajectory``;
    this validator is the boundary check (RD §6) and intentionally returns a
    list of human-readable violations instead of raising.
    """

    REQUIRED_KEYS: List[str] = [
        "metadata",
        "events",
        "search_log",
        "llm_calls",
        "candidate_snapshots",
        "iteration_summaries",
        "planner_conversations",
        "executor_conversations",
        "pipeline_state",
        "messages",
    ]

    METADATA_REQUIRED_KEYS: List[str] = [
        "task",
        "model",
        "status",
    ]

    @classmethod
    def validate(cls, doc: Dict[str, Any]) -> List[str]:
        """Return a list of schema violations; empty list means valid."""
        violations: List[str] = []
        if not isinstance(doc, dict):
            return ["trajectory doc is not a dict"]
        for key in cls.REQUIRED_KEYS:
            if key not in doc:
                violations.append(f"missing top-level key: {key}")
        metadata = doc.get("metadata")
        if isinstance(metadata, dict):
            for key in cls.METADATA_REQUIRED_KEYS:
                if key not in metadata:
                    violations.append(f"missing metadata key: {key}")
        elif "metadata" in doc:
            violations.append("metadata is not a dict")
        for key in ("events", "search_log", "llm_calls", "messages"):
            if key in doc and not isinstance(doc[key], list):
                violations.append(f"{key} is not a list")
        return violations
