"""
Search-to-Crawl Controller

Monitors the search trajectory and determines when the agent should
transition from surface-level searching to page-level evidence gathering.

Models tend to over-use search and under-use crawl_urls, even when
promising URLs have already been found. This controller acts as a
balance mechanism to enforce deeper engagement with discovered sources.

Two-stage evaluation:
1. Fast rule-based signal aggregation (no LLM)
2. LLM-based judgment when signals are ambiguous

Output is a structured verdict with full reasoning.
"""

import json
import os
import re
from typing import Dict, List, Optional

from loguru import logger

from memory.query_history import QueryHistoryMemory

from llm.compat import build_chat_completion_kwargs, chat_completion_with_structuring
from llm.factory import build_openai_client
from core.config import settings


# Verdict constants
CONTINUE_SEARCH = "continue_search"
CRAWL_NOW = "crawl_now"
HYBRID = "hybrid"
PIVOT_SOURCE_FAMILY = "pivot_source_family"


class SearchCrawlVerdict:
    """Structured verdict from the search-to-crawl controller."""

    def __init__(
        self,
        decision: str,
        reason: str,
        signals: Optional[Dict] = None,
        recommended_urls: Optional[List[str]] = None,
        recommended_queries: Optional[List[str]] = None,
    ):
        """
        Args:
            decision: One of continue_search, crawl_now, hybrid, pivot_source_family.
            reason: Full reasoning explaining the decision.
            signals: Individual signal values for transparency.
            recommended_urls: If crawl_now/hybrid, specific URLs to crawl.
            recommended_queries: If continue_search/hybrid/pivot, suggested queries.
        """
        self.decision = decision
        self.reason = reason
        self.signals = signals or {}
        self.recommended_urls = recommended_urls or []
        self.recommended_queries = recommended_queries or []

    @property
    def should_crawl(self) -> bool:
        return self.decision in (CRAWL_NOW, HYBRID)

    @property
    def should_search(self) -> bool:
        return self.decision in (CONTINUE_SEARCH, HYBRID)

    def to_dict(self) -> Dict:
        d = {
            "decision": self.decision,
            "reason": self.reason,
            "signals": self.signals,
        }
        if self.recommended_urls:
            d["recommended_urls"] = self.recommended_urls
        if self.recommended_queries:
            d["recommended_queries"] = self.recommended_queries
        return d

    def __repr__(self):
        return f"SearchCrawlVerdict({self.decision}, reason='{self.reason[:80]}...')"


