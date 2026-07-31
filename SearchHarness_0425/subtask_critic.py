"""
Subtask Critic

Evaluates a proposed subtask against subtask execution history before assignment.
Prevents the planner from repeatedly assigning the same failed subtask to the executor.

Two-stage evaluation:
1. Fast rule-based checks (literal duplicate, repeated failure) — no LLM needed
2. Deep semantic analysis via LLM when rules are inconclusive
"""

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

from deepseek_thinking_compat import build_chat_completion_kwargs
from openai_client_factory import build_openai_client


# Verdict constants
ALLOW = "allow"
ALLOW_WITH_WARNING = "allow_with_warning"
REJECT_AS_REDUNDANT = "reject_as_redundant"
SUGGEST_PIVOT = "suggest_pivot"


@dataclass
class SubtaskRecord:
    """A record of a previously executed subtask."""
    name: str
    status: str  # completed, partial, failed, unknown, rejected
    summary: str = ""


class SubtaskVerdict:
    """Structured verdict from the subtask critic."""

    def __init__(self, decision: str, reason: str):
        self.decision = decision
        self.reason = reason

    @property
    def is_allowed(self) -> bool:
        return self.decision in (ALLOW, ALLOW_WITH_WARNING)

    def to_dict(self) -> Dict[str, Any]:
        return {"decision": self.decision, "reason": self.reason}

    def __repr__(self):
        return f"SubtaskVerdict({self.decision}, reason='{self.reason[:80]}...')"


def _normalize(name: str) -> str:
    return re.sub(r'\s+', ' ', name.strip().lower())


def _looks_candidate_specific(text: str) -> bool:
    tokens = re.findall(r"[A-Za-z][A-Za-z'-]+", text)
    capitalized = [t for t in tokens if t[:1].isupper()]
    return len(capitalized) >= 2


