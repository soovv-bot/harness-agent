"""Search harness memory and compact utilities.

Implements three non-manual memory layers for the search harness:
1. External structured state store (never compact away)
2. Tool-result micro compact (older observations become summaries)
3. Phase-boundary auto snapshots
"""

from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional
from urllib.parse import urlparse


URL_RE = re.compile(r"https?://[^\s\]\)\">]+")


@dataclass
class ToolObservation:
    tool_name: str
    arguments: Dict[str, Any]
    raw_result: str
    compact_summary: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self, include_raw: bool = True) -> Dict[str, Any]:
        data = {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "compact_summary": self.compact_summary,
            "created_at": self.created_at,
        }
        if include_raw:
            data["raw_result"] = self.raw_result
        return data


@dataclass
class SearchSnapshot:
    phase: str
    objective: str
    resolved_uncertainties: List[str]
    remaining_uncertainties: List[str]
    active_source_families: List[str]
    ruled_out_source_families: List[str]
    current_candidates: List[str]
    eliminated_candidates: List[str]
    top_evidence: List[Dict[str, Any]]
    pending_urls: List[str]
    query_history_summary: Dict[str, Any]
    controller_signals: Dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "objective": self.objective,
            "resolved_uncertainties": self.resolved_uncertainties,
            "remaining_uncertainties": self.remaining_uncertainties,
            "active_source_families": self.active_source_families,
            "ruled_out_source_families": self.ruled_out_source_families,
            "current_candidates": self.current_candidates,
            "eliminated_candidates": self.eliminated_candidates,
            "top_evidence": self.top_evidence,
            "pending_urls": self.pending_urls,
            "query_history_summary": self.query_history_summary,
            "controller_signals": self.controller_signals,
            "created_at": self.created_at,
        }


