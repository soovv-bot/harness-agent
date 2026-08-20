"""Planning agent v3 with cleaner continuation and memory-friendly inputs."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

# tools package is now local: SearchHarness_0425/tools/
root_path = os.path.dirname(os.path.dirname(__file__))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from llm_reasoning_compat import (
    assistant_message_to_dict,
    build_chat_completion_kwargs,
    chat_completion_with_structuring,
)

_PLANNER_FORMAT_HINT = (
    "Output exactly one <planning>...</planning> block with valid JSON "
    'containing: task, steps (each with step, action, search_query, reasoning, '
    'and status="pending"), and status. Example step: '
    '{"step": 1, "action": "search", "search_query": "...", "reasoning": "...", "status": "pending"}.'
)
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


def _env_flag(name: str, default: str = "1") -> bool:
    raw = (os.getenv(name, default) or "").strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


class PlanningAgentV3:
    SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), 'planning_agent_prompt_v3.md')

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model_id: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.4,
        max_turns: int = 20,
        search_budget: int = 10,
        event_callback=None,
        reasoning_effort: Optional[str] = None,
    ):
        self.api_base = api_base
        self.api_key = api_key
        self.model_id = model_id
        self.temperature = temperature
        self.max_turns = _env_int("PLANNER_MAX_TURNS", max_turns)
        self.search_budget = search_budget
        self._search_count = 0
        self.max_output_tokens = _env_int("PLANNER_MAX_TOKENS", 1200)
        self.fail_fast_on_malformed_plan = _env_flag("PLANNER_FAIL_FAST_ON_MALFORMED_PLAN", "1")
        self._event_callback = event_callback  # callable(event_type, data) for trajectory recording
        # Per-role reasoning control (mirrors SearchAgentV3). When None, falls
        # back to LLM_THINKING_BUDGET_TOKENS via _resolve_effort() in the compat
        # layer. Pass explicitly to avoid the "minimal → ignored by endpoint →
        # 30K reasoning with 0 content" trap on GLM-5.2/tenyun.
        self.reasoning_effort = reasoning_effort

        if system_prompt:
            base_prompt = system_prompt
        elif os.getenv("PLANNER_SIMPLE_PROMPT", "").strip() in {"1", "true", "yes"}:
            # Reasoning-capable models can get
            # stuck in long reasoning when the system prompt is too long. Use a
            # compact prompt that lets the model emit a parseable <planning> block
            # instead of endless reasoning.
            simple_path = os.path.join(os.path.dirname(__file__), 'planning_agent_prompt_simple.md')
            with open(simple_path, 'r', encoding='utf-8') as f:
                base_prompt = f.read()
        else:
            with open(self.SYSTEM_PROMPT_PATH, 'r', encoding='utf-8') as f:
                base_prompt = f.read()

        self.system_prompt = base_prompt + f"""

You have no tools. Do not call tools, browse, search, or update the candidate pool yourself.
All search, browsing, candidate expansion, and candidate verification must be assigned to the executor through concrete subtasks.
Keep every plan compact: at most 6 steps, no large candidate dumps, and no long enumerations.

If the task is not solved, output exactly one <planning>...</planning> block with valid JSON only.
If the task is solved, output exactly one <answer>...</answer> block.

