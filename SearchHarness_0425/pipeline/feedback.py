"""Feedback / reflexion / CRAG / direction helpers (RD step4b).

Pure functions taking the pipeline instance as the first parameter; re-bound
on the class as private attribute names so existing call sites keep working.

These emit user-role "feedback" messages injected back into the planner loop:
- gap-summary + stagnation warnings (planner coaching)
- reflexion note after batch eliminations (single LLM call, non-fatal)
- CRAG relevance assessment on subtask findings (single LLM call, non-fatal)
- forced direction-critic actions (pool rebuild / rotate / final_check)
"""
from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger

from llm.compat import chat_completion_with_structuring

if TYPE_CHECKING:  # avoid circular import with .orchestrator
    from pipeline.orchestrator import SearchHarnessPipelineV4


def build_stagnation_feedback(
    pipeline: "SearchHarnessPipelineV4",
    verdict,
) -> Dict[str, str]:
    suggestions_text = "\n".join(f"- {s}" for s in verdict.suggestions) if verdict.suggestions else ""
    return {
        "role": "user",
        "content": (
            f"DIRECTION STAGNATION WARNING\n\n"
            f"The direction critic has determined that your planning direction has been stagnant.\n\n"
            f"Reason: {verdict.reason}\n\n"
            f"The executor has not produced useful results under the current direction for multiple rounds. "
            f"You MUST change your approach.\n\n"
            f"Consider:\n"
            f"1. Re-read the original question carefully — you may be misinterpreting a key constraint or clue\n"
            f"2. Consider alternative interpretations of ambiguous terms (slang, nicknames, abbreviations, homophones)\n"
            f"3. Try a simpler, more concrete subtask that can produce definitive results before tackling the full question\n"
            f"4. Switch to a completely different source family or search angle\n"
            f"5. If you've been searching forward from a hypothesis, try working backwards from known facts instead\n"
            f"{suggestions_text}"
        ),
    }


def build_gap_summary(
    pipeline: "SearchHarnessPipelineV4",
    iteration: int,
) -> Optional[Dict[str, str]]:
    """P1-3A: Build a concise iteration gap summary for the planner.

    Lists what constraints have evidence, what candidates are active/eliminated,
    and what search directions have been tried. Helps the planner focus on
    unresolved gaps instead of re-trying exhausted directions.
    """
    try:
        compact_state = pipeline.state_store.export_compact_state()
        candidate_records = compact_state.get("candidate_records", []) or []
        current_candidates = compact_state.get("current_candidates", []) or []
        eliminated = compact_state.get("eliminated_candidates", []) or []
        confirmed_wrong = compact_state.get("confirmed_wrong_candidates", []) or []
        executions = compact_state.get("current_plan_executions", []) or []
        visited_domains = compact_state.get("visited_domains", []) or []

        # Summarize verified vs. partial candidates with evidence
        verified = []
        partial = []
        for cr in candidate_records:
            if not isinstance(cr, dict):
                continue
            name = cr.get("name", "?")
            vs = str(cr.get("verification_status", "")).lower()
            ev_count = len(cr.get("evidence", []) or [])
            if vs == "verified" and ev_count > 0:
                verified.append(f"  ✓ {name} ({ev_count} evidence)")
            elif vs == "partial":
                partial.append(f"  ? {name} ({ev_count} evidence)")

        # Summarize executed subtask types
        subtask_types = []
        for ex in executions[-10:]:
            st = (ex or {}).get("subtask_type", "") or (ex or {}).get("phase", "")
            if st and st not in subtask_types:
                subtask_types.append(st)

        lines = [f"ITERATION GAP SUMMARY (after iteration {iteration})"]
        lines.append(f"Active candidates: {len(current_candidates)} | Eliminated: {len(eliminated)} | Confirmed wrong: {len(confirmed_wrong)}")
        if verified:
            lines.append("Verified (with evidence):")
            lines.extend(verified[:5])
        if partial:
            lines.append("Partial (needs more evidence):")
            lines.extend(partial[:5])
        if eliminated:
            lines.append(f"Eliminated: {', '.join(eliminated[:8])}")
        if subtask_types:
            lines.append(f"Subtask types tried: {', '.join(subtask_types)}")
        if visited_domains:
            lines.append(f"Domains visited ({len(visited_domains)}): {', '.join(visited_domains[:8])}")
        lines.append("Focus your next subtask on UNRESOLVED constraints. Do not repeat exhausted search directions.")

        return {"role": "user", "content": "\n".join(lines)}
    except Exception as e:
        logger.debug(f"[Pipeline] gap summary build error: {e}")
        return None


