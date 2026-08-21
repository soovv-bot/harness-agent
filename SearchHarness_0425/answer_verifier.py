"""Self-verification before commit (Plan A).

Independent verification of the finalizer's candidate answer against the
original question, before the answer is committed. Implements a lightweight
form of Chain-of-Verification (CoVe, Meta 2024) / self-refine that is
grounded in the search environment rather than pure LLM introspection.

Pipeline:
    candidate answer
        -> extract checkable claim from (question, answer, candidate_record)
        -> issue ONE verification search via the existing Serper `search()` tool
        -> ask an LLM whether the evidence confirms or contradicts the claim
        -> return a Verdict(verified | refuted | inconclusive)

Design goals (minimal-change, theory-forward, practical):
- Reuses the existing `search()` tool from OffSeeker-main/inference/src/tools.
- Reuses `candidate_records.unresolved_constraints` as the verification focus.
- One extra search + one extra LLM call per finalize. Cost bound is constant.
- Failure-safe: any infra/parse error degrades to `inconclusive` and the
  original answer is still returned (never blocks the pipeline).

Theory anchor (for the paper):
    Replacing "pick strongest candidate" with "candidate + independent grounded
    verification" converts the finalizer from a ranker into a verifier. The
    verification step is grounded in fresh web evidence, so a candidate that
    was merely *plausible* (strong-but-false) can be caught before commit. This
    directly targets the dominant BrowseComp failure mode of converging on a
    confident wrong candidate.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger

from llm.compat import build_chat_completion_kwargs, chat_completion_with_structuring  # noqa: E402
from llm.factory import build_openai_client  # noqa: E402

try:
    from tools.search_tools import search as _serper_search  # type: ignore
except Exception as _import_err:  # pragma: no cover - import guarded for tests
    _serper_search = None
    logger.debug(f"[AnswerVerifier] search_tools import failed: {_import_err}")


VERIFIED = "verified"
REFUTED = "refuted"
INCONCLUSIVE = "inconclusive"


@dataclass
class VerificationResult:
    """Outcome of a single self-verification pass."""
    verdict: str
    reason: str
    verification_query: str = ""
    evidence_snippet: str = ""
    confidence: str = "low"  # low | medium | high

    @property
    def is_verified(self) -> bool:
        return self.verdict == VERIFIED

    @property
    def is_refuted(self) -> bool:
        return self.verdict == REFUTED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "reason": self.reason,
            "verification_query": self.verification_query,
            "evidence_snippet": self.evidence_snippet,
            "confidence": self.confidence,
        }


@dataclass
class ContrastiveResult:
    """Outcome of contrastive (multi-candidate) verification.

    Selects the candidate that best satisfies the question's required answer
    type + all constraints. Targets two dominant BrowseComp failure modes:
    - Candidate bias: converging on a strong-but-wrong candidate.
    - Question misreading: answering the wrong dimension (e.g. asked for an
      author, answered an institution).
    """

    answer_type: str
    winner: Optional[str]  # None = no candidate satisfies the required type
    reason: str
    constraint_check: str = ""
    confidence: str = "low"  # low | medium | high

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer_type": self.answer_type,
            "winner": self.winner,
            "reason": self.reason,
            "constraint_check": self.constraint_check,
            "confidence": self.confidence,
        }


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_flag(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _truncate(text: str, n: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[:n] + "..."


class AnswerVerifier:
    """Grounded self-verification of a finalizer answer.

    One search + one LLM judgment per call. Constant cost, failure-safe.
    """

    SYSTEM_PROMPT = (
        "You are a strict fact verifier. You judge whether a piece of evidence "
        "CONFIRMS or CONTRADICTS a specific factual claim. "
        "You must not rely on your own parametric memory; only use the provided "
        "evidence. If the evidence does not clearly confirm or refute the claim, "
        "output inconclusive."
    )

    CONTRASTIVE_SYSTEM_PROMPT = (
        "You are a strict answer selector. Given a research question and "
        "multiple candidate answers with evidence, you identify which "
        "candidate the question actually ASKS FOR (the required answer type) "
        "and select the candidate that best matches that type and satisfies "
        "all stated constraints. You must not rely on your own parametric "
        "memory; only use the provided evidence.\n\n"
        "INTERPRETIVE AMBIGUITY RULE (critical): When a question constraint "
        "is ambiguous and two candidates each satisfy it under a different "
        "reasonable interpretation (e.g. 'made from a particular flower' could "
        "mean a substance directly extracted from the flower OR a derivative "
        "of that substance), do NOT pick a winner by preferring one "
        "interpretation of the ambiguous phrase over the other. Instead, look "
        "for DISAMBIGUATING constraints elsewhere in the question (entity type, "
        "date, name, distinctive fact) that distinguish the candidates. If the "
        "ambiguous constraint is the ONLY distinguishing constraint and no "
        "other constraint breaks the tie, set winner to null (the question is "
        "under-specified for the provided evidence)."
    )

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model_id: str,
        *,
        max_search_results: int = 2000,
    ):
        self.client = build_openai_client(api_base, api_key)
        self.model_id = model_id
        self.max_search_results = max_search_results
        self.max_output_tokens = _env_int("VERIFIER_MAX_TOKENS", 400)
        self.enabled = _env_flag("ANSWER_VERIFIER_ENABLED", True)

    def verify(
        self,
        question: str,
        answer: str,
        candidate_record: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """Verify a candidate answer against the original question.

        Args:
            question: The original BrowseComp-style research question.
            answer: The candidate answer produced by the finalizer.
            candidate_record: Optional candidate record carrying
                unresolved_constraints / supporting_constraints used to focus
                the verification query.

        Returns:
            VerificationResult. Never raises; infra/parse errors -> inconclusive.
        """
        if not self.enabled:
            return VerificationResult(
                verdict=INCONCLUSIVE,
                reason="Answer verifier disabled by ANSWER_VERIFIER_ENABLED.",
            )
        if not answer or answer.strip().lower() in {"unknown", "none", "null", ""}:
            return VerificationResult(
                verdict=INCONCLUSIVE,
                reason="No candidate answer to verify.",
            )

        claim = self._build_claim(question, answer, candidate_record)
        vquery = self._build_verification_query(question, answer, candidate_record)
        if not vquery:
            return VerificationResult(
                verdict=INCONCLUSIVE,
                reason="Could not construct a verification query.",
            )

        evidence = self._search_evidence(vquery)
        if not evidence:
            return VerificationResult(
                verdict=INCONCLUSIVE,
                reason="Verification search returned no usable evidence.",
                verification_query=vquery,
            )

        verdict = self._judge(claim, vquery, evidence, question=question)
        verdict.verification_query = vquery
        return verdict

    def contrastive_verify(
        self,
        question: str,
        candidates: List[Dict[str, str]],
        answer_type_hint: str = "",
    ) -> ContrastiveResult:
        """Compare top-N candidates and select the one best satisfying the
        question's required answer type + all constraints. No extra search;
        uses evidence already gathered in compact_state.

        Args:
            answer_type_hint: Deterministic hint (person/institution/...) from
                the pipeline's _infer_question_answer_type. Used as fallback
                when the LLM returns an empty answer_type.

        Targets two dominant BrowseComp failure modes:
        - Candidate bias (converging on a wrong strong candidate) -> pairwise
          comparison selects the constraint-best candidate.
        - Question misreading (answering the wrong dimension, e.g. asked for
          author, answered institution) -> forced answer_type analysis
          rejects candidates that don't match the required type.

        Failure-safe: any error -> winner=None (does not block the pipeline).
        """
        if not self.enabled:
            return ContrastiveResult(
                answer_type="",
                winner=None,
                reason="Answer verifier disabled by ANSWER_VERIFIER_ENABLED.",
            )
        clean: List[Dict[str, str]] = []
        for c in candidates:
            name = str(c.get("name", "")).strip()
            if name and name.lower() not in {"unknown", "none", "null"}:
                clean.append(
                    {
                        "name": name,
                        "evidence": _truncate(str(c.get("evidence", "")), 600),
                        "supporting_constraints": c.get("supporting_constraints") or [],
                        "unresolved_constraints": c.get("unresolved_constraints") or [],
                        "verification_status": str(c.get("verification_status", "unverified")),
                    }
                )
        if not clean:
            return ContrastiveResult(
                answer_type="",
                winner=None,
                reason="No valid candidates to compare.",
            )

        def _fmt_list(items: List[str], prefix: str = "  - ") -> str:
            if not items:
                return "  (none)"
            return "\n".join(f"{prefix}{_truncate(str(item), 120)}" for item in items[:8])

        cand_block = "\n".join(
            f"{i + 1}. {c['name']} (verification: {c['verification_status']})\n"
            f"   Satisfied constraints:\n{_fmt_list(c['supporting_constraints'])}\n"
            f"   UNRESOLVED constraints:\n{_fmt_list(c['unresolved_constraints'])}\n"
            f"   Evidence: {c['evidence']}"
            for i, c in enumerate(clean)
        )
        prompt = (
            f"Research question:\n{_truncate(question, 1200)}\n\n"
            f"Candidate answers with constraints and evidence:\n{cand_block}\n\n"
            "You are a strict answer selector. Decide which candidate is correct.\n"
            "Steps:\n"
            "1. ANSWER TYPE: Identify WHAT TYPE of entity the question ASKS FOR "
            "(person / institution / place / year / work / etc.). The question "
            "may DESCRIBE a subject of one type but ASK FOR a different type as "
            "the answer. The answer must match what the question ASKS FOR.\n"
            "2. CONSTRAINT CHECK: For each candidate, compare its SATISFIED vs "
            "UNRESOLVED constraints. Pay special attention to:\n"
            "   - Candidates with UNRESOLVED constraints containing negative "
            "signals (e.g., 'does not match', 'not consistent') are WEAKER.\n"
            "   - Candidates with satisfied DISCRIMINATIVE constraints (not just "
            "broad ones like '300+ centuries') are STRONGER.\n"
            "   - Fewer unresolved constraints = more thoroughly verified.\n"
            "3. SELECT the candidate that best matches the answer type AND "
            "satisfies the most DISCRIMINATIVE constraints with the FEWEST "
            "unresolved or negative-signal constraints.\n"
            "4. If NO candidate matches the required answer type, set winner "
            "to null.\n\n"
            "Judge ONLY from the provided evidence (do not use your own memory). "
            "Output JSON with exactly these fields:\n"
            '{"answer_type": "...", "winner": "candidate name or null", '
            '"reason": "...", "constraint_check": "per-candidate summary", '
            '"confidence": "low|medium|high"}'
        )
        try:
            message = chat_completion_with_structuring(
                self.client,
                model_id=self.model_id,
                messages=[
                    {"role": "system", "content": self.CONTRASTIVE_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=self.max_output_tokens,
                structurer_format_hint="Output the result as JSON.",
            )
            content = (getattr(message, "content", None) or "").strip()
            if not content:
                content = (getattr(message, "reasoning_content", None) or "").strip()
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if not match:
                return ContrastiveResult(
                    answer_type="",
                    winner=None,
                    reason=f"Unparseable: {_truncate(content, 120)}",
                )
            payload = json.loads(match.group(0))
            winner = payload.get("winner")
            if isinstance(winner, str):
                winner = winner.strip()
                if winner.lower() in {"null", "none", ""}:
                    winner = None
                else:
                    # Match winner to a known candidate name (case-insensitive).
                    known = {c["name"].lower(): c["name"] for c in clean}
                    winner = known.get(winner.lower(), winner if winner else None)
            else:
                winner = None
            llm_answer_type = _truncate(str(payload.get("answer_type", "")).strip(), 80)
            # Fallback: if LLM returned empty answer_type, use the deterministic
            # hint from the pipeline. This prevents false "no candidate matches"
            # downgrades when the LLM fails to classify the answer type.
            if not llm_answer_type and answer_type_hint:
                llm_answer_type = answer_type_hint
            return ContrastiveResult(
                answer_type=llm_answer_type,
                winner=winner,
                reason=_truncate(str(payload.get("reason", "")), 400),
                constraint_check=_truncate(
                    str(payload.get("constraint_check", "")), 400
                ),
                confidence=str(payload.get("confidence", "low")).strip().lower(),
            )
        except Exception as exc:
            logger.warning(f"[AnswerVerifier] contrastive_verify failed: {exc}")
            return ContrastiveResult(
                answer_type="",
                winner=None,
                reason=f"contrastive_verify exception: {exc}",
            )

    # ------------------------------------------------------------------ helpers

    def _build_claim(
        self,
        question: str,
        answer: str,
        candidate_record: Optional[Dict[str, Any]],
    ) -> str:
        """Build a single declarative claim to be verified."""
        unresolved = self._unresolved_constraints(candidate_record)
        if unresolved:
            return (
                f"The answer to the question is '{answer}'. "
                f"It must satisfy these still-unresolved constraints: "
                + "; ".join(unresolved[:3])
                + "."
            )
        return (
            f"The answer to the question '{_truncate(question, 800)}' is '{answer}'."
        )

    def _build_verification_query(
        self,
        question: str,
        answer: str,
        candidate_record: Optional[Dict[str, Any]],
    ) -> str:
        """Build a search query that, if the answer is correct, should return
        evidence linking the answer to the question's distinctive constraints."""
        unresolved = self._unresolved_constraints(candidate_record)
        parts: List[str] = [f'"{answer}"']
        if unresolved:
            parts.append(_truncate(unresolved[0], 80))
        else:
            # Use the LAST sentence of the question (usually the actual ASK)
            # rather than the first tokens, which may be descriptive preamble.
            sentences = re.split(r'[.?!]+', question)
            last_sentence = sentences[-1].strip() if sentences else question
            if len(last_sentence) < 10:
                last_sentence = sentences[-2].strip() if len(sentences) > 1 else question
            q_tokens = [t for t in re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", last_sentence)
                        if t.lower() not in _QUESTION_STOPWORDS]
            parts.append(" ".join(q_tokens[:5]))
        return " ".join(parts)

    def _unresolved_constraints(self, candidate_record: Optional[Dict[str, Any]]) -> List[str]:
        if not candidate_record:
            return []
        raw = candidate_record.get("unresolved_constraints") or []
        if isinstance(raw, str):
            raw = [raw]
        return [str(c).strip() for c in raw if str(c).strip()][:3]

    def _search_evidence(self, query: str) -> str:
        """Run ONE grounded search and return compact evidence text."""
        if _serper_search is None:
            return ""
        try:
            raw = _serper_search(query)
            return self._compact_search_results(raw)
        except Exception as exc:
            logger.warning(f"[AnswerVerifier] verification search failed: {exc}")
            return ""

    def _compact_search_results(self, raw: str) -> str:
        """Flatten Serper JSON into a compact evidence string."""
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return _truncate(raw, self.max_search_results)
        # search() may return either a single result object or a list of
        # {query, result} entries (multi-query form). Handle both.
        items: List[Dict[str, Any]] = []
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict):
                    sub = entry.get("result") or entry
                    if isinstance(sub, str):
                        try:
                            sub = json.loads(sub)
                        except (ValueError, TypeError):
                            items.append({"snippet": _truncate(sub, 300)})
                            continue
                    if isinstance(sub, dict):
                        items.extend(sub.get("organic") or [])
                    elif isinstance(sub, list):
                        items.extend(sub)
        elif isinstance(data, dict):
            items = data.get("organic") or []
        lines: List[str] = []
        for it in items[:5]:
            if not isinstance(it, dict):
                continue
            title = _truncate(str(it.get("title", "")), 120)
            snippet = _truncate(str(it.get("snippet", "")), 220)
            link = _truncate(str(it.get("link", "")), 120)
            if title or snippet:
                lines.append(f"- {title} | {snippet} | {link}")
        out = "\n".join(lines)
        return _truncate(out, self.max_search_results)

    def _judge(self, claim: str, vquery: str, evidence: str, question: str = "") -> VerificationResult:
        """Ask the LLM to judge the evidence against the claim.

        Type-aware verification (VERIFIER_TYPE_AWARE, default on): the judge is
        instructed to first identify WHAT TYPE of entity the question asks for,
        then verify the answer against that type + constraints. This prevents the
        false-negative where the verifier confuses the question's SUBJECT type
        (e.g. "a person who...") with the expected ANSWER type (e.g. "a school").
        """
        type_aware = _env_flag("VERIFIER_TYPE_AWARE", True)
        type_instruction = ""
        if type_aware and question:
            type_instruction = (
                "\n\nTYPE-AWARE VERIFICATION (critical):\n"
                "1. First, identify WHAT TYPE of entity the question is ASKING FOR as "
                "the answer (e.g. person / school / place / organization / year / "
                "title / work / etc.). This is the ANSWER type.\n"
                "2. The question may DESCRIBE a subject of a different type (e.g. "
                "'a person who graduated from...') — that subject type is NOT the "
                "answer type. The answer must match what the question ASKS FOR, not "
                "what it DESCRIBES.\n"
                "3. To REFUTE, the evidence must show the proposed answer is NOT of "
                "the correct answer type, OR does not satisfy the question's "
                "constraints. If the answer IS of the correct type but you cannot "
                "confirm the constraints from the evidence, output inconclusive.\n"
                "4. NEVER refute merely because the answer is a different type from "
                "the question's described subject."
            )
        prompt = (
            f"Original question:\n{_truncate(question, 1200)}\n\n"
            f"Claim to verify:\n{claim}\n\n"
            f"Verification query used:\n{vquery}\n\n"
            f"Evidence retrieved from the web:\n{evidence}\n\n"
            "Judge ONLY from the evidence above (do not use your own memory). "
            "Output JSON with exactly these fields:\n"
            '{"verdict": "verified | refuted | inconclusive", "reason": "...", "confidence": "low|medium|high"}'
            f"{type_instruction}"
        )
        try:
            message = chat_completion_with_structuring(
                self.client,
                model_id=self.model_id,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=self.max_output_tokens,
                structurer_format_hint="Output the result as JSON.",
            )
            content = (getattr(message, "content", None) or "").strip()
            if not content:
                reasoning = (getattr(message, "reasoning_content", None) or "").strip()
                content = reasoning
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if not match:
                return VerificationResult(
                    verdict=INCONCLUSIVE,
                    reason=f"Verifier LLM output unparseable: {_truncate(content, 120)}",
                    evidence_snippet=_truncate(evidence, 200),
                )
            payload = json.loads(match.group(0))
            verdict = str(payload.get("verdict", "")).strip().lower()
            if verdict not in {VERIFIED, REFUTED, INCONCLUSIVE}:
                verdict = INCONCLUSIVE
            return VerificationResult(
                verdict=verdict,
                reason=_truncate(str(payload.get("reason", "")), 400),
                evidence_snippet=_truncate(evidence, 200),
                confidence=str(payload.get("confidence", "low")).strip().lower(),
            )
        except Exception as exc:
            logger.warning(f"[AnswerVerifier] judge LLM call failed: {exc}")
            return VerificationResult(
                verdict=INCONCLUSIVE,
                reason=f"Verifier LLM call failed: {exc}",
                evidence_snippet=_truncate(evidence, 200),
            )


_QUESTION_STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "which", "who",
    "what", "when", "where", "whose", "whom", "was", "were", "has", "had",
    "have", "been", "also", "into", "their", "his", "her", "its", "such",
    "any", "all", "some", "most", "than", "then", "but", "not", "are",
    "did", "does", "done", "one", "two", "three", "first", "last", "same",
    "during", "while", "after", "before", "between", "among", "about",
}
