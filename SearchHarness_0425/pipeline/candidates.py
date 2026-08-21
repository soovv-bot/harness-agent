"""Candidate-pool lifecycle helpers.

Pure functions extracted from ``SearchHarnessPipelineV4`` (RD §5.2 step4b).
Each takes the pipeline as its first parameter; the class rebinds the private
methods to these helpers so existing behaviour and private API names are
preserved.
"""

from __future__ import annotations

import json
import re
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger

if TYPE_CHECKING:
    from pipeline.orchestrator import SearchHarnessPipelineV4

def force_pool_rebuild(
    pipeline: "SearchHarnessPipelineV4", iteration: int, answer_type: str) -> None:
    """Force the pipeline back to candidate_generation after a contrastive
    rejection, so the planner searches for entities of the correct type.
    Also allocates extra search budget so the rebuild can actually search
    and clears old wrong-type candidates so the fallback can't reselect them."""
    pipeline.workflow_stage = pipeline.CANDIDATE_GENERATION
    pipeline.stage_round_counts[pipeline.CANDIDATE_GENERATION] = 0
    pipeline.verification_queue = []
    pipeline.active_candidate = None
    pipeline.active_candidate_rounds = 0
    pipeline._stage_answer = None
    # Clear old candidate records so the fallback_answer_from_pool can't
    # reselect wrong-type candidates (e.g. institutions when a person is
    # required). The rebuild's whole point is a fresh candidate search.
    old_count = len(pipeline.state_store.candidate_records)
    pipeline.state_store.candidate_records.clear()
    # Allocate extra search budget for the rebuild round. The pipeline may
    # have already used far more searches than the original limit (the stop
    # check only fires at iteration boundaries, not mid-subtask), so we
    # set the new ceiling relative to the current usage, not the old max.
    current_search_calls = len(pipeline.query_memory.records)
    extra = 15
    pipeline.max_total_searches = current_search_calls + extra
    pipeline.planner.search_budget += 5
    pipeline.executor.search_budget += 10
    logger.info(
        f"[Pipeline] Forced pool rebuild: CANDIDATE_GENERATION "
        f"(contrastive reject, answer_type={answer_type}, iter={iteration}, "
        f"cleared {old_count} old candidates, "
        f"+{extra} search budget -> total={pipeline.max_total_searches} "
        f"(used={current_search_calls})"
    )
    pipeline._record_event_for_trajectory("contrastive_reject_rebuild", iteration, {
        "answer_type": answer_type,
        "forced_stage": pipeline.CANDIDATE_GENERATION,
        "extra_budget": extra,
        "cleared_candidates": old_count,
        "current_search_calls": current_search_calls,
    })


def mark_candidate_eliminated(
    pipeline: "SearchHarnessPipelineV4", answer: str, reason: str) -> None:
    """Mark a candidate record as eliminated when it is refuted by
    grounded verification. This prevents the fallback salvage from
    reselecting a refuted answer (pos6 v13 root cause)."""
    a_norm = (answer or "").strip().lower()
    if not a_norm:
        return
    for record in pipeline.state_store.candidate_records:
        if not isinstance(record, dict):
            continue
        name = str(record.get("candidate") or record.get("name") or "").strip().lower()
        if name == a_norm:
            record["status"] = "eliminated"
            record["elimination_reason"] = f"refuted by grounded verification: {reason[:200]}"
            logger.info(
                f"[Pipeline] Marked candidate {name!r} as eliminated "
                f"(refuted by grounded verification)"
            )
            return