Strict output contract:
- Your assistant content must start with <planning> or <answer>.
- Your assistant content must end with the matching closing tag.
- Do not put analysis prose outside those tags.
- If the model supports hidden reasoning, keep it in hidden reasoning fields, not in the visible content field.
"""

        self.client = build_openai_client(api_base, api_key)
        self.messages: List[Dict[str, Any]] = []
        self._workflow_stage: Optional[str] = None
        self._stage_context: Dict[str, Any] = {}
        self._fallback_count = 0

    def _get_tool_schemas(self) -> List[Dict[str, Any]]:
        return []

    def _extract_answer(self, content: str) -> Optional[str]:
        text = content or ""
        text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL | re.IGNORECASE)
        matches = re.findall(r"<answer>(.*?)</answer>", text, re.DOTALL | re.IGNORECASE)
        if not matches:
            return None
        return matches[-1].strip()

    def _repair_planning_json(self, raw: str) -> List[str]:
        candidates: List[str] = []
        text = (raw or "").strip()
        if not text:
            return candidates

        candidates.append(text)

        fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
        if fenced and fenced not in candidates:
            candidates.append(fenced)

        start = fenced.find("{")
        end = fenced.rfind("}")
        clipped = fenced
        if start != -1 and end != -1 and end > start:
            clipped = fenced[start:end + 1].strip()
            if clipped and clipped not in candidates:
                candidates.append(clipped)

        repaired = clipped
        repair_attempts = [
            (r'(\[\s*)\{\s*\{', r'\1{'),
            (r'(\,\s*)\{\s*\{', r'\1{'),
            (r'\}\s*\}', r'}'),
            (r',(\s*[}\]])', r'\1'),
        ]
        for pattern, replacement in repair_attempts:
            repaired = re.sub(pattern, replacement, repaired, flags=re.DOTALL)
        repaired = repaired.strip()
        if repaired and repaired not in candidates:
            candidates.append(repaired)

        return candidates

    def _extract_planning(self, content: str) -> Optional[Dict[str, Any]]:
        matches = re.findall(r"<planning>(.*?)</planning>", content or "", re.DOTALL)
        if not matches:
            partial = self._extract_partial_planning_candidate(content)
            if partial:
                matches = [partial]
        # Try from last match first — planner may echo the example <planning>...</planning>
        # before outputting real JSON
        candidates = list(reversed(matches)) if matches else [content or ""]
        for raw in candidates:
            for candidate in self._repair_planning_json(raw):
                try:
                    plan = json.loads(candidate)
                    if isinstance(plan, dict):
                        return plan
                except json.JSONDecodeError:
                    continue
        if matches:
            logger.warning(f"All <planning> blocks failed to parse ({len(matches)} blocks found)")
        else:
            logger.warning("No <planning> block found and raw planning JSON recovery failed")
        return None

    def _extract_partial_planning_candidate(self, content: Optional[str]) -> Optional[str]:
        text = (content or "").strip()
        if not text:
            return None
        open_tag = text.rfind("<planning>")
        if open_tag == -1:
            return None
        partial = text[open_tag + len("<planning>"):].strip()
        return partial or None

    def _response_requires_fallback(self, content: str, response_dict: Dict[str, Any], parse_failures: int) -> bool:
        if not self.fail_fast_on_malformed_plan:
            return False
        if parse_failures < 1:
            return False
        text = (content or "").strip()
        reasoning = str(response_dict.get("reasoning_content") or "").strip()
        has_open = "<planning>" in text
        has_close = "</planning>" in text
        if not text and reasoning:
            return True
        if has_open and not has_close:
            return True
        return False

    def build_initial_prompt(self, question: str) -> str:
        use_simple = os.getenv("PLANNER_SIMPLE_PROMPT", "").strip() in {"1", "true", "yes"}
        if use_simple:
            return (
                f"Question: {question}\n\n"
                f"First identify what TYPE of entity this question asks for (person, band, place, school, organization, etc.). "
                f"Then identify the most distinctive constraints. "
                f"Output <planning>...</planning> with a search plan NOW. Do not reason."
            )
        return f"""Please analyze the following search question and create or update a search plan.

## Search Question
{question}

Output your plan inside <planning>...</planning> tags as valid JSON.

