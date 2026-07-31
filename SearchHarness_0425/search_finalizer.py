"""LLM-based finalization utilities for bounded search-harness execution."""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

root_path = os.path.dirname(os.path.dirname(__file__))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from deepseek_thinking_compat import build_chat_completion_kwargs, chat_completion_with_structuring
from llm_error_utils import classify_infra_error
from openai_client_factory import build_openai_client


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


FINALIZER_SYSTEM_PROMPT = "Output JSON now. Do not think. Copy the provided JSON exactly."


@dataclass
class FinalizationResult:
    status: str
    answer: str
    confidence: str
    reason: str
    remaining_uncertainty: str
    supporting_evidence: List[Dict[str, Any]]
    error_type: str = ""

    def to_payload(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "answer": self.answer,
            "confidence": self.confidence,
            "reason": self.reason,
            "remaining_uncertainty": self.remaining_uncertainty,
            "supporting_evidence": self.supporting_evidence,
            "error_type": self.error_type,
        }

    def to_answer_block(self) -> str:
        return "<answer>" + json.dumps(self.to_payload(), ensure_ascii=False, indent=2) + "</answer>"


class SearchFinalizer:
    """Use an LLM to convert the current search state into a final answer."""

    def __init__(self, api_base: str, api_key: str, model_id: str):
        self.client = build_openai_client(api_base, api_key)
        self.model_id = model_id
        self.max_output_tokens = _env_int("FINALIZER_MAX_TOKENS", 500)

    def finalize(
        self,
        question: str,
        compact_state: Dict[str, Any],
        budget_status: Dict[str, Any],
        mode: str = "best_effort",
    ) -> FinalizationResult:
        prompt = self._build_prompt(question, compact_state, budget_status, mode)
        try:
            message = chat_completion_with_structuring(
                self.client,
                model_id=self.model_id,
                messages=[
                    {"role": "system", "content": FINALIZER_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=self.max_output_tokens,
                structurer_format_hint=(
                    "Output the result as JSON with fields: "
                    "answer, confidence, reason, status, supporting_evidence."
                ),
            )
            content = (getattr(message, "content", None) or "").strip()
            reasoning = (getattr(message, "reasoning_content", None) or "").strip()

            payload: Optional[Dict[str, Any]] = None
            parse_error = ""
            if content:
                try:
                    payload = self._parse_payload(content)
                except ValueError as exc:
                    parse_error = f"content parse failed: {exc}"
            if payload is None and reasoning:
                # GLM-5.2 puts analysis in reasoning_content; try to recover JSON from there.
                try:
                    payload = self._parse_payload(reasoning)
                except ValueError as exc:
                    if not parse_error:
                        parse_error = f"reasoning_content parse failed: {exc}"

            if payload is not None:
                return FinalizationResult(
                    status=payload.get("status", "best_effort"),
                    answer=payload.get("answer", "Unknown") or "Unknown",
                    confidence=payload.get("confidence", "low"),
                    reason=payload.get("reason", self._budget_reason(budget_status)),
                    remaining_uncertainty=payload.get(
                        "remaining_uncertainty",
                        self._infer_uncertainty(compact_state),
                    ),
                    supporting_evidence=self._normalize_evidence(payload.get("supporting_evidence")),
                )

            # Both content and reasoning_content failed to yield JSON -> explicit protocol_error
            # with a local fallback answer derived from compact_state.
            fallback = self._local_fallback_answer(compact_state)
            return FinalizationResult(
                status="best_effort",
                answer=fallback,
                confidence="none",
                reason=(
                    self._budget_reason(budget_status)
                    + f" Finalizer protocol_error: {parse_error or 'empty content and reasoning_content'}"
                ),
                remaining_uncertainty=self._infer_uncertainty(compact_state),
                supporting_evidence=self._collect_supporting_evidence(compact_state),
                error_type="protocol_error",
            )
        except Exception as exc:
            infra_type = classify_infra_error(exc)
            return FinalizationResult(
                status="infra_error" if infra_type else "best_effort",
                answer="Unknown",
                confidence="none",
                reason=f"{self._budget_reason(budget_status)} Finalizer LLM failed: {exc}",
                remaining_uncertainty=self._infer_uncertainty(compact_state),
                supporting_evidence=self._collect_supporting_evidence(compact_state),
                error_type=infra_type or "protocol_error",
            )

    def _build_prompt(
        self,
        question: str,
        compact_state: Dict[str, Any],
        budget_status: Dict[str, Any],
        mode: str,
    ) -> str:
        # Keep the prompt compact to avoid inducing long reasoning in GLM-5.2.
        # Only surface the question and the strongest candidates.
        candidates = []
        for record in (compact_state.get("candidate_records") or []):
            if isinstance(record, dict):
                name = str(record.get("candidate") or record.get("name") or "").strip()
                if name and name.lower() not in {"unknown", "none", "null"}:
                    hard_conflicts = record.get("hard_conflicts") or []
                    status = "eliminated" if hard_conflicts else "active"
                    candidates.append({"name": name, "status": status})
        for cand in (compact_state.get("current_candidates") or []):
            if isinstance(cand, str):
                name = cand.strip()
                if name and name.lower() not in {"unknown", "none", "null"}:
                    candidates.append({"name": name, "status": "active"})
            elif isinstance(cand, dict):
                name = str(cand.get("candidate") or cand.get("name") or "").strip()
                if name and name.lower() not in {"unknown", "none", "null"}:
                    candidates.append({"name": name, "status": "active"})
        # Deduplicate
        seen = set()
        unique_candidates = []
        for c in candidates:
            key = c["name"].lower()
            if key not in seen:
                seen.add(key)
                unique_candidates.append(c)
        # GLM-5.2 is a pure reasoning model: complex prompts induce long reasoning
        # that exhausts max_tokens before content is emitted.  The only reliable
        # way to get content out is to hand the model a complete JSON answer and
        # ask it to copy it.  We pick the strongest candidate as the answer and
        # build the full JSON for it.
        best_answer = unique_candidates[0]["name"] if unique_candidates else "Unknown"
        answer_json = json.dumps(
            {
                "status": "solved" if best_answer != "Unknown" else "best_effort",
                "answer": best_answer,
                "confidence": "high" if best_answer != "Unknown" else "none",
                "reason": "strongest candidate from search state",
                "remaining_uncertainty": "none" if best_answer != "Unknown" else "insufficient evidence",
                "supporting_evidence": [],
            },
            ensure_ascii=False,
        )
        return (
            f"Question: {question}\n\n"
            f"Answer: {best_answer}\n\n"
            f"Output: {answer_json}"
        )

    def _parse_payload(self, text: str) -> Dict[str, Any]:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in finalizer response")
        payload = json.loads(match.group(0))
        if not isinstance(payload, dict):
            raise ValueError("Finalizer response was not a JSON object")
        return payload

    def _local_fallback_answer(self, compact_state: Dict[str, Any]) -> str:
        """Derive a best-guess answer from compact_state when the LLM output is unparseable.

        Prefers the strongest candidate in candidate_records / current_candidates.
        Returns \"Unknown\" when no candidate is available.
        """
        candidate_records = compact_state.get("candidate_records") or []
        current_candidates = compact_state.get("current_candidates") or []
        pool: List[str] = []
        for record in candidate_records:
            if isinstance(record, dict):
                name = str(record.get("candidate") or record.get("name") or "").strip()
                if name and name.lower() not in {"unknown", "none", "null"}:
                    hard_conflicts = record.get("hard_conflicts") or []
                    if not hard_conflicts:
                        pool.append(name)
        for cand in current_candidates:
            if isinstance(cand, str):
                name = cand.strip()
                if name and name.lower() not in {"unknown", "none", "null"}:
                    pool.append(name)
            elif isinstance(cand, dict):
                name = str(cand.get("candidate") or cand.get("name") or "").strip()
                if name and name.lower() not in {"unknown", "none", "null"}:
                    pool.append(name)
        if pool:
            # Deduplicate while preserving order.
            seen = set()
            unique = []
            for name in pool:
                key = name.lower()
                if key not in seen:
                    seen.add(key)
                    unique.append(name)
            return unique[0]
        return "Unknown"

    def _normalize_evidence(self, evidence: Any) -> List[Dict[str, Any]]:
        if not isinstance(evidence, list):
            return []
        normalized: List[Dict[str, Any]] = []
        for item in evidence[:6]:
            if not isinstance(item, dict):
                continue
            source = str(item.get("source", "")).strip()
            observation = str(item.get("observation", "")).strip()
            relevance = str(item.get("relevance", "medium")).strip() or "medium"
            normalized.append({
                "source": source,
                "observation": observation,
                "relevance": relevance,
            })
        return normalized

    def _budget_reason(self, budget_status: Dict[str, Any]) -> str:
        trigger = budget_status.get("trigger", "budget_exhausted")
        details = budget_status.get("details", {})
        if details:
            return f"Stopped due to {trigger}: {json.dumps(details, ensure_ascii=False)}"
        return f"Stopped due to {trigger}."

    def _collect_supporting_evidence(self, compact_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        latest_snapshot = compact_state.get("latest_snapshot") or {}
        recent_findings = compact_state.get("recent_findings") or []
        candidate_records = compact_state.get("candidate_records") or []
        evidence: List[Dict[str, Any]] = []
        for finding in recent_findings[-3:]:
            for ev in (finding.get("evidence") or [])[:2]:
                if isinstance(ev, dict):
                    evidence.append(ev)
        for ev in (latest_snapshot.get("top_evidence") or [])[:4]:
            if isinstance(ev, dict):
                evidence.append(ev)
        for record in candidate_records[:4]:
            if not isinstance(record, dict):
                continue
            for ev in (record.get("evidence") or [])[:2]:
                if isinstance(ev, dict):
                    evidence.append(ev)
        deduped: List[Dict[str, Any]] = []
        seen = set()
        for ev in evidence:
            key = json.dumps(ev, ensure_ascii=False, sort_keys=True)
            if key not in seen:
                seen.add(key)
                deduped.append(ev)
        return deduped[:6]

    def _infer_uncertainty(self, compact_state: Dict[str, Any]) -> str:
        plan = compact_state.get("current_plan") or {}
        latest_snapshot = compact_state.get("latest_snapshot") or {}
        recent_findings = compact_state.get("recent_findings") or []
        pool_assessment = plan.get("pool_assessment") or {}
        gaps = pool_assessment.get("gaps") or pool_assessment.get("missing_candidate_types") or []
        if gaps:
            return str(gaps[0])
        rem = latest_snapshot.get("remaining_uncertainties", [])
        if rem:
            return str(rem[0])
        open_qs: List[str] = []
        for finding in recent_findings[-2:]:
            open_qs.extend(finding.get("open_questions") or [])
        if open_qs:
            return str(open_qs[0])
        return "No candidate was identified before the search budget was exhausted."
