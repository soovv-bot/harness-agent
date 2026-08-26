"""
Query Critic

Evaluates a proposed search query against query history before execution.
Prevents redundant, low-value, or repetitive searches.

Two-stage evaluation:
1. Fast rule-based checks (literal duplicate, etc.) — no LLM needed
2. Deep semantic analysis via LLM when rules are inconclusive

Output is a structured verdict with full reasoning, not just a label.

Optimizations (2026-07):
- Semantic cache: similar query patterns reuse prior verdict (skip LLM)
- Batch evaluation: multiple queries judged in one LLM call
"""

import json
import os
import re
from typing import Dict, List, Optional, Tuple

from loguru import logger

from memory.query_history import QueryHistoryMemory, QueryRecord

from llm.compat import build_chat_completion_kwargs, chat_completion_with_structuring
from llm.factory import build_openai_client
from core.config import settings


# Verdict constants + QueryVerdict moved to the contract layer (RD §6);
# re-exported here so existing import paths keep working.
from contract.candidate import (
    ALLOW,
    ALLOW_WITH_WARNING,
    REJECT_AS_REDUNDANT,
    SUGGEST_PIVOT,
    QueryVerdict,
)


def _normalize_query(query: str) -> str:
    """Normalize a query for comparison."""
    return re.sub(r'\s+', ' ', query.strip().lower())


