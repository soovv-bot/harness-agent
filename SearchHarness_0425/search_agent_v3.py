"""Search execution agent v3 with query critic hooks and micro compact support."""

from __future__ import annotations

import json
import os
import re
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from loguru import logger

# tools package is now local: SearchHarness_0425/tools/
_offseeker_src_path = None  # legacy path removed

from tools.tool_processor import ToolProcessor  # type: ignore
from tools.search_tools import authoritative_domains_in, high_weight_sources_in  # type: ignore
from search_memory import SearchStateStore

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from query_history import QueryHistoryMemory
from query_critic import QueryCritic, QueryVerdict, SUGGEST_PIVOT, _normalize_query
from search_crawl_controller import SearchCrawlController
from llm_reasoning_compat import (
    assistant_message_to_dict,
    build_chat_completion_kwargs,
    chat_completion_with_structuring,
)
from openai_client_factory import build_openai_client
from llm_error_utils import classify_infra_error


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


class SearchAgentV3:
    SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), 'search_agent_prompt_v3.md')

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model_id: str,
        state_store: SearchStateStore,
        query_memory: QueryHistoryMemory,
        query_critic: QueryCritic,
        crawl_controller: SearchCrawlController,
        system_prompt: Optional[str] = None,
        temperature: float = 0.4,
        max_turns: int = 20,
        search_budget: int = 30,
        enable_query_critic: bool = True,
        event_callback=None,
        reasoning_effort: Optional[str] = None,
        openai_client: Optional[Any] = None,
    ):
        self.api_base = api_base
        self.api_key = api_key
        self.model_id = model_id
        self.reasoning_effort = reasoning_effort
        # tool_choice mode for action turns: "auto" (model decides), "required"
        # (force a tool call every action turn — minimizes pre-tool reasoning),
        # or "first_turn" (force only on the first turn of each subtask, then auto).
        self.tool_choice_mode = (os.getenv("EXECUTOR_TOOL_CHOICE", "first_turn").strip().lower()
                                 or "first_turn")
        if self.tool_choice_mode not in {"auto", "required", "first_turn"}:
            self.tool_choice_mode = "first_turn"
        self.state_store = state_store
        self.query_memory = query_memory
        self.query_critic = query_critic
        self.enable_query_critic = enable_query_critic
        self.crawl_controller = crawl_controller
        self.temperature = temperature
        self.max_turns = _env_int("EXECUTOR_MAX_TURNS", max_turns)
        self.search_budget = search_budget
        self._search_count = 0
        self._crawl_count = 0
        self._crawl_nudge_sent = False
        self._forced_crawl_count = 0
        self._tool_lock = threading.Lock()
        # Authority-consensus early-stop: once a candidate is backed by ≥N
        # *independent* authoritative domains (tier>=4), the subtask is
        # effectively solved — nudge the agent to wrap up and save search turns.
        # Only fires on verification-type subtasks (expansion needs broad recall).
        self._authority_early_stop = os.getenv(
            "EXECUTOR_AUTHORITY_EARLY_STOP", "1").strip().lower() in {"1", "true", "yes"}
        self._authority_min_sources = _env_int("EXECUTOR_AUTHORITY_MIN_SOURCES", 2)
        # Fact-confirmed early-stop: >=N independent *weight-10* sources
        # (official docs / academic / official financial reports) agree on one
        # candidate → fact established, stop immediately (no more search rounds).
        # Default 2 matches the "2 high-weight sources → fact confirmed" rule.
        self._fact_confirm_min_sources = _env_int("EXECUTOR_FACT_CONFIRM_MIN_SOURCES", 2)
        self._authority_consensus_done = False  # inject wrap-up at most once
        self.max_output_tokens = _env_int("EXECUTOR_MAX_TOKENS", 1400)
        self._event_callback = event_callback  # callable(event_type, data) for trajectory recording

        if system_prompt:
            base_prompt = system_prompt
        elif os.getenv("EXECUTOR_SIMPLE_PROMPT", "").strip() in {"1", "true", "yes"}:
            # Reasoning-capable models can get
            # stuck in reasoning when the system prompt is too long. Use a compact
            # prompt that still carries the core execution contract but lets the
            # model emit tool_calls / content.
            simple_path = os.path.join(os.path.dirname(__file__), 'search_agent_prompt_simple.md')
            with open(simple_path, 'r', encoding='utf-8') as f:
                base_prompt = f.read()
        else:
            with open(self.SYSTEM_PROMPT_PATH, 'r', encoding='utf-8') as f:
                base_prompt = f.read()

        self.tool_schemas = self._get_tool_schemas()
        use_simple = os.getenv("EXECUTOR_SIMPLE_PROMPT", "").strip() in {"1", "true", "yes"}
        if use_simple:
            # The simple prompt already embeds a compact tool description; the
            # full function schemas are provided via the API `tools` parameter,
            # so we don't duplicate them in the system prompt.
            self.system_prompt = base_prompt + f"""

You must never output <answer>.
You must output exactly one <findings>...</findings> block before finishing.
Inside <findings>, output valid JSON only with fields:
subtask, status, summary, evidence, candidate_updates, source_feedback, suggestion_for_planner.
"""
        else:
            self.system_prompt = base_prompt + f"""

You must never output <answer>.
You must output exactly one <findings>...</findings> block before finishing.
Inside <findings>, output valid JSON only with fields:
subtask, status, summary, evidence, candidate_updates, source_feedback, suggestion_for_planner.

Candidate handling is critical:
- You have two candidate tools: `add_candidates` and `update_candidate`.
- Use `add_candidates` in discovery / pool-expansion subtasks to register candidate entities that satisfy the current subtask's requested entity type and restriction scope.
- Use `update_candidate` when you have evidence, uncertainty, or contradictions for a specific candidate.
- Candidate tools accumulate structured candidate_updates for the final findings; you must still output one <findings> block.
- candidate_updates.new_candidates and candidate_updates.eliminated_candidates may contain either plain strings or objects.
- Whenever you mention a concrete candidate in the summary or evidence, strongly prefer adding it or updating it with the candidate tools.
- Use candidate_updates.candidate_assessments as a list of objects like:
  {{"name": "...", "status": "active|eliminated", "verification_status": "unverified|partial|verified|contradicted", "confidence": "low|medium|high", "supporting_constraints": ["..."], "unresolved_constraints": ["..."], "hard_conflicts": ["..."], "evidence": [{{"source": "...", "observation": "..."}}]}}
- For discovery / candidate-pool-expansion subtasks, prioritize recall among entities that satisfy the current subtask's entity type and restriction scope. Mark them as verification_status "unverified" or "partial" unless directly proven.
- In candidate-pool-expansion subtasks, do not spend most of the budget deeply verifying a small set. Search outward, build the candidate universe required by the subtask, and add only entities that meet the subtask's stated entry requirements.
- Planner-provided names, bands, or examples are seeds only, not an exhaustive list. Do not let them define the boundary of the search.
- Avoid popularity bias. Do not focus only on the most famous or most familiar candidates; search for less obvious entities that fit the subtask scope.
- Do not skip or reject a candidate from memory, intuition, or unverified recall. If it meets the current subtask's entry requirements but another constraint is uncertain or suspected to fail, keep it active with unresolved constraints.
- For verification subtasks, be stricter: collect direct evidence, update conflicts, and only mark verification_status "verified" when the candidate satisfies the relevant constraints with evidence.
- Put any decisive contradiction in hard_conflicts. A candidate should be status "eliminated" only when explicit evidence shows it fails a required constraint.
- Do not put a candidate in eliminated_candidates just because it is weak, uncertain, or not fully verified. Keep such candidates active with unresolved_constraints.
- INTERPRETIVE AMBIGUITY (critical): When two or more candidates both plausibly satisfy a question constraint under different interpretations (e.g. "made from a particular flower" could mean directly extracted opium OR derivatives laudanum/morphine), do NOT eliminate one candidate in favor of another based solely on your preferred interpretation of the question wording. Keep BOTH candidates active with verification_status "partial", record the interpretive ambiguity in unresolved_constraints for each, and let the planner/contrastive verifier decide. Eliminating a candidate requires a FACTUAL contradiction (wrong author, wrong date, wrong subject, wrong entity type), not a preference for one reading of an ambiguous phrase over another.
"""

        self.client = openai_client or build_openai_client(api_base, api_key)
        self.tool_processor = ToolProcessor()
        self.messages: List[Dict[str, Any]] = []

    def _get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [
            {"type": "function", "function": {"name": "search", "description": "Search the web for information using Google search", "parameters": {"type": "object", "properties": {"query": {"type": "array", "items": {"type": "string"}}}, "required": ["query"]}}},
            {"type": "function", "function": {"name": "search_wiki", "description": "Search Wikipedia for information about entities", "parameters": {"type": "object", "properties": {"entities": {"type": "array", "items": {"type": "string"}}}, "required": ["entities"]}}},
            {"type": "function", "function": {"name": "visit_urls", "description": "Visit URLs and return raw content for shorter pages, or query-focused extracted reports for longer pages.", "parameters": {"type": "object", "properties": {"urls": {"type": "array", "items": {"type": "string"}, "description": "List of URLs to visit"}, "query": {"type": "string", "description": "Optional; defaults to the current search question."}}, "required": ["urls"]}}},
            {
                "type": "function",
                "function": {
                    "name": "add_candidates",
                    "description": (
                        "Register candidate names discovered while executing the current subtask. "
                        "Use for candidates that fit the current subtask boundary. "
                        "For discovery or candidate-pool-expansion, this records names only; use update_candidate "
                        "for evidence, uncertainty, or contradictions."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "candidates": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Candidate names that fit the current subtask's requested entity type and restriction scope.",
                            },
                        },
                        "required": ["candidates"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "update_candidate",
                    "description": (
                        "Merge evidence-backed updates into one candidate record. Unspecified fields are left unchanged. "
                        "Use status='active' for surviving or uncertain candidates. Use status='eliminated' only with explicit hard_conflicts for decisive contradictions."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Candidate or important entity name to update."},
                            "status": {"type": "string", "enum": ["active", "eliminated"], "description": "Candidate state after this subtask evidence."},
                            "verification_status": {"type": "string", "enum": ["unverified", "partial", "verified", "contradicted"], "description": "How well this candidate is verified for the current subtask constraints."},
                            "confidence": {"type": "string", "enum": ["low", "medium", "high"], "description": "Confidence in this candidate record after the current evidence."},
                            "supporting_constraints": {"type": "array", "items": {"type": "string"}, "description": "Constraints supported by observed evidence."},
                            "unresolved_constraints": {"type": "array", "items": {"type": "string"}, "description": "Relevant constraints still not verified."},
                            "hard_conflicts": {"type": "array", "items": {"type": "string"}, "description": "Decisive contradictions found in evidence."},
                            "evidence": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "source": {"type": "string"},
                                        "observation": {"type": "string"},
                                        "relevance": {"type": "string"},
                                    },
                                    "required": ["source", "observation"],
                                },
                                "description": "Evidence items supporting this update.",
                            },
                        },
                        "required": ["name"],
                    },
                },
            },
            {"type": "function", "function": {"name": "execute_code", "description": "Execute Python code", "parameters": {"type": "object", "properties": {"code": {"type": "string", "description": "Python code to execute"}}, "required": ["code"]}}},
        ]

    def _has_findings_block(self, content: str) -> bool:
        return bool(re.search(r"<findings\b[^>]*>.*?</findings>", content or "", re.DOTALL)) or bool(
            re.search(r"<[^>]*findings[^>]*>.*?</[^>]*findings[^>]*>", content or "", re.DOTALL)
        )

    def _strip_json_wrappers(self, raw: str) -> str:
        raw = raw.strip()
        fenced = re.fullmatch(r"```(?:json|JSON)?\s*(.*?)\s*```", raw, re.DOTALL)
        if fenced:
            return fenced.group(1).strip()
        return raw

    def _json_candidates_from_text(self, content: str) -> List[str]:
        candidates: List[str] = []
        text = content or ""
        candidates.extend(re.findall(r"```(?:json|JSON)?\s*(.*?)\s*```", text, re.DOTALL))
        candidates.append(text.strip())

        for start in [m.start() for m in re.finditer(r"\{", text)]:
            depth = 0
            in_string = False
            escape = False
            for idx in range(start, len(text)):
                ch = text[idx]
                if in_string:
                    if escape:
                        escape = False
                    elif ch == "\\":
                        escape = True
                    elif ch == '"':
                        in_string = False
                    continue
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidates.append(text[start:idx + 1])
                        break
        return candidates

    def _coerce_findings(self, payload: Any, *, source: str = "parsed") -> Optional[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return None
        if "findings" in payload and isinstance(payload.get("findings"), dict):
            payload = payload["findings"]
        if not isinstance(payload, dict):
            return None
        if not any(k in payload for k in ("summary", "candidate_updates", "evidence", "source_feedback", "suggestion_for_planner")):
            return None
        findings = dict(payload)
        findings.setdefault("subtask", getattr(self, "_current_subtask_text", "unknown"))
        findings.setdefault("status", "partial")
        findings.setdefault("summary", f"Recovered executor findings from {source}.")
        findings.setdefault("evidence", [])
        findings.setdefault("candidate_updates", self._empty_candidate_tool_updates())
        findings.setdefault("source_feedback", {"promising_sources": [], "unhelpful_sources": []})
        findings.setdefault("suggestion_for_planner", "")
        # Reasoning models may emit candidate_updates as a list of candidate objects
        # instead of the expected dict format.  Coerce list -> dict so downstream
        # code can safely access new_candidates / candidate_assessments.
        if isinstance(findings.get("candidate_updates"), list):
            list_updates = findings["candidate_updates"]
            new_candidates = []
            assessments = []
            for item in list_updates:
                if isinstance(item, dict):
                    name = str(item.get("name") or item.get("candidate") or "").strip()
                    if name:
                        new_candidates.append(name)
                    assessments.append(item)
                elif isinstance(item, str):
                    new_candidates.append(item)
            findings["candidate_updates"] = {
                "new_candidates": new_candidates,
                "eliminated_candidates": [],
                "candidate_assessments": assessments,
            }
        if not isinstance(findings.get("candidate_updates"), dict):
            findings["candidate_updates"] = self._empty_candidate_tool_updates()
        updates = findings["candidate_updates"]
        updates.setdefault("new_candidates", [])
        updates.setdefault("eliminated_candidates", [])
        updates.setdefault("candidate_assessments", [])
        # P0-2A: Evidence anchoring — downgrade evidence-less "verified" to "partial".
        # A candidate marked "verified" MUST have at least one evidence entry with
        # a source_url, otherwise it is downgraded to "partial" to prevent the
        # model from claiming verification based on memory rather than search results.
        # This ensures distillation training data shows "evidence -> conclusion" chains.
        for assessment in updates.get("candidate_assessments", []):
            if not isinstance(assessment, dict):
                continue
            vstatus = str(assessment.get("verification_status", "")).lower().strip()
            if vstatus == "verified":
                evidence_list = assessment.get("evidence", [])
                if not isinstance(evidence_list, list):
                    evidence_list = []
                has_anchored = False
                for ev in evidence_list:
                    if not isinstance(ev, dict):
                        continue
                    # Accept both "source_url" (new prompt schema) and "source"
                    # (legacy/executor-native field name) as anchored evidence.
                    url_val = ev.get("source_url") or ev.get("source") or ""
                    if isinstance(url_val, str) and url_val.strip().startswith("http"):
                        has_anchored = True
                        break
                if not has_anchored:
                    assessment["verification_status"] = "partial"
                    assessment.setdefault("_downgrade_reason", "no_anchored_evidence")
                    logger.debug(
                        f"[Executor] evidence-anchor: downgraded '{assessment.get('name','?')}' "
                        f"verified->partial (no source_url/source in evidence)"
                    )
        return findings

    def _extract_dsml_candidate_updates(self, content: str) -> Optional[Dict[str, Any]]:
        text = content or ""
        updates = self._empty_candidate_tool_updates()
        found = False

        dsml_list_too_large = False
        for match in re.finditer(
            r"<[^>]*invoke[^>]*name=[\"']add_candidates[\"'][^>]*>(.*?)</[^>]*invoke>",
            text,
            re.DOTALL,
        ):
            body = match.group(1)
            param = re.search(r"<[^>]*parameter[^>]*name=[\"']candidates[\"'][^>]*>(.*?)</[^>]*parameter>", body, re.DOTALL)
            raw = self._strip_json_wrappers(param.group(1).strip()) if param else body.strip()
            try:
                values = json.loads(raw)
            except json.JSONDecodeError:
                values = [x.strip(" \t\r\n\"'") for x in re.split(r"[,;\n]", raw) if x.strip()]
            if isinstance(values, str):
                values = [values]
            if isinstance(values, list) and len(values) > 50:
                dsml_list_too_large = True
                continue
            for value in values if isinstance(values, list) else []:
                name = self._candidate_name(value)
                if name and name not in updates["new_candidates"]:
                    updates["new_candidates"].append(name)
                    found = True

        for match in re.finditer(
            r"<[^>]*invoke[^>]*name=[\"']update_candidate[\"'][^>]*>(.*?)</[^>]*invoke>",
            text,
            re.DOTALL,
        ):
            body = match.group(1)
            args: Dict[str, Any] = {}
            for param in re.finditer(r"<[^>]*parameter[^>]*name=[\"']([^\"']+)[\"'][^>]*>(.*?)</[^>]*parameter>", body, re.DOTALL):
                key = param.group(1)
                raw = param.group(2).strip()
                try:
                    args[key] = json.loads(raw)
                except json.JSONDecodeError:
                    args[key] = raw
            assessment = self._candidate_update_from_args(args)
            if assessment:
                updates["candidate_assessments"].append(assessment)
                if assessment.get("status") == "eliminated":
                    updates["eliminated_candidates"].append(assessment["name"])
                else:
                    updates["new_candidates"].append(assessment["name"])
                found = True

        if not found:
            if dsml_list_too_large:
                return {
                    "subtask": getattr(self, "_current_subtask_text", "unknown"),
                    "status": "blocked",
                    "summary": "The executor attempted a malformed candidate update with an overly broad candidate list. The list was not merged because it did not provide structured evidence or a bounded set matching the current subtask.",
                    "evidence": [],
                    "candidate_updates": self._empty_candidate_tool_updates(),
                    "source_feedback": {"promising_sources": [], "unhelpful_sources": []},
                    "suggestion_for_planner": "Issue a narrower candidate-expansion subtask with explicit entry requirements, then add candidates in a bounded set.",
                }
            return None
        return {
            "subtask": getattr(self, "_current_subtask_text", "unknown"),
            "status": "partial",
            "summary": "Recovered candidate updates from a malformed DSML-style tool-call response. The executor did not produce a valid findings block.",
            "evidence": [],
            "candidate_updates": updates,
            "source_feedback": {"promising_sources": [], "unhelpful_sources": []},
            "suggestion_for_planner": "Continue from the recovered candidates and verify them against the original constraints.",
        }

    def _extract_findings(self, content: str, *, allow_dsml_recovery: bool = True) -> Optional[Dict[str, Any]]:
        matches = re.findall(r"<findings\b[^>]*>(.*?)</findings>", content or "", re.DOTALL)
        matches.extend(re.findall(r"<[^>]*findings[^>]*>(.*?)</[^>]*findings[^>]*>", content or "", re.DOTALL))
        for raw in reversed(matches):
            raw = self._strip_json_wrappers(raw)
            if not raw:
                continue
            try:
                findings = self._coerce_findings(json.loads(raw), source="findings block")
                if findings is not None:
                    return findings
            except json.JSONDecodeError:
                pass

        for raw in reversed(self._json_candidates_from_text(content or "")):
            raw = self._strip_json_wrappers(raw)
            if not raw:
                continue
            try:
                findings = self._coerce_findings(json.loads(raw), source="loose JSON")
                if findings is not None:
                    return findings
            except json.JSONDecodeError:
                continue

        if allow_dsml_recovery:
            dsml_findings = self._extract_dsml_candidate_updates(content or "")
            if dsml_findings is not None:
                logger.warning("Recovered findings from malformed DSML-style candidate tool call")
                return dsml_findings

        if matches:
            logger.warning(f"All <findings> blocks failed to parse ({len(matches)} blocks found)")
        return None

    def _append_force_tool_call(self) -> None:
        """Append a user message forcing the executor to output a tool call.

        Used when the LLM returns 0-content + 0-tool_calls (true empty response).
        Instead of prematurely wrapping up with findings, this nudges the model
        to continue searching — the correct behavior during candidate_generation.
        """
        self.messages.append({
            "role": "user",
            "content": (
                "Your previous response produced no visible output and no tool calls. "
                "You MUST call the search tool now with a relevant query to make progress. "
                "Output exactly one search tool call. Do not output findings or prose."
            ),
        })

    def _append_findings_format_retry(self, previous_content: str = "") -> None:
        previous_excerpt = (previous_content or "").strip()
        if len(previous_excerpt) > 3000:
            previous_excerpt = previous_excerpt[-3000:]
        self.messages.append({
            "role": "user",
            "content": (
                "Your previous response could not be parsed as valid findings. "
                "Do not make more tool calls. Re-output exactly one <findings>...</findings> block now.\n\n"
                "Inside <findings>, include raw JSON only: no markdown code fence, no ```json, no prose, no DSML tags. "
                "Use double quotes for all JSON keys and string values. "
                "If you attempted to call add_candidates or update_candidate, convert that information into "
                "candidate_updates.new_candidates and candidate_updates.candidate_assessments in the JSON instead.\n\n"
                "Use exactly this JSON structure inside <findings>:\n"
                "{\n"
                "  \"subtask\": \"...\",\n"
                "  \"status\": \"completed | partial | blocked\",\n"
                "  \"summary\": \"...\",\n"
                "  \"evidence\": [\n"
                "    {\"source\": \"...\", \"observation\": \"...\", \"relevance\": \"high | medium | low\"}\n"
                "  ],\n"
                "  \"candidate_updates\": {\n"
                "    \"new_candidates\": [],\n"
                "    \"eliminated_candidates\": [],\n"
                "    \"candidate_assessments\": [\n"
                "      {\n"
                "        \"name\": \"...\",\n"
                "        \"status\": \"active | eliminated\",\n"
                "        \"verification_status\": \"unverified | partial | verified | contradicted\",\n"
                "        \"confidence\": \"low | medium | high\",\n"
                "        \"supporting_constraints\": [],\n"
                "        \"unresolved_constraints\": [],\n"
                "        \"hard_conflicts\": [],\n"
                "        \"evidence\": [{\"source\": \"...\", \"observation\": \"...\"}]\n"
                "      }\n"
                "    ]\n"
                "  },\n"
                "  \"source_feedback\": {\n"
                "    \"promising_sources\": [],\n"
                "    \"unhelpful_sources\": []\n"
                "  },\n"
                "  \"suggestion_for_planner\": \"...\"\n"
                "}\n\n"
                f"Previous unparsable response excerpt:\n{previous_excerpt}"
            ),
        })

    def _contains_dsml_candidate_call(self, content: str) -> bool:
        text = content or ""
        return bool(
            re.search(r"<[^>]*invoke[^>]*name=[\"'](?:add_candidates|update_candidate)[\"']", text, re.DOTALL)
            or re.search(r"<[^>]*DSML[^>]*tool_calls[^>]*>", text, re.DOTALL)
        )

    def _empty_candidate_tool_updates(self) -> Dict[str, Any]:
        return {"new_candidates": [], "eliminated_candidates": [], "candidate_assessments": []}

    def _candidate_name(self, candidate: Any) -> str:
        if isinstance(candidate, dict):
            return str(candidate.get("name", "")).strip()
        return str(candidate or "").strip()

    def _string_list(self, value: Any) -> List[str]:
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if not isinstance(value, list):
            return []
        result: List[str] = []
        for item in value:
            text = str(item).strip()
            if text and text not in result:
                result.append(text)
        return result

    def _current_source_recommendations(self) -> List[str]:
        plan = self.state_store.current_plan or {}
        raw = plan.get("source_recommendations")
        if raw is None:
            raw = plan.get("source_hypotheses")
        recommendations: List[str] = []
        for item in raw or []:
            if isinstance(item, str):
                text = item.strip()
            elif isinstance(item, dict):
                text = str(item.get("source_family") or item.get("source_type") or item.get("site") or "").strip()
            else:
                text = str(item).strip()
            if text:
                recommendations.append(text)
        return recommendations

    def _evidence_list(self, value: Any) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            return []
        evidence: List[Dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            source = str(item.get("source", "")).strip()
            observation = str(item.get("observation", item.get("fact", ""))).strip()
            if not source or not observation:
                continue
            normalized = {"source": source, "observation": observation}
            relevance = str(item.get("relevance", "")).strip()
            if relevance:
                normalized["relevance"] = relevance
            if normalized not in evidence:
                evidence.append(normalized)
        return evidence

    def _candidate_update_from_args(self, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        name = self._candidate_name(arguments)
        if not name:
            return None
        assessment: Dict[str, Any] = {"name": name}
        status = str(arguments.get("status", "")).strip().lower()
        if status in {"active", "eliminated"}:
            assessment["status"] = status
        verification_status = str(arguments.get("verification_status", "")).strip().lower()
        if verification_status in {"unverified", "partial", "verified", "contradicted"}:
            assessment["verification_status"] = verification_status
        confidence = str(arguments.get("confidence", "")).strip().lower()
        if confidence in {"low", "medium", "high"}:
            assessment["confidence"] = confidence
        for field_name in ("supporting_constraints", "unresolved_constraints", "hard_conflicts"):
            values = self._string_list(arguments.get(field_name))
            if values:
                assessment[field_name] = values
        evidence = self._evidence_list(arguments.get("evidence"))
        if evidence:
            assessment["evidence"] = evidence
        if assessment.get("status") == "eliminated" and not assessment.get("hard_conflicts"):
            assessment["status"] = "active"
            assessment.setdefault("verification_status", "partial")
            unresolved = assessment.setdefault("unresolved_constraints", [])
            unresolved.append("Elimination was requested but no explicit hard-conflict evidence was provided.")
        if assessment.get("status") == "eliminated" and "verification_status" not in assessment:
            assessment["verification_status"] = "contradicted"
        return assessment

    def _append_new_candidate_names(self, names: List[str]) -> List[str]:
        added: List[str] = []
        existing = {str(name).strip().lower() for name in self._candidate_tool_updates["new_candidates"]}
        # pos9 fix: reject pseudo-candidates (search-intent phrases) and cap
        # how many candidates a single subtask can inject so the pool cannot
        # explode (pos9 had 90 candidates added in one subtask, swamping
        # verification). Reuses the shared _is_pseudo_candidate helper from
        # search_memory to stay consistent with the state-store gate.
        from search_memory import _is_pseudo_candidate  # local import to avoid cycle
        max_per_subtask = 15
        for name in names:
            candidate_name = str(name).strip()
            key = candidate_name.lower()
            if not candidate_name or key in existing:
                continue
            if _is_pseudo_candidate(candidate_name):
                logger.debug(f"[Executor] rejected pseudo-candidate: {candidate_name!r}")
                continue
            self._candidate_tool_updates["new_candidates"].append(candidate_name)
            existing.add(key)
            added.append(candidate_name)
            if len(self._candidate_tool_updates["new_candidates"]) >= max_per_subtask:
                logger.info(f"[Executor] candidate cap reached ({max_per_subtask}) for this subtask, ignoring rest")
                break
        return added

    def _execute_add_candidates_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        raw_candidates = arguments.get("candidates")
        if raw_candidates is None:
            raw_candidates = arguments.get("names")
        if raw_candidates is None and arguments.get("name"):
            raw_candidates = [arguments.get("name")]
        if isinstance(raw_candidates, str):
            raw_candidates = [raw_candidates]
        if not isinstance(raw_candidates, list):
            return {"ok": False, "error": "Pass candidates as a non-empty string array."}
        names = [self._candidate_name(item) for item in raw_candidates]
        added = self._append_new_candidate_names(names)
        self.query_memory.add_candidates_to_last_record(added)
        return {"ok": True, "added_count": len(added), "added_candidates": added}

    def _execute_update_candidate_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        assessment = self._candidate_update_from_args(arguments)
        if not assessment:
            return {"ok": False, "error": "Missing candidate name."}
        if assessment.get("status") == "eliminated":
            eliminated = self._candidate_tool_updates["eliminated_candidates"]
            if assessment["name"] not in eliminated:
                eliminated.append(assessment["name"])
        else:
            added = self._append_new_candidate_names([assessment["name"]])
            self.query_memory.add_candidates_to_last_record(added)
        self._candidate_tool_updates["candidate_assessments"].append(assessment)
        return {"ok": True, "updated_candidate": assessment["name"], "recorded_fields": sorted(k for k in assessment if k != "name")}

    def _merge_candidate_tool_updates_into_findings(self, findings: Dict[str, Any]) -> Dict[str, Any]:
        updates = findings.setdefault("candidate_updates", {})
        if not isinstance(updates, dict):
            updates = {}
            findings["candidate_updates"] = updates
        tool_updates = getattr(self, "_candidate_tool_updates", self._empty_candidate_tool_updates())
        for key in ("new_candidates", "eliminated_candidates"):
            merged = list(updates.get(key, []) or [])
            for item in tool_updates.get(key, []) or []:
                if item not in merged:
                    merged.append(item)
            updates[key] = merged
        assessments = list(updates.get("candidate_assessments", []) or [])
        assessments.extend(tool_updates.get("candidate_assessments", []) or [])
        updates["candidate_assessments"] = assessments
        self._sync_findings_candidates_to_query_history(updates)
        return findings

    def _consensus_candidate(self) -> Optional[Dict[str, Any]]:
        """Return a candidate backed by enough source weight, or None.

        Two-tier decision (matches the "2 high-weight sources → fact confirmed"
        rule; weight=10 = official docs / academic / official financial reports,
        weight=2 = UGC / self-media):
          1. FACT-CONFIRMED: >=N independent weight-10 sources (default 2) agree
             on one candidate → fact established, stop immediately (strongest
             early-stop; the "2 high-weight sources → fact confirmed" rule).
          2. AUTHORITATIVE CONSENSUS: >=N independent weight>=8 sources (tier>=4;
             default 2) agree → early-stop (the original authoritative-tier rule).

        Returns ``{"name", "kind", "sources"}`` where kind is
        ``"fact_confirmed"`` or ``"authoritative_consensus"``, or None.
        """
        if not self._authority_early_stop or self._authority_consensus_done:
            return None
        try:
            assessments = self._candidate_tool_updates.get("candidate_assessments", []) or []
        except Exception:
            return None
        # Group evidence URLs by candidate name (case-insensitive).
        per_candidate: Dict[str, List[str]] = {}
        for assessment in assessments:
            if not isinstance(assessment, dict):
                continue
            name = self._candidate_name(assessment)
            if not name:
                continue
            # Skip explicitly-eliminated / contradicted candidates.
            status = str(assessment.get("status", "")).strip().lower()
            vstatus = str(assessment.get("verification_status", "")).strip().lower()
            if status == "eliminated" or vstatus == "contradicted":
                continue
            urls = per_candidate.setdefault(name, [])
            for ev in assessment.get("evidence", []) or []:
                if not isinstance(ev, dict):
                    continue
                url_val = ev.get("source_url") or ev.get("source") or ""
                if isinstance(url_val, str) and url_val.strip().startswith("http"):
                    urls.append(url_val.strip())
        fact_min = self._fact_confirm_min_sources
        auth_min = self._authority_min_sources
        for name, urls in per_candidate.items():
            # Tier 1: weight-10 sources (fact confirmed) — needs only fact_min.
            high = high_weight_sources_in(urls, min_weight=10)
            if len(high) >= fact_min:
                return {"name": name, "kind": "fact_confirmed", "sources": high}
            # Tier 2: weight>=8 authoritative consensus (encyclopedia / official
            # institutions / authoritative media) — needs auth_min.
            auth = authoritative_domains_in(urls)
            if len(auth) >= auth_min:
                return {"name": name, "kind": "authoritative_consensus", "sources": auth}
        return None

    def _authority_consensus_candidate(self) -> Optional[str]:
        """Backward-compatible wrapper: return candidate name or None.

        Prefer ``_consensus_candidate`` for new code (returns kind + sources).
        """
        result = self._consensus_candidate()
        return result["name"] if result else None

    def _sync_findings_candidates_to_query_history(self, updates: Dict[str, Any]) -> None:
        names: List[str] = []
        for item in updates.get("new_candidates", []) or []:
            name = self._candidate_name(item)
            if name:
                names.append(name)
        for assessment in updates.get("candidate_assessments", []) or []:
            if not isinstance(assessment, dict) or assessment.get("status") == "eliminated":
                continue
            name = self._candidate_name(assessment)
            if name:
                names.append(name)
        self.query_memory.add_candidates_to_last_record(names)

    def build_subtask_prompt(self, question: str, overall_plan: Dict[str, Any], subtask: Dict[str, Any], executor_state: Optional[Dict[str, Any]] = None) -> str:
        subtask_type = subtask.get("subtask_type") or subtask.get("type") or subtask.get("mode") or "infer_from_subtask"
        prompt = f"""## Original Search Question
{question}

## Your Current Subtask
{json.dumps(subtask, ensure_ascii=False, indent=2)}

## Subtask Type
{subtask_type}
"""
        if executor_state:
            prompt += "\n## Search State\n" + json.dumps(executor_state, ensure_ascii=False, indent=2) + "\n"
        prompt += "\nUse the available tools to complete only this subtask.\n\n"
        if subtask_type == "candidate_expansion":
            prompt += (
                "Candidate expansion rules:\n"
                "- Your goal is to expand the candidate pool, not to fully verify a small number of candidates.\n"
                "- Use search to follow the subtask requirements and build the candidate universe requested by this subtask.\n"
                "- The current subtask defines the candidate-entry boundary: requested entity type and stated entry restrictions.\n"
                "- Within that boundary, favor recall and add candidates broadly; do not filter down to only high-confidence or fully verified candidates.\n"
                "- Do not add unrelated named entities from search results, but do add every concrete entity that plausibly satisfies the current subtask boundary.\n"
                "- Planner-provided names, bands, or examples are only seeds. Do not treat them as exhaustive, and do not restrict the search to them.\n"
                "- Avoid popularity or familiarity bias. Do not focus only on very famous candidates; include less obvious entities that plausibly fit the subtask.\n"
                "- Do not reject or skip a candidate based on memory, intuition, or unverified biographical recall. If it meets the subtask entry requirements but another constraint is uncertain or suspected to fail, add it as active with unresolved constraints.\n"
                "- Do not wait for full verification. If there is no explicit evidence ruling a candidate out, keep it active with unresolved constraints.\n"
                "- Do only lightweight checks needed to keep the expansion relevant; save strict evidence collection for candidate_verification subtasks.\n"
                "- Crawl encouragement: after 2+ searches, if the results contain promising source URLs, call visit_urls on 1-2 high-value URLs to read the actual page content. Page content often reveals candidates that are not visible in search snippets (e.g. names in article body, lists, footnotes). Snippet-only expansion misses candidates.\n"
            )
        elif subtask_type == "candidate_verification":
            prompt += (
                "Candidate verification rules:\n"
                "- Verify the specified candidate or small candidate set strictly from evidence.\n"
                "- Update candidate records with supporting constraints, unresolved constraints, hard conflicts, and evidence.\n"
                "- Do not guess. Do not eliminate candidates without explicit hard-conflict evidence.\n"
                "- Page evidence required (CRITICAL): after your first search, if the results contain any source URLs, you MUST call `visit_urls` on at least one relevant URL to read the actual page content before reporting findings. Verification based only on search snippets (without a `visit_urls` call) will be downgraded to unverified — search summaries are NOT sufficient proof for a verification subtask.\n"
            )
            # If the subtask itself names URLs, list them so the executor crawls them.
            _subtask_body = subtask.get("subtask") or subtask.get("name") or ""
            _urls = re.findall(r'https?://[^\s\)\]\}>\"]+', _subtask_body)
            if _urls:
                prompt += "- Required URLs to visit (call visit_urls with these): " + ", ".join(_urls[:5]) + "\n"
        else:
            prompt += (
                "Candidate handling rules:\n"
                "- Add or update candidates when concrete entities appear.\n"
                "- Keep weak or unresolved candidates active unless explicit hard-conflict evidence rules them out.\n"
            )
        return prompt

    def run(self, question: str, overall_plan: Dict[str, Any], subtask: Dict[str, Any], executor_state: Optional[Dict[str, Any]] = None, stop_event: Optional[threading.Event] = None) -> Dict[str, Any]:
        self._current_question = question
        subtask_text = subtask.get("subtask") or subtask.get("name") or "unknown"
        self._current_subtask_text = subtask_text
        self.messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.build_subtask_prompt(question, overall_plan, subtask, executor_state=executor_state)},
        ]
        self._search_count = 0  # Reset per subtask
        self._crawl_count = 0  # Reset per subtask
        self._crawl_nudge_sent = False
        self._forced_crawl_count = 0
        self._budget_exhausted = False
        self._candidate_tool_updates = self._empty_candidate_tool_updates()
        self._infra_retry_count = 0  # P0-B: reset infra retry counter per subtask
        self._authority_consensus_done = False  # reset per-subtask early-stop gate
        disable_tools_for_wrapup = False
        missing_findings_reminders = 0
        malformed_findings_reminders = 0
        phase = overall_plan.get("phase", "unknown")
        metadata = {"question": question, "subtask": subtask_text, "phase": phase, "model": self.model_id, "started_at": datetime.now().isoformat(), "turns": 0}

        for turn in range(self.max_turns):
            if stop_event is not None and stop_event.is_set():
                logger.info(f"[Executor] sibling early-stop signaled — winding down subtask='{subtask_text[:60]}'")
                metadata.update({"finished_at": datetime.now().isoformat(), "status": "sibling_early_stop"})
                return {"findings": None, "trajectory": self.messages, "metadata": metadata}
            metadata["turns"] = turn + 1
            logger.info(f"[Executor] turn={turn+1}/{self.max_turns} subtask='{subtask_text[:60]}' phase={phase}")
            try:
                _t0 = time.time()
                # tool_choice: force a tool call on action turns to minimize
                # pre-tool reasoning (industry best practice for reasoning models).
                # On wrap-up turns (tools disabled) tool_choice is irrelevant.
                extra_kwargs: Dict[str, Any] = {}
                if not disable_tools_for_wrapup and self.tool_schemas:
                    if self.tool_choice_mode == "required":
                        extra_kwargs["tool_choice"] = "required"
                    elif self.tool_choice_mode == "first_turn" and turn == 0:
                        extra_kwargs["tool_choice"] = "required"
                response = chat_completion_with_structuring(
                    self.client,
                    model_id=self.model_id,
                    messages=self.messages,
                    tools=None if disable_tools_for_wrapup else self.tool_schemas,
                    temperature=self.temperature,
                    max_tokens=self.max_output_tokens,
                    reasoning_effort_override=self.reasoning_effort,
                    structurer_format_hint=(
                        "Output your findings in a <findings>...</findings> block with valid JSON "
                        "containing: subtask, status, summary, evidence, candidate_updates, "
                        "source_feedback, suggestion_for_planner."
                    ),
                    **extra_kwargs,
                )
                logger.info(f"[Executor] LLM turn={turn+1} done in {time.time()-_t0:.1f}s")
                response_dict = assistant_message_to_dict(response)
                # Sanitize tool_call arguments: GLM-5.2 sometimes emits
                # malformed JSON in tool_call.function.arguments (truncated
                # strings, unescaped quotes). The API rejects these with a
                # 400 error on the NEXT turn, crashing the subtask. Repair or
                # replace invalid arguments before storing the message.
                _tc_list = response_dict.get("tool_calls") or []
                for _tc in _tc_list:
                    if isinstance(_tc, dict) and isinstance(_tc.get("function"), dict):
                        _args = _tc["function"].get("arguments")
                        if isinstance(_args, str) and _args:
                            try:
                                json.loads(_args)
                            except (json.JSONDecodeError, ValueError):
                                logger.warning(
                                    f"[Executor] sanitizing invalid tool_call arguments "
                                    f"for {_tc['function'].get('name','?')}: "
                                    f"{_args[:80]!r}"
                                )
                                # Try simple repairs: add closing brace/bracket
                                _repaired = _args
                                for _suffix in ["}", "]", "}}", "]}"]:
                                    try:
                                        json.loads(_repaired + _suffix)
                                        _repaired = _repaired + _suffix
                                        break
                                    except (json.JSONDecodeError, ValueError):
                                        continue
                                try:
                                    json.loads(_repaired)
                                    _tc["function"]["arguments"] = _repaired
                                except (json.JSONDecodeError, ValueError):
                                    # Last resort: empty args (tool will use defaults)
                                    _tc["function"]["arguments"] = "{}"
                self.messages.append(response_dict)
                content = response.content or ""
                allow_dsml_recovery = malformed_findings_reminders > 0
                findings = self._extract_findings(content, allow_dsml_recovery=allow_dsml_recovery)
                if findings is not None:
                    # Debug: log findings before merge
                    _nc_before = (findings.get("candidate_updates") or {}).get("new_candidates", [])
                    logger.info(f"[Executor] findings extracted: new_candidates_before_merge={_nc_before}")
                    findings = self._merge_candidate_tool_updates_into_findings(findings)
                    _nc_after = (findings.get("candidate_updates") or {}).get("new_candidates", [])
                    logger.info(f"[Executor] findings after merge: new_candidates_after_merge={_nc_after}")
                    metadata.update({"finished_at": datetime.now().isoformat(), "status": "completed"})
                    return {"findings": findings, "trajectory": self.messages, "metadata": metadata}
                if self._contains_dsml_candidate_call(content) and malformed_findings_reminders < 1:
                    malformed_findings_reminders += 1
                    self._append_findings_format_retry(content)
                    disable_tools_for_wrapup = True
                    continue
                if self._has_findings_block(content) and malformed_findings_reminders < 1:
                    malformed_findings_reminders += 1
                    self._append_findings_format_retry(content)
                    disable_tools_for_wrapup = True
                    continue

                if not response.tool_calls:
                    # True 0-content (no text, no tool calls). During candidate_generation
                    # with tools still available, force a tool call to keep searching
                    # rather than prematurely wrapping up with findings.
                    if phase == "candidate_generation" and not disable_tools_for_wrapup and missing_findings_reminders < 1:
                        missing_findings_reminders += 1
                        logger.info("[Executor] 0-content + no tool_calls → forcing tool call retry")
                        self._append_force_tool_call()
                        continue
                    if missing_findings_reminders < 1:
                        missing_findings_reminders += 1
                        self._append_findings_format_retry(content)
                        disable_tools_for_wrapup = True
                        continue
                    metadata.update({"finished_at": datetime.now().isoformat(), "status": "stopped_without_findings"})
                    return {"findings": None, "trajectory": self.messages, "metadata": metadata}

                tool_messages = self._execute_tool_calls_parallel(response.tool_calls, phase, subtask)
                self.messages.extend(tool_messages)
                self._micro_compact_tool_messages()

                # Crawl nudge / forced crawl: GLM-5.2 tends to keep searching
                # instead of crawling, leaving subtasks with crawls=0 (only
                # Serper snippets, no page content). A passive nudge message is
                # ignored. Instead, ONCE per subtask (after ~3 searches with
                # 0 crawls), directly execute visit_urls on the most promising
                # pending URLs and inject the result so the LLM has real page
                # content to extract candidates from.
                #
                # NOTE: We do NOT crawl periodically. Repeated crawl injections
                # (1) add latency that causes timeout/unfinished subtasks, and
                # (2) inject user messages that disrupt LLM conversation flow
                # and cause answer regressions. A single early crawl is enough
                # to give the LLM page content to work with.
                _pu_len = len(self.state_store.pending_urls) if self.state_store.pending_urls else 0
                logger.debug(f"[CrawlNudge] subtask_search={self._search_count} crawls={self._crawl_count} pending_urls={_pu_len} nudge_sent={self._crawl_nudge_sent} wrapup={disable_tools_for_wrapup}")
                if (
                    not disable_tools_for_wrapup
                    and not self._crawl_nudge_sent
                    and self._search_count >= 3
                    and self._crawl_count == 0
                    and self.state_store.pending_urls
                ):
                    self._crawl_nudge_sent = True
                    _nudge_urls = [u for u in list(self.state_store.pending_urls)[:2] if u]
                    if _nudge_urls:
                        try:
                            from tools.search_tools import visit_urls as _visit_urls_fn
                            _t_fc = time.time()
                            logger.warning(f"[ForcedCrawl] auto-crawling {len(_nudge_urls)} URLs: {_nudge_urls}")
                            _fc_results = _visit_urls_fn(_nudge_urls, self._current_question or "")
                            _fc_result = "\n".join(_fc_results) if isinstance(_fc_results, list) else str(_fc_results)
                            _fc_lat = (time.time() - _t_fc) * 1000.0
                            logger.warning(f"[ForcedCrawl] done in {_fc_lat/1000:.1f}s result_len={len(_fc_result)}")
                            with self._tool_lock:
                                self._crawl_count += 1
                                self._forced_crawl_count += 1
                                self.state_store.register_tool_observation(
                                    "visit_urls", {"urls": _nudge_urls}, _fc_result
                                )
                            if self._event_callback:
                                try:
                                    self._event_callback("visit_urls_executed", {
                                        "urls": _nudge_urls,
                                        "query": (self._current_question or "")[:120],
                                        "result_len": len(_fc_result),
                                        "phase": "forced_crawl",
                                        "subtask": subtask.get("text", "")[:120] if isinstance(subtask, dict) else str(subtask)[:120],
                                    })
                                except Exception:
                                    pass
                            _excerpt_chars = int(os.getenv("EXECUTOR_VISIT_URLS_EXCERPT_CHARS", "2000"))
                            self.messages.append({
                                "role": "user",
                                "content": (
                                    "You have performed several searches but have not yet visited any page. "
                                    "Search snippets are often incomplete and miss key details. "
                                    f"I have automatically fetched the page content for {_nudge_urls} so you can read it below. "
                                    "Use this page evidence to verify candidates and discover entities not visible in snippets. "
                                    f"Page content excerpt:\n{_fc_result[:_excerpt_chars]}"
                                ),
                            })
                        except Exception as _fc_e:
                            logger.error(f"[ForcedCrawl] failed: {_fc_e}")
                            # On failure, still mark as attempted to avoid retry storm
                            with self._tool_lock:
                                self._forced_crawl_count += 1
                            self.messages.append({
                                "role": "user",
                                "content": (
                                    "You have performed several searches but have not yet visited any page. "
                                    "Search snippets are often incomplete and miss key details. "
                                    f"Please call visit_urls on one of these promising URLs to read the actual page content: {_nudge_urls}. "
                                    "Page evidence is essential to verify candidates and discover entities not visible in snippets."
                                ),
                            })

                # After tool results, check if budget was exhausted — nudge agent to wrap up
                if self._budget_exhausted:
                    self.messages.append({
                        "role": "user",
                        "content": "Your search budget for this subtask is exhausted. Please organize all information you have gathered so far and output your findings in a <findings>...</findings> block. Do NOT make any more tool calls.",
                    })
                    self._budget_exhausted = False  # Only inject once
                    disable_tools_for_wrapup = True
                else:
                    # Authority-consensus early-stop: a candidate now has >=N
                    # independent authoritative sources backing it. Only on
                    # verification-type subtasks — expansion needs broad recall.
                    subtask_type = (subtask.get("subtask_type") or subtask.get("type")
                                    or subtask.get("mode") or "")
                    is_verify = "verif" in str(subtask_type).lower()
                    if is_verify:
                        consensus = self._consensus_candidate()
                        if consensus:
                            self._authority_consensus_done = True
                            cname = consensus["name"]
                            ckind = consensus["kind"]
                            ctrigger = ("authority_consensus_early_stop"
                                        if ckind == "authoritative_consensus"
                                        else "fact_confirmed_early_stop")
                            logger.info(
                                f"[Executor] {ckind}: candidate='{cname}' backed by "
                                f"{len(consensus['sources'])} {ckind} sources "
                                f"({consensus['sources']})"
                            )
                            try:
                                self._event_callback and self._event_callback(
                                    ctrigger,
                                    {"candidate": cname, "kind": ckind,
                                     "sources": consensus["sources"]},
                                )
                            except Exception:
                                pass
                            if ckind == "fact_confirmed":
                                wrap_msg = (
                                    f"A candidate ({cname}) is now backed by "
                                    f"{len(consensus['sources'])} or more independent "
                                    "high-weight sources (official site / official "
                                    "financial report / academic — weight 10). Two "
                                    "such sources agreeing establishes the fact. Stop "
                                    "searching and output your findings now in a "
                                    "<findings>...</findings> block. Do NOT make any "
                                    "more tool calls."
                                )
                            else:
                                wrap_msg = (
                                    f"A candidate ({cname}) is now backed by "
                                    f"{self._authority_min_sources} or more independent "
                                    "authoritative sources (official/academic/encyclopedia/"
                                    "tier-1 media). That is sufficient corroboration. "
                                    "Stop searching and output your findings now in a "
                                    "<findings>...</findings> block. Do NOT make any more "
                                    "tool calls."
                                )
                            self.messages.append({
                                "role": "user",
                                "content": wrap_msg,
                            })
                            disable_tools_for_wrapup = True
            except Exception as e:
                # P0-B: retry transient infra errors (network/service/rate-limit)
                # instead of aborting the whole subtask on a single API failure.
                # This prevents a correct candidate from being left under-verified
                # just because one LLM call hit a transient 500/timeout.
                _infra_type = classify_infra_error(e)
                _retryable = _infra_type in {"network_error", "service_error", "rate_limit"}
                _retry_attempts = int(os.getenv("EXECUTOR_INFRA_RETRY", "2"))
                if _retryable and getattr(self, "_infra_retry_count", 0) < _retry_attempts and turn < self.max_turns - 1:
                    self._infra_retry_count = getattr(self, "_infra_retry_count", 0) + 1
                    _backoff = min(2.0 ** self._infra_retry_count, 8.0)
                    logger.warning(
                        f"[Executor] transient infra error ({_infra_type}), "
                        f"retrying subtask turn after {_backoff:.1f}s backoff "
                        f"(attempt {self._infra_retry_count}/{_retry_attempts}): {e}"
                    )
                    time.sleep(_backoff)
                    continue
                logger.error(f"[Executor] Error in conversation loop: {e}")
                # 400 errors from invalid tool_call JSON: try to recover by
                # removing the last assistant message (which has bad tool_calls)
                # and asking the LLM to output findings directly instead of
                # crashing the subtask with empty findings.
                _err_str = str(e)
                if "400" in _err_str and ("valid JSON" in _err_str or "arguments" in _err_str):
                    logger.warning("[Executor] 400 invalid-JSON error; attempting recovery by removing bad assistant message")
                    # Remove last assistant message with tool_calls
                    for _i in range(len(self.messages) - 1, -1, -1):
                        _m = self.messages[_i]
                        if isinstance(_m, dict) and _m.get("role") == "assistant" and _m.get("tool_calls"):
                            self.messages.pop(_i)
                            # Also remove any trailing tool result messages for those call_ids
                            _bad_ids = set()
                            for _tc in (_m.get("tool_calls") or []):
                                if isinstance(_tc, dict):
                                    _bad_ids.add(_tc.get("id"))
                            while self.messages and isinstance(self.messages[-1], dict) \
                                    and self.messages[-1].get("role") == "tool" \
                                    and self.messages[-1].get("tool_call_id") in _bad_ids:
                                self.messages.pop()
                            break
                    # Inject a wrap-up request and retry the turn
                    self.messages.append({
                        "role": "user",
                        "content": (
                            "A previous tool call had malformed arguments and was removed. "
                            "Please output your findings now in a <findings>...</findings> block "
                            "with valid JSON. Include subtask, status, summary, evidence, "
                            "candidate_updates, source_feedback, and suggestion_for_planner. "
                            "Do NOT make any more tool calls."
                        ),
                    })
                    disable_tools_for_wrapup = True
                    continue
                metadata.update({"finished_at": datetime.now().isoformat(), "status": "error", "error": str(e)})
                return {"findings": None, "trajectory": self.messages, "metadata": metadata}

        # max_turns exhausted — inject wrap-up message and give one final turn
        self.messages.append({
            "role": "user",
                "content": (
                    "You have reached the maximum number of turns for this subtask. "
                    "Please organize all information you have gathered and output your findings now.\n\n"
                    "Output exactly one <findings>...</findings> block with valid JSON containing these fields:\n"
                    "- subtask: the subtask name\n"
                "- status: \"completed\" or \"partial\"\n"
                "- summary: what you found (be specific about names, dates, facts)\n"
                "- evidence: list of {source, fact} objects\n"
                "- candidate_updates: {\"new_candidates\": [...], \"eliminated_candidates\": [...], \"candidate_assessments\": [{\"name\": \"...\", \"status\": \"active|eliminated\", \"verification_status\": \"unverified|partial|verified|contradicted\", \"confidence\": \"low|medium|high\", \"supporting_constraints\": [...], \"unresolved_constraints\": [...], \"hard_conflicts\": [...], \"evidence\": [{\"source\": \"...\", \"observation\": \"...\"}]}]}\n"
                "- source_feedback: {\"promising_sources\": [...], \"unhelpful_sources\": [...]}\n"
                "- suggestion_for_planner: what the planner should do next\n\n"
                "Do NOT make any more tool calls."
            ),
        })
        try:
            _t_wrap = time.time()
            logger.info(f"[Executor] wrap-up LLM start (max_turns reached)")
            response = chat_completion_with_structuring(
                self.client,
                model_id=self.model_id,
                messages=self.messages,
                temperature=self.temperature,
                max_tokens=self.max_output_tokens,
                reasoning_effort_override=self.reasoning_effort,
                structurer_format_hint=(
                    "Output your findings in a <findings>...</findings> block with valid JSON."
                ),
            )
            logger.info(f"[Executor] wrap-up LLM done in {time.time()-_t_wrap:.1f}s")
            self.messages.append(assistant_message_to_dict(response))
            content = response.content or ""
            findings = self._extract_findings(content, allow_dsml_recovery=False)
            if findings is not None:
                findings = self._merge_candidate_tool_updates_into_findings(findings)
                metadata.update({"finished_at": datetime.now().isoformat(), "status": "completed"})
                return {"findings": findings, "trajectory": self.messages, "metadata": metadata}
            if content.strip():
                self._append_findings_format_retry(content)
                _t_retry = time.time()
                logger.info("[Executor] wrap-up LLM retry start (findings format)")
                response = chat_completion_with_structuring(
                    self.client,
                    model_id=self.model_id,
                    messages=self.messages,
                    temperature=self.temperature,
                    max_tokens=self.max_output_tokens,
                    reasoning_effort_override=self.reasoning_effort,
                    structurer_format_hint=(
                        "Output your findings in a <findings>...</findings> block with valid JSON."
                    ),
                )
                logger.info(f"[Executor] wrap-up LLM retry done in {time.time()-_t_retry:.1f}s")
                self.messages.append(assistant_message_to_dict(response))
                findings = self._extract_findings(response.content or "", allow_dsml_recovery=True)
                if findings is not None:
                    findings = self._merge_candidate_tool_updates_into_findings(findings)
                    metadata.update({"finished_at": datetime.now().isoformat(), "status": "completed"})
                    return {"findings": findings, "trajectory": self.messages, "metadata": metadata}
        except Exception:
            pass
        metadata.update({"finished_at": datetime.now().isoformat(), "status": "max_turns_reached"})
        return {"findings": None, "trajectory": self.messages, "metadata": metadata}

    def _execute_tool_calls_parallel(self, tool_calls: List[Any], phase: str, subtask: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute tool calls in parallel when 2+ calls are present, sequentially otherwise."""
        if not tool_calls:
            return []

        # Parse all tool calls upfront
        parsed = []
        for tool_call in tool_calls:
            func_name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments) if isinstance(tool_call.function.arguments, str) else tool_call.function.arguments
            except json.JSONDecodeError as e:
                parsed.append((tool_call.id, func_name, None, f"Error: invalid JSON arguments: {e}"))
                continue
            parsed.append((tool_call.id, func_name, arguments, None))

        # Single tool call or only error entries — sequential (no thread overhead)
        valid_calls = [p for p in parsed if p[2] is not None]
        if len(valid_calls) <= 1:
            tool_messages = []
            for call_id, func_name, arguments, err in parsed:
                if err is not None:
                    tool_messages.append({"role": "tool", "tool_call_id": call_id, "name": func_name, "content": err})
                    continue
                _t_tool = time.time()
                logger.info(f"[Executor] tool_call start: {func_name} args={json.dumps(arguments, ensure_ascii=False)[:120]}")
                result = self._execute_tool_with_controls(func_name, arguments, phase, subtask)
                logger.info(f"[Executor] tool_call done: {func_name} in {time.time()-_t_tool:.1f}s result_len={len(str(result))}")
                tool_messages.append({"role": "tool", "tool_call_id": call_id, "name": func_name, "content": str(result)})
            return tool_messages

        # Multiple valid tool calls — parallel execution
        max_workers = min(3, len(valid_calls))
        logger.info(f"[Executor] parallel tool execution: {len(valid_calls)} calls, {max_workers} workers")
        _t_par = time.time()

        # Map call_id -> index for ordered output
        ordered_ids = {p[0]: i for i, p in enumerate(parsed)}
        results: List[Optional[Dict[str, Any]]] = [None] * len(parsed)

        def _run_single(call_id: str, func_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            _t = time.time()
            logger.info(f"[Executor] tool_call start: {func_name} args={json.dumps(arguments, ensure_ascii=False)[:120]}")
            result = self._execute_tool_with_controls(func_name, arguments, phase, subtask)
            logger.info(f"[Executor] tool_call done: {func_name} in {time.time()-_t:.1f}s result_len={len(str(result))}")
            return {"role": "tool", "tool_call_id": call_id, "name": func_name, "content": str(result)}

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_id = {}
            for call_id, func_name, arguments, err in parsed:
                if err is not None:
                    results[ordered_ids[call_id]] = {"role": "tool", "tool_call_id": call_id, "name": func_name, "content": err}
                    continue
                future = pool.submit(_run_single, call_id, func_name, arguments)
                future_to_id[future] = call_id

            for future in as_completed(future_to_id):
                call_id = future_to_id[future]
                try:
                    results[ordered_ids[call_id]] = future.result()
                except Exception as e:
                    func_name = next(p[1] for p in parsed if p[0] == call_id)
                    logger.error(f"[Executor] tool_call {func_name} failed: {e}")
                    results[ordered_ids[call_id]] = {"role": "tool", "tool_call_id": call_id, "name": func_name, "content": f"Error: {e}"}

        logger.info(f"[Executor] parallel tools done in {time.time()-_t_par:.1f}s ({len(valid_calls)} calls)")
        return [r for r in results if r is not None]

    def _execute_tool_with_controls(self, func_name: str, arguments: Dict[str, Any], phase: str, subtask: Dict[str, Any]) -> Any:
        subtask_text = subtask.get("subtask") or subtask.get("name") or "unknown"
        if func_name == "add_candidates":
            return json.dumps(self._execute_add_candidates_tool(arguments), ensure_ascii=False)

        if func_name == "update_candidate":
            return json.dumps(self._execute_update_candidate_tool(arguments), ensure_ascii=False)

        if func_name == "search":
            raw_queries = arguments.get("query", []) or []
            if isinstance(raw_queries, str):
                queries = [raw_queries]
            elif isinstance(raw_queries, list):
                queries = raw_queries
            else:
                queries = []
            allowed_queries: List[str] = []
            critic_feedback: List[Dict[str, Any]] = []
            budget_hit = False
            # Phase 1: validate + budget check (no LLM). Collect queries that pass
            # so the critic can judge them together in ONE LLM call (batch).
            validated: List[str] = []  # cleaned, non-empty, in-budget queries
            for raw_query in queries:
                q = str(raw_query).strip()
                if not q:
                    critic_feedback.append({"query": raw_query, "verdict": "blocked", "reason": "Empty or invalid query."})
                    continue
                # Budget check under lock (atomic check-and-reserve)
                with self._tool_lock:
                    if self._search_count >= self.search_budget:
                        critic_feedback.append({"query": q, "verdict": "budget_exhausted", "reason": f"Per-subtask search budget reached ({self._search_count}/{self.search_budget})"})
                        budget_hit = True
                        continue
                validated.append(q)
            # Phase 2: batch QueryCritic evaluation (1 LLM call for all validated
            # queries). Previously this loop issued one LLM call per query.
            if not self.enable_query_critic:
                batch_verdicts: List[QueryVerdict] = [
                    QueryVerdict(decision="allow", reason="Query critic disabled.", checks={"query_critic_disabled": True})
                    for _ in validated
                ]
            else:
                try:
                    batch_verdicts = self.query_critic.batch_evaluate(
                        queries=validated,
                        phase=phase,
                        subtask=subtask_text,
                        question=getattr(self, '_current_question', ''),
                        use_llm=True,
                    )
                except Exception as e:
                    logger.warning(f"[Executor] batch QueryCritic error: {e}; failing open")
                    batch_verdicts = [
                        QueryVerdict(decision="allow", reason=f"Batch critic error ({e}), allowing query.", checks={})
                        for _ in validated
                    ]
            # Phase 3: apply verdicts to build allowed list + feedback.
            pivot_queries: List[str] = []  # accumulate alternative_queries from suggest_pivot
            for q, verdict in zip(validated, batch_verdicts):
                fb = verdict.to_dict()
                fb["query"] = q  # enrich trajectory feedback with the query string
                critic_feedback.append(fb)
                if verdict.is_allowed:
                    allowed_queries.append(q)
                elif verdict.decision == SUGGEST_PIVOT and verdict.alternative_queries:
                    # Use critic-suggested pivots instead of the rejected query
                    pivot_queries.extend(verdict.alternative_queries[:2])
            # If all queries were rejected but the critic suggested pivots,
            # use the pivots instead of blocking. This prevents dead-ends where
            # the executor keeps proposing the same failed pattern and the
            # critic blocks every search, ending the subtask with no results.
            if not allowed_queries and pivot_queries:
                # Dedupe while preserving order
                seen = set()
                for pq in pivot_queries:
                    nq = _normalize_query(pq)
                    if nq and nq not in seen:
                        seen.add(nq)
                        allowed_queries.append(pq)
                logger.info(f"[Executor] all queries rejected, using {len(allowed_queries)} pivot suggestions: {allowed_queries[:3]}")
            if budget_hit:
                with self._tool_lock:
                    self._budget_exhausted = True
            # Record per-query critic verdicts for trajectory
            if self._event_callback:
                for cf in critic_feedback:
                    try:
                        self._event_callback("search_query", {
                            "query": cf.get("query", ""),
                            "verdict": cf.get("verdict", cf.get("decision", "")),
                            "critic_reason": cf.get("reason", ""),
                            "phase": phase,
                            "subtask": subtask_text,
                        })
                    except Exception:
                        pass
            if not allowed_queries:
                return json.dumps({"blocked": True, "reason": "No queries passed critic/budget check.", "critic_feedback": critic_feedback}, ensure_ascii=False)
            new_args = {"query": allowed_queries}
            _t_search = time.time()
            logger.info(f"[Executor] search start: {len(allowed_queries)} queries: {allowed_queries[:3]}")
            result = self.tool_processor.tools[func_name](new_args)  # HTTP call — no lock
            _search_lat = (time.time() - _t_search) * 1000.0
            logger.info(f"[Executor] search done in {_search_lat/1000:.1f}s result_len={len(str(result))}")
            # State mutation under lock (fast, protects counters and memory)
            with self._tool_lock:
                self._search_count += len(allowed_queries)
                result_summary = self._summarize_tool_result(result)
                domains = self._extract_domains(result)
                urls = self._extract_urls(result)
                quality = self._infer_result_quality(result_summary, urls)
                for q in allowed_queries:
                    self.query_memory.record(
                        query=q,
                        phase=phase,
                        subtask=subtask_text,
                        results_summary=result_summary,
                        new_source_families=domains[:5],
                        new_candidates=[],
                        result_quality=quality,
                        led_to_crawl=False,
                        crawl_urls=[],
                        metadata={"critic_feedback": critic_feedback},
                    )
                self.state_store.register_tool_observation("search", new_args, result)
            # Record allowed searches with results for trajectory
            if self._event_callback:
                for q in allowed_queries:
                    try:
                        self._event_callback("search_executed", {
                            "query": q,
                            "verdict": "allow",
                            "result_count": len(urls),
                            "domains": domains[:5],
                            "latency_ms": _search_lat,
                            "phase": phase,
                            "subtask": subtask_text,
                        })
                    except Exception:
                        pass
            return json.dumps({"result": result, "critic_feedback": critic_feedback, "summary": result_summary}, ensure_ascii=False)

        if func_name == "visit_urls":
            from tools.search_tools import visit_urls
            # Controller evaluation — read state under lock (fast)
            with self._tool_lock:
                verdict = self.crawl_controller.evaluate(
                    phase=phase,
                    pending_urls=self.state_store.pending_urls,
                    current_candidates=self.state_store.current_candidates,
                    active_sources=self._current_source_recommendations(),
                    use_llm=False,
                )
                self.state_store.set_controller_signals(verdict.to_dict())
            urls = arguments.get("urls", []) or []
            query = arguments.get("query") or self._current_question or ""
            try:
                _t_crawl = time.time()
                logger.info(f"[Executor] visit_urls start: {len(urls)} urls, query='{query[:50]}'")
                results = visit_urls(urls, query)  # HTTP call — no lock
                logger.info(f"[Executor] visit_urls done in {time.time()-_t_crawl:.1f}s ({len(urls)} urls)")
                result = "\n".join(results)
            except Exception as e:
                logger.error(f"[Executor] visit_urls failed: {e}")
                result = f"Error visiting URLs: {e}"
            crawled_urls = urls
            # State mutation under lock
            with self._tool_lock:
                self._crawl_count += 1
                if self.query_memory.records:
                    self.query_memory.update_last_record(led_to_crawl=True, crawl_urls=crawled_urls)
                self.state_store.register_tool_observation("visit_urls", arguments, result)
            if self._event_callback:
                try:
                    self._event_callback("visit_urls_executed", {
                        "urls": crawled_urls,
                        "query": query[:120],
                        "result_len": len(result),
                        "phase": phase,
                        "subtask": subtask.get("text", "")[:120] if isinstance(subtask, dict) else str(subtask)[:120],
                    })
                except Exception:
                    pass
            # Return a compact excerpt (not the full page) in the tool message
            # to keep the conversation context small across turns. The full
            # content is already persisted in state_store above. The excerpt
            # is large enough for the LLM to extract evidence quotes without
            # re-sending 50K+ chars every turn until micro-compaction kicks in.
            _excerpt_chars = int(os.getenv("EXECUTOR_VISIT_URLS_EXCERPT_CHARS", "2000"))
            return json.dumps({"controller_verdict": verdict.to_dict(), "result_excerpt": result[:_excerpt_chars], "summary": self._summarize_tool_result(result)}, ensure_ascii=False)

        if func_name == "execute_code":
            result = self.tool_processor.tools[func_name](arguments)
            self.state_store.register_tool_observation("execute_code", arguments, result)
            return json.dumps({"result": result, "summary": self._summarize_tool_result(result)}, ensure_ascii=False)

        result = self.tool_processor.tools[func_name](arguments)
        self.state_store.register_tool_observation(func_name, arguments, result)
        return result

    def _micro_compact_tool_messages(self) -> None:
        tool_indices = [i for i, m in enumerate(self.messages) if isinstance(m, dict) and m.get("role") == "tool"]
        keep = 3
        if len(tool_indices) <= keep:
            return
        for idx in tool_indices[:-keep]:
            msg = self.messages[idx]
            content = str(msg.get("content", ""))
            if len(content) <= 500:
                continue
            msg["content"] = content[:500] + " ... [compacted older tool output]"

    def _summarize_tool_result(self, result: Any) -> str:
        text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        text = re.sub(r"\s+", " ", text)
        return text[:350]

    def _extract_urls(self, result: Any) -> List[str]:
        text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        return list(dict.fromkeys(re.findall(r"https?://[^\s\]\)\">]+", text)))

    def _extract_domains(self, result: Any) -> List[str]:
        domains: List[str] = []
        for u in self._extract_urls(result):
            try:
                d = urlparse(u).netloc.lower()
                if d and d not in domains:
                    domains.append(d)
            except Exception:
                pass
        return domains

    def _infer_result_quality(self, summary: str, urls: List[str]) -> str:
        lowered = summary.lower()
        if not urls and ("no results" in lowered or "not found" in lowered):
            return "empty"
        if len(urls) == 0:
            return "low"
        if len(urls) >= 3:
            return "high"
        return "medium"