class SearchCrawlController:
    """
    Monitors search/crawl balance and advises on next action.

    Usage:
        controller = SearchCrawlController(memory, api_base, api_key, model_id)
        verdict = controller.evaluate(
            phase="candidate_narrowing",
            pending_urls=["https://en.wikipedia.org/wiki/Walther_Penck"],
            current_candidates=["Walther Penck"],
        )
        if verdict.should_crawl:
            # instruct agent to crawl recommended_urls
    """

    CONTROLLER_PROMPT = """You are a search-to-crawl balance controller. Your job is to evaluate the current search trajectory and determine whether the agent should continue searching or transition to crawling specific URLs.

You must output a JSON object with the following structure:

```json
{{
  "decision": "continue_search | crawl_now | hybrid | pivot_source_family",
  "reason": "Detailed explanation (2-4 sentences). Explain what signals you see, why the current balance is off (or appropriate), and what the agent should do next.",
  "search_exhaustion": "low | medium | high | critical",
  "url_readiness": "none | weak | strong",
  "candidate_stability": "unstable | emerging | stable",
  "phase_alignment": "aligned | misaligned",
  "recommended_urls": ["url1", "url2"],
  "recommended_queries": ["query1", "query2"]
}}
```

Decision criteria:
- **continue_search**: The agent still needs more surface-level exploration. URLs found so far are not promising enough, or no URLs have been found yet. New search directions may yield better sources.
- **crawl_now**: Promising URLs have been discovered but not yet crawled. The agent should stop searching and crawl these URLs immediately. Further searching at this point is wasting turns.
- **hybrid**: The agent should do both — one or two targeted searches alongside crawling the best URLs found so far. This is appropriate when partial information exists but some gaps remain.
- **pivot_source_family**: The current source family is not yielding results. The agent should switch to a fundamentally different source type (e.g., from general web to Wikipedia, from web to domain-specific databases).

Signal interpretation guidelines:
- **search_exhaustion**: How burnt out the current search direction is. "critical" means recent queries have all returned noise/empty. "low" means searches are still productive.
- **url_readiness**: How many promising, uncrawled URLs are available. "strong" means multiple high-relevance URLs found but not crawled. "none" means no URLs worth crawling.
- **candidate_stability**: How stable the current candidate set is. "stable" means the same candidates keep appearing across searches. "unstable" means every search surfaces different entities.
- **phase_alignment**: Whether the current search/crawl behavior matches the expected phase. In narrowing/verification phases, crawling should dominate. In source_identification, searching should dominate.

## Search History (recent {recent_count} queries)

{history}

## Current Context

Phase: {phase}
Pending URLs (found but not yet crawled): {pending_urls}
Current candidates: {current_candidates}
Current source families in use: {active_sources}

Evaluate and output JSON only (no markdown, no extra text)."""

    def __init__(
        self,
        memory: QueryHistoryMemory,
        api_base: str,
        api_key: str,
        model_id: Optional[str] = None,
        lookback: int = 10,
    ):
        """
        Args:
            memory: The query history memory to analyze.
            api_base: LLM API base URL.
            api_key: LLM API key.
            model_id: Model to use for LLM-based evaluation.
            lookback: Number of recent queries to consider for signal analysis.
        """
        self.memory = memory
        self.api_base = api_base
        self.api_key = api_key
        self.model_id = model_id or settings().model_id
        self.lookback = lookback

        self.client = build_openai_client(api_base, api_key)
        # P1: decision cache — key is (phase, n_candidates, n_pending_urls), value is verdict dict
        self._decision_cache: Dict[str, dict] = {}
        self._cache_max_size = 100

    def _decision_cache_key(
        self,
        phase: str,
        pending_urls: List[str],
        current_candidates: List[str],
    ) -> str:
        """Build cache key from phase + candidate count + url count (coarse-grained)."""
        return f"{phase}|c={len(current_candidates)}|u={len(pending_urls)}"

    def _lookup_decision_cache(self, key: str) -> Optional["SearchCrawlVerdict"]:
        entry = self._decision_cache.get(key)
        if entry is None:
            return None
        data = entry["verdict"]
        logger.info(f"[SearchCrawlController] Cache HIT: {data['decision']}")
        return SearchCrawlVerdict(
            decision=data["decision"],
            reason=f"[cached] {data['reason']}",
            signals={},
        )

    def _store_decision_cache(self, key: str, verdict: "SearchCrawlVerdict") -> None:
        if len(self._decision_cache) >= self._cache_max_size:
            keys = list(self._decision_cache.keys())
            for k in keys[: self._cache_max_size // 4]:
                self._decision_cache.pop(k, None)
        self._decision_cache[key] = {
            "verdict": {
                "decision": verdict.decision,
                "reason": verdict.reason,
            },
        }

    def evaluate(
        self,
        phase: str,
        pending_urls: Optional[List[str]] = None,
        current_candidates: Optional[List[str]] = None,
        active_sources: Optional[List[str]] = None,
        use_llm: bool = True,
    ) -> SearchCrawlVerdict:
        """
        Evaluate whether to continue searching or start crawling.

        Args:
            phase: Current planning phase.
            pending_urls: URLs that have been found but not yet crawled.
            current_candidates: Current candidate answers under consideration.
            active_sources: Source families currently being explored.
            use_llm: Whether to use LLM for deep analysis.

        Returns:
            SearchCrawlVerdict with decision and full reasoning.
        """
        pending_urls = pending_urls or []
        current_candidates = current_candidates or []
        active_sources = active_sources or []

        # P1: decision cache lookup (coarse-grained by phase + counts)
        cache_key = self._decision_cache_key(phase, pending_urls, current_candidates)
        cached = self._lookup_decision_cache(cache_key)
        if cached is not None:
            return cached

        signals = self._compute_signals(pending_urls, current_candidates, active_sources)

        # Stage 1: Rule-based check
        rule_verdict = self._rule_based_check(signals, pending_urls)
        if rule_verdict:
            rule_verdict.signals = signals
            logger.info(f"[SearchCrawlController] Rule-based verdict: {rule_verdict.decision}")
            self._store_decision_cache(cache_key, rule_verdict)
            return rule_verdict

        # Stage 2: LLM-based check (default OFF — P1 optimization: rules first)
        if not use_llm:
            v = SearchCrawlVerdict(
                decision=CONTINUE_SEARCH,
                reason="No rule triggers. LLM check skipped.",
                signals=signals,
            )
            self._store_decision_cache(cache_key, v)
            return v

        result = self._llm_based_check(phase, pending_urls, current_candidates, active_sources, signals)
        self._store_decision_cache(cache_key, result)
        return result

    def _compute_signals(
        self,
        pending_urls: List[str],
        current_candidates: List[str],
        active_sources: List[str],
    ) -> Dict:
        """Compute numeric/heuristic signals from history."""
        signals = {}
        recent = self.memory.records[-self.lookback:]

        # 1. Recent search yield
        if recent:
            quality_counts = {}
            for rec in recent:
                q = rec.result_quality
                quality_counts[q] = quality_counts.get(q, 0) + 1
            signals["recent_quality_distribution"] = quality_counts

            low_yield_count = sum(
                1 for rec in recent
                if rec.result_quality in ("empty", "noise", "low")
            )
            signals["low_yield_ratio"] = round(low_yield_count / len(recent), 2)
        else:
            signals["recent_quality_distribution"] = {}
            signals["low_yield_ratio"] = 0.0

        # 2. Pending URL count
        signals["pending_url_count"] = len(pending_urls)

        # 3. Recent crawl activity
        if recent:
            crawl_count = sum(1 for rec in recent if rec.led_to_crawl)
            signals["recent_crawl_count"] = crawl_count
            signals["recent_search_count"] = len(recent) - crawl_count
        else:
            signals["recent_crawl_count"] = 0
            signals["recent_search_count"] = 0

        # 4. Candidate count
        signals["candidate_count"] = len(current_candidates)

        # 5. Active source families
        signals["active_source_count"] = len(active_sources)
        signals["known_source_families"] = self.memory.source_families

        # 6. Total history size
        signals["total_queries"] = len(self.memory)

        return signals

    def _rule_based_check(
        self,
        signals: Dict,
        pending_urls: List[str],
    ) -> Optional[SearchCrawlVerdict]:
        """
        Fast rule-based checks.

        Returns SearchCrawlVerdict if a clear decision emerges, None otherwise.
        """
        # 1. No history at all — must search first
        if signals["total_queries"] == 0:
            return SearchCrawlVerdict(
                decision=CONTINUE_SEARCH,
                reason="No queries executed yet. Must search first to discover URLs and sources.",
                recommended_queries=None,
            )

        # 2. Promising URLs found but never crawled — force crawl
        if signals["pending_url_count"] >= 2 and signals["recent_crawl_count"] == 0:
            return SearchCrawlVerdict(
                decision=CRAWL_NOW,
                reason=(
                    f"{signals['pending_url_count']} pending URLs have been discovered "
                    f"but none have been crawled in the recent {self.lookback} actions. "
                    f"Surface-level searching is unlikely to yield better URLs than these. "
                    f"Crawl the pending URLs to gather page-level evidence."
                ),
                recommended_urls=pending_urls[:3],
            )

        # 3. Critical search exhaustion with pending URLs
        if (signals["low_yield_ratio"] >= 0.7
                and signals["pending_url_count"] >= 1
                and signals["total_queries"] >= 5):
            return SearchCrawlVerdict(
                decision=CRAWL_NOW,
                reason=(
                    f"Search exhaustion is critical: {signals['low_yield_ratio']:.0%} of recent queries "
                    f"returned empty/noise/low results. Meanwhile, {signals['pending_url_count']} "
                    f"pending URL(s) remain uncrawled. Stop searching and crawl what you have."
                ),
                recommended_urls=pending_urls[:3],
            )

        # 4. High search-to-crawl imbalance
        if (signals["recent_search_count"] >= 6
                and signals["recent_crawl_count"] <= 1
                and signals["pending_url_count"] >= 1):
            return SearchCrawlVerdict(
                decision=HYBRID,
                reason=(
                    f"Imbalanced trajectory: {signals['recent_search_count']} searches vs "
                    f"{signals['recent_crawl_count']} crawl(s) in recent actions. "
                    f"At least {signals['pending_url_count']} URL(s) are pending. "
                    f"Do one targeted search alongside crawling pending URLs."
                ),
                recommended_urls=pending_urls[:2],
            )

        # 5. All recent queries empty — pivot
        if (signals["low_yield_ratio"] == 1.0
                and len(signals.get("recent_quality_distribution", {})) >= 3
                and signals["pending_url_count"] == 0):
            return SearchCrawlVerdict(
                decision=PIVOT_SOURCE_FAMILY,
                reason=(
                    f"All recent {self.lookback} queries returned empty/noise results. "
                    f"No pending URLs available. The current source family and search "
                    f"approach are not working. Pivot to a different source type "
                    f"(e.g., Wikipedia, domain-specific databases)."
                ),
            )

        # P1: Extended rules — cover more cases to reduce LLM fallback
        # 6. Have candidates and pending URLs → hybrid (crawl + verify)
        if (signals.get("candidate_count", 0) >= 1
                and signals["pending_url_count"] >= 1
                and signals["recent_crawl_count"] >= 1):
            return SearchCrawlVerdict(
                decision=HYBRID,
                reason=(
                    f"{signals['candidate_count']} candidate(s) and {signals['pending_url_count']} "
                    f"pending URL(s). Continue searching while crawling to verify candidates."
                ),
                recommended_urls=pending_urls[:2],
            )

        # 7. Many candidates, no pending URLs — keep searching to narrow down
        if (signals.get("candidate_count", 0) >= 3
                and signals["pending_url_count"] == 0
                and signals["recent_search_count"] < 8):
            return SearchCrawlVerdict(
                decision=CONTINUE_SEARCH,
                reason=(
                    f"{signals['candidate_count']} candidates need narrowing. "
                    f"Search for distinguishing constraints."
                ),
            )

        # 8. Few queries and no pending URLs — keep searching
        if (signals["total_queries"] <= 3
                and signals["pending_url_count"] == 0):
            return SearchCrawlVerdict(
                decision=CONTINUE_SEARCH,
                reason="Early in search; keep gathering URLs and sources.",
            )

        # Rules inconclusive — defer to LLM
        return None

    def _llm_based_check(
        self,
        phase: str,
        pending_urls: List[str],
        current_candidates: List[str],
        active_sources: List[str],
        signals: Dict,
    ) -> SearchCrawlVerdict:
        """Use LLM to evaluate search/crawl balance."""
        recent = self.memory.records[-self.lookback:]
        history_lines = []
        for i, rec in enumerate(recent):
            crawl_note = ""
            if rec.led_to_crawl and rec.crawl_urls:
                crawl_note = f" → crawled: {rec.crawl_urls}"
            history_lines.append(
                f"  [{i}] query=\"{rec.query}\" | quality={rec.result_quality} | "
                f"new_sources={rec.new_source_families} | "
                f"new_candidates={rec.new_candidates}{crawl_note}"
            )

        history_text = "\n".join(history_lines) if history_lines else "(no recent queries)"

        prompt = self.CONTROLLER_PROMPT.format(
            recent_count=len(recent),
            history=history_text,
            phase=phase,
            pending_urls=pending_urls if pending_urls else "(none)",
            current_candidates=current_candidates if current_candidates else "(none)",
            active_sources=active_sources if active_sources else "(none)",
        )

        try:
            message = chat_completion_with_structuring(
                self.client,
                model_id=self.model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=1024,
                structurer_format_hint="Output the result as JSON.",
            )
            content = (getattr(message, "content", None) or "").strip()

            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if not json_match:
                logger.error(f"[SearchCrawlController] Failed to parse LLM response: {content[:200]}")
                return SearchCrawlVerdict(
                    decision=CONTINUE_SEARCH,
                    reason="Failed to parse LLM controller response. Defaulting to continue_search.",
                    signals=signals,
                )

            result = json.loads(json_match.group())

            decision = result.get("decision", CONTINUE_SEARCH)
            reason = result.get("reason", "")
            recommended_urls = result.get("recommended_urls", [])
            recommended_queries = result.get("recommended_queries", [])

            for key in ["search_exhaustion", "url_readiness", "candidate_stability", "phase_alignment"]:
                if key in result:
                    signals[key] = result[key]

            logger.info(f"[SearchCrawlController] LLM verdict: {decision}")

            return SearchCrawlVerdict(
                decision=decision,
                reason=reason,
                signals=signals,
                recommended_urls=recommended_urls,
                recommended_queries=recommended_queries,
            )

        except Exception as e:
            logger.error(f"[SearchCrawlController] LLM call failed: {e}")
            return SearchCrawlVerdict(
                decision=CONTINUE_SEARCH,
                reason=f"LLM controller call failed ({str(e)}). Defaulting to continue_search.",
                signals=signals,
            )


def create_search_crawl_controller(
    memory: QueryHistoryMemory,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    model_id: Optional[str] = None,
) -> SearchCrawlController:
    """Factory function to create a SearchCrawlController from environment variables."""
    from dotenv import load_dotenv
    load_dotenv()

    _api_base = api_base or os.getenv("OPENAI_BASE_URL")
    _api_key = api_key or os.getenv("OPENAI_API_KEY")
    _model_id = model_id or settings().model_id

    return SearchCrawlController(
        memory=memory,
        api_base=_api_base,
        api_key=_api_key,
        model_id=_model_id,
    )