class QueryCritic:
    """
    Evaluates proposed search queries against history.

    Usage:
        critic = QueryCritic(memory, api_base, api_key, model_id)
        verdict = critic.evaluate(
            query="Albrecht Penck glacial studies Alps",
            phase="source_identification",
            subtask="Identify the European earth scientist",
        )
        if verdict.is_allowed:
            # proceed with search
        else:
            # handle rejection or pivot suggestion
    """

    CRITIC_PROMPT = """You are a search query critic. Evaluate whether a proposed search query is worth executing given the history of previous searches.

Output a JSON object with exactly two fields:
```json
{{"decision": "allow | allow_with_warning | reject_as_redundant | suggest_pivot", "reason": "..."}}
```

Decision criteria:
- **allow**: The query explores a genuinely new direction, new constraints, or new source families.
- **allow_with_warning**: The query has some overlap with history but introduces a meaningful variation.
- **reject_as_redundant**: The query is essentially a repeat of a previous search with no meaningful change.
- **suggest_pivot**: The query repeats the same failed pattern. A fundamentally different approach is needed. Include "alternative_queries" in the reason.

## Original Question

{question}

## Current Subtask

{subtask}

## Important: Multi-hop questions require cross-domain searches

The original question may span multiple domains (e.g., aviation, music, sports, geography). A query that shifts to a different domain from previous searches is **not** redundant — it may be a necessary step in a multi-hop reasoning chain. Do not reject a query simply because it explores a different topic than prior searches. Evaluate whether the query is relevant to the **current subtask** and the **original question**, not just whether it matches previous search topics.

## Important: Recall over precision in candidate generation

In the candidate_generation phase, prefer **allow** or **allow_with_warning** over **reject_as_redundant** when a query introduces any new entity name, constraint angle, or source type — even if it shares words with prior queries. Rejecting a query here means the correct answer may never be found. Only reject when a query is an exact or near-exact word-for-word repeat of a previous search.

## History

{history}

## Proposed Query

Query: {query}
Phase: {phase}

Evaluate and output JSON only (no markdown, no extra text)."""

    BATCH_CRITIC_PROMPT = """You are a search query critic. Evaluate a batch of proposed search queries against the history of previous searches. Judge EACH query independently.

Output a JSON array with exactly one object per query, IN THE SAME ORDER as the input queries. Each object has exactly two fields:
```json
[{{"decision": "allow | allow_with_warning | reject_as_redundant | suggest_pivot", "reason": "..."}}, ...]
```

Decision criteria (same as single-query):
- **allow**: The query explores a genuinely new direction, new constraints, or new source families.
- **allow_with_warning**: The query has some overlap with history but introduces a meaningful variation.
- **reject_as_redundant**: The query is essentially a repeat of a previous search with no meaningful change.
- **suggest_pivot**: The query repeats the same failed pattern. A fundamentally different approach is needed. Include "alternative_queries" in the reason.

## Important: Multi-hop questions require cross-domain searches

The original question may span multiple domains. A query that shifts to a different domain from previous searches is **not** redundant — it may be a necessary step in a multi-hop reasoning chain. Evaluate whether each query is relevant to the **current subtask** and the **original question**, not just whether it matches previous search topics.

## Important: Recall over precision in candidate generation

In the candidate_generation phase, the goal is to cast a wide net and discover as many plausible candidates as possible. Prefer **allow** or **allow_with_warning** over **reject_as_redundant** when a query introduces any new entity name, constraint angle, or source type — even if it shares words with prior queries. Rejecting a query here means the correct answer may never be found. Only reject when a query is an exact or near-exact word-for-word repeat of a previous search.

## Original Question

{question}

## Current Subtask

{subtask}

## History

{history}

## Proposed Queries (evaluate each, in order)

{queries_block}

Output a JSON array only (no markdown, no extra text). The array MUST have exactly {count} elements, one per query, in the input order."""

    def __init__(
        self,
        memory: QueryHistoryMemory,
        api_base: str,
        api_key: str,
        model_id: Optional[str] = None,
    ) -> None:
        self.memory = memory
        self.api_base = api_base
        self.api_key = api_key
        self.model_id = model_id or settings().model_id
        self.max_output_tokens = 1024

        self.client = build_openai_client(api_base, api_key)
        # P0: semantic cache — key is normalized query+phase, value is (verdict_dict, use_count)
        self._verdict_cache: Dict[str, dict] = {}
        self._cache_max_size = 200
        # P0: fuzzy cache threshold (Jaccard) — only rejective verdicts reused
        self.FUZZY_CACHE_JACCARD = 0.85
        # P1: early-reject threshold (Jaccard) — skip LLM for near-duplicates.
        # Raised from 0.75 to 0.80 to reduce false rejections of queries that
        # share common words but target different entities (improves recall).
        self.EARLY_REJECT_JACCARD = 0.80

    def _cache_key(self, query: str, phase: str) -> str:
        """Build a cache key from normalized query + phase."""
        return f"{phase}::{_normalize_query(query)[:200]}"

    def _lookup_cache(self, query: str, phase: str) -> Optional["QueryVerdict"]:
        """Return a cached verdict if available, updating use count."""
        key = self._cache_key(query, phase)
        entry = self._verdict_cache.get(key)
        if entry is None:
            return None
        entry["uses"] = entry.get("uses", 0) + 1
        data = entry["verdict"]
        logger.info(f"[QueryCritic] Cache HIT (uses={entry['uses']}): {data['decision']}")
        return QueryVerdict(
            decision=data["decision"],
            reason=f"[cached] {data['reason']}",
            alternative_queries=data.get("alternative_queries", []),
            checks={},
        )

    def _lookup_cache_fuzzy(self, query: str, phase: str) -> Optional["QueryVerdict"]:
        """P0: Fuzzy lookup — return a cached REJECTIVE verdict if Jaccard >= threshold.

        Only rejective verdicts (reject_as_redundant, suggest_pivot) are reused.
        Reusing an 'allow' verdict for a near-duplicate would incorrectly bypass
        the early-reject rule (P1) which may need to reject it.
        """
        query_words = set(_normalize_query(query).split())
        if not query_words:
            return None

        phase_prefix = f"{phase}::"
        best_entry = None
        best_jaccard = 0.0

        for key, entry in self._verdict_cache.items():
            if not key.startswith(phase_prefix):
                continue
            cached_decision = entry["verdict"]["decision"]
            if cached_decision not in (REJECT_AS_REDUNDANT, SUGGEST_PIVOT):
                continue
            cached_query_text = key[len(phase_prefix):]
            cached_words = set(cached_query_text.split())
            if not cached_words:
                continue
            jaccard = len(query_words & cached_words) / len(query_words | cached_words)
            if jaccard > best_jaccard:
                best_jaccard = jaccard
                best_entry = entry

        if best_entry is not None and best_jaccard >= self.FUZZY_CACHE_JACCARD:
            best_entry["uses"] = best_entry.get("uses", 0) + 1
            data = best_entry["verdict"]
            logger.info(
                f"[QueryCritic] Fuzzy cache HIT (jaccard={best_jaccard:.3f}, "
                f"uses={best_entry['uses']}): {data['decision']}"
            )
            return QueryVerdict(
                decision=data["decision"],
                reason=f"[cached-fuzzy jaccard={best_jaccard:.3f}] {data['reason']}",
                alternative_queries=data.get("alternative_queries", []),
                checks={},
            )
        return None

    def _store_cache(self, query: str, phase: str, verdict: "QueryVerdict") -> None:
        """Store a verdict in the cache (if allowed-ish). Evict if too large."""
        if len(self._verdict_cache) >= self._cache_max_size:
            # Evict oldest 25% by insertion order (FIFO-ish)
            keys = list(self._verdict_cache.keys())
            for k in keys[: self._cache_max_size // 4]:
                self._verdict_cache.pop(k, None)
        key = self._cache_key(query, phase)
        self._verdict_cache[key] = {
            "verdict": {
                "decision": verdict.decision,
                "reason": verdict.reason,
                "alternative_queries": verdict.alternative_queries,
            },
            "uses": 0,
        }

    def evaluate(
        self,
        query: str,
        phase: str,
        subtask: str,
        question: str = "",
        use_llm: bool = True,
    ) -> QueryVerdict:
        """
        Evaluate a proposed search query.

        Args:
            query: The proposed search query.
            phase: Current planning phase.
            subtask: Current subtask description.
            question: The original search question (for cross-domain awareness).
            use_llm: Whether to use LLM for deep analysis (default True).

        Returns:
            QueryVerdict with decision and full reasoning.
        """
        self._current_question = question
        checks = {}

        # P0: exact cache lookup (before rules + LLM)
        cached = self._lookup_cache(query, phase)
        if cached is not None:
            return cached

        # P0: fuzzy cache lookup (only returns rejective verdicts)
        cached_fuzzy = self._lookup_cache_fuzzy(query, phase)
        if cached_fuzzy is not None:
            return cached_fuzzy

        # Stage 1: Fast rule-based checks
        rule_verdict = self._rule_based_check(query, checks)
        if rule_verdict:
            rule_verdict.checks = checks
            logger.info(f"[QueryCritic] Rule-based verdict: {rule_verdict.decision}")
            self._store_cache(query, phase, rule_verdict)
            return rule_verdict

        # Stage 2: LLM-based deep analysis
        if not use_llm:
            v = QueryVerdict(
                decision=ALLOW,
                reason="No rule violations detected. LLM check skipped.",
                checks=checks,
            )
            self._store_cache(query, phase, v)
            return v

        result = self._llm_based_check(query, phase, subtask, checks)
        self._store_cache(query, phase, result)
        return result

    def batch_evaluate(
        self,
        queries: List[str],
        phase: str,
        subtask: str,
        question: str = "",
        use_llm: bool = True,
    ) -> List[QueryVerdict]:
        """Evaluate multiple proposed queries in one batch.

        Fast paths (exact cache, fuzzy cache, rule-based) run per-query with NO
        LLM. Only the queries that remain undecided after the fast paths are sent
        to the LLM together in a SINGLE call. Verdicts are returned in the same
        order as the input queries.

        This collapses N sequential LLM calls into (at most) one, which is the
        main latency win: a single ``search`` tool call with N queries previously
        issued N critic LLM round-trips.

        Args:
            queries: List of proposed search queries (any order preserved).
            phase: Current planning phase.
            subtask: Current subtask description.
            question: The original search question (for cross-domain awareness).
            use_llm: Whether to use LLM for the undecided queries (default True).

        Returns:
            List of QueryVerdict aligned 1:1 with the input ``queries``.
        """
        self._current_question = question
        verdicts: List[Optional[QueryVerdict]] = [None] * len(queries)
        needs_llm: List[Tuple[int, str]] = []  # (original index, query)

        # Phase 1: per-query fast paths (cache + rules) — no LLM, parallel-safe.
        for i, raw in enumerate(queries):
            q = str(raw).strip()
            if not q:
                verdicts[i] = QueryVerdict(
                    decision=REJECT_AS_REDUNDANT,
                    reason="Empty query.",
                    checks={"empty": True},
                )
                continue

            cached = self._lookup_cache(q, phase)
            if cached is not None:
                verdicts[i] = cached
                continue

            cached_fuzzy = self._lookup_cache_fuzzy(q, phase)
            if cached_fuzzy is not None:
                verdicts[i] = cached_fuzzy
                continue

            checks: Dict[str, any] = {}
            rule_verdict = self._rule_based_check(q, checks)
            if rule_verdict is not None:
                rule_verdict.checks = checks
                logger.info(f"[QueryCritic] batch rule verdict[{i}]: {rule_verdict.decision}")
                self._store_cache(q, phase, rule_verdict)
                verdicts[i] = rule_verdict
                continue

            if not use_llm:
                v = QueryVerdict(
                    decision=ALLOW,
                    reason="No rule violations detected. LLM check skipped.",
                    checks=checks,
                )
                self._store_cache(q, phase, v)
                verdicts[i] = v
            else:
                needs_llm.append((i, q))

        # Phase 2: a single LLM call for all undecided queries.
        if needs_llm:
            llm_verdicts = self._llm_batch_check(
                queries=[q for _, q in needs_llm],
                phase=phase,
                subtask=subtask,
            )
            for (i, q), v in zip(needs_llm, llm_verdicts):
                self._store_cache(q, phase, v)
                verdicts[i] = v

        # Defensive: every slot must be filled.
        return [v if v is not None else QueryVerdict(
            decision=ALLOW_WITH_WARNING,
            reason="Batch slot unfilled (defensive default).",
            checks={},
        ) for v in verdicts]

    def _llm_batch_check(
        self,
        queries: List[str],
        phase: str,
        subtask: str,
    ) -> List[QueryVerdict]:
        """Use ONE LLM call to evaluate a batch of queries against history.

        Returns a list of QueryVerdict aligned 1:1 with ``queries``. On any
        parse/transport failure the whole batch degrades gracefully to
        ``ALLOW_WITH_WARNING`` (fail-open, like the single-query path).
        """
        if not queries:
            return []

        recent_records = self.memory.records[-20:]
        history_lines = []
        for rec in recent_records:
            history_lines.append(
                f"- Query: \"{rec.query}\" | Phase: {rec.phase} | "
                f"Quality: {rec.result_quality} | "
                f"New sources: {rec.new_source_families} | "
                f"New candidates: {rec.new_candidates} | "
                f"Led to crawl: {rec.led_to_crawl}"
            )
        history_text = "\n".join(history_lines) if history_lines else "(no previous queries)"

        queries_block = "\n".join(
            f"{idx + 1}. \"{q}\""
            for idx, q in enumerate(queries)
        )

        prompt = self.BATCH_CRITIC_PROMPT.format(
            question=getattr(self, "_current_question", ""),
            subtask=subtask,
            history=history_text,
            queries_block=queries_block,
            count=len(queries),
        )

        try:
            message = chat_completion_with_structuring(
                self.client,
                model_id=self.model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=self.max_output_tokens,
                structurer_format_hint="Output the result as a JSON array.",
            )
            content = (getattr(message, "content", None) or "").strip()

            # Parse JSON array — tolerate markdown code fences.
            array_match = re.search(r'\[.*\]', content, re.DOTALL)
            if not array_match:
                logger.error(
                    f"[QueryCritic] batch LLM returned no JSON array: {content[:200]}"
                )
                return [QueryVerdict(
                    decision=ALLOW_WITH_WARNING,
                    reason="Failed to parse batch LLM response. Allowing with warning.",
                    checks={},
                ) for _ in queries]

            parsed = json.loads(array_match.group())
            if not isinstance(parsed, list):
                raise ValueError("batch LLM response was not a JSON array")

            # Align to input order by index. If count mismatch, fail-open the extras.
            results: List[QueryVerdict] = []
            for idx, q in enumerate(queries):
                entry = parsed[idx] if idx < len(parsed) and isinstance(parsed[idx], dict) else {}
                decision = entry.get("decision", ALLOW_WITH_WARNING)
                reason = entry.get("reason", "")
                alternative_queries = entry.get("alternative_queries", []) or []
                # Coerce unknown decisions to a safe allow-with-warning.
                if decision not in (ALLOW, ALLOW_WITH_WARNING, REJECT_AS_REDUNDANT, SUGGEST_PIVOT):
                    decision = ALLOW_WITH_WARNING
                    reason = f"[coerced] {reason}"
                logger.info(f"[QueryCritic] batch LLM verdict[{idx}] '{q[:40]}': {decision}")
                results.append(QueryVerdict(
                    decision=decision,
                    reason=reason,
                    alternative_queries=alternative_queries,
                    checks={"batch": True},
                ))
            return results

        except Exception as e:
            logger.error(f"[QueryCritic] batch LLM call failed: {e}")
            return [QueryVerdict(
                decision=ALLOW_WITH_WARNING,
                reason=f"Batch LLM critic call failed ({str(e)}). Allowing with warning.",
                checks={},
            ) for _ in queries]

    def _rule_based_check(
        self,
        query: str,
        checks: Dict,
    ) -> Optional[QueryVerdict]:
        """
        Fast checks that don't require LLM.

        Returns QueryVerdict if a definitive decision can be made, None otherwise.
        """
        normalized = _normalize_query(query)
        checks["history_size"] = len(self.memory)

        # 1. Literal duplicate
        if normalized in self.memory._query_texts:
            checks["literal_duplicate"] = True
            # Find the original record
            for rec in self.memory.records:
                if _normalize_query(rec.query) == normalized:
                    checks["duplicate_quality"] = rec.result_quality
                    break

            reason = (
                f"Exact duplicate of a previous query. "
                f"The same query was already executed with quality='{checks.get('duplicate_quality', 'unknown')}'. "
                f"Repeating it is unlikely to yield different results."
            )
            return QueryVerdict(
                decision=REJECT_AS_REDUNDANT,
                reason=reason,
                checks=checks,
            )

        checks["literal_duplicate"] = False

        # 2. Near-duplicate handling intentionally relaxed.
        # Keep overlap metadata for transparency, but defer the actual
        # similarity judgment to the LLM critic.
        query_words = set(normalized.split())
        best_jaccard = 0.0
        best_match = None
        for rec in self.memory.records:
            rec_words = set(_normalize_query(rec.query).split())
            if not query_words or not rec_words:
                continue

            overlap = query_words & rec_words
            union = query_words | rec_words
            jaccard = len(overlap) / len(union) if union else 0
            if jaccard > best_jaccard:
                best_jaccard = jaccard
                best_match = rec.query

        if best_match is not None:
            checks["nearest_query_overlap_of"] = best_match
            checks["nearest_query_overlap_jaccard"] = round(best_jaccard, 3)

        # P1: early-reject — if very similar to a prior query, skip LLM
        if best_jaccard >= self.EARLY_REJECT_JACCARD:
            checks["early_reject_jaccard"] = round(best_jaccard, 3)
            reason = (
                f"Query is {round(best_jaccard * 100)}% similar to a previous query "
                f"(\"{checks.get('nearest_query_overlap_of', '?')}\"). "
                f"Repeating a near-duplicate search is unlikely to yield new information."
            )
            return QueryVerdict(
                decision=REJECT_AS_REDUNDANT,
                reason=reason,
                checks=checks,
            )

        # 3. No history yet — always allow
        if len(self.memory) == 0:
            checks["no_history"] = True
            return QueryVerdict(
                decision=ALLOW,
                reason="No prior query history. First query is always allowed.",
                checks=checks,
            )

        # Rules inconclusive — defer to LLM
        return None

    def _llm_based_check(
        self,
        query: str,
        phase: str,
        subtask: str,
        checks: Dict,
    ) -> QueryVerdict:
        """Use LLM to evaluate query against history."""
        # Build history summary for the prompt
        recent_records = self.memory.records[-20:]  # Last 20 records for context
        history_lines = []
        for rec in recent_records:
            history_lines.append(
                f"- Query: \"{rec.query}\" | Phase: {rec.phase} | "
                f"Quality: {rec.result_quality} | "
                f"New sources: {rec.new_source_families} | "
                f"New candidates: {rec.new_candidates} | "
                f"Led to crawl: {rec.led_to_crawl}"
            )

        if not history_lines:
            history_text = "(no previous queries)"
        else:
            history_text = "\n".join(history_lines)

        question = getattr(self, '_current_question', '')

        prompt = self.CRITIC_PROMPT.format(
            question=question,
            subtask=subtask,
            history=history_text,
            query=query,
            phase=phase,
        )

        try:
            message = chat_completion_with_structuring(
                self.client,
                model_id=self.model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=self.max_output_tokens,
                structurer_format_hint="Output the result as JSON.",
            )
            content = (getattr(message, "content", None) or "").strip()

            # Parse JSON — handle potential markdown wrapping
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if not json_match:
                logger.error(f"[QueryCritic] Failed to parse LLM response: {content[:200]}")
                return QueryVerdict(
                    decision=ALLOW_WITH_WARNING,
                    reason="Failed to parse LLM critic response. Allowing with warning.",
                    checks=checks,
                )

            result = json.loads(json_match.group())

            decision = result.get("decision", ALLOW)
            reason = result.get("reason", "")
            alternative_queries = result.get("alternative_queries", [])

            logger.info(f"[QueryCritic] LLM verdict: {decision}")

            return QueryVerdict(
                decision=decision,
                reason=reason,
                alternative_queries=alternative_queries,
                checks=checks,
            )

        except Exception as e:
            logger.error(f"[QueryCritic] LLM call failed: {e}")
            return QueryVerdict(
                decision=ALLOW_WITH_WARNING,
                reason=f"LLM critic call failed ({str(e)}). Allowing with warning.",
                checks=checks,
            )


def create_query_critic(
    memory: QueryHistoryMemory,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    model_id: Optional[str] = None,
) -> QueryCritic:
    """Factory function to create a QueryCritic from environment variables."""
    from dotenv import load_dotenv
    load_dotenv()

    _api_base = api_base or os.getenv("OPENAI_BASE_URL")
    _api_key = api_key or os.getenv("OPENAI_API_KEY")
    _model_id = model_id or settings().model_id

    return QueryCritic(
        memory=memory,
        api_base=_api_base,
        api_key=_api_key,
        model_id=_model_id,
    )