class SubtaskCritic:
    """
    Evaluates proposed subtasks against execution history.

    Usage:
        critic = SubtaskCritic(api_base, api_key, model_id)
        verdict = critic.evaluate(
            subtask_name="Find 2019 songs about identified athletes",
            subtask_guidance=["Search for ..."],
            overall_plan=plan,
        )
        if verdict.is_allowed:
            # assign to executor
        else:
            # feed rejection back to planner
    """

    CRITIC_PROMPT = """You are a subtask critic for a search planning system. Evaluate whether a proposed subtask is worth executing given the history of previous subtask attempts.

Output a JSON object with exactly two fields:
{{"decision": "allow | allow_with_warning | reject_as_redundant | suggest_pivot", "reason": "..."}}

Decision criteria:
- **allow**: The subtask explores a genuinely new direction, new constraints, or new source families.
- **allow_with_warning**: The subtask overlaps with history but introduces a meaningful variation in approach or guidance.
- **reject_as_redundant**: The subtask is essentially the same as a previous failed attempt with no meaningful change.
- **suggest_pivot**: The subtask repeats the same failed pattern. A fundamentally different approach is needed.

Important exception:
- If the proposed subtask is candidate-specific because a concrete person or entity already appears to match multiple core constraints, do not reject it merely for narrowing the search. Targeted candidate verification is allowed when it is a short attempt to confirm or eliminate a strong candidate.

## Subtask History

{history}

## Proposed Subtask

Name: {name}
Guidance: {guidance}
Plan phase: {phase}

Evaluate and output JSON only (no markdown, no extra text)."""

    def __init__(self, api_base: str, api_key: str, model_id: str = "GLM-5.2"):
        self.api_base = api_base
        self.api_key = api_key
        self.model_id = model_id
        self.records: List[SubtaskRecord] = []
        self.max_output_tokens = 1024

        self.client = build_openai_client(api_base, api_key)

    def record(self, name: str, status: str, summary: str = ""):
        """Record a subtask execution result."""
        self.records.append(SubtaskRecord(name=name, status=status, summary=summary))

    def evaluate(
        self,
        subtask_name: str,
        subtask_guidance: Optional[List[str]] = None,
        overall_plan: Optional[Dict[str, Any]] = None,
        use_llm: bool = True,
    ) -> SubtaskVerdict:
        """
        Evaluate a proposed subtask.

        Args:
            subtask_name: The name of the proposed subtask.
            subtask_guidance: The guidance/instructions for this subtask.
            overall_plan: The current overall plan.
            use_llm: Whether to use LLM for deep analysis (default True).

        Returns:
            SubtaskVerdict with decision and reasoning.
        """
        # Stage 1: Rule-based checks
        rule_verdict = self._rule_based_check(
            subtask_name,
            subtask_guidance or [],
            overall_plan,
        )
        if rule_verdict:
            logger.info(f"[SubtaskCritic] Rule-based verdict: {rule_verdict.decision}")
            return rule_verdict

        # Stage 2: LLM-based deep analysis
        if not use_llm:
            return SubtaskVerdict(
                decision=ALLOW,
                reason="No rule violations detected. LLM check skipped.",
            )

        return self._llm_based_check(
            subtask_name,
            subtask_guidance or [],
            overall_plan,
        )

    def _rule_based_check(
        self,
        subtask_name: str,
        subtask_guidance: Optional[List[str]] = None,
        overall_plan: Optional[Dict[str, Any]] = None,
    ) -> Optional[SubtaskVerdict]:
        """Fast checks that don't require LLM."""
        normalized = _normalize(subtask_name)
        candidate_specific = _looks_candidate_specific(subtask_name)

        overloaded = self._overloaded_candidate_expansion(
            subtask_name,
            subtask_guidance or [],
            overall_plan or {},
        )
        if overloaded:
            return overloaded

        if not self.records:
            return SubtaskVerdict(
                decision=ALLOW,
                reason="No prior subtask history. First subtask is always allowed.",
            )

        # 1. Check for repeated failures with same name
        recent = self.records[-5:]  # Look at last 5 subtasks
        consecutive_failures = 0
        for rec in reversed(recent):
            if _normalize(rec.name) == normalized and rec.status in ("failed", "partial", "unknown", "rejected"):
                consecutive_failures += 1
            else:
                break

        if consecutive_failures >= 2:
            if candidate_specific:
                return SubtaskVerdict(
                    decision=ALLOW_WITH_WARNING,
                    reason=(
                        f"Candidate-specific subtask '{subtask_name}' resembles recently unsuccessful work, "
                        f"but targeted verification of a strong candidate can still be worthwhile if it closes key constraints quickly."
                    ),
                )
            return SubtaskVerdict(
                decision=REJECT_AS_REDUNDANT,
                reason=(
                    f"Subtask '{subtask_name}' has failed {consecutive_failures} consecutive times "
                    f"(statuses: {[r.status for r in self.records[-consecutive_failures:]]}). "
                    f"Repeating it is unlikely to produce different results."
                ),
            )

        # 2. Literal duplicate of last failed subtask
        if self.records and _normalize(self.records[-1].name) == normalized:
            if self.records[-1].status in ("failed", "partial", "unknown"):
                if candidate_specific:
                    return SubtaskVerdict(
                        decision=ALLOW_WITH_WARNING,
                        reason=(
                            f"Same candidate-specific subtask '{subtask_name}' was just attempted with "
                            f"status='{self.records[-1].status}', but one more targeted verification pass may still be useful."
                        ),
                    )
                return SubtaskVerdict(
                    decision=REJECT_AS_REDUNDANT,
                    reason=(
                        f"Same subtask '{subtask_name}' was just attempted and returned "
                        f"status='{self.records[-1].status}'. No meaningful change detected."
                    ),
                )

        # 3. Near-duplicate check (Jaccard on word sets)
        query_words = set(normalized.split())
        for rec in reversed(recent):
            if rec.status in ("completed",):
                continue
            rec_words = set(_normalize(rec.name).split())
            if not query_words or not rec_words:
                continue
            overlap = query_words & rec_words
            union = query_words | rec_words
            jaccard = len(overlap) / len(union) if union else 0
            if jaccard >= 0.9:
                if candidate_specific:
                    return SubtaskVerdict(
                        decision=ALLOW_WITH_WARNING,
                        reason=(
                            f"Subtask '{subtask_name}' is very similar to previous work on the same candidate, "
                            f"but candidate-specific verification may still be justified if it targets a remaining hard constraint."
                        ),
                    )
                return SubtaskVerdict(
                    decision=REJECT_AS_REDUNDANT,
                    reason=(
                        f"Near-duplicate of previous subtask '{rec.name}' (status={rec.status}). "
                        f"Word-level Jaccard similarity: {jaccard:.1%}. "
                        f"Only minor rephrasing detected."
                    ),
                )

        # Rules inconclusive — defer to LLM
        return None

    def _overloaded_candidate_expansion(
        self,
        subtask_name: str,
        subtask_guidance: List[str],
        overall_plan: Dict[str, Any],
    ) -> Optional[SubtaskVerdict]:
        """Reject candidate-expansion subtasks that are really full verification sweeps."""
        phase = str(overall_plan.get("phase") or "").lower()
        subtask_type = ""
        for step in overall_plan.get("steps", []) or []:
            if (step.get("subtask") or step.get("name")) == subtask_name:
                subtask_type = str(step.get("subtask_type") or step.get("type") or "").lower()
                break

        is_expansion = subtask_type == "candidate_expansion" or phase in {
            "candidate_generation",
            "source_identification",
        }
        if not is_expansion:
            return None

        guidance_text = " ".join(str(item) for item in subtask_guidance if item)
        text = f"{subtask_name} {guidance_text}"
        lower = text.lower()
        first_sentence = re.split(r"[.!?]", subtask_name, maxsplit=1)[0]

        verification_phrases = (
            "check all constraints",
            "check all criteria",
            "check the criteria",
            "check the constraints",
            "check every",
            "fully verify",
            "against these criteria",
            "against the criteria",
            "same criteria",
            "all hard constraints",
            "systematically",
        )
        verification_pressure = sum(1 for phrase in verification_phrases if phrase in lower)

        list_pressure = first_sentence.count(",") + len(re.findall(r"\band\b", first_sentence, flags=re.I))
        has_long_example_list = bool(re.search(r"\b(e\.g\.|for example)\b", lower)) and subtask_name.count(",") >= 5
        capitalized_tokens = re.findall(r"\b[A-Z][A-Za-z0-9'&/-]+\b", subtask_name)
        has_named_entity_dump = subtask_name.count(",") >= 8 and len(capitalized_tokens) >= 8
        asks_many_checks = bool(re.search(r"\bfor each\b.{0,80}\bcheck\b", lower))
        three_part_entry = (
            " who " in f" {first_sentence.lower()} "
            and first_sentence.count(",") >= 2
            and re.search(r"\band\b", first_sentence, flags=re.I)
        )
        unbounded_harvest = (
            bool(re.search(r"\badd (any|every)\b", lower))
            and "regardless of other constraints" in lower
        ) or bool(re.search(r"\b(all|any)\s+\w+\s+who\s+\w+", lower)) and "favor recall over precision" in lower

        if verification_pressure >= 2 or list_pressure >= 7 or has_long_example_list or has_named_entity_dump or asks_many_checks or three_part_entry:
            return SubtaskVerdict(
                decision=SUGGEST_PIVOT,
                reason=(
                    "The proposed candidate-expansion subtask appears to bundle too many entry and verification "
                    "constraints into one executor task. Rewrite it as a bounded expansion task with one or two "
                    "searchable entry constraints, and leave the remaining constraints unresolved for later verification."
                ),
            )

        if unbounded_harvest:
            return SubtaskVerdict(
                decision=SUGGEST_PIVOT,
                reason=(
                    "The proposed candidate-expansion subtask is too unbounded: it asks the executor to harvest a very "
                    "broad class of entities without enough relevance boundaries. Rewrite it with a concrete source "
                    "family or domain boundary plus one or two searchable entry constraints."
                ),
            )

        return None

    def _llm_based_check(
        self,
        subtask_name: str,
        subtask_guidance: List[str],
        overall_plan: Optional[Dict[str, Any]],
    ) -> SubtaskVerdict:
        """Use LLM to evaluate subtask against history."""
        history_lines = []
        for rec in self.records[-10:]:
            history_lines.append(
                f"- Subtask: \"{rec.name}\" | Status: {rec.status} | Summary: {rec.summary[:200]}"
            )
        history_text = "\n".join(history_lines) if history_lines else "(no previous subtasks)"

        guidance_text = "\n".join(f"- {g}" for g in subtask_guidance) if subtask_guidance else "(none)"
        phase = (overall_plan or {}).get("phase", "unknown")

        prompt = self.CRITIC_PROMPT.format(
            history=history_text,
            name=subtask_name,
            guidance=guidance_text,
            phase=phase,
        )

        try:
            response = self.client.chat.completions.create(
                **build_chat_completion_kwargs(
                    model_id=self.model_id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                    max_tokens=2048,
                )
            )
            content = response.choices[0].message.content.strip()

            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if not json_match:
                logger.error(f"[SubtaskCritic] Failed to parse LLM response: {content[:200]}")
                return SubtaskVerdict(
                    decision=ALLOW_WITH_WARNING,
                    reason="Failed to parse LLM critic response. Allowing with warning.",
                )

            result = json.loads(json_match.group())
            decision = result.get("decision", ALLOW)
            reason = result.get("reason", "")

            logger.info(f"[SubtaskCritic] LLM verdict: {decision}")
            return SubtaskVerdict(decision=decision, reason=reason)

        except Exception as e:
            logger.error(f"[SubtaskCritic] LLM call failed: {e}")
            return SubtaskVerdict(
                decision=ALLOW_WITH_WARNING,
                reason=f"LLM critic call failed ({str(e)}). Allowing with warning.",
            )


def create_subtask_critic(
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    model_id: Optional[str] = None,
) -> SubtaskCritic:
    """Factory function to create a SubtaskCritic from environment variables."""
    from dotenv import load_dotenv
    load_dotenv()

    _api_base = api_base or os.getenv("OPENAI_BASE_URL")
    _api_key = api_key or os.getenv("OPENAI_API_KEY")
    _model_id = model_id or os.getenv("MODEL_NAME", "deepseek-chat")

    return SubtaskCritic(
        api_base=_api_base,
        api_key=_api_key,
        model_id=_model_id,
    )