def direction_critic_context(
    pipeline: "SearchHarnessPipelineV4",
) -> Dict[str, Any]:
    compact_state = pipeline.state_store.export_compact_state()
    all_records = pipeline._all_candidate_records()
    viable_records = pipeline._viable_candidate_records()
    eliminated_count = sum(
        1 for r in all_records
        if isinstance(r, dict) and (r.get("status") == "eliminated" or r.get("hard_conflicts"))
    )
    total_count = len(all_records)
    elimination_rate = (eliminated_count / total_count) if total_count else 0.0
    # Infer candidate "types" from names to detect type mismatch.
    # e.g., if the question asks for a university but all candidates are
    # person names, the pool has a type mismatch.
    candidate_type_hints = pipeline._infer_candidate_type_hints(all_records)
    return {
        "workflow_stage": pipeline.workflow_stage,
        "active_candidate": pipeline.active_candidate,
        "verification_queue_remaining": len(pipeline.verification_queue),
        "completed_verification_candidates": pipeline.completed_verification_candidates[-10:],
        "current_candidates": pipeline.state_store.current_candidates,
        "viable_candidate_count": len(viable_records),
        "remaining_uncertainties": (compact_state.get("latest_snapshot") or {}).get("remaining_uncertainties") or [],
        "total_candidate_count": total_count,
        "eliminated_count": eliminated_count,
        "elimination_rate": round(elimination_rate, 2),
        "candidate_type_hints": candidate_type_hints,
        "question_answer_type_hint": pipeline._infer_question_answer_type(getattr(pipeline, "_question", "") or ""),
    }


def reflect_on_elimination(
    pipeline: "SearchHarnessPipelineV4",
    eliminated_records: List[Dict[str, Any]],
    subtask_name: str,
    findings: Dict[str, Any],
    iteration: int,
) -> Optional[Dict[str, str]]:
    """Reflexion hook: extract a verbal lesson from eliminated candidates.

    Fires only when this iteration eliminated >=1 candidate. Makes ONE
    lightweight LLM call. On any error returns None (no regression).
    """
    if not pipeline._reflexion_enabled or not eliminated_records:
        return None
    if len(pipeline._reflection_notes) >= pipeline._max_reflection_notes:
        return None
    question = getattr(pipeline, "_question", "") or ""
    try:
        # Bundle up to 3 eliminated records into the prompt so a single
        # reflection covers a batch elimination round.
        sample_records = eliminated_records[:3]
        record_summaries = []
        for rec in sample_records:
            record_summaries.append(
                f"- {rec.get('name', '?')}: "
                f"conflicts={json.dumps(rec.get('hard_conflicts', [])[:2], ensure_ascii=False)}"
            )
        prompt = pipeline.REFLEXION_PROMPT.format(
            question=question[:400],
            candidate_name="; ".join(r.get("name", "?") for r in sample_records),
            hard_conflicts="\n".join(record_summaries)[:600],
            subtask_name=subtask_name[:120],
            subtask_summary=str(findings.get("summary", ""))[:300],
        )
        resp = chat_completion_with_structuring(
            client=pipeline._rank_client,
            model=pipeline._model_id,
            system_prompt="You are a research reflection assistant.",
            user_prompt=prompt,
            max_tokens=220,
            temperature=0.3,
        )
        note_text = (resp or "").strip()
        if not note_text or len(note_text) < 20:
            return None
        pipeline._reflection_notes.append({
            "iteration": iteration,
            "candidates": [r.get("name", "") for r in sample_records],
            "note": note_text[:300],
        })
        pipeline._record_event_for_trajectory("elimination_reflection", iteration, {
            "candidates": [r.get("name", "") for r in sample_records],
            "note": note_text[:200],
        })
        logger.info(
            f"[Pipeline] REFLEXION iter={iteration} learned: {note_text[:100]}"
        )
        return {
            "role": "user",
            "content": (
                f"REFLECTION FROM A PRIOR ELIMINATION (apply this lesson):\n"
                f"{note_text}\n\n"
                f"Use this when planning the next subtask: prefer the suggested "
                f"entity type and search angle."
            ),
        }
    except Exception as exc:
        logger.debug(f"[Pipeline] reflexion hook failed (non-fatal): {exc}")
        return None


