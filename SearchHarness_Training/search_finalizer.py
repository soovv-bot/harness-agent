"""LLM-based finalization utilities for bounded search-harness execution."""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, List

root_path = os.path.dirname(os.path.dirname(__file__))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from deepseek_thinking_compat import build_chat_completion_kwargs
from openai_client_factory import build_openai_client


FINALIZER_SYSTEM_PROMPT = """You are the finalizer for a search harness.

You must produce the best possible final answer using only the provided question,
search state, findings, and stop reason. Do not invent new evidence. Do not call
tools. Do not continue searching.

Important rules:
- Answer the original question directly.
- Do not output an intermediate candidate unless the question itself asks for that candidate.
- If the state strongly supports a final answer, provide it.
- If the evidence is insufficient, return answer as \"Unknown\".
- Prefer concise, specific answers over explanations.
- Treat candidate_records as the source of truth for candidate quality.
- Do not finalize from a candidate that has any hard_conflicts unless the conflict is explicitly resolved by stronger evidence already present in the state.
- Prefer candidates with concrete supporting_constraints over candidates that only appear in summaries.

Output JSON only:
{
  \"status\": \"solved | best_effort\",
  \"answer\": \"string\",
  \"confidence\": \"high | medium | low | none\",
  \"reason\": \"brief explanation\",
  \"remaining_uncertainty\": \"brief explanation\",
  \"supporting_evidence\": [
    {\"source\": \"string\", \"observation\": \"string\", \"relevance\": \"high | medium | low\"}
  ]
}
"""


@dataclass
class FinalizationResult:
    status: str
    answer: str
    confidence: str
    reason: str
    remaining_uncertainty: str
    supporting_evidence: List[Dict[str, Any]]

    def to_payload(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "answer": self.answer,
            "confidence": self.confidence,
            "reason": self.reason,
            "remaining_uncertainty": self.remaining_uncertainty,
            "supporting_evidence": self.supporting_evidence,
        }

    def to_answer_block(self) -> str:
        return "<answer>" + json.dumps(self.to_payload(), ensure_ascii=False, indent=2) + "</answer>"


class SearchFinalizer:
    """Use an LLM to convert the current search state into a final answer."""

    def __init__(self, api_base: str, api_key: str, model_id: str):
        self.client = build_openai_client(api_base, api_key)
        self.model_id = model_id
        self.last_messages: List[Dict[str, str]] = []

    def finalize(
        self,
        question: str,
        compact_state: Dict[str, Any],
        budget_status: Dict[str, Any],
        mode: str = "best_effort",
    ) -> FinalizationResult:
        prompt = self._build_prompt(question, compact_state, budget_status, mode)
        self.last_messages = []
        try:
            messages = [
                {"role": "system", "content": FINALIZER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
            completion = self.client.chat.completions.create(
                **build_chat_completion_kwargs(
                    model_id=self.model_id,
                    messages=messages,
                    temperature=0.0,
                )
            )
            text = completion.choices[0].message.content or ""
            self.last_messages = messages + [{"role": "assistant", "content": text}]
            payload = self._parse_payload(text)
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
        except Exception as exc:
            return FinalizationResult(
                status="best_effort",
                answer="Unknown",
                confidence="none",
                reason=f"{self._budget_reason(budget_status)} Finalizer LLM failed: {exc}",
                remaining_uncertainty=self._infer_uncertainty(compact_state),
                supporting_evidence=self._collect_supporting_evidence(compact_state),
            )

    def _build_prompt(
        self,
        question: str,
        compact_state: Dict[str, Any],
        budget_status: Dict[str, Any],
        mode: str,
    ) -> str:
        prompt_payload = {
            "question": question,
            "requested_mode": mode,
            "budget_status": budget_status,
            "compact_state": compact_state,
        }
        return json.dumps(prompt_payload, ensure_ascii=False, indent=2)

    def _parse_payload(self, text: str) -> Dict[str, Any]:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in finalizer response")
        payload = json.loads(match.group(0))
        if not isinstance(payload, dict):
            raise ValueError("Finalizer response was not a JSON object")
        return payload

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