def fallback_answer_from_pool(
    pipeline: "SearchHarnessPipelineV4") -> Optional[str]:
    """Pick the strongest viable candidate as a fallback answer when the
    planner/finalizer emits Unknown. Ranks by verification_status and
    supporting-constraint count, so a verified/partial candidate beats a
    bare unverified one. Returns None when no viable candidate exists.

    This fixes pos10-style failures where the planner wraps up with
    ``<answer>Unknown</answer>`` even though the candidate pool still holds
    an active, unevaluated candidate. The salvaged answer still flows
    through ``_verify_planner_answer`` afterwards, so a fallback that is
    refuted by fresh web evidence is correctly downgraded back to Unknown.

    pos6 p1h2 fix: when the question's answer type is known (e.g.
    'book_title'), STRONGLY prefer candidates whose inferred type matches.
    Without this, the fallback picks the most-verified candidate of ANY
    type — e.g. an author ('Barbara Hodgson') when the question asks for a
    book title — and returns the wrong entity type as the answer. A
    type-matching candidate always beats a non-matching one regardless of
    verification score; only when no type-matching candidate exists do we
    fall back to the original verification-score ranking.
    """
    viable = viable_candidate_records(pipeline)
    if not viable:
        return None
    vorder = {"verified": 0, "partial": 1, "unverified": 2, "contradicted": 3}

    qtype = (infer_question_answer_type(pipeline, getattr(pipeline, "_question", "") or "") or "").strip().lower()
    type_hints = infer_candidate_type_hints(pipeline, viable) if qtype and qtype != "unknown" else []
    indexed_viable = list(enumerate(viable))

    def _score(rec: Dict[str, Any], idx: int) -> tuple:
        vs = str(rec.get("verification_status") or "unverified").lower()
        support_n = len(rec.get("supporting_constraints") or [])
        has_evidence = 1 if rec.get("evidence") else 0
        # Type-match preference: a candidate whose inferred type matches the
        # question's answer type ranks ahead of any non-matching candidate.
        type_match = 0
        if qtype and qtype != "unknown" and type_hints:
            ct = type_hints[idx] if idx < len(type_hints) else "unknown"
            type_match = 0 if ct == qtype else 1
        return (type_match, vorder.get(vs, 2), -support_n, -has_evidence)

    indexed_viable.sort(key=lambda pair: _score(pair[1], pair[0]))
    best = indexed_viable[0][1] if indexed_viable else None
    if best is None:
        return None
    name = str(best.get("candidate") or best.get("name") or "").strip()
    return name or None


def all_candidate_records(
    pipeline: "SearchHarnessPipelineV4") -> List[Dict[str, Any]]:
    return [
        record for record in pipeline.state_store.candidate_records.values()
        if isinstance(record, dict)
    ]