Your visible assistant content must begin with <planning> and end with </planning>.
Do not include analysis prose before or after the planning block."""

    def _build_compact_state_message(self, compact_state: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
        if not compact_state:
            return None
        return {"role": "user", "content": "Current compact state:\n" + json.dumps(compact_state, ensure_ascii=False, indent=2)}

    def _build_workflow_stage_message(
        self,
        workflow_stage: Optional[str],
        stage_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, str]]:
        if not workflow_stage:
            return None
        stage_context = stage_context or {}
        if workflow_stage == "candidate_generation":
            generation_round = stage_context.get("generation_round")
            stage_budget = stage_context.get("generation_budget")
            candidate_count = stage_context.get("current_candidate_count")
            budget_text = ""
            if generation_round is not None and stage_budget is not None:
                budget_text = f" This is candidate-generation round {generation_round} of {stage_budget}."
            candidate_text = ""
            if candidate_count is not None:
                candidate_text = f" The tracked pool currently contains {candidate_count} candidate(s)."
            return {
                "role": "user",
                "content": (
                    f"Suggested workflow stage for this turn: candidate_generation.{budget_text}{candidate_text} "
                    "Start the search from candidate_generation unless the current state clearly supports a later stage. "
                    "You decide whether the next executor subtask should be candidate_expansion, candidate_verification, or final_check. "
                    "Use candidate_expansion subtasks to build or repair the candidate pool rather than choose a winner. "
                    "A candidate does not have to be the final answer string; it may be any important entity or hypothesis that helps the search progress. "
                    "Do not add candidates yourself. Ask the executor to search and add candidates using its candidate tools. "
                    "For candidate_expansion subtasks, explicitly tell the executor to favor recall, avoid subjective exclusion, add plausible candidates unless direct evidence rules them out, and store uncertain constraints as unresolved. "
                    "CRITICAL (anti-premature-elimination): Do NOT silently exclude a candidate from your reasoning based on your own knowledge (e.g. 'X did not attend art college'). If you consider an entity as a possible candidate, you MUST emit a targeted candidate_expansion or candidate_verification subtask that searches for that specific entity against the constraints, and let the executor's grounded evidence decide. Reasoning-based exclusion without a search drops correct candidates. "
                    "When the question references a group/organization (band, team, company, school), enumerate its members and issue per-member verification subtasks rather than batch-eliminating them all in one reasoning step. "
                    "Use candidate_verification subtasks when the pool has plausible candidates and the executor should check hard constraints against evidence. "
                    "Use final_check only when the answer path is already strongly supported and only final confirmation remains. "
                    "Do not rely on only the most famous or first-seen names. "
                    "Every pending step must include the appropriate subtask_type. Keep the plan compact: at most 6 steps, and each subtask should be short and executable. "
                    "You must include pool_assessment and explicitly reflect on whether the pool is broad enough. "
                    "Only move to verification or set stage_status='ready_to_advance' if the pool is sufficiently covered or if the stage budget is exhausted and you have explained the remaining gaps."
                ),
            }
        if workflow_stage == "candidate_verification":
            viable_count = stage_context.get("viable_candidate_count")
            active_candidate = stage_context.get("active_candidate")
            verification_round = stage_context.get("candidate_verification_round")
            viable_text = ""
            if viable_count is not None:
                viable_text = f" The current state has {viable_count} viable candidate record(s)."
            candidate_text = ""
            if active_candidate:
                candidate_text = f" The current candidate to verify is: {active_candidate}."
            round_text = ""
            if verification_round is not None:
                round_text = f" This is verification round {verification_round} for that candidate."
            return {
                "role": "user",
                "content": (
                    f"Suggested workflow stage for this turn: candidate_verification.{viable_text}{candidate_text}{round_text} "
                    "Prefer candidate_narrowing or verification unless the pool clearly needs repair or the answer is fully resolved. "
                    "Start from the current candidate pool unless evidence shows that broad candidate generation should reopen. "
                    "Use candidate_verification subtasks to verify candidates one by one. If a current candidate is named above, normally focus on that candidate before switching. "
                    "You may verify multiple constraints for the same candidate across multiple subtasks, but do not abandon the current candidate until it has been adequately checked. "
                    "Write down hard conflicts aggressively, and remember that the candidate may be an upstream entity rather than the final answer string. "
                    "If the viable pool collapses or is clearly incomplete, you may issue a candidate_expansion subtask to repair it. "
                    "Every pending step must include the appropriate subtask_type. "
                    "Only set stage_status='ready_to_advance' when the current verification work has been sufficiently checked for this stage, either positively or negatively."
                ),
            }
        if workflow_stage == "final_check":
            return {
                "role": "user",
                "content": (
                    "Suggested workflow stage for this turn: final_check. "
                    "Use final_check when the surviving candidate path is actually sufficient for the final answer. "
                    "Do not broaden the pool unless you discover a concrete reason to fall back. "
                    "If key constraints remain unresolved, output a plan that says so instead of pretending the task is solved."
                ),
            }
        return None

    def run(
        self,
        question: str,
        feedback_history: Optional[List[Dict[str, str]]] = None,
        compact_state: Optional[Dict[str, Any]] = None,
        workflow_stage: Optional[str] = None,
        stage_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self._workflow_stage = workflow_stage
        self._stage_context = dict(stage_context or {})
        self._current_question = question
        self.messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.build_initial_prompt(question)},
        ]
        compact_state_msg = self._build_compact_state_message(compact_state)
        if compact_state_msg:
            self.messages.append(compact_state_msg)
        workflow_stage_msg = self._build_workflow_stage_message(workflow_stage, stage_context)
        if workflow_stage_msg:
            self.messages.append(workflow_stage_msg)
        if feedback_history:
            self.messages.extend(feedback_history)
        return self._conversation_loop(question=question)

    def continue_with_feedback(
        self,
        feedback_messages: List[Dict[str, str]],
        compact_state: Optional[Dict[str, Any]] = None,
        workflow_stage: Optional[str] = None,
        stage_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self._workflow_stage = workflow_stage
        self._stage_context = dict(stage_context or {})
        compact_state_msg = self._build_compact_state_message(compact_state)
        if compact_state_msg:
            self.messages.append({"role": "user", "content": compact_state_msg["content"].replace("Current compact state", "Updated compact state", 1)})
        workflow_stage_msg = self._build_workflow_stage_message(workflow_stage, stage_context)
        if workflow_stage_msg:
            self.messages.append(workflow_stage_msg)
        self.messages.extend(feedback_messages)
        return self._conversation_loop(question=None)

    def _conversation_loop(self, question: Optional[str]) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "question": question,
            "model": self.model_id,
            "started_at": datetime.now().isoformat(),
            "turns": 0,
        }
        latest_plan = self._latest_plan_from_messages()
        self._budget_exhausted = False
        force_planning_attempts = 0
        parse_failures = 0

        for turn in range(self.max_turns):
            metadata["turns"] = turn + 1
            logger.info(f"[Planner] turn={turn+1}/{self.max_turns}")
            try:
                _t0 = time.time()
                response = chat_completion_with_structuring(
                    self.client,
                    model_id=self.model_id,
                    messages=self.messages,
                    tools=None,
                    temperature=self.temperature,
                    max_tokens=self.max_output_tokens,
                    structurer_format_hint=_PLANNER_FORMAT_HINT,
                    reasoning_effort_override=self.reasoning_effort,
                )
                logger.info(f"[Planner] LLM turn={turn+1} done in {time.time()-_t0:.1f}s")
                response_dict = assistant_message_to_dict(response)
                self.messages.append(response_dict)

                tool_calls = getattr(response, "tool_calls", None) or response_dict.get("tool_calls") or []
                if tool_calls:
                    for tool_call in tool_calls:
                        if isinstance(tool_call, dict):
                            tool_call_id = tool_call.get("id", "")
                            fn = tool_call.get("function") or {}
                            name = fn.get("name")
                        else:
                            tool_call_id = getattr(tool_call, "id", "")
                            fn = getattr(tool_call, "function", None)
                            name = getattr(fn, "name", None)
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "name": name or "unsupported_tool",
                            "content": json.dumps({"ok": False, "error": "Planner has no tools. Output a planning block assigning executor subtasks instead."}, ensure_ascii=False),
                        })
                    self.messages.append({
                        "role": "user",
                        "content": (
                            "You attempted a tool call, but the planner has no tools. "
                            "Do not call tools. Output exactly one compact <planning>...</planning> block with executor subtasks only."
                        ),
                    })
                    continue

                content = response.content or ""
                answer = self._extract_answer(content)
                if answer:
                    metadata.update({"finished_at": datetime.now().isoformat(), "status": "solved"})
                    return {
                        "answer": answer,
                        "plan": latest_plan,
                        "trajectory": self.messages,
                        "metadata": metadata,
                        "candidate_updates": {},
                    }

                plan = self._extract_planning(content)
                if plan:
                    latest_plan = plan
                    parse_failures = 0
                elif (content or "").strip():
                    parse_failures += 1
                elif response_dict.get("reasoning_content"):
                    parse_failures += 1

                if not latest_plan and self._response_requires_fallback(content, response_dict, parse_failures):
                    fallback_plan = self._fallback_plan(question=question)
                    metadata.update({
                        "finished_at": datetime.now().isoformat(),
                        "status": "fallback_plan",
                        "fallback_reason": "malformed_or_reasoning_only_planner_output",
                    })
                    return {
                        "answer": None,
                        "plan": fallback_plan,
                        "trajectory": self.messages,
                        "metadata": metadata,
                        "candidate_updates": {},
                    }

                if not plan and not answer and not tool_calls and force_planning_attempts < 2:
                    force_planning_attempts += 1
                    self.messages.append({
                        "role": "user",
                        "content": (
                            "Your previous response was free-form analysis and did not contain an executable plan. "
                            "Stop analyzing in prose. Output exactly one <planning>...</planning> block with valid JSON only. "
                            "The plan must contain at least one concrete pending executor subtask for the current workflow stage. "
                            "Your visible content must start with <planning> and end with </planning>. "
                            "Do not call tools in this retry."
                        ),
                    })
                    continue

                if not latest_plan and (parse_failures >= 2 or force_planning_attempts >= 2):
                    fallback_plan = self._fallback_plan(question=question)
                    metadata.update({"finished_at": datetime.now().isoformat(), "status": "fallback_plan"})
                    return {
                        "answer": None,
                        "plan": fallback_plan,
                        "trajectory": self.messages,
                        "metadata": metadata,
                        "candidate_updates": {},
                    }

                metadata.update({"finished_at": datetime.now().isoformat(), "status": "plan_updated" if latest_plan else "no_output"})
                return {
                    "answer": None,
                    "plan": latest_plan,
                    "trajectory": self.messages,
                    "metadata": metadata,
                    "candidate_updates": {},
                }
            except Exception as e:
                logger.error(f"[Planner] Error in conversation loop: {e}")
                if latest_plan is None:
                    fallback_plan = self._fallback_plan(question=question)
                    metadata.update({"finished_at": datetime.now().isoformat(), "status": "fallback_plan", "error": str(e)})
                    return {
                        "answer": None,
                        "plan": fallback_plan,
                        "trajectory": self.messages,
                        "metadata": metadata,
                        "candidate_updates": {},
                    }
                metadata.update({"finished_at": datetime.now().isoformat(), "status": "error", "error": str(e)})
                return {
                    "answer": None,
                    "plan": latest_plan,
                    "trajectory": self.messages,
                    "metadata": metadata,
                    "candidate_updates": {},
                }

        # max_turns exhausted — inject wrap-up message and give one final turn
        self.messages.append({
            "role": "user",
            "content": (
                "You have reached the maximum number of turns. "
                "Based on all the information gathered so far, please output the most likely answer now.\n\n"
                "Output exactly one <answer>...</answer> block with the answer. "
                "Do NOT make any more tool calls or planning updates."
            ),
        })
        try:
            _t_ans = time.time()
            logger.info(f"[Planner] max_turns answer LLM start")
            response = chat_completion_with_structuring(
                self.client,
                model_id=self.model_id,
                messages=self.messages,
                temperature=self.temperature,
                max_tokens=self.max_output_tokens,
                structurer_format_hint=(
                    "Output exactly one <answer>...</answer> block with the most likely answer."
                ),
                reasoning_effort_override=self.reasoning_effort,
            )
            logger.info(f"[Planner] max_turns answer LLM done in {time.time()-_t_ans:.1f}s")
            self.messages.append(assistant_message_to_dict(response))
            content = response.content or ""
            answer = self._extract_answer(content)
            if answer:
                metadata.update({"finished_at": datetime.now().isoformat(), "status": "max_turns_answer"})
                return {
                    "answer": answer,
                    "plan": latest_plan,
                    "trajectory": self.messages,
                    "metadata": metadata,
                    "candidate_updates": {},
                }
        except Exception:
            pass
        metadata.update({"finished_at": datetime.now().isoformat(), "status": "max_turns_reached"})
        return {
            "answer": None,
            "plan": latest_plan,
            "trajectory": self.messages,
            "metadata": metadata,
            "candidate_updates": {},
        }

    def _fallback_plan(self, question: Optional[str]) -> Dict[str, Any]:
        self._fallback_count += 1
        workflow_stage = self._workflow_stage or "candidate_generation"
        stage_context = self._stage_context or {}
        objective = self._fallback_objective(question)

        if workflow_stage == "candidate_verification":
            active_candidate = stage_context.get("active_candidate") or "the strongest current candidate"
            return {
                "phase": "verification",
                "workflow_stage": workflow_stage,
                "stage_status": "continue",
                "objective": objective,
                "active_candidate": active_candidate,
                "steps": [
                    {
                        "id": 1,
                        "subtask": f"Verify {active_candidate} against the hardest unresolved constraints from the original question using direct evidence, and record supporting constraints, unresolved constraints, and hard conflicts.",
                        "subtask_type": "candidate_verification",
                        "status": "pending",
                        "progress": 0,
                        "result": "",
                        "guidance": [
                            "Use direct evidence only.",
                            "Resolve contradictions before broadening the search.",
                            "Update the candidate record even if the result is negative.",
                        ],
                    }
                ],
            }

        if workflow_stage == "final_check":
            return {
                "phase": "final_check",
                "workflow_stage": workflow_stage,
                "stage_status": "continue",
                "objective": objective,
                "steps": [
                    {
                        "id": 1,
                        "subtask": "Perform one final evidence check on the strongest surviving answer path and confirm whether the original question can be answered directly. If a required constraint is still unresolved, identify that exact gap.",
                        "subtask_type": "final_check",
                        "status": "pending",
                        "progress": 0,
                        "result": "",
                        "guidance": [
                            "Do not restart broad exploration unless the current answer path collapses.",
                            "Prefer direct answer-path confirmation over gathering more weak leads.",
                        ],
                    }
                ],
            }

        fallback_idx = (self._fallback_count - 1) % 4
        fallback_subtasks = [
            "Search for candidate entities that satisfy the most distinctive one or two constraints in the original question, then add every plausible candidate without fully verifying all later constraints.",
            "Search for a distinctive phrase or acknowledgement pattern from the question that can directly identify a document, work, or entity tied to the answer path.",
            "Search Wikipedia and encyclopedic sources for biographical or historical entries related to the key entities and time period implied by the question.",
            "Decompose the question into individual constraints and search for each one separately, starting with the least common or most unusual constraint, to find candidates that may not appear in broader searches.",
        ]
        return {
            "phase": "candidate_generation",
            "workflow_stage": workflow_stage,
            "stage_status": "continue",
            "objective": objective,
            "pool_assessment": {
                "coverage_status": "partial",
                "gaps": ["Need a broader but still relevant candidate pool before verification."],
            },
            "steps": [
                {
                    "id": 1,
                    "subtask": fallback_subtasks[fallback_idx],
                    "subtask_type": "candidate_expansion",
                    "status": "pending",
                    "progress": 0,
                    "result": "",
                    "guidance": [
                        "Favor recall over early elimination.",
                        "Use source families that are likely to contain entity lists, biographies, or catalog-style records.",
                        "Store unresolved constraints instead of guessing.",
                    ],
                },
                {
                    "id": 2,
                    "subtask": "Search for a distinctive phrase or acknowledgement pattern from the question that can directly identify a document, work, or entity tied to the answer path.",
                    "subtask_type": "candidate_expansion",
                    "status": "pending",
                    "progress": 0,
                    "result": "",
                    "guidance": [
                        "Prefer highly discriminative phrases over broad topic searches.",
                        "If a document is identified, capture its author and related named entities as candidates.",
                    ],
                },
            ],
        }

    def _fallback_objective(self, question: Optional[str]) -> str:
        text = (question or getattr(self, "_current_question", "") or "").strip()
        if not text:
            return "Create an executable search plan that advances the current workflow stage."
        snippet = text[:180].rstrip()
        return f"Advance the current workflow stage for the question: {snippet}"

    def _planner_candidate_updates(self, assessments: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {}

    def _latest_plan_from_messages(self) -> Optional[Dict[str, Any]]:
        for msg in reversed(self.messages):
            if msg.get("role") != "assistant":
                continue  # Only assistant messages contain planning JSON
            content = msg.get("content", "") if isinstance(msg, dict) else ""
            if not isinstance(content, str):
                continue
            plan = self._extract_planning(content)
            if plan:
                return plan
        return None
