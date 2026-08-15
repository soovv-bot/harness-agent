"""Direction Critic — LLM-based detection of planner direction stagnation.

Evaluates whether the planner has been pursuing the same direction across
multiple rounds without producing useful results. Called every 2 subtasks
by the pipeline.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger

root_path = os.path.dirname(os.path.dirname(__file__))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from llm_reasoning_compat import build_chat_completion_kwargs, chat_completion_with_structuring
from openai_client_factory import build_openai_client


@dataclass
class DirectionVerdict:
    is_stagnant: bool
    reason: str
    stagnation_duration: int = 0
    force_action: str = "none"
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "is_stagnant": self.is_stagnant,
            "reason": self.reason,
            "stagnation_duration": self.stagnation_duration,
            "force_action": self.force_action,
        }
        if self.suggestions:
            d["suggestions"] = self.suggestions
        return d


EVALUATION_PROMPT = """You are evaluating whether a search planner is stuck in a directionally stagnant loop.

## Original Question

{question}

## Plan History (most recent first)

{plan_history}

## Executor Findings History (most recent first)

{findings_history}

## Evaluation Criteria

The planner is stagnating if ALL of the following are true:
1. The planning direction (objective, source recommendations, and executor-facing steps) has not meaningfully changed across rounds.
2. Executor findings consistently show no substantial progress — no new candidates confirmed, no definitive evidence found, statuses like "partial" or "no_progress".
3. The planner keeps reassigning essentially the same subtask with minor rephrasings.

Important nuances:
- A direction change that still fails is NOT stagnation — the planner is trying different approaches.
- Lack of a final answer is NOT stagnation if the planner is making genuine progress narrowing candidates.
- Changing only the wording of a subtask while keeping the same target entity/source is stagnation.

## Output

JSON only (no markdown, no extra text):
{{"is_stagnant": true/false, "reason": "concise explanation", "stagnation_duration": 2, "suggestions": ["suggestion 1", "suggestion 2"]}}

The "suggestions" field should only be non-empty when is_stagnant is true. Provide 2-3 concrete, actionable suggestions for how the planner could change direction."""

ENHANCED_EVALUATION_PROMPT = """You are evaluating whether a search harness is stuck in a directionally stagnant loop.

## Original Question

{question}

## Current Harness Context

{context}

## Plan History (most recent first)

{plan_history}

## Executor Findings History (most recent first)

{findings_history}

## Evaluation Criteria

The search is stagnating if ALL of the following are broadly true:
1. The planning direction has not meaningfully changed across rounds.
2. Executor findings show little real progress.
3. The planner keeps reassigning essentially the same search frame.

Important nuances:
- A failed but genuinely new direction is NOT stagnation.
- Lack of a final answer is NOT stagnation if the planner is making genuine progress narrowing candidates.
- Repeatedly swapping among very similar weak candidates inside the same mistaken search frame CAN still be stagnation.
- Repeatedly searching broad lists of the same type without producing a strong candidate CAN still be stagnation.
- If the current pool is visibly damaged or insufficient, forcing a return to candidate generation can be better than continuing verification.

### Critical: Type Mismatch Detection

Check the harness context for `question_answer_type_hint` and `candidate_type_hints`:
- If the question asks for type X (e.g., "institution", "year", "place") but ALL candidate_type_hints are a different type (e.g., all "person"), the pool has a TYPE MISMATCH. This is severe stagnation — the correct answer cannot be in the pool.
- If `elimination_rate` is >= 0.6 and only 1-2 viable candidates remain, the pool is collapsing. If the remaining candidates are all the same type/domain, force a rebuild from a different angle.

### Critical: Domain Monoculture Detection

If all candidates share the same domain, affiliation, or source (e.g., all from the same university, all in the same academic field, all cited from the same paper), and none has been confirmed as the answer after multiple verification rounds, the search is stagnating. The correct answer likely lives in a different domain entirely.

## Available Harness Actions

Choose exactly one force_action:
- "none": do not force a harness intervention
- "rebuild_candidate_pool": force return to candidate_generation and rebuild the pool from a materially different angle
- "rotate_active_candidate": stop over-focusing the current verification candidate and move to another candidate
- "force_final_check": only when the evidence really indicates the task is ready for final_check

Guidance:
- Prefer "rebuild_candidate_pool" when the same search frame keeps failing or the pool is damaged or insufficient.
- Prefer "rebuild_candidate_pool" IMMEDIATELY when a type mismatch is detected (question_answer_type_hint differs from all candidate_type_hints).
- Prefer "rebuild_candidate_pool" when elimination_rate >= 0.6 and remaining viable candidates share the same domain/type.
- Prefer "rotate_active_candidate" when verification is over-investing in one candidate while other viable candidates remain.
- Prefer "none" when the planner is still making meaningful progress.
- Use "force_final_check" rarely.