def viable_candidate_records(
    pipeline: "SearchHarnessPipelineV4", compact_state: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    records = all_candidate_records(pipeline)
    return [
        record for record in records
        if isinstance(record, dict) and record.get("status") != "eliminated" and not record.get("hard_conflicts")
    ]


def current_candidate_record(
    pipeline: "SearchHarnessPipelineV4", compact_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not pipeline.active_candidate:
        return None
    for record in all_candidate_records(pipeline):
        if isinstance(record, dict) and str(record.get("name", "")).strip() == pipeline.active_candidate:
            return record
    return None


def should_rotate_active_candidate(
    pipeline: "SearchHarnessPipelineV4", plan: Dict[str, Any], compact_state: Dict[str, Any]) -> bool:
    if pipeline.workflow_stage != pipeline.CANDIDATE_VERIFICATION or not pipeline.active_candidate:
        return False
    stage_status = (plan.get("stage_status") or "continue").strip().lower()
    if stage_status == "ready_to_advance":
        return True
    record = current_candidate_record(pipeline, compact_state)
    if record and record.get("hard_conflicts"):
        return True
    return pipeline.active_candidate_rounds >= 2


def rotate_active_candidate(
    pipeline: "SearchHarnessPipelineV4", compact_state: Dict[str, Any]) -> bool:
    if not pipeline.active_candidate:
        return False
    if pipeline.active_candidate not in pipeline.completed_verification_candidates:
        pipeline.completed_verification_candidates.append(pipeline.active_candidate)
    remaining = []
    for name in pipeline.verification_queue:
        if name and name not in pipeline.completed_verification_candidates:
            remaining.append(name)
    pipeline.verification_queue = remaining
    viable_names = {
        str(record.get("name", "")).strip()
        for record in viable_candidate_records(pipeline)
        if isinstance(record, dict)
    }
    next_candidate = None
    while pipeline.verification_queue:
        candidate = pipeline.verification_queue.pop(0)
        if candidate in viable_names:
            next_candidate = candidate
            break
    pipeline.active_candidate = next_candidate
    pipeline.active_candidate_rounds = 0
    return next_candidate is not None


def should_rebuild_candidate_pool(
    pipeline: "SearchHarnessPipelineV4", compact_state: Dict[str, Any]) -> bool:
    if pipeline.workflow_stage != pipeline.CANDIDATE_VERIFICATION:
        return False
    if pipeline.active_candidate or pipeline.verification_queue:
        return False
    viable_records = viable_candidate_records(pipeline)
    if viable_records:
        return False
    candidate_records = all_candidate_records(pipeline)
    damaged_records = [
        record for record in candidate_records
        if isinstance(record, dict) and record.get("hard_conflicts")
    ]
    return bool(damaged_records)


def infer_candidate_type_hints(
    pipeline: "SearchHarnessPipelineV4", records: List[Dict[str, Any]]) -> List[str]:
    """Infer the entity type of each candidate from its name/record.

    Returns a list of type labels (e.g., 'person', 'university',
    'organization', 'place', 'year', 'book_title') to help the direction
    critic detect type mismatches between the question's expected answer
    type and the candidate pool.
    """
    type_hints: List[str] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        name = str(record.get("name", "")).strip()
        # Strip parenthetical annotations like "(1330 centuries, CueTracker)"
        clean_name = re.sub(r'\s*\([^)]*\)\s*', '', name).strip()
        institutional_keywords = [
            "university", "institute", "college", "school", "academy",
            "hospital", "centre", "center", "foundation", "society",
            "association", "corporation", "company", "press", "library",
        ]
        name_lower = clean_name.lower()
        # pos6 v17 fix: detect book_title candidates. Book titles typically
        # contain " by <author>" or are long multi-word phrases that don't
        # match the 2-word person pattern, or contain lowercase articles
        # (the/a/an) + multiple words.
        if any(kw in name_lower for kw in [
            " by ", ": ", " a history of", " the tragic", " the story of",
        ]):
            type_hints.append("book_title")
            continue
        if any(kw in name_lower for kw in institutional_keywords):
            type_hints.append("institution")
        elif re.match(r'^\d{3,4}$', clean_name):
            type_hints.append("year")
        elif re.match(r'^[A-Z][a-zA-Z\'\.-]+\s+[A-Z]', clean_name):
            type_hints.append("person")
        else:
            type_hints.append("unknown")
    return type_hints


def infer_question_answer_type(
    pipeline: "SearchHarnessPipelineV4", question: str) -> str:
    """Infer what TYPE of entity the question asks for as the answer.

    BrowseComp questions often DESCRIBE a subject of one type in the body
    but ASK FOR a different type at the end. We check the last sentence
    (the actual question) first, then fall back to the full question.

    Common patterns: 'the name of the player' → person,
    'which university' → institution, 'what year' → year, etc.
    """
    q = (question or "").lower()
    # Split into sentences; the last clause is the actual question.
    # Common separators: '. ', '? '
    clauses = [c.strip() for c in re.split(r'[.?!]\s+', q) if c.strip()]
    ask_clause = clauses[-1] if clauses else q

    # Check the ASK clause (the actual question) first.
    # pos6 v16 fix: check book_title BEFORE person, because "name of the
    # book" and "full title of the book" contain "name of the" which would
    # otherwise match the person pattern and mis-classify as "person".
    if any(kw in ask_clause for kw in ["title of the book", "full title of the book", "title of", "name of the book", "what book", "which book"]):
        return "book_title"
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

    # Fallback: scan the full question (description may contain the answer type).
    # But person keywords take priority over institution keywords, since
    # questions often describe institutions but ask for people.
    if any(kw in q for kw in ["title of the book", "full title of the book", "title of", "name of the book", "what book", "which book"]):
        return "book_title"
    if any(kw in q for kw in ["husband", "wife", "spouse", "full name of"]):
        return "person"
    if any(kw in q for kw in ["university", "college", "institute", "school", "academy"]):
        return "institution"
    if any(kw in q for kw in ["what year", "which year", "in what year", "what date"]):
        return "year"
    if any(kw in q for kw in ["which country", "what city", "what place", "which place", "where"]):
        return "place"
    return "unknown"


def check_pool_health(
    pipeline: "SearchHarnessPipelineV4", question: str, iteration: int) -> Optional[Dict[str, str]]:
    """Detect candidate-pool health issues the direction critic may miss.

    Two lightweight heuristic checks (no LLM call):

    1. **Type mismatch**: the question asks for entity type X (e.g.,
       "university") but all candidates are a different type (e.g.,
       "person"). This was the pos7 failure mode: the pool was all Spanish
       studies scholars but the answer was a university.

    2. **Domain monoculture + high elimination**: >60% of candidates
       eliminated and the remaining viable candidates are homogeneous
       (all same type/domain). Suggests the pool was built from a single
       source and needs to be rebuilt from a different angle.

    Returns a feedback message dict when an issue is detected, or None.
    Each issue type fires at most once per run to avoid nagging.
    """
    # Type mismatch check runs in BOTH candidate_generation and
    # candidate_verification: a pool built from wrong-type candidates
    # should be caught as early as possible, before the pipeline wastes
    # verification budget on candidates that can never be the answer.
    if pipeline.workflow_stage not in (pipeline.CANDIDATE_GENERATION, pipeline.CANDIDATE_VERIFICATION):
        return None
    all_records = all_candidate_records(pipeline)
    logger.info(
        f"[Pipeline] _check_pool_health: stage={pipeline.workflow_stage} "
        f"records={len(all_records)} findings_history={len(pipeline.state_store.findings_history)} "
        f"current_candidates={len(pipeline.state_store.current_candidates)}"
    )
    if len(all_records) < 3:
        # Diagnostic: if we have findings but no candidate records,
        # the executor didn't call add_candidates tool. Log the
        # findings summaries to help diagnose.
        if len(pipeline.state_store.findings_history) >= 1:
            for fh in pipeline.state_store.findings_history[-3:]:
                s = str((fh or {}).get("summary", ""))[:120]
                nc = ((fh or {}).get("candidate_updates") or {}).get("new_candidates", [])
                logger.info(f"[Pipeline] _check_pool_health: findings summary={s!r} new_cands={nc}")
        return None

    # Guard: each issue type fires at most once per run.
    if not hasattr(pipeline, "_pool_health_fired"):
        pipeline._pool_health_fired: set = set()

    question_type = infer_question_answer_type(pipeline, question)
    candidate_types = infer_candidate_type_hints(pipeline, all_records)
    viable_records = viable_candidate_records(pipeline)
    eliminated_count = sum(
        1 for r in all_records
        if isinstance(r, dict) and (r.get("status") == "eliminated" or r.get("hard_conflicts"))
    )
    total_count = len(all_records)
    elimination_rate = (eliminated_count / total_count) if total_count else 0.0

    # Check 1: type mismatch (question asks for type X, all candidates are type Y)
    if (
        question_type != "unknown"
        and "type_mismatch" not in pipeline._pool_health_fired
    ):
        non_matching = sum(
            1 for ct in candidate_types
            if ct != "unknown" and ct != question_type
        )
        matching = sum(1 for ct in candidate_types if ct == question_type)
        # If >70% of typed candidates are a different type and none match
        typed_count = sum(1 for ct in candidate_types if ct != "unknown")
        if typed_count >= 3 and matching == 0 and non_matching / typed_count >= 0.7:
            pipeline._pool_health_fired.add("type_mismatch")
            viable_names = [r.get("name", "") for r in viable_records[:3]]
            logger.warning(
                f"[Pipeline] POOL TYPE MISMATCH: question asks for '{question_type}' "
                f"but all {typed_count} typed candidates are different types"
            )
            pipeline._record_event_for_trajectory("pool_type_mismatch", iteration, {
                "question_answer_type": question_type,
                "candidate_types": candidate_types[:8],
                "elimination_rate": round(elimination_rate, 2),
                "forced_stage_rebuild": True,
            })
            # Force the pipeline back to candidate_generation so the
            # planner immediately sees the new stage and generates a
            # search plan targeting the correct entity type. This mirrors
            # the direction critic's rebuild_candidate_pool action but
            # uses a deterministic heuristic (no LLM call).
            pipeline.workflow_stage = pipeline.CANDIDATE_GENERATION
            pipeline.stage_round_counts[pipeline.CANDIDATE_GENERATION] = 0
            pipeline.verification_queue = []
            pipeline.active_candidate = None
            pipeline.active_candidate_rounds = 0
            # pos6 v15: clear wrong-type candidate records so the executor
            # can't keep verifying them and the fallback can't reselect
            # them. The whole point of the rebuild is a fresh candidate
            # search of the CORRECT type. Without clearing, the executor
            # sees the stale wrong-type records and continues verifying
            # them (pos6 p1h: type mismatch fired at iter 0, planner
            # ignored the nudge and jumped to candidate_verification, and
            # the executor kept verifying authors instead of searching
            # for books).
            wrong_type_keys = []
            for key, rec in list(pipeline.state_store.candidate_records.items()):
                if not isinstance(rec, dict):
                    continue
                # candidate_type is never persisted on records; infer it
                # from the name using the same heuristic as
                # _infer_candidate_type_hints so the clear actually fires.
                hints = infer_candidate_type_hints(pipeline, [rec])
                ct = hints[0] if hints else "unknown"
                if ct and ct != "unknown" and ct != question_type:
                    wrong_type_keys.append(key)
            if wrong_type_keys:
                for key in wrong_type_keys:
                    pipeline.state_store.candidate_records.pop(key, None)
                # Also prune them from the current/eliminated lists so the
                # compact_state the planner sees is clean.
                pipeline.state_store.current_candidates = [
                    n for n in pipeline.state_store.current_candidates
                    if pipeline.state_store._candidate_key(n) not in set(wrong_type_keys)
                ]
                pipeline.state_store.eliminated_candidates = [
                    n for n in pipeline.state_store.eliminated_candidates
                    if pipeline.state_store._candidate_key(n) not in set(wrong_type_keys)
                ]
            logger.info(
                f"[Pipeline] Forced stage: CANDIDATE_GENERATION reset "
                f"(type mismatch, iter={iteration}, cleared {len(wrong_type_keys)} wrong-type candidates)"
            )
            return {
                "role": "user",
                "content": (
                    f"CANDIDATE POOL TYPE MISMATCH — STAGE RESET\n\n"
                    f"The original question appears to ask for a '{question_type}' as the answer, "
                    f"but ALL current candidates appear to be a different type of entity "
                    f"(persons, organizations, etc.). The correct answer may not be in the "
                    f"current pool at all.\n\n"
                    f"The pipeline has been FORCED back to candidate_generation. "
                    f"You MUST now search for '{question_type}' entities that satisfy the "
                    f"question's constraints. Do NOT propose verifying existing candidates "
                    f"of the wrong type.\n\n"
                    f"Previous viable candidates (wrong type): {json.dumps(viable_names, ensure_ascii=False)}\n"
                    f"Elimination rate: {elimination_rate:.0%} ({eliminated_count}/{total_count})\n\n"
                    f"Search strategy suggestions:\n"
                    f"1. Re-read the original question and identify what TYPE of entity the answer is\n"
                    f"2. Search for '{question_type}' entities matching the question's key constraints\n"
                    f"3. Use different search queries that would surface '{question_type}' results"
                    + (
                        f"\n4. The previous candidates were AUTHORS/PERSONS but the answer must be a "
                        f"BOOK TITLE. For each author previously found as a viable candidate, search "
                        f"explicitly for that author's published BOOKS (e.g. 'Barbara Hodgson books', "
                        f"'Barbara Hodgson bibliography', 'books by <author>') and add each book title "
                        f"as a candidate. A single author may have MULTIPLE books about the same topic — "
                        f"add ALL of them as separate candidates so they can be compared."
                        if question_type == "book_title"
                        else ""
                    )
                ),
            }

    # Check 2: domain monoculture + high elimination
    # Lowered threshold from 0.6/≤2 to 0.4/≤4 so the rebuild fires earlier,
    # before the pipeline burns all its crawl budget verifying wrong
    # candidates (pos6 v13 root cause: 57% elimination with 3 viable
    # candidates never triggered the rebuild, pipeline ran out of budget
    # at iter 5 with all candidates wrong).
    if (
        "domain_monoculture" not in pipeline._pool_health_fired
        and elimination_rate >= 0.4
        and len(viable_records) <= 4
    ):
        pipeline._pool_health_fired.add("domain_monoculture")
        viable_names = [r.get("name", "") for r in viable_records[:3]]
        # Build elimination-aware feedback: list each eliminated
        # candidate and the reason it was eliminated so the planner
        # knows what didn't work and can search from a different angle.
        eliminated_info = []
        for r in all_records:
            if not isinstance(r, dict):
                continue
            if r.get("status") == "eliminated" or r.get("hard_conflicts"):
                ename = r.get("name", "")
                ereason = str(r.get("elimination_reason") or r.get("supporting_constraints") or "contradicted")[:150]
                eliminated_info.append(f"  - {ename}: {ereason}")
        eliminated_summary = "\n".join(eliminated_info[:5]) if eliminated_info else "  (no detailed reasons available)"
        logger.warning(
            f"[Pipeline] POOL DOMAIN MONOCULTURE: {elimination_rate:.0%} eliminated, "
            f"{len(viable_records)} viable remaining"
        )
        pipeline._record_event_for_trajectory("pool_domain_monoculture", iteration, {
            "elimination_rate": round(elimination_rate, 2),
            "viable_count": len(viable_records),
            "total_count": total_count,
            "forced_stage_rebuild": True,
        })
        # Force the pipeline back to candidate_generation so the
        # planner searches from a completely different angle.
        pipeline.workflow_stage = pipeline.CANDIDATE_GENERATION
        pipeline.stage_round_counts[pipeline.CANDIDATE_GENERATION] = 0
        pipeline.verification_queue = []
        pipeline.active_candidate = None
        pipeline.active_candidate_rounds = 0
        # Allocate extra search budget for the regeneration round so it
        # can actually search (mirrors _force_pool_rebuild).
        current_search_calls = len(pipeline.query_memory.records)
        extra = 15
        pipeline.max_total_searches = max(pipeline.max_total_searches, current_search_calls + extra)
        pipeline.planner.search_budget += 5
        pipeline.executor.search_budget += 10
        logger.info(
            f"[Pipeline] Forced stage transition: CANDIDATE_VERIFICATION -> "
            f"CANDIDATE_GENERATION (domain monoculture, iter={iteration}, "
            f"+{extra} search budget -> total={pipeline.max_total_searches})"
        )
        # Type-aware guidance: if the question asks for a specific type
        # (e.g. book_title) but candidates were a different type (e.g.
        # person), explicitly tell the planner to search for the correct
        # type.
        type_guidance = ""
        if question_type != "unknown":
            type_guidance = (
                f"\n5. The answer should be a '{question_type}', but previous "
                f"candidates were all a different type. Search for "
                f"'{question_type}' entities directly, not the entities "
                f"you've been verifying."
            )
        return {
            "role": "user",
            "content": (
                f"CANDIDATE POOL COLLAPSE — STAGE RESET\n\n"
                f"{eliminated_count} of {total_count} candidates have been eliminated "
                f"({elimination_rate:.0%} elimination rate), and only {len(viable_records)} "
                f"viable candidate(s) remain. The current pool was likely built from a "
                f"single source or domain and may not contain the correct answer.\n\n"
                f"ELIMINATED CANDIDATES AND REASONS:\n{eliminated_summary}\n\n"
                f"The pipeline has been FORCED back to candidate_generation. "
                f"You MUST search from a COMPLETELY DIFFERENT angle:\n"
                f"1. Re-read the original question for alternative interpretations\n"
                f"2. Search for a different TYPE of entity (e.g., institution instead of person)\n"
                f"3. Use a different source family or search strategy\n"
                f"4. Consider that the answer may be an upstream entity (publisher, employer, "
                f"location) rather than the entities you've been verifying"
                f"{type_guidance}\n\n"
                f"Remaining viable: {json.dumps(viable_names, ensure_ascii=False)}"
            ),
        }

    return None