def assess_subtask_relevance(
    pipeline: "SearchHarnessPipelineV4",
    subtask: Dict[str, Any],
    findings: Dict[str, Any],
    iteration: int,
) -> Optional[Dict[str, str]]:
    """CRAG hook: assess whether the just-completed subtask's findings
    actually advanced the goal. Returns a corrective feedback message
    when the verdict is IRRELEVANT or AMBIGUOUS, otherwise None.
    """
    if not pipeline._crag_enabled:
        return None
    if len(pipeline._relevance_notes) >= pipeline._max_relevance_notes:
        return None
    # Skip in final_check stage — at that point the executor is wrapping up
    # and "no new candidates" is the expected outcome.
    if pipeline.workflow_stage == pipeline.FINAL_CHECK:
        return None
    try:
        subtask_name = str(subtask.get("subtask") or subtask.get("name", ""))[:120]
        subtask_type = str(
            subtask.get("subtask_type") or subtask.get("type") or subtask.get("mode") or ""
        )[:40]
        cu = (findings or {}).get("candidate_updates", {}) or {}
        new_candidate_count = len(cu.get("new_candidates", []) or [])
        eliminated_count = len(cu.get("eliminated_candidates", []) or [])
        evidence_count = len((findings or {}).get("evidence", []) or [])
        findings_summary = str((findings or {}).get("summary", ""))[:300]
        # Skip the LLM call when findings are obviously useful —
        # new candidates or successful elimination = relevant by definition.
        if new_candidate_count > 0 and eliminated_count > 0:
            return None
        if new_candidate_count >= 2:
            return None
        prompt = pipeline.CRAG_PROMPT.format(
            subtask_name=subtask_name,
            subtask_type=subtask_type,
            findings_summary=findings_summary,
            evidence_count=evidence_count,
            new_candidate_count=new_candidate_count,
            eliminated_count=eliminated_count,
        )
        resp = chat_completion_with_structuring(
            client=pipeline._rank_client,
            model=pipeline._model_id,
            system_prompt="You are a retrieval relevance assessor.",
            user_prompt=prompt,
            max_tokens=120,
            temperature=0.0,
        )
        verdict_line = (resp or "").strip().splitlines()[0] if resp else ""
        verdict = "AMBIGUOUS"
        hint = ""
        if "verdict=" in verdict_line.lower():
            parts = verdict_line.split("|", 1)
            verdict = parts[0].split("=", 1)[1].strip().upper()
            if len(parts) > 1 and "hint=" in parts[1].lower():
                hint = parts[1].split("=", 1)[1].strip()
        if verdict not in {"IRRELEVANT", "AMBIGUOUS"}:
            return None
        if not hint:
            hint = "Rewrite the search query with more specific keywords."
        pipeline._relevance_notes.append({
            "iteration": iteration,
            "subtask": subtask_name,
            "verdict": verdict,
            "hint": hint[:200],
        })
        pipeline._record_event_for_trajectory("subtask_relevance", iteration, {
            "subtask": subtask_name,
            "verdict": verdict,
            "hint": hint[:200],
        })
        logger.warning(
            f"[Pipeline] CRAG verdict={verdict} iter={iteration} "
            f"subtask='{subtask_name[:60]}' hint='{hint[:80]}'"
        )
        return {
            "role": "user",
            "content": (
                f"RETRIEVAL RELEVANCE WARNING (CRAG)\n\n"
                f"The previous subtask '{subtask_name}' produced findings that "
                f"do not appear to meaningfully advance the goal "
                f"(verdict: {verdict}).\n\n"
                f"Corrective hint: {hint}\n\n"
                f"Rewrite the next search query to target a different angle. "
                f"Do NOT repeat the same search that produced these findings."
            ),
        }
    except Exception as exc:
        logger.debug(f"[Pipeline] CRAG hook failed (non-fatal): {exc}")
        return None


def apply_direction_critic_action(
    pipeline: "SearchHarnessPipelineV4",
    question: str,
    verdict,
    iteration: int,
    current_plan: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    action = (getattr(verdict, "force_action", "none") or "none").strip().lower()
    if action == "none":
        return None

    compact_state = pipeline.state_store.export_compact_state()
    feedback_text: Optional[str] = None

    if action == "rebuild_candidate_pool":
        pipeline.workflow_stage = pipeline.CANDIDATE_GENERATION
        pipeline.stage_round_counts[pipeline.CANDIDATE_GENERATION] = 0
        pipeline.active_candidate = None
        pipeline.active_candidate_rounds = 0
        pipeline.verification_queue = []
        feedback_text = (
            "HARNESS ACTION: direction critic forced a rebuild of the candidate pool. "
            "Return to candidate_generation immediately. "
            "Drop the current search frame and rebuild from a materially different angle, source family, or interpretation."
        )
    elif action == "rotate_active_candidate" and pipeline.workflow_stage == pipeline.CANDIDATE_VERIFICATION:
        rotated = pipeline._rotate_active_candidate(compact_state)
        if rotated and pipeline.active_candidate:
            feedback_text = (
                "HARNESS ACTION: direction critic forced a candidate rotation. "
                f"Stop over-investing in the previous candidate and switch to: {pipeline.active_candidate}. "
                "Stay in candidate_verification and focus on this candidate only."
            )
        else:
            return None
    elif action == "force_final_check":
        pipeline.workflow_stage = pipeline.FINAL_CHECK
        feedback_text = (
            "HARNESS ACTION: direction critic forced final_check. "
            "Do not broaden the pool. Determine whether the surviving path is actually sufficient."
        )
    else:
        return None

    logger.warning(f"[Pipeline] Applying direction-critic action: {action}")
    _t_pr = time.time()
    planner_result = pipeline.planner.run(
        question=question,
        feedback_history=[{"role": "user", "content": feedback_text}],
        compact_state=pipeline.state_store.export_compact_state(),
        workflow_stage=pipeline.workflow_stage,
        stage_context=pipeline._stage_context(),
    )
    if pipeline.trajectory_recorder:
        pipeline.trajectory_recorder.record_planner(messages=pipeline.planner.messages, iteration=iteration, latency_ms=(time.time() - _t_pr) * 1000.0)
    forced_plan = pipeline._prepare_plan_for_stage(planner_result.get("plan") or current_plan)
    pipeline._plan_history.append(forced_plan)
    phase_changed = pipeline.state_store.add_plan(forced_plan)
    if phase_changed:
        pipeline.state_store.create_snapshot()
    return forced_plan