## Output

JSON only (no markdown, no extra text):
{{"is_stagnant": true/false, "reason": "concise explanation", "stagnation_duration": 2, "force_action": "none|rebuild_candidate_pool|rotate_active_candidate|force_final_check", "suggestions": ["suggestion 1", "suggestion 2"]}}

The suggestions field should only be non-empty when is_stagnant is true. Provide 2-3 concrete, actionable suggestions for how the planner or harness should change direction."""


class DirectionCritic:
    """LLM-based critic that detects planner direction stagnation."""

    def __init__(self, api_base: str, api_key: str, model_id: str):
        self.client = build_openai_client(api_base, api_key)
        self.model_id = model_id

    def evaluate(
        self,
        question: str,
        plan_history: List[Dict[str, Any]],
        findings_history: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> DirectionVerdict:
        """Evaluate whether the planner is stagnating.

        Args:
            question: The original search question.
            plan_history: Recent plans (most recent last), up to 4.
            findings_history: Recent executor findings (most recent last), up to 4.

        Returns:
            DirectionVerdict with stagnation assessment and suggestions.
        """
        # Format plan history
        plan_lines = []
        for i, plan in enumerate(reversed(plan_history)):
            round_num = len(plan_history) - i
            source_recommendations = plan.get("source_recommendations")
            if source_recommendations is None:
                source_recommendations = plan.get("source_hypotheses", [])
            plan_lines.append(
                f"### Round {round_num}\n"
                f"- Phase: {plan.get('phase', 'unknown')}\n"
                f"- Objective: {plan.get('objective', 'N/A')}\n"
                f"- Source recommendations: {json.dumps(source_recommendations, ensure_ascii=False)[:300]}\n"
                f"- Candidate status: {(plan.get('candidate_status') or {}).get('state', 'N/A')}\n"
                f"- Steps: {json.dumps(plan.get('steps', []), ensure_ascii=False)[:500]}"
            )
        plan_text = "\n\n".join(plan_lines) if plan_lines else "(no plan history)"

        # Format findings history
        finding_lines = []
        for i, f in enumerate(reversed(findings_history)):
            round_num = len(findings_history) - i
            cand_updates = f.get("candidate_updates", {})
            finding_lines.append(
                f"### Round {round_num}\n"
                f"- Subtask: {f.get('subtask', 'N/A')}\n"
                f"- Status: {f.get('status', 'N/A')}\n"
                f"- Summary: {f.get('summary', 'N/A')[:300]}\n"
                f"- New candidates: {cand_updates.get('new_candidates', [])}\n"
                f"- Eliminated: {cand_updates.get('eliminated_candidates', [])}\n"
                f"- Suggestion for planner: {f.get('suggestion_for_planner', 'N/A')[:200]}"
            )
        findings_text = "\n\n".join(finding_lines) if finding_lines else "(no findings history)"

        prompt = ENHANCED_EVALUATION_PROMPT.format(
            question=question,
            context=json.dumps(context or {}, ensure_ascii=False, indent=2),
            plan_history=plan_text,
            findings_history=findings_text,
        )

        try:
            message = chat_completion_with_structuring(
                self.client,
                model_id=self.model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=2048,
                structurer_format_hint="Output the result as JSON.",
            )
            content = (getattr(message, "content", None) or "").strip()

            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if not json_match:
                logger.error(f"[DirectionCritic] Failed to parse response: {content[:200]}")
                return DirectionVerdict(
                    is_stagnant=False,
                    reason="Failed to parse critic response.",
                )

            result = json.loads(json_match.group())
            verdict = DirectionVerdict(
                is_stagnant=bool(result.get("is_stagnant", False)),
                reason=result.get("reason", ""),
                stagnation_duration=int(result.get("stagnation_duration", 0)),
                force_action=str(result.get("force_action", "none") or "none"),
                suggestions=result.get("suggestions", []),
            )
            logger.info(
                f"[DirectionCritic] is_stagnant={verdict.is_stagnant} | "
                f"force_action={verdict.force_action} | reason={verdict.reason[:120]}"
            )
            return verdict

        except Exception as e:
            logger.error(f"[DirectionCritic] Evaluation failed: {e}")
            return DirectionVerdict(
                is_stagnant=False,
                reason=f"Critic evaluation failed: {e}",
            )
