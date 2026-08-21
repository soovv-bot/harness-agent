"""LLM-based finalization utilities for bounded search-harness execution."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from loguru import logger

from llm.compat import build_chat_completion_kwargs, chat_completion_with_structuring
from llm.errors import classify_infra_error
from llm.factory import build_openai_client
from answer_verifier import (
    AnswerVerifier,
    VerificationResult,
    ContrastiveResult,
    _env_flag,
)


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
    verification: Optional[Dict[str, Any]] = None

    def to_payload(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "answer": self.answer,
            "confidence": self.confidence,
            "reason": self.reason,
            "remaining_uncertainty": self.remaining_uncertainty,
            "supporting_evidence": self.supporting_evidence,
            "error_type": self.error_type,
            "verification": self.verification,
        }

    def to_answer_block(self) -> str:
        return "<answer>" + json.dumps(self.to_payload(), ensure_ascii=False, indent=2) + "</answer>"


class SearchFinalizer:
    """Use an LLM to convert the current search state into a final answer.

    When ``enable_verification`` is True (default), a grounded self-verification
    pass (Plan A, ``AnswerVerifier``) runs after the candidate answer is
    selected. A refuted candidate is downgraded to ``Unknown`` so the pipeline
    does not commit a strong-but-false answer.
    """

    def __init__(self, api_base: str, api_key: str, model_id: str, *, enable_verification: Optional[bool] = None):
        self.client = build_openai_client(api_base, api_key)
        self.model_id = model_id
        self.max_output_tokens = _env_int("FINALIZER_MAX_TOKENS", 500)
        if enable_verification is None:
            enable_verification = _env_flag("ANSWER_VERIFIER_ENABLED", True)
        self.enable_verification = enable_verification
        self.verifier = AnswerVerifier(api_base, api_key, model_id) if enable_verification else None

    def finalize(
        self,
        question: str,
        compact_state: Dict[str, Any],
        budget_status: Dict[str, Any],
        mode: str = "best_effort",
    ) -> FinalizationResult:
        prompt, rule_best_answer, candidate_names = self._build_prompt(question, compact_state, budget_status, mode)
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
                # Reasoning models put analysis in reasoning_content; try to recover JSON from there.
                try:
                    payload = self._parse_payload(reasoning)
                except ValueError as exc:
                    if not parse_error:
                        parse_error = f"reasoning_content parse failed: {exc}"

            if payload is not None:
                llm_answer = (payload.get("answer") or "Unknown").strip()
                # Guard against finalizer hallucination: if the LLM ignored the
                # "copy JSON" instruction and emitted a free-form answer not in
                # the candidate pool, fall back to the rule-selected best_answer.
                # This prevents answers that never appeared in the trajectory
                # (e.g. pos2 "Joseph G. Rosa" which occurred 0 times).
                if (
                    llm_answer
                    and llm_answer.lower() not in {"unknown", "none", "null", ""}
                    and candidate_names
                    and not self._answer_matches_candidates(llm_answer, candidate_names)
                ):
                    logger.warning(
                        f"Finalizer hallucination guard: LLM answer "
                        f"{llm_answer!r} not in candidate pool "
                        f"{candidate_names[:5]}; falling back to rule answer "
                        f"{rule_best_answer!r}"
                    )
                    llm_answer = rule_best_answer
                    payload["answer"] = llm_answer
                    payload["reason"] = (
                        payload.get("reason", "")
                        + " [hallucination guard: LLM answer not in candidate pool, "
                        "reverted to rule-selected best answer]"
                    )
                result = FinalizationResult(
                    status=payload.get("status", "best_effort"),
                    answer=llm_answer or "Unknown",
                    confidence=payload.get("confidence", "low"),
                    reason=payload.get("reason", self._budget_reason(budget_status)),
                    remaining_uncertainty=payload.get(
                        "remaining_uncertainty",
                        self._infer_uncertainty(compact_state),
                    ),
                    supporting_evidence=self._normalize_evidence(payload.get("supporting_evidence")),
                )
                return self._maybe_verify(question, compact_state, result)

            # Both content and reasoning_content failed to yield JSON -> explicit protocol_error
            # with a local fallback answer derived from compact_state.
            fallback = self._local_fallback_answer(compact_state)
            result = FinalizationResult(
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
            return self._maybe_verify(question, compact_state, result)
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

    def _maybe_verify(
        self,
        question: str,
        compact_state: Dict[str, Any],
        result: FinalizationResult,
    ) -> FinalizationResult:
        """Run grounded self-verification (Plan A) on a produced answer.

        Two-stage verification:
        1. Contrastive verification (P0): if multiple candidates exist, compare
           them and select the one best matching the question's required answer
           type + all constraints. Fixes candidate bias (wrong strong candidate)
           and question misreading (answering the wrong dimension).
        2. Grounded single-candidate verification (Plan A): verify the chosen
           answer against fresh web evidence. REFUTE -> downgrade to Unknown.

        - If verification is disabled or the answer is already Unknown, no-op.
        - Verified / inconclusive results keep the (possibly replaced) answer;
          verification metadata is attached for downstream analysis.
        """
        if not self.verifier:
            return result
        answer = (result.answer or "").strip()
        if not answer or answer.lower() in {"unknown", "none", "null"}:
            return result

        type_hint = self._infer_answer_type_hint(question)

        # --- Stage 1: contrastive (multi-candidate) verification ---------------
        contrastive_meta: Optional[Dict[str, Any]] = None
        candidates = self._collect_candidates_for_contrast(compact_state, answer)
        if len(candidates) >= 2:
            try:
                cr = self.verifier.contrastive_verify(
                    question, candidates, answer_type_hint=type_hint
                )
                contrastive_meta = cr.to_dict()
                if cr.winner and cr.winner.strip().lower() != answer.lower():
                    logger.info(
                        f"[Finalizer] contrastive_verify replaced answer: "
                        f"{answer!r} -> {cr.winner!r} "
                        f"(answer_type={cr.answer_type})"
                    )
                    result.answer = cr.winner
                    answer = cr.winner
                    result.reason = (
                        (result.reason + " | " if result.reason else "")
                        + f"Contrastive verification selected {cr.winner} "
                        f"(answer_type={cr.answer_type}): {cr.reason[:200]}"
                    )
            except Exception as exc:
                logger.warning(f"[Finalizer] contrastive_verify failed: {exc}")

        # --- Stage 2: grounded single-candidate verification (Plan A) -------
        candidate_record = self._pick_candidate_record(compact_state, answer)
        try:
            vr = self.verifier.verify(question, answer, candidate_record)
        except Exception as exc:
            logger.warning(f"[Finalizer] verification failed (inconclusive): {exc}")
            vr = VerificationResult(
                verdict="inconclusive",
                reason=f"verification exception: {exc}",
            )
        result.verification = vr.to_dict()
        if contrastive_meta:
            result.verification["contrastive"] = contrastive_meta
        if vr.is_refuted:
            logger.info(
                f"[Finalizer] answer REFUTED by grounded verification: "
                f"answer={answer!r} reason={vr.reason[:120]}"
            )
            result.answer = "Unknown"
            result.confidence = "none"
            result.status = "best_effort"
            result.reason = (
                (result.reason + " | " if result.reason else "")
                + f"Self-verification REFUTED candidate: {vr.reason}"
            )
            result.error_type = result.error_type or "verification_refuted"
        return result

    @staticmethod
    def _infer_answer_type_hint(question: str) -> str:
        """Lightweight keyword-based answer-type inference (mirrors pipeline's
        _infer_question_answer_type). Used as fallback when the LLM's
        contrastive_verify returns an empty answer_type.

        Checks the last clause (the actual question) first, since BrowseComp
        questions often describe one entity type but ask for another."""
        q = (question or "").lower()
        import re
        clauses = [c.strip() for c in re.split(r'[.?!]\s+', q) if c.strip()]
        ask_clause = clauses[-1] if clauses else q
        if any(kw in ask_clause for kw in [
            "the name of the player", "the name of the person", "who is", "who was",
            "the name of the author", "the name of the academic",
            "husband", "wife", "spouse", "full name of", "name of the",
            "the name of the", "whose", "who did", "who wrote", "who directed",
            "who painted", "who composed", "who founded", "who discovered",
        ]):
            return "person"
        if any(kw in ask_clause for kw in ["university", "college", "institute", "school", "academy"]):
            return "institution"
        if any(kw in ask_clause for kw in ["what year", "which year", "in what year", "what date"]):
            return "year"
        if any(kw in ask_clause for kw in ["which country", "what city", "what place", "which place", "where"]):
            return "place"
        if any(kw in q for kw in ["husband", "wife", "spouse", "full name of"]):
            return "person"
        if any(kw in q for kw in ["university", "college", "institute", "school", "academy"]):
            return "institution"
        if any(kw in q for kw in ["what year", "which year", "in what year", "what date"]):
            return "year"
        if any(kw in q for kw in ["which country", "what city", "what place", "which place", "where"]):
            return "place"
        return ""

    def _collect_candidates_for_contrast(
        self,
        compact_state: Dict[str, Any],
        current_answer: str,
        top_n: int = 5,
    ) -> List[Dict[str, str]]:
        """Collect top-N candidates with evidence for contrastive verification.

        Ranks viable (non-eliminated) candidates by satisfied-constraint count,
        includes current_candidates, and ensures the finalizer's chosen answer
        is in the pool. Returns [{"name": str, "evidence": str}].
        """
        records = compact_state.get("candidate_records") or []
        viable: List[Dict[str, Any]] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            name = str(record.get("candidate") or record.get("name") or "").strip()
            if not name or name.lower() in {"unknown", "none", "null"}:
                continue
            if record.get("hard_conflicts"):
                continue
            ev_list = record.get("evidence") or []
            ev_text = "; ".join(
                str(e.get("observation", "")) if isinstance(e, dict) else str(e)
                for e in ev_list[:3]
            )
            sup_constraints = record.get("supporting_constraints") or []
            unr_constraints = record.get("unresolved_constraints") or []
            viable.append(
                {
                    "name": name,
                    "support": len(sup_constraints),
                    "evidence": ev_text,
                    "supporting_constraints": sup_constraints[:8],
                    "unresolved_constraints": unr_constraints[:8],
                    "verification_status": str(
                        record.get("verification_status") or "unverified"
                    ),
                }
            )
        # Add current_candidates not already present.
        for cand in compact_state.get("current_candidates") or []:
            name = ""
            if isinstance(cand, str):
                name = cand.strip()
            elif isinstance(cand, dict):
                name = str(cand.get("candidate") or cand.get("name") or "").strip()
            if name and name.lower() not in {"unknown", "none", "null"}:
                if not any(v["name"].lower() == name.lower() for v in viable):
                    viable.append({
                        "name": name, "support": 0, "evidence": "",
                        "supporting_constraints": [], "unresolved_constraints": [],
                        "verification_status": "unverified",
                    })
        # Ensure the finalizer's chosen answer is in the pool.
        if current_answer and current_answer.lower() not in {"unknown", "none", "null"}:
            if not any(v["name"].lower() == current_answer.lower() for v in viable):
                viable.append({
                    "name": current_answer, "support": 0, "evidence": "",
                    "supporting_constraints": [], "unresolved_constraints": [],
                    "verification_status": "unverified",
                })
        # Sort by support desc, take top_n.
        viable.sort(key=lambda v: -v["support"])
        return [
            {
                "name": v["name"],
                "evidence": v["evidence"],
                "supporting_constraints": v.get("supporting_constraints", []),
                "unresolved_constraints": v.get("unresolved_constraints", []),
                "verification_status": v.get("verification_status", "unverified"),
            }
            for v in viable[:top_n]
        ]

    def _pick_candidate_record(
        self,
        compact_state: Dict[str, Any],
        answer: str,
    ) -> Optional[Dict[str, Any]]:
        """Find the candidate record matching the chosen answer, if any."""
        key = answer.strip().lower()
        if not key:
            return None
        for record in (compact_state.get("candidate_records") or []):
            if not isinstance(record, dict):
                continue
            name = str(record.get("candidate") or record.get("name") or "").strip().lower()
            if name and name == key:
                return record
        return None

    def _collect_viable_candidates(
        self,
        compact_state: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Collect unique viable (non-eliminated) candidates from compact_state.

        Returns a list of {"name": str, "status": "active"} dicts, deduplicated.
        """
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
        # Deduplicate preserving order
        seen = set()
        unique = []
        for c in candidates:
            key = c["name"].lower()
            if key not in seen:
                seen.add(key)
                unique.append(c)
        return unique

    def _select_best_answer(
        self,
        compact_state: Dict[str, Any],
    ) -> tuple:
        """Select the strongest viable candidate as the answer.

        Returns (best_answer, viable_candidate_names). Uses Plan B ranking
        (supporting-constraint count, verification status tiebreaker).
        """
        unique_candidates = self._collect_viable_candidates(compact_state)
        viable = [c for c in unique_candidates if c["status"] != "eliminated"]
        viable = self._rank_candidates_by_support(viable, compact_state)
        best_answer = viable[0]["name"] if viable else "Unknown"
        names = [c["name"] for c in viable]
        return best_answer, names

    @staticmethod
    def _answer_matches_candidates(answer: str, candidate_names: List[str]) -> bool:
        """Check if the LLM-returned answer matches any candidate (fuzzy).

        Guards against finalizer hallucination: if the model ignores the
        "copy JSON" instruction and emits a free-form answer not in the
        candidate pool, the caller should fall back to the rule-selected
        best_answer instead.
        """
        if not answer:
            return False
        a_norm = re.sub(r"[^a-z0-9]", "", answer.lower())
        if not a_norm:
            return False
        for name in candidate_names:
            n_norm = re.sub(r"[^a-z0-9]", "", (name or "").lower())
            if not n_norm:
                continue
            # exact normalized match, or one contains the other (covers short
            # answers like "a cigarette" vs "cigarette")
            if a_norm == n_norm or a_norm in n_norm or n_norm in a_norm:
                return True
        return False

    def _build_prompt(
        self,
        question: str,
        compact_state: Dict[str, Any],
        budget_status: Dict[str, Any],
        mode: str,
    ) -> tuple:
        """Build the finalizer prompt.

        Returns (prompt, best_answer, candidate_names) so the caller can
        validate the LLM-returned answer against the candidate pool.
        """
        best_answer, candidate_names = self._select_best_answer(compact_state)
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
        prompt = (
            f"Question: {question}\n\n"
            f"Answer: {best_answer}\n\n"
            f"Output: {answer_json}"
        )
        return prompt, best_answer, candidate_names

    def _parse_payload(self, text: str) -> Dict[str, Any]:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in finalizer response")
        payload = json.loads(match.group(0))
        if not isinstance(payload, dict):
            raise ValueError("Finalizer response was not a JSON object")
        return payload

    def _rank_candidates_by_support(
        self,
        candidates: List[Dict[str, Any]],
        compact_state: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Rank viable candidates by satisfied-constraint count (Plan B).

        Uses ``candidate_records.supporting_constraints`` as a lightweight
        process reward. Falls back to original order when no records exist.

        Ranking factors (in order):
        1. Supporting-constraint count (more = stronger evidence)
        2. Negative signals in unresolved constraints (fewer = better):
           detects phrases like "does not match" that indicate active
           disqualification evidence, not just unverified questions
        3. Unresolved-constraint count (fewer = more complete verification)
        4. Verification status: verified > partial > unverified > contradicted
        5. Source diversity (more independent URLs = better)
        """
        records = {str(r.get("candidate") or r.get("name") or "").strip().lower(): r
                   for r in (compact_state.get("candidate_records") or [])
                   if isinstance(r, dict)}
        vorder = {"verified": 0, "partial": 1, "unverified": 2, "contradicted": 3}
        _NEGATIVE_PATTERNS = [
            "does not match", "doesn't match", "not consistent",
            "contradicts", "does not fit", "not compatible",
            "no evidence", "not found", "no match", "ruled out",
        ]

        def _unique_sources(rec: Dict[str, Any]) -> int:
            ev = rec.get("evidence") or []
            sources = set()
            for e in ev:
                if not isinstance(e, dict):
                    continue
                s = str(e.get("source_url") or e.get("source") or "").strip()
                if s:
                    sources.add(s)
            return len(sources)

        def _negative_signals(rec: Dict[str, Any]) -> int:
            count = 0
            for u in (rec.get("unresolved_constraints") or []):
                u_lower = str(u).lower()
                if any(neg in u_lower for neg in _NEGATIVE_PATTERNS):
                    count += 1
            return count

        def score(c: Dict[str, Any]) -> tuple:
            name = str(c.get("name", "")).strip().lower()
            rec = records.get(name, {})
            support_n = len(rec.get("supporting_constraints") or [])
            unique_sources = _unique_sources(rec)
            vs = str(rec.get("verification_status") or "unverified").lower()
            unresolved_n = len(rec.get("unresolved_constraints") or [])
            neg_signals = _negative_signals(rec)
            return (
                -support_n, neg_signals, unresolved_n,
                vorder.get(vs, 2), -unique_sources,
            )

        return sorted(candidates, key=score)

    def _local_fallback_answer(self, compact_state: Dict[str, Any]) -> str:
        """Derive a best-guess answer from compact_state when the LLM output is unparseable.

        Delegates to _select_best_answer for consistency with _build_prompt.
        """
        best_answer, _ = self._select_best_answer(compact_state)
        return best_answer

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
        if not isinstance(plan, dict):
            plan = {}
        latest_snapshot = compact_state.get("latest_snapshot") or {}
        if not isinstance(latest_snapshot, dict):
            latest_snapshot = {}
        recent_findings = compact_state.get("recent_findings") or []
        pool_assessment = plan.get("pool_assessment")
        if not isinstance(pool_assessment, dict):
            pool_assessment = {}
        gaps = pool_assessment.get("gaps") or pool_assessment.get("missing_candidate_types") or []
        if gaps:
            return str(gaps[0])
        rem = latest_snapshot.get("remaining_uncertainties", [])
        if rem:
            return str(rem[0])
        open_qs: List[str] = []
        for finding in recent_findings[-2:]:
            if not isinstance(finding, dict):
                continue
            open_qs.extend(finding.get("open_questions") or [])
        if open_qs:
            return str(open_qs[0])
        return "No candidate was identified before the search budget was exhausted."
