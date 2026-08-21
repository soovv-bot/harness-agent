"""Verification helpers (cross-checking, gating, early-stop logic).

Pure functions extracted from ``SearchHarnessPipelineV4`` (RD §5.2 step4b).
Each takes the pipeline as its first parameter; the class rebinds the private
methods to these helpers so existing behaviour and private API names are
preserved.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger

from llm.compat import chat_completion_with_structuring
from tools.search_tools import authoritative_domains_in, high_weight_sources_in  # type: ignore

if TYPE_CHECKING:
    from pipeline.orchestrator import SearchHarnessPipelineV4

def consume_stage_answer(
    pipeline: "SearchHarnessPipelineV4",
    iterations: int) -> Optional[Dict[str, Any]]:
    if not pipeline._stage_answer:
        return None
    answer = pipeline._stage_answer
    pipeline._stage_answer = None
    _r = pipeline._finish_with_answer(answer, iterations=iterations)
    return _r  # may be None if contrastive retry triggered


def pipeline_status_for_answer(
    pipeline: "SearchHarnessPipelineV4",
    answer: str) -> str:
    text = (answer or "").strip()
    if not text:
        return "unfinished"
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        answer_text = str(payload.get("answer", "")).strip()
        answer_status = str(payload.get("status", "")).strip().lower()
        if answer_status == "infra_error":
            return "infra_error"
        if answer_status and answer_status != "solved":
            return "unfinished"
        text = answer_text or text
    if text.strip().lower() in {"unknown", "unk", "n/a", "none", "null"}:
        return "unfinished"
    return "finished"


def verify_planner_answer(
    pipeline: "SearchHarnessPipelineV4",
    answer: str, *, iterations_remaining: int = 0, iteration: int = 0) -> Optional[str]:
    """Full-path pipeline-verification for planner-committed answers.

    Two-stage verification (mirrors SearchFinalizer._maybe_verify):
    1. Contrastive verification: if multiple candidates exist, compare them
       to select the one matching the question's required answer type + all
       constraints. Fixes question-misreading (answering wrong dimension)
       and candidate bias (wrong strong candidate). If no candidate matches
       the required type, downgrade to Unknown.
    2. Grounded single-candidate verification (Plan A): verify the chosen
       answer against fresh web evidence. Refuted -> Unknown.

    The planner can short-circuit with a direct ``<answer>`` via
    ``_finish_with_answer``, bypassing ``SearchFinalizer``. To give
    verification coverage over *every* committed answer — matching the
