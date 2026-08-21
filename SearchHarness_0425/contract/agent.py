"""Planner / executor contracts (RD §6).

Pure data structures — no project imports (rule R1).

The planner and subtask pipeline currently pass plain dicts (see
``pipeline.orchestrator._subtask_from_step``). These dataclasses define
the canonical shapes; producers migrate incrementally (RD migration
discipline), so every class provides a tolerant ``from_dict`` adapter and
consumers must keep accepting plain dicts until the migration completes.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PlanStep:
    """One step inside a planner-produced plan."""

    subtask: str = ""
    name: str = ""
    status: str = "pending"  # pending | in_progress | done | skipped
    subtask_type: Optional[str] = None
    guidance: List[str] = field(default_factory=list)
    result_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PlanStep":
        return cls(
            subtask=d.get("subtask", "") or "",
            name=d.get("name", "") or "",
            status=d.get("status", "pending") or "pending",
            subtask_type=d.get("subtask_type") or d.get("type") or d.get("mode"),
            guidance=list(d.get("guidance") or d.get("executor_guidance") or []),
            result_summary=d.get("result_summary", "") or "",
        )


@dataclass
class Plan:
    """A planner-produced plan: ordered steps within a workflow phase."""

    steps: List[PlanStep] = field(default_factory=list)
    phase: str = ""  # e.g. source_identification / candidate_generation / verification
    workflow_stage: str = ""
    status: str = "active"
    objective: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "steps": [s.to_dict() for s in self.steps],
            "phase": self.phase,
            "workflow_stage": self.workflow_stage,
            "status": self.status,
            "objective": self.objective,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Plan":
        return cls(
            steps=[PlanStep.from_dict(s) for s in (d.get("steps") or []) if isinstance(s, dict)],
            phase=d.get("phase", "") or "",
            workflow_stage=d.get("workflow_stage", "") or "",
            status=d.get("status", "active") or "active",
            objective=d.get("objective", "") or "",
            metadata=dict(d.get("metadata") or {}),
        )


@dataclass
class Subtask:
    """A unit of executor work derived from a plan step."""

    subtask: str
    subtask_type: Optional[str] = None  # candidate_expansion | candidate_verification | ...
    guidance: List[str] = field(default_factory=list)
    source_recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"subtask": self.subtask}
        if self.subtask_type:
            d["subtask_type"] = self.subtask_type
        if self.guidance:
            d["guidance"] = self.guidance
        if self.source_recommendations:
            d["source_recommendations"] = self.source_recommendations
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Subtask":
        return cls(
            subtask=d.get("subtask", "") or "",
            subtask_type=d.get("subtask_type"),
            guidance=list(d.get("guidance") or []),
            source_recommendations=list(d.get("source_recommendations") or []),
        )


@dataclass
class Findings:
    """Structured findings returned by an executor for one subtask."""

    summary: str = ""
    new_candidates: List[str] = field(default_factory=list)
    resolved_uncertainties: List[str] = field(default_factory=list)
    remaining_uncertainties: List[str] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    pending_urls: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Findings":
        return cls(
            summary=d.get("summary", "") or "",
            new_candidates=list(d.get("new_candidates") or []),
            resolved_uncertainties=list(d.get("resolved_uncertainties") or []),
            remaining_uncertainties=list(d.get("remaining_uncertainties") or []),
            evidence=list(d.get("evidence") or []),
            pending_urls=list(d.get("pending_urls") or []),
        )


@dataclass
class SubtaskResult:
    """Outcome of executing one ``Subtask``."""

    subtask: str
    status: str = "completed"  # completed | failed | skipped
    findings: Findings = field(default_factory=Findings)
    verdict: Optional[str] = None
    latency_ms: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subtask": self.subtask,
            "status": self.status,
            "findings": self.findings.to_dict(),
            "verdict": self.verdict,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SubtaskResult":
        findings = d.get("findings")
        return cls(
            subtask=d.get("subtask", "") or "",
            status=d.get("status", "completed") or "completed",
            findings=Findings.from_dict(findings) if isinstance(findings, dict) else Findings(),
            verdict=d.get("verdict"),
            latency_ms=d.get("latency_ms"),
            error=d.get("error"),
        )
