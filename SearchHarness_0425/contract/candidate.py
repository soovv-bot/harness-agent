"""Candidate / query contracts (RD §6).

Pure data structures — no project imports (rule R1).

``QueryRecord`` physically moves from ``query_history.py`` and ``QueryVerdict``
from ``query_critic.py``; both original modules keep import aliases so existing
consumers are untouched. Behavior is preserved exactly:

* ``QueryRecord`` is **not** frozen — ``QueryHistoryMemory`` mutates the last
  record post-init (``update_last_record`` / ``add_candidates_to_last_record``).
* ``None`` list/dict arguments normalize to empty containers in
  ``__post_init__`` (the legacy ``or []`` semantics), and ``timestamp``
  defaults to ``datetime.now().isoformat()`` at construction time.
* ``QueryVerdict.to_dict()`` only includes ``alternative_queries`` when
  non-empty — downstream serialization depends on that.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

# Verdict decision constants (canonical home; ``query_critic`` re-exports them).
ALLOW = "allow"
ALLOW_WITH_WARNING = "allow_with_warning"
REJECT_AS_REDUNDANT = "reject_as_redundant"
SUGGEST_PIVOT = "suggest_pivot"

DECISIONS = (ALLOW, ALLOW_WITH_WARNING, REJECT_AS_REDUNDANT, SUGGEST_PIVOT)

# Candidate lifecycle statuses (canonical string values; not enforced).
CANDIDATE_STATUS_ACTIVE = "active"
CANDIDATE_STATUS_ELIMINATED = "eliminated"
CANDIDATE_STATUS_VERIFIED = "verified"


@dataclass
class QueryRecord:
    """A single query history entry (moved from ``query_history.QueryRecord``)."""

    query: str
    phase: str
    subtask: str
    results_summary: str = ""
    new_source_families: Optional[List[str]] = None
    new_candidates: Optional[List[str]] = None
    result_quality: str = "unknown"  # empty | noise | low | medium | high | unknown
    led_to_crawl: bool = False
    crawl_urls: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None
    turn_index: Optional[int] = None

    def __post_init__(self) -> None:
        # Preserve legacy ``or []`` normalization — construction sites pass
        # explicit None and rely on the container defaults materializing.
        self.new_source_families = self.new_source_families or []
        self.new_candidates = self.new_candidates or []
        self.crawl_urls = self.crawl_urls or []
        self.metadata = self.metadata or {}
        self.timestamp = self.timestamp or datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "phase": self.phase,
            "subtask": self.subtask,
            "results_summary": self.results_summary,
            "new_source_families": self.new_source_families,
            "new_candidates": self.new_candidates,
            "result_quality": self.result_quality,
            "led_to_crawl": self.led_to_crawl,
            "crawl_urls": self.crawl_urls,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "turn_index": self.turn_index,
        }


@dataclass
class QueryVerdict:
    """Structured verdict from the query critic (moved from ``query_critic``)."""

    decision: str
    reason: str
    checks: Optional[Dict[str, Any]] = None
    alternative_queries: Optional[List[str]] = None

    def __post_init__(self) -> None:
        self.checks = self.checks or {}
        self.alternative_queries = self.alternative_queries or []

    @property
    def is_allowed(self) -> bool:
        return self.decision in (ALLOW, ALLOW_WITH_WARNING)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "decision": self.decision,
            "reason": self.reason,
            "checks": self.checks,
        }
        if self.alternative_queries:
            d["alternative_queries"] = self.alternative_queries
        return d

    def __repr__(self) -> str:
        return f"QueryVerdict({self.decision}, reason='{self.reason[:80]}...')"


@dataclass
class CandidateRecord:
    """Structured record for one answer candidate.

    Mirrors the dict shape built by ``SearchStateStore._ensure_candidate_record``.
    Construction sites will migrate to this type incrementally (RD migration
    discipline); consumers must keep tolerating plain dicts via ``from_dict``.
    """

    name: str
    status: str = CANDIDATE_STATUS_ACTIVE
    verification_status: str = "unverified"
    confidence: str = "low"
    supporting_constraints: List[str] = field(default_factory=list)
    unresolved_constraints: List[str] = field(default_factory=list)
    hard_conflicts: List[str] = field(default_factory=list)
    evidence: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "verification_status": self.verification_status,
            "confidence": self.confidence,
            "supporting_constraints": self.supporting_constraints,
            "unresolved_constraints": self.unresolved_constraints,
            "hard_conflicts": self.hard_conflicts,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CandidateRecord":
        return cls(
            name=d.get("name", ""),
            status=d.get("status", CANDIDATE_STATUS_ACTIVE),
            verification_status=d.get("verification_status", "unverified"),
            confidence=d.get("confidence", "low"),
            supporting_constraints=list(d.get("supporting_constraints") or []),
            unresolved_constraints=list(d.get("unresolved_constraints") or []),
            hard_conflicts=list(d.get("hard_conflicts") or []),
            evidence=list(d.get("evidence") or []),
        )