class SearchStateStore:
    """External structured state for the search harness."""

    def __init__(self, keep_recent_observations: int = 3):
        self.question: str = ""
        self.current_plan: Optional[Dict[str, Any]] = None
        self.plan_history: List[Dict[str, Any]] = []
        self.plan_counter: int = 0
        # Lightweight ledger of (plan step -> executor result) to support planning continuation
        # without requiring the agent to infer what happened from raw findings alone.
        self.plan_execution_history: List[Dict[str, Any]] = []
        self.findings_history: List[Dict[str, Any]] = []
        self.snapshots: List[SearchSnapshot] = []
        self.pending_urls: List[str] = []
        self.crawled_urls: List[str] = []
        self.visited_domains: List[str] = []
        self.current_candidates: List[str] = []
        self.eliminated_candidates: List[str] = []
        self.candidate_records: Dict[str, Dict[str, Any]] = {}
        self.ruled_out_source_families: List[str] = []
        self.last_phase: Optional[str] = None
        self.controller_signals: Dict[str, Any] = {}
        self.keep_recent_observations = keep_recent_observations
        self.observations: List[ToolObservation] = []
        self.recent_observations: Deque[ToolObservation] = deque(maxlen=keep_recent_observations)

    def set_question(self, question: str) -> None:
        self.question = question

    def set_controller_signals(self, signals: Dict[str, Any]) -> None:
        self.controller_signals = signals or {}

    def add_plan(self, plan: Dict[str, Any]) -> bool:
        """Add plan. Returns True if phase changed."""
        if "_plan_id" not in plan:
            self.plan_counter += 1
            plan["_plan_id"] = self.plan_counter
        phase = plan.get("phase")
        phase_changed = self.last_phase is not None and phase != self.last_phase
        self.current_plan = plan
        self.plan_history.append(plan)
        self.last_phase = phase
        return phase_changed

    def add_findings(self, findings: Dict[str, Any]) -> None:
        self.findings_history.append(findings)

        candidate_updates = findings.get("candidate_updates", {}) or {}
        evidence = findings.get("evidence", []) or []
        summary = findings.get("summary", "") or ""

        for c in candidate_updates.get("new_candidates", []) or []:
            name = self._candidate_name(c)
            if not name:
                continue
            self._ensure_candidate_record(name)
            self._promote_candidate(name)

        for c in candidate_updates.get("eliminated_candidates", []) or []:
            name = self._candidate_name(c)
            if not name:
                continue
            record = self._ensure_candidate_record(name)
            if not isinstance(c, dict):
                self._merge_unique_list(
                    record["unresolved_constraints"],
                    ["Executor suggested elimination but did not provide explicit hard-conflict evidence."],
                    limit=6,
                )

        for assessment in candidate_updates.get("candidate_assessments", []) or []:
            if isinstance(assessment, dict):
                self._merge_candidate_assessment(assessment)

        for c in candidate_updates.get("new_candidates", []) or []:
            if isinstance(c, dict):
                self._merge_candidate_assessment({
                    "name": self._candidate_name(c),
                    "status": c.get("status", "active"),
                    "verification_status": c.get("verification_status", "unverified"),
                    "confidence": c.get("confidence", "low"),
                    "supporting_constraints": c.get("supporting_constraints", []),
                    "unresolved_constraints": c.get("unresolved_constraints", []),
                    "hard_conflicts": c.get("hard_conflicts", []),
                    "evidence": c.get("evidence", []),
                })

        for c in candidate_updates.get("eliminated_candidates", []) or []:
            if isinstance(c, dict):
                self._merge_candidate_assessment({
                    "name": self._candidate_name(c),
                    "status": "eliminated",
                    "verification_status": c.get("verification_status", "contradicted"),
                    "confidence": c.get("confidence", "low"),
                    "hard_conflicts": c.get("hard_conflicts", []),
                    "unresolved_constraints": c.get("unresolved_constraints", []),
                    "evidence": c.get("evidence", []),
                })

        self._attach_evidence_to_recent_candidates(evidence)
        self._refresh_candidate_lists()

    def record_subtask_execution(
        self,
        *,
        iteration: int,
        plan: Dict[str, Any],
        subtask: Dict[str, Any],
        findings: Dict[str, Any],
        keep_last: int = 50,
    ) -> None:
        """Append a minimal execution ledger entry (no open-ended questions)."""
        updates = findings.get("candidate_updates") or {}
        new_candidates_raw = updates.get("new_candidates", []) or []
        eliminated_candidates_raw = updates.get("eliminated_candidates", []) or []
        new_names = [self._candidate_name(c) for c in new_candidates_raw]
        touched_elimination_names = [self._candidate_name(c) for c in eliminated_candidates_raw]
        for assessment in updates.get("candidate_assessments", []) or []:
            if not isinstance(assessment, dict):
                continue
            name = self._candidate_name(assessment)
            if name and (assessment.get("hard_conflicts") or assessment.get("status") == "eliminated"):
                touched_elimination_names.append(name)
        eliminated_names: List[str] = []
        for name in touched_elimination_names:
            record = self.candidate_records.get(self._candidate_key(name))
            if record and self._is_confirmed_wrong_record(record) and name not in eliminated_names:
                eliminated_names.append(name)
        step_id, step_index = self._locate_plan_step(plan, str(subtask.get("subtask") or subtask.get("name") or ""))

        entry: Dict[str, Any] = {
            "iteration": int(iteration),
            "plan_id": plan.get("_plan_id"),
            "phase": str(plan.get("phase", "") or ""),
            "step_id": step_id,
            "step_index": step_index,
            "subtask": str(subtask.get("subtask") or subtask.get("name") or ""),
            "subtask_type": str(subtask.get("subtask_type") or subtask.get("type") or subtask.get("mode") or ""),
            "status": str(findings.get("status", "") or ""),
            "summary": str(findings.get("summary", "") or "")[:300],
            "candidate_delta": {
                "new": [n for n in new_names if n],
                "eliminated": [n for n in eliminated_names if n],
            },
            "evidence_count": len(findings.get("evidence") or []),
        }
        self.plan_execution_history.append(entry)
        if keep_last and len(self.plan_execution_history) > keep_last:
            self.plan_execution_history = self.plan_execution_history[-keep_last:]

        source_feedback = findings.get("source_feedback", {}) or {}
        for s in source_feedback.get("unhelpful_sources", []) or []:
            if s and s not in self.ruled_out_source_families:
                self.ruled_out_source_families.append(s)

    def _locate_plan_step(self, plan: Dict[str, Any], subtask_name: str) -> tuple[Any, Any]:
        for idx, step in enumerate(plan.get("steps", []) or []):
            step_name = step.get("subtask") or step.get("name") or ""
            if str(step_name).strip() == subtask_name.strip():
                return step.get("id", idx), idx
        return None, None

    def register_tool_observation(self, tool_name: str, arguments: Dict[str, Any], raw_result: Any) -> ToolObservation:
        raw_text = self._normalize_result(raw_result)
        summary = self._compact_tool_result(tool_name, arguments, raw_text)
        obs = ToolObservation(tool_name=tool_name, arguments=arguments, raw_result=raw_text, compact_summary=summary)
        self.observations.append(obs)
        self.recent_observations.append(obs)

        urls = self._extract_urls(raw_text)
        if tool_name == "search":
            for url in urls:
                if url not in self.pending_urls and url not in self.crawled_urls:
                    self.pending_urls.append(url)
        elif tool_name in {"crawl_urls", "visit_urls"}:
            crawled = arguments.get("urls", []) if isinstance(arguments, dict) else []
            for url in crawled:
                if url in self.pending_urls:
                    self.pending_urls.remove(url)
                if url not in self.crawled_urls:
                    self.crawled_urls.append(url)
                domain = self._domain_of(url)
                if domain and domain not in self.visited_domains:
                    self.visited_domains.append(domain)
        return obs

    def create_snapshot(self) -> SearchSnapshot:
        plan = self.current_plan or {}
        source_recommendations = plan.get("source_recommendations")
        if source_recommendations is None:
            source_recommendations = plan.get("source_hypotheses", []) or []
        active_sources = []
        for source in source_recommendations or []:
            if isinstance(source, str) and source.strip():
                active_sources.append(source.strip())
            elif isinstance(source, dict):
                text = source.get("source_family") or source.get("source_type") or source.get("site")
                if text:
                    active_sources.append(str(text))
        resolved_uncertainties: List[str] = []
        pool_assessment = plan.get("pool_assessment") or {}
        remaining_uncertainties = [str(x) for x in pool_assessment.get("gaps", []) or [] if x]
        for step in plan.get("steps", []) or []:
            if step.get("status") == "completed" and step.get("result"):
                step_name = step.get("subtask") or step.get("name") or "step"
                resolved_uncertainties.append(f"{step_name}: {step.get('result', '')}")

        top_evidence = []
        for item in self.findings_history[-3:]:
            for ev in (item.get("evidence", []) or [])[:2]:
                top_evidence.append(ev)
        top_evidence = top_evidence[:6]

        query_summary = {
            "total_plans": len(self.plan_history),
            "total_findings": len(self.findings_history),
            "total_observations": len(self.observations),
            "recent_observation_summaries": [o.compact_summary for o in list(self.recent_observations)],
            "visited_domains": self.visited_domains[-10:],
        }

        snapshot = SearchSnapshot(
            phase=plan.get("phase", "unknown"),
            objective=plan.get("objective", ""),
            resolved_uncertainties=resolved_uncertainties,
            remaining_uncertainties=remaining_uncertainties,
            active_source_families=active_sources,
            ruled_out_source_families=self.ruled_out_source_families[-10:],
            current_candidates=self.current_candidates,
            eliminated_candidates=self.eliminated_candidates,
            top_evidence=top_evidence,
            pending_urls=self.pending_urls[-20:],
            query_history_summary=query_summary,
            controller_signals=self.controller_signals,
        )
        self.snapshots.append(snapshot)
        return snapshot

    def build_planner_feedback(self, max_findings: int = 3) -> List[Dict[str, str]]:
        """Return compact feedback messages for the planner."""
        messages: List[Dict[str, str]] = []
        if self.current_plan:
            messages.append({
                "role": "user",
                "content": "Current compact state snapshot:\n" + json.dumps(self.export_compact_state(), ensure_ascii=False, indent=2),
            })
        for finding in self.findings_history[-max_findings:]:
            compact_finding = self._compact_finding(finding)
            messages.append({
                "role": "user",
                "content": "Execution feedback:\n" + json.dumps(compact_finding, ensure_ascii=False, indent=2),
            })
        if self.snapshots:
            snap = self.snapshots[-1]
            compact_snap = {
                "phase": snap.phase,
                "objective": snap.objective,
                "resolved_uncertainties": snap.resolved_uncertainties,
                "remaining_uncertainties": snap.remaining_uncertainties,
                "active_source_families": snap.active_source_families,
                "current_candidates": snap.current_candidates,
                "eliminated_candidates": snap.eliminated_candidates,
                "pending_urls": snap.pending_urls[:10],
                "controller_signals": snap.controller_signals,
            }
            messages.append({
                "role": "user",
                "content": "Latest phase snapshot:\n" + json.dumps(compact_snap, ensure_ascii=False, indent=2),
            })
        return messages

    def export_executor_state(self) -> Dict[str, Any]:
        """Slim state for executor — only what it needs to perform a subtask."""
        current_plan_id = (self.current_plan or {}).get("_plan_id")
        current_plan_executions = [
            execution for execution in self.plan_execution_history
            if execution.get("plan_id") == current_plan_id
        ]
        confirmed_wrong = self._export_confirmed_wrong_candidates()
        return {
            "current_candidates": self.current_candidates,
            "eliminated_candidates": [item["name"] for item in confirmed_wrong],
            "confirmed_wrong_candidates": confirmed_wrong,
            "candidate_records": self._export_candidate_records(include_eliminated=False),
            "current_plan_executions": current_plan_executions[-10:],
            "pending_urls": self.pending_urls[-15:],
            "crawled_urls": self.crawled_urls[-10:],
            "visited_domains": self.visited_domains[-20:],
        }

    def export_compact_state(self) -> Dict[str, Any]:
        current_plan_id = (self.current_plan or {}).get("_plan_id")
        current_plan_executions = [
            execution for execution in self.plan_execution_history
            if execution.get("plan_id") == current_plan_id
        ]
        confirmed_wrong = self._export_confirmed_wrong_candidates()
        return {
            "question": self.question,
            "current_plan": self.current_plan,
            "current_candidates": self.current_candidates,
            "eliminated_candidates": [item["name"] for item in confirmed_wrong],
            "confirmed_wrong_candidates": confirmed_wrong,
            "candidate_records": self._export_candidate_records(include_eliminated=False),
            "current_plan_executions": current_plan_executions[-20:],
            "recent_executions": self.plan_execution_history[-3:],
            "pending_urls": self.pending_urls[-20:],
            "crawled_urls": self.crawled_urls[-20:],
            "visited_domains": self.visited_domains[-20:],
            "ruled_out_source_families": self.ruled_out_source_families[-10:],
            "recent_findings": [self._compact_finding(f) for f in self.findings_history[-3:]],
            "recent_observations": [o.to_dict(include_raw=False) for o in list(self.recent_observations)],
            "latest_snapshot": self.snapshots[-1].to_dict() if self.snapshots else None,
            "controller_signals": self.controller_signals,
        }

    def _compact_finding(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "subtask": finding.get("subtask", ""),
            "status": finding.get("status", ""),
            "summary": finding.get("summary", ""),
            "candidate_updates": finding.get("candidate_updates", {}),
            "source_feedback": finding.get("source_feedback", {}),
            "suggestion_for_planner": finding.get("suggestion_for_planner", ""),
        }

    def _normalize_result(self, raw_result: Any) -> str:
        if raw_result is None:
            return ""
        if isinstance(raw_result, str):
            return raw_result
        try:
            return json.dumps(raw_result, ensure_ascii=False, indent=2)
        except Exception:
            return str(raw_result)

    def _compact_tool_result(self, tool_name: str, arguments: Dict[str, Any], raw_text: str) -> str:
        urls = self._extract_urls(raw_text)
        domains = sorted({self._domain_of(u) for u in urls if self._domain_of(u)})
        head = raw_text.strip().replace("\n", " ")
        head = re.sub(r"\s+", " ", head)[:300]

        if tool_name == "search":
            queries = arguments.get("query", []) if isinstance(arguments, dict) else []
            return json.dumps({
                "tool": tool_name,
                "queries": queries,
                "top_domains": domains[:8],
                "url_count": len(urls),
                "snippet": head,
            }, ensure_ascii=False)
        if tool_name in {"crawl_urls", "visit_urls"}:
            crawled = arguments.get("urls", []) if isinstance(arguments, dict) else []
            return json.dumps({
                "tool": tool_name,
                "urls": crawled[:5],
                "domains": [self._domain_of(u) for u in crawled[:5]],
                "snippet": head,
            }, ensure_ascii=False)
        return json.dumps({"tool": tool_name, "snippet": head}, ensure_ascii=False)

    def _extract_urls(self, text: str) -> List[str]:
        return list(dict.fromkeys(URL_RE.findall(text or "")))

    def _domain_of(self, url: str) -> str:
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return ""

    def _candidate_name(self, candidate: Any) -> str:
        if isinstance(candidate, str):
            return candidate.strip()
        if isinstance(candidate, dict):
            return str(candidate.get("name", "")).strip()
        return ""

    def _candidate_key(self, name: str) -> str:
        return re.sub(r"\s+", " ", name.strip().lower())

    def _ensure_candidate_record(self, name: str) -> Dict[str, Any]:
        key = self._candidate_key(name)
        record = self.candidate_records.get(key)
        if record is None:
            record = {
                "name": name,
                "status": "active",
                "verification_status": "unverified",
                "confidence": "low",
                "supporting_constraints": [],
                "unresolved_constraints": [],
                "hard_conflicts": [],
                "evidence": [],
            }
            self.candidate_records[key] = record
        else:
            record["name"] = name
        return record

    def _merge_unique_list(self, target: List[Any], values: List[Any], limit: int = 8) -> None:
        for value in values or []:
            if not value:
                continue
            if value not in target:
                target.append(value)
        if len(target) > limit:
            del target[:-limit]

    def _promote_candidate(self, name: str) -> None:
        if name not in self.current_candidates:
            self.current_candidates.append(name)
        if name in self.eliminated_candidates:
            self.eliminated_candidates.remove(name)

    def _eliminate_candidate(self, name: str, reason: str = "") -> None:
        if name not in self.eliminated_candidates:
            self.eliminated_candidates.append(name)
        if name in self.current_candidates:
            self.current_candidates.remove(name)
        record = self._ensure_candidate_record(name)
        record["status"] = "eliminated"
        record["verification_status"] = "contradicted"
        record["confidence"] = "low"
        if reason:
            self._merge_unique_list(record["hard_conflicts"], [reason], limit=6)

    def _merge_candidate_assessment(self, assessment: Dict[str, Any]) -> None:
        name = self._candidate_name(assessment)
        if not name:
            return
        record = self._ensure_candidate_record(name)
        status = str(assessment.get("status", "")).strip().lower()
        if status in {"active", "viable", "promising", "leading"}:
            record["status"] = "active"
            self._promote_candidate(name)
        elif status in {"eliminated", "ruled_out", "rejected"}:
            self._eliminate_candidate(name, reason="")

        self._merge_unique_list(record["supporting_constraints"], assessment.get("supporting_constraints", []) or [])
        self._merge_unique_list(record["unresolved_constraints"], assessment.get("unresolved_constraints", []) or [])
        self._merge_unique_list(record["hard_conflicts"], assessment.get("hard_conflicts", []) or [], limit=6)
        self._merge_unique_list(record["evidence"], assessment.get("evidence", []) or [], limit=6)
        verification_status = str(assessment.get("verification_status", "")).strip().lower()
        if verification_status in {"unverified", "partial", "verified", "contradicted"}:
            record["verification_status"] = verification_status
        confidence = str(assessment.get("confidence", "")).strip().lower()
        if confidence in {"low", "medium", "high"}:
            record["confidence"] = confidence

        if record["hard_conflicts"]:
            record["status"] = "eliminated"
            record["verification_status"] = "contradicted"
            self._eliminate_candidate(name)
        elif record["status"] == "eliminated":
            record["status"] = "active"
            if record.get("verification_status") == "contradicted":
                record["verification_status"] = "partial"
            self._promote_candidate(name)
        else:
            self._promote_candidate(name)

    def _attach_evidence_to_recent_candidates(self, evidence: List[Dict[str, Any]]) -> None:
        if not evidence:
            return
        for name in list(self.current_candidates[-4:]) + list(self.eliminated_candidates[-4:]):
            record = self._ensure_candidate_record(name)
            for ev in evidence[:3]:
                if isinstance(ev, dict):
                    self._merge_unique_list(record["evidence"], [ev], limit=6)

    def _refresh_candidate_lists(self) -> None:
        active: List[str] = []
        eliminated: List[str] = []
        for record in self.candidate_records.values():
            name = record.get("name", "")
            if not name:
                continue
            if record.get("hard_conflicts"):
                record["status"] = "eliminated"
                record["verification_status"] = "contradicted"
            elif record.get("status") == "eliminated":
                record["status"] = "active"
                if record.get("verification_status") == "contradicted":
                    record["verification_status"] = "partial"
            if self._is_confirmed_wrong_record(record):
                if name not in eliminated:
                    eliminated.append(name)
            else:
                if name not in active:
                    active.append(name)
        self.current_candidates = active
        self.eliminated_candidates = eliminated

    def _is_confirmed_wrong_record(self, record: Dict[str, Any]) -> bool:
        return bool(record.get("hard_conflicts")) and (
            record.get("status") == "eliminated"
            or record.get("verification_status") == "contradicted"
        )

    def _export_confirmed_wrong_candidates(self) -> List[Dict[str, Any]]:
        exported: List[Dict[str, Any]] = []
        for record in self.candidate_records.values():
            if not isinstance(record, dict) or not self._is_confirmed_wrong_record(record):
                continue
            exported.append({
                "name": record.get("name", ""),
                "hard_conflicts": record.get("hard_conflicts", [])[:5],
                "evidence": record.get("evidence", [])[:2],
            })
        return exported

    def _export_candidate_records(self, limit: Optional[int] = None, include_eliminated: bool = False) -> List[Dict[str, Any]]:
        records = list(self.candidate_records.values())
        if not include_eliminated:
            records = [
                record for record in records
                if isinstance(record, dict) and not self._is_confirmed_wrong_record(record)
            ]
        if limit is not None:
            records = records[-limit:]
        exported: List[Dict[str, Any]] = []
        for record in records:
            exported.append({
                "name": record.get("name", ""),
                "status": record.get("status", "active"),
                "verification_status": record.get("verification_status", "unverified"),
                "confidence": record.get("confidence", "low"),
                "supporting_constraints": record.get("supporting_constraints", [])[:5],
                "unresolved_constraints": record.get("unresolved_constraints", [])[:5],
                "hard_conflicts": record.get("hard_conflicts", [])[:5],
                "evidence": record.get("evidence", [])[:3],
            })
        return exported