outer-verification-loop design of AREX-style agents — we run both checks here
too. Failure-safe: any error keeps the original answer.
    """
    verifier = getattr(pipeline.finalizer, "verifier", None)
    if verifier is None:
        return answer
    a = (answer or "").strip()
    if not a or a.lower() in {"unknown", "none", "null"}:
        return answer

    question = getattr(pipeline, "_question", "")
    compact_state = pipeline.state_store.export_compact_state()

    # --- Stage 1: contrastive verification ---
    try:
        candidates = pipeline.finalizer._collect_candidates_for_contrast(compact_state, a)
        if len(candidates) >= 2:
            type_hint = pipeline._infer_question_answer_type(question)
            cr = verifier.contrastive_verify(
                question, candidates, answer_type_hint=type_hint
            )
            if cr.winner is None:
                # Contrastive verify rejected all candidates. Do NOT
                # trigger a pool rebuild — the rebuild is destructive: it
                # clears the candidate pool (including the correct
                # candidate the planner chose) and the finalizer then
                # salvages a wrong candidate from stale message context
                # (pos2 regression: planner chose correct "Marguerite
                # Smith", contrastive_verify rejected both candidates,
                # rebuild cleared the pool, finalizer salvaged wrong
                # "Alma Lutz"). Instead keep the planner's answer and fall
                # through to Stage 2 grounded verification, which will
                # downgrade to Unknown only if fresh web evidence
                # refutes the answer. The planner already chose based on
                # all gathered evidence; a noisy contrastive verdict
                # should not override it.
                logger.info(
                    f"[Pipeline] contrastive_verify rejected all candidates "
                    f"(answer_type={cr.answer_type!r}); keeping original "
                    f"planner answer {a!r} (not triggering rebuild — Stage 2 "
                    f"grounded verification will still refute if wrong)"
                )
                # Fall through to Stage 2 grounded verification
            if cr.winner is not None and cr.winner.strip().lower() != a.lower():
                logger.info(
                    f"[Pipeline] contrastive_verify replaced answer: "
                    f"{a!r} -> {cr.winner!r} (answer_type={cr.answer_type})"
                )
                a = cr.winner
                answer = cr.winner
    except Exception as exc:
        logger.warning(f"[Pipeline] contrastive_verify failed (kept original): {exc}")

    # --- Stage 2: grounded single-candidate verification (Plan A) ---
    try:
        candidate_record = pipeline.finalizer._pick_candidate_record(compact_state, a)
        vr = verifier.verify(question, a, candidate_record)
        if vr.is_refuted:
            logger.info(
                f"[Pipeline] planner answer REFUTED by grounded verification: "
                f"{a!r} -> Unknown | reason={vr.reason[:120]}"
            )
            # Mark the matching candidate record as eliminated so the
            # fallback salvage can't reselect it (pos6 v13 root cause:
            # refuted "Kazuo Ishiguro" was salvaged from the pool because
            # its record status was never updated).
            pipeline._mark_candidate_eliminated(a, vr.reason)
            return "Unknown"
        logger.info(
            f"[Pipeline] planner answer verification: {a!r} -> {vr.verdict}"
        )
    except Exception as exc:
        logger.warning(f"[Pipeline] planner-answer verification failed (kept original): {exc}")
    return answer


def gate_verification_short_circuit(
    pipeline: "SearchHarnessPipelineV4",
    answer: str, iteration: int
    ) -> Optional[str]:
    """pos6 fix: gate the planner's direct <answer> short-circuit while
    still in candidate_verification.

    Returns None if the answer is allowed to commit (the candidate is
    already verified, or no further verification is possible). Returns a
    non-None sentinel (the blocked answer) if the short-circuit must be
    deferred so the pipeline can verify the answer candidate or one of its
    unverified viable siblings first.

    Conditions that block the short-circuit:
    1. The answer candidate exists in the pool but is not yet
       verification_status=verified (only partial/unverified).
    2. There are other viable candidates that have never been verified at
       all (verification_status=unverified) — they deserve a verification
       turn before the planner commits.
    A safety cap (active_candidate_rounds >= 3 or iteration >= 8) prevents
    indefinite blocking near the iteration budget.
    """
    if not answer or str(answer).strip().lower() in {"unknown", "none", "null"}:
        return None
    viable_records = pipeline._viable_candidate_records()
    if not viable_records:
        return None
    answer_low = str(answer).strip().lower()
    # Locate the candidate record matching the answer (substring match,
    # since the answer may be a book title while the candidate name may
    # carry extra context).
    answer_record = None
    for rec in viable_records:
        rname = str(rec.get("name", "")).strip()
        if not rname:
            continue
        if rname.lower() in answer_low or answer_low in rname.lower():
            answer_record = rec
            break
    # Safety: near the iteration budget, let the planner commit.
    if iteration >= 8 or pipeline.active_candidate_rounds >= 3:
        return None
    # Condition 1: answer candidate not yet verified.
    if answer_record is not None:
        vs = str(answer_record.get("verification_status", "")).lower()
        if vs not in {"verified", "contradicted"}:
            logger.info(
                f"[Pipeline] top-2 gate (short-circuit): answer candidate "
                f"{answer_record.get('name', '')!r} is verification_status="
                f"{vs!r} — deferring planner answer for one more verification pass"
            )
            # Re-queue this candidate for verification.
            pipeline.active_candidate = str(answer_record.get("name", "")).strip()
            pipeline.active_candidate_rounds = 0
            if pipeline.active_candidate in pipeline.completed_verification_candidates:
                pipeline.completed_verification_candidates.remove(pipeline.active_candidate)
            return answer
    # Condition 2: other viable candidates never verified at all.
    unverified_siblings = [
        rec for rec in viable_records
        if rec is not answer_record
        and str(rec.get("verification_status", "")).lower() == "unverified"
    ]
    if unverified_siblings:
        # Pick the first unverified sibling and re-queue it.
        sibling = unverified_siblings[0]
        sname = str(sibling.get("name", "")).strip()
        logger.info(
            f"[Pipeline] top-2 gate (short-circuit): "
            f"{len(unverified_siblings)} viable candidate(s) never verified "
            f"(e.g. {sname!r}) — deferring planner answer so they get a "
            f"verification turn"
        )
        pipeline.active_candidate = sname
        pipeline.active_candidate_rounds = 0
        if sname in pipeline.completed_verification_candidates:
            pipeline.completed_verification_candidates.remove(sname)
        return answer
    return None


def initialize_verification_queue(pipeline: "SearchHarnessPipelineV4") -> None:
    candidate_records = pipeline._all_candidate_records()
    ordered: List[str] = []
    for record in candidate_records:
        if not isinstance(record, dict):
            continue
        name = str(record.get("name", "")).strip()
        if not name or record.get("status") == "eliminated":
            continue
        if name not in ordered:
            ordered.append(name)
    for name in pipeline.state_store.current_candidates:
        if name and name not in ordered:
            ordered.append(name)
    # Rank candidates by question-constraint relevance so the most
    # discriminating constraints are checked first. Falls back to
    # insertion order on any error (no regression).
    ranked = rank_verification_queue_by_question(pipeline, ordered)
    pipeline.verification_queue = ranked
    pipeline.completed_verification_candidates = []
    pipeline.active_candidate = pipeline.verification_queue.pop(0) if pipeline.verification_queue else None
    pipeline.active_candidate_rounds = 0


def rank_verification_queue_by_question(
    pipeline: "SearchHarnessPipelineV4",
    candidates: List[str]) -> List[str]:
    """Reorder verification candidates by question-constraint relevance.

    Makes ONE lightweight LLM call asking the model to rank candidates by
    how well each satisfies the question's MOST DISCRIMINATING constraints
    (not just the broad criteria that generated the list). This ensures
    that the correct answer — which may not be the highest-scoring on the
    broad metric — is verified early enough within the iteration budget.

    Falls back to insertion order on any error, so existing behaviour is
    preserved when the ranking call is unavailable or disabled.
    """
    if not pipeline._rank_enabled or len(candidates) <= 2:
        return candidates
    question = getattr(pipeline, "_question", "") or ""
    if not question:
        return candidates
    try:
        candidates_text = "\n".join(
            f"{i}. {name}" for i, name in enumerate(candidates)
        )
        prompt = pipeline.VERIFICATION_RANKING_PROMPT.format(
            question=question[:1500],
            candidates=candidates_text,
            n_minus_one=len(candidates) - 1,
        )
        _t_rank = time.time()
        message = chat_completion_with_structuring(
            pipeline._rank_client,
            model_id=pipeline._model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=1024,
            structurer_format_hint="Output the result as JSON.",
        )
        content = (getattr(message, "content", None) or "").strip()
        if not content:
            content = (getattr(message, "reasoning_content", None) or "").strip()
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if not match:
            logger.debug("[Pipeline] verify-ranking: no JSON in response, using insertion order")
            return candidates
        result = json.loads(match.group())
        ranked_indices = result.get("ranked_indices", [])
        if not isinstance(ranked_indices, list):
            return candidates
        # Build ranked list, validating indices
        ranked: List[str] = []
        seen = set()
        for idx in ranked_indices:
            if isinstance(idx, int) and 0 <= idx < len(candidates):
                name = candidates[idx]
                if name not in seen:
                    ranked.append(name)
                    seen.add(name)
        # Append any candidates not covered by the ranking
        for name in candidates:
            if name not in seen:
                ranked.append(name)
        if len(ranked) != len(candidates):
            return candidates
        logger.info(
            f"[Pipeline] verify-ranking done in {time.time()-_t_rank:.1f}s "
            f"| top3={ranked[:3]}"
        )
        pipeline._record_event_for_trajectory("verify_queue_ranked", 0, {
            "original_order": candidates[:5],
            "ranked_order": ranked[:5],
            "reasoning": str(result.get("reasoning", ""))[:300],
        })
        return ranked
    except Exception as e:
        logger.warning(f"[Pipeline] verify-ranking failed ({e}), using insertion order")
        return candidates


def verified_candidate_early_stop(
    pipeline: "SearchHarnessPipelineV4",
    iteration: int) -> Optional[Dict[str, Any]]:
    """Return an early-stop dict when a candidate is verified & conflict-free."""
    # pos6 fix: only allow verified-candidate early stop during the
    # candidate_verification stage. During candidate_generation the
    # executor may pipeline-report verification_status=verified, but that
    # should NOT trigger an early stop — the candidate must go through
    # the formal verification queue first, and other viable candidates
    # deserve a verification turn (top-2 principle).
    if pipeline.workflow_stage != pipeline.CANDIDATE_VERIFICATION:
        return None
    records = (pipeline.state_store.export_compact_state().get("candidate_records") or [])
    viable_records = pipeline._viable_candidate_records()
    # top-2 gate: do not early-stop if there are other viable candidates
    # that have not yet been verified or contradicted. They must get a
    # verification turn before we commit.
    unverified_siblings = [
        rec for rec in viable_records
        if str(rec.get("verification_status", "")).lower() not in {"verified", "contradicted"}
    ]
    for record in records:
        if not isinstance(record, dict):
            continue
        name = str(record.get("candidate") or record.get("name") or "").strip()
        if not name or name.lower() in {"unknown", "none", "null"}:
            continue
        vs = str(record.get("verification_status") or "").strip().lower()
        hard_conflicts = record.get("hard_conflicts") or []
        unresolved = record.get("unresolved_constraints") or []
        if vs == "verified" and not hard_conflicts and not unresolved:
            if unverified_siblings:
                logger.info(
                    f"[Pipeline] top-2 gate (early-stop): candidate {name!r} "
                    f"is verified, but {len(unverified_siblings)} viable "
                    f"sibling(s) remain unverified — deferring early stop"
                )
                return None
            return {
                "trigger": "verified_candidate_early_stop",
                "details": {
                    "iteration": iteration,
                    "candidate": name,
                    "verification_status": vs,
                },
            }
    return None


def tied_candidate_blocks_early_stop(
    pipeline: "SearchHarnessPipelineV4",
    record: Dict[str, Any],
        viable_records: List[Dict[str, Any]],
        iteration: int,
        max_iterations: int,
    ) -> bool:
    """P1-B: Block early-stop when viable candidates are tied and a
    distinguishing constraint remains unresolved.

    Prevents premature convergence when the trigger candidate hits an
    authority/verified early-stop condition but other viable candidates
    have comparable support with unresolved constraints — the
    differentiating constraint has not been verified for any of them,
    so committing now risks picking the wrong tied candidate.

    Budget-aware: when iteration is within the last 25% of the budget,
    the gate releases (returns False) so the pipeline can commit the
    best-supported candidate instead of exhausting the budget and
    falling through to a blind best-effort finish. This preserves the
    early-iteration anti-convergence benefit without the 3x latency
    regression seen when constraints can never be resolved (e.g. when
    the executor never crawls).

    Returns True to defer the early-stop (the caller should ``continue``
    to the next candidate or fall through to the normal iteration loop).
    """
    if len(viable_records) <= 1:
        return False
    # Budget-aware release: near the iteration cap, let the pipeline
    # commit rather than burning the remaining budget on verification
    # that the executor has already shown it cannot complete.
    # pos6 fix: even near budget cap, do NOT release if there is a
    # viable sibling that has NEVER been verified or contradicted. The
    # top-2 principle still applies — committing a verified-but-wrong
    # candidate over an unverified-but-correct sibling is the exact
    # failure mode pos6 exposed (planner picked "Opium" because the
    # executor never verified "In the Arms of Morpheus"). Force at
    # least one verification turn on the top unverified sibling before
    # allowing the release.
    near_cap = max_iterations > 0 and iteration >= max_iterations - max(2, max_iterations // 4)
    trigger_name = str(record.get("candidate") or record.get("name") or "").strip()
    if near_cap:
        unverified_siblings = [
            sib for sib in viable_records
            if str(sib.get("candidate") or sib.get("name") or "").strip() != trigger_name
            and str(sib.get("verification_status") or "").strip().lower() not in {"verified", "contradicted"}
        ]
        if unverified_siblings:
            logger.info(
                f"[Pipeline] tied gate: near budget cap at iteration="
                f"{iteration}/{max_iterations}, but {len(unverified_siblings)} "
                f"viable sibling(s) remain unverified (e.g. "
                f"{str(unverified_siblings[0].get('candidate') or unverified_siblings[0].get('name',''))!r}) "
                f"— top-2 gate holds; deferring release for a verification pass"
            )
            return True
        logger.info(
            f"[Pipeline] tied gate: releasing at iteration={iteration}/"
            f"{max_iterations} (near budget cap, all siblings verified/contradicted) — allowing early-stop "
            f"for candidate "
            f"{str(record.get('candidate') or record.get('name',''))!r}"
        )
        return False
    trigger_vs = str(record.get("verification_status") or "").strip().lower()
    trigger_support = len(record.get("supporting_constraints") or [])
    trigger_unresolved = record.get("unresolved_constraints") or []
    for sib in viable_records:
        sib_name = str(sib.get("candidate") or sib.get("name") or "").strip()
        if not sib_name or sib_name == trigger_name:
            continue
        sib_vs = str(sib.get("verification_status") or "").strip().lower()
        # Top-2 gate: an unverified viable sibling deserves a
        # verification turn before we commit (mirrors the gate in
        # _verified_candidate_early_stop).
        if sib_vs not in {"verified", "contradicted"}:
            logger.info(
                f"[Pipeline] tied gate: candidate {trigger_name!r} hit "
                f"early-stop, but viable sibling {sib_name!r} is still "
                f"verification_status={sib_vs!r} — deferring for a "
                f"verification pass"
            )
            return True
        # Tied-support gate: if the trigger is only partial (not fully
        # verified) and a sibling has comparable support AND carries
        # unresolved constraints, a distinguishing constraint likely
        # remains unverified for both → defer.
        if trigger_vs not in {"verified", "contradicted"} and trigger_unresolved:
            sib_support = len(sib.get("supporting_constraints") or [])
            sib_unresolved = sib.get("unresolved_constraints") or []
            if sib_support >= trigger_support - 1 and sib_unresolved:
                logger.info(
                    f"[Pipeline] tied gate: candidate {trigger_name!r} "
                    f"(support={trigger_support}, vs={trigger_vs!r}) hit "
                    f"early-stop, but tied sibling {sib_name!r} "
                    f"(support={sib_support}) also has unresolved "
                    f"distinguishing constraints — deferring early stop"
                )
                return True
    return False


def authoritative_consensus_early_stop(
    pipeline: "SearchHarnessPipelineV4",
    iteration: int, max_iterations: int = 10) -> Optional[Dict[str, Any]]:
    """Early-stop when a candidate is backed by enough source weight.

    Two-tier decision (matches the "2 high-weight sources → fact confirmed"
    rule; weight=10 = official docs / academic / official financial reports,
    weight=2 = UGC / pipeline-media):
      1. FACT-CONFIRMED: >=N independent weight-10 sources (default 2) agree
         on one candidate → fact established, stop the pipeline immediately.
         Trigger: ``fact_confirmed_early_stop``.
      2. AUTHORITATIVE CONSENSUS: >=N independent weight>=8 sources (tier>=4;
         default 2) agree → early-stop. Trigger:
         ``authoritative_consensus_early_stop``.

    Both complement ``_verified_candidate_early_stop`` (which waits for the
    executor to pipeline-report verification_status=verified). FACT-CONFIRMED
    fires on objective source-weight counting — no need for the executor to
    pipeline-report, saving iterations on well-corroborated answers. Disabled
    on contradicted/eliminated candidates. Gated by
    ``PIPELINE_AUTHORITY_EARLY_STOP`` (default on); thresholds via
    ``PIPELINE_FACT_CONFIRM_MIN_SOURCES`` (default 2) and
    ``PIPELINE_AUTHORITY_MIN_SOURCES`` (default 2).
    """
    if os.getenv("PIPELINE_AUTHORITY_EARLY_STOP", "1").strip().lower() not in {"1", "true", "yes"}:
        return None
    # pos6 fix: only allow authority-consensus early stop during the
    # candidate_verification stage. The same top-2 principle applies —
    # during candidate_generation a candidate may collect authoritative
    # sources, but other viable candidates must get a verification turn
    # before we commit to a single answer.
    if pipeline.workflow_stage != pipeline.CANDIDATE_VERIFICATION:
        return None
    fact_min = int(os.getenv("PIPELINE_FACT_CONFIRM_MIN_SOURCES", "2") or "2")
    auth_min = int(os.getenv("PIPELINE_AUTHORITY_MIN_SOURCES", "2") or "2")
    records = (pipeline.state_store.export_compact_state().get("candidate_records") or [])
    viable_records = pipeline._viable_candidate_records()
    for record in records:
        if not isinstance(record, dict):
            continue
        name = str(record.get("candidate") or record.get("name") or "").strip()
        if not name or name.lower() in {"unknown", "none", "null"}:
            continue
        status = str(record.get("status") or "").strip().lower()
        vs = str(record.get("verification_status") or "").strip().lower()
        if status == "eliminated" or vs == "contradicted":
            continue
        evidence = record.get("evidence") or []
        urls = []
        for ev in evidence:
            if not isinstance(ev, dict):
                continue
            url_val = ev.get("source_url") or ev.get("source") or ""
            if isinstance(url_val, str) and url_val.strip().startswith("http"):
                urls.append(url_val.strip())
        # P1-B: tied-candidate gate — if other viable candidates have
        # comparable support with unresolved distinguishing constraints,
        # defer the early-stop so the differentiating constraint gets
        # verified instead of committing to a tied candidate.
        if pipeline._tied_candidate_blocks_early_stop(record, viable_records, iteration, max_iterations):
            continue
        # Tier 1: weight-10 sources (fact confirmed).
        high = high_weight_sources_in(urls, min_weight=10)
        if len(high) >= fact_min:
            return {
                "trigger": "fact_confirmed_early_stop",
                "details": {
                    "iteration": iteration,
                    "candidate": name,
                    "high_weight_domains": high,
                    "min_sources": fact_min,
                },
            }
        # Tier 2: weight>=8 authoritative consensus.
        auth = authoritative_domains_in(urls)
        if len(auth) >= auth_min:
            return {
                "trigger": "authoritative_consensus_early_stop",
                "details": {
                    "iteration": iteration,
                    "candidate": name,
                    "authoritative_domains": auth,
                    "min_sources": auth_min,
                },
            }
    return None
