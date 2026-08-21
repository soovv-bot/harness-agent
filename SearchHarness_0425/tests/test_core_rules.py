"""
Unit tests for SearchHarness core logic (pure functions + rules).

Run: pytest tests/test_core_rules.py -v

Covers:
- query_critic._normalize_query (pure)
- QueryCritic._rule_based_check (literal duplicate, empty history, jaccard)
- search_crawl_controller._compute_signals (signal extraction)
- SearchCrawlController._rule_based_check (rule coverage)
- config.settings (env loading)
- llm_client._is_retryable (error classification)
"""

from __future__ import annotations

import pytest

from query_critic import _normalize_query, QueryCritic, QueryVerdict  # noqa: E402
from query_history import QueryHistoryMemory  # noqa: E402
from search_crawl_controller import SearchCrawlController  # noqa: E402
from config import settings  # noqa: E402
from llm.client import _is_retryable  # noqa: E402


# ---------------------------------------------------------------------------
# _normalize_query (pure function)
# ---------------------------------------------------------------------------

class TestNormalizeQuery:
    def test_lowercases(self):
        assert _normalize_query("Hello World") == "hello world"

    def test_collapses_whitespace(self):
        assert _normalize_query("  hello   world  ") == "hello world"

    def test_strips_punctuation_boundary(self):
        assert _normalize_query("\t foo  bar \n") == "foo bar"

    def test_empty_string(self):
        assert _normalize_query("") == ""

    def test_idempotent(self):
        once = _normalize_query("Mixed   CASE  Query")
        twice = _normalize_query(once)
        assert once == twice


# ---------------------------------------------------------------------------
# QueryCritic._rule_based_check
# ---------------------------------------------------------------------------

class TestQueryCriticRules:
    def _make_critic(self, memory: QueryHistoryMemory) -> QueryCritic:
        return QueryCritic(memory=memory, api_base="", api_key="", model_id="test-model")

    def _record(self, mem, query, quality="medium"):
        return mem.record(query=query, phase="discover", subtask="test", result_quality=quality)

    def test_empty_history_allows_first_query(self):
        mem = QueryHistoryMemory()
        critic = self._make_critic(mem)
        checks: dict = {}
        verdict = critic._rule_based_check("any query", checks)
        assert verdict is not None
        assert verdict.decision == "allow"
        assert checks.get("no_history") is True

    def test_literal_duplicate_rejected(self):
        mem = QueryHistoryMemory()
        self._record(mem, "custer death site", "medium")
        critic = self._make_critic(mem)
        checks: dict = {}
        verdict = critic._rule_based_check("Custer Death Site", checks)
        assert verdict is not None
        assert verdict.decision == "reject_as_redundant"
        assert checks.get("literal_duplicate") is True

    def test_case_insensitive_duplicate(self):
        mem = QueryHistoryMemory()
        self._record(mem, "Custer", "high")
        critic = self._make_critic(mem)
        checks: dict = {}
        verdict = critic._rule_based_check("CUSTER", checks)
        assert verdict is not None
        assert verdict.decision == "reject_as_redundant"

    def test_distinct_query_returns_none(self):
        mem = QueryHistoryMemory()
        self._record(mem, "george armstrong custer biography", "medium")
        critic = self._make_critic(mem)
        checks: dict = {}
        verdict = critic._rule_based_check("little bighorn battle casualties", checks)
        assert verdict is None
        assert checks.get("literal_duplicate") is False

    def test_jaccard_metadata_recorded(self):
        mem = QueryHistoryMemory()
        self._record(mem, "custer death site dakota", "low")
        critic = self._make_critic(mem)
        checks: dict = {}
        critic._rule_based_check("custer death site montana", checks)
        assert "nearest_query_overlap_jaccard" in checks
        assert 0 < checks["nearest_query_overlap_jaccard"] <= 1.0

    def test_p1_early_reject_high_jaccard(self):
        """P1: jaccard >= 0.75 should reject without LLM."""
        mem = QueryHistoryMemory()
        self._record(mem, "george armstrong custer death site", "medium")
        critic = self._make_critic(mem)
        checks: dict = {}
        # 5 words, 4 overlap → jaccard = 4/6 = 0.667 (below threshold)
        verdict_low = critic._rule_based_check("george armstrong custer death monument", checks)
        assert verdict_low is None  # defer to LLM
        # 5 words, 5 overlap → jaccard = 5/5 = 1.0 (exact, but not literal dup due to word order?)
        # Actually exact same words → literal duplicate. Use near-dup instead:
        # "custer death site dakota" vs "custer death site montana" = 4 words, 3 overlap, jaccard=0.6
        # Need higher: use 4 shared + 1 different
        mem2 = QueryHistoryMemory()
        self._record(mem2, "custer death site battle", "medium")
        critic2 = self._make_critic(mem2)
        checks2: dict = {}
        # {custer, death, site, battle} vs {custer, death, site, monument} = 3/5 = 0.6
        # Try: {a, b, c, d} vs {a, b, c, d, e} = 4/5 = 0.8 >= 0.75
        mem3 = QueryHistoryMemory()
        self._record(mem3, "alpha beta gamma delta", "medium")
        critic3 = self._make_critic(mem3)
        checks3: dict = {}
        verdict = critic3._rule_based_check("alpha beta gamma delta epsilon", checks3)
        assert verdict is not None
        assert verdict.decision == "reject_as_redundant"
        assert checks3.get("early_reject_jaccard") is not None
        assert checks3["early_reject_jaccard"] >= 0.75


# ---------------------------------------------------------------------------
# QueryCritic semantic cache (P0 optimization)
# ---------------------------------------------------------------------------

class TestQueryCriticCache:
    def test_cache_key_normalizes_whitespace(self):
        mem = QueryHistoryMemory()
        critic = QueryCritic(mem, "", "", "test-model")
        k1 = critic._cache_key("hello  world", "discover")
        k2 = critic._cache_key("hello world", "discover")
        assert k1 == k2

    def test_cache_key_differs_by_phase(self):
        mem = QueryHistoryMemory()
        critic = QueryCritic(mem, "", "", "test-model")
        assert critic._cache_key("query", "discover") != critic._cache_key("query", "verify")

    def test_store_then_lookup_hits(self):
        mem = QueryHistoryMemory()
        critic = QueryCritic(mem, "", "", "test-model")
        v = QueryVerdict(decision="allow", reason="test", alternative_queries=[], checks={})
        critic._store_cache("test query", "discover", v)
        hit = critic._lookup_cache("test query", "discover")
        assert hit is not None
        assert hit.decision == "allow"
        assert hit.reason.startswith("[cached]")

    def test_lookup_miss_returns_none(self):
        mem = QueryHistoryMemory()
        critic = QueryCritic(mem, "", "", "test-model")
        assert critic._lookup_cache("nonexistent", "discover") is None


# ---------------------------------------------------------------------------
# QueryCritic fuzzy cache (P0 fix)
# ---------------------------------------------------------------------------

class TestQueryCriticFuzzyCache:
    def _make_critic(self, memory: QueryHistoryMemory = None) -> QueryCritic:
        return QueryCritic(memory=memory or QueryHistoryMemory(), api_base="", api_key="", model_id="test-model")

    def test_fuzzy_hit_rejective_verdict(self):
        """Fuzzy cache returns rejective verdict when jaccard >= threshold."""
        critic = self._make_critic()
        v = QueryVerdict(decision="reject_as_redundant", reason="dup", checks={})
        # 6 shared words, 7 union → jaccard = 6/7 = 0.857 >= 0.85
        critic._store_cache("alpha beta gamma delta epsilon zeta", "discover", v)
        hit = critic._lookup_cache_fuzzy("alpha beta gamma delta epsilon zeta theta", "discover")
        assert hit is not None
        assert hit.decision == "reject_as_redundant"
        assert "cached-fuzzy" in hit.reason

    def test_fuzzy_miss_low_jaccard(self):
        """Fuzzy cache returns None when jaccard < threshold."""
        critic = self._make_critic()
        v = QueryVerdict(decision="reject_as_redundant", reason="dup", checks={})
        critic._store_cache("alpha beta gamma", "discover", v)
        # jaccard = 1/5 = 0.2
        hit = critic._lookup_cache_fuzzy("alpha delta epsilon zeta", "discover")
        assert hit is None

    def test_fuzzy_ignores_allow_verdicts(self):
        """Fuzzy cache does NOT return 'allow' verdicts (would bypass early-reject)."""
        critic = self._make_critic()
        v = QueryVerdict(decision="allow", reason="ok", checks={})
        critic._store_cache("alpha beta gamma delta epsilon zeta", "discover", v)
        # Near-duplicate of an 'allow' verdict should NOT be fuzzy-matched
        hit = critic._lookup_cache_fuzzy("alpha beta gamma delta epsilon eta", "discover")
        assert hit is None

    def test_fuzzy_respects_phase_boundary(self):
        """Fuzzy cache only matches within the same phase."""
        critic = self._make_critic()
        v = QueryVerdict(decision="reject_as_redundant", reason="dup", checks={})
        critic._store_cache("alpha beta gamma delta epsilon zeta", "discover", v)
        hit = critic._lookup_cache_fuzzy("alpha beta gamma delta epsilon eta", "verify")
        assert hit is None


# ---------------------------------------------------------------------------
# SearchCrawlController._compute_signals
# ---------------------------------------------------------------------------

class TestCrawlControllerSignals:
    def _make_controller(self, memory: QueryHistoryMemory) -> SearchCrawlController:
        return SearchCrawlController(memory=memory, api_base="", api_key="", model_id="test-model")

    def _record(self, mem, query, quality="medium"):
        return mem.record(query=query, phase="discover", subtask="test", result_quality=quality)

    def test_empty_history_signals(self):
        mem = QueryHistoryMemory()
        ctrl = self._make_controller(mem)
        signals = ctrl._compute_signals([], [], [])
        assert signals["total_queries"] == 0
        assert signals["pending_url_count"] == 0
        assert signals["candidate_count"] == 0
        assert signals["active_source_count"] == 0

    def test_candidate_and_url_counts(self):
        mem = QueryHistoryMemory()
        self._record(mem, "test", "medium")
        ctrl = self._make_controller(mem)
        signals = ctrl._compute_signals(
            pending_urls=["http://a.com", "http://b.com"],
            current_candidates=["Custer", "Sitting Bull"],
            active_sources=["wikipedia"],
        )
        assert signals["pending_url_count"] == 2
        assert signals["candidate_count"] == 2
        assert signals["active_source_count"] == 1


# ---------------------------------------------------------------------------
# SearchCrawlController._rule_based_check (extended P1 rules)
# ---------------------------------------------------------------------------

class TestCrawlControllerRules:
    def _make_controller(self, memory: QueryHistoryMemory) -> SearchCrawlController:
        return SearchCrawlController(memory=memory, api_base="", api_key="", model_id="test-model")

    def _record(self, mem, query, quality="medium"):
        return mem.record(query=query, phase="discover", subtask="test", result_quality=quality)

    def test_no_history_must_search(self):
        mem = QueryHistoryMemory()
        ctrl = self._make_controller(mem)
        signals = ctrl._compute_signals([], [], [])
        verdict = ctrl._rule_based_check(signals, [])
        assert verdict is not None
        assert verdict.decision == "continue_search"

    def test_pending_urls_never_crawled_force_crawl(self):
        mem = QueryHistoryMemory()
        self._record(mem, "custer", "medium")
        ctrl = self._make_controller(mem)
        signals = ctrl._compute_signals(
            pending_urls=["http://a.com", "http://b.com"],
            current_candidates=[],
            active_sources=[],
        )
        verdict = ctrl._rule_based_check(signals, ["http://a.com", "http://b.com"])
        assert verdict is not None
        assert verdict.decision == "crawl_now"

    def test_few_queries_no_pending_continue_search(self):
        mem = QueryHistoryMemory()
        self._record(mem, "q1", "medium")
        ctrl = self._make_controller(mem)
        signals = ctrl._compute_signals([], [], [])
        verdict = ctrl._rule_based_check(signals, [])
        assert verdict is not None
        assert verdict.decision == "continue_search"


# ---------------------------------------------------------------------------
# SearchCrawlController decision cache (P1 optimization)
# ---------------------------------------------------------------------------

class TestCrawlControllerCache:
    def test_decision_cache_key_buckets_by_counts(self):
        mem = QueryHistoryMemory()
        ctrl = SearchCrawlController(mem, "", "", "test-model")
        k1 = ctrl._decision_cache_key("discover", ["u1", "u2"], ["c1"])
        k2 = ctrl._decision_cache_key("discover", ["u3", "u4"], ["c2"])
        assert k1 == k2

    def test_decision_cache_differs_by_phase(self):
        mem = QueryHistoryMemory()
        ctrl = SearchCrawlController(mem, "", "", "test-model")
        assert ctrl._decision_cache_key("discover", [], []) != ctrl._decision_cache_key("verify", [], [])

    def test_store_then_lookup_hits(self):
        mem = QueryHistoryMemory()
        ctrl = SearchCrawlController(mem, "", "", "test-model")
        from search_crawl_controller import SearchCrawlVerdict
        v = SearchCrawlVerdict(decision="crawl_now", reason="test", signals={})
        key = ctrl._decision_cache_key("discover", ["u1"], [])
        ctrl._store_decision_cache(key, v)
        hit = ctrl._lookup_decision_cache(key)
        assert hit is not None
        assert hit.decision == "crawl_now"
        assert hit.reason.startswith("[cached]")


# ---------------------------------------------------------------------------
# config.settings
# ---------------------------------------------------------------------------

class TestConfig:
    def test_settings_loads_defaults(self, monkeypatch):
        for var in ["MODEL_NAME", "OPENAI_BASE_URL", "OPENAI_API_KEY", "CRAWLER_ENGINE"]:
            monkeypatch.delenv(var, raising=False)
        s = settings()
        assert s.model_id == ""  # model-agnostic: no hardcoded default
        assert s.api_base == ""
        assert s.tools.crawler_engine == "jina"

    def test_settings_reads_env(self, monkeypatch):
        monkeypatch.setenv("MODEL_NAME", "custom-model")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://example.com/v1")
        monkeypatch.setenv("CRAWLER_ENGINE", "html2text")
        s = settings()
        assert s.model_id == "custom-model"
        assert s.api_base == "https://example.com/v1"
        assert s.tools.crawler_engine == "html2text"

    def test_executor_falls_back_to_model_name(self, monkeypatch):
        monkeypatch.delenv("EXECUTOR_MODEL_NAME", raising=False)
        monkeypatch.setenv("MODEL_NAME", "fallback-model")
        s = settings()
        assert s.executor_model_id == "fallback-model"

    def test_grader_falls_back_to_llm_config(self, monkeypatch):
        for var in ["GRADER_API_BASE", "GRADER_OPENAI_BASE_URL", "GRADER_API_KEY", "GRADER_MODEL"]:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("OPENAI_BASE_URL", "https://llm.example.com/v1")
        monkeypatch.setenv("MODEL_NAME", "main-model")
        s = settings()
        assert s.grader.api_base == "https://llm.example.com/v1"
        assert s.grader.model_id == "main-model"

    def test_bool_flags(self, monkeypatch):
        monkeypatch.setenv("PLANNER_SIMPLE_PROMPT", "1")
        monkeypatch.setenv("EXECUTOR_SIMPLE_PROMPT", "false")
        s = settings()
        assert s.prompt.planner_simple_prompt is True
        assert s.prompt.executor_simple_prompt is False


# ---------------------------------------------------------------------------
# llm_client._is_retryable
# ---------------------------------------------------------------------------

class TestIsRetryable:
    def test_connection_error_retryable(self):
        class APIConnectionError(Exception):
            pass
        assert _is_retryable(APIConnectionError()) is True

    def test_rate_limit_retryable(self):
        class RateLimitError(Exception):
            pass
        assert _is_retryable(RateLimitError()) is True

    def test_5xx_status_retryable(self):
        class APIStatusError(Exception):
            status_code = 503
        assert _is_retryable(APIStatusError()) is True

    def test_4xx_status_not_retryable(self):
        class APIStatusError(Exception):
            status_code = 400
        assert _is_retryable(APIStatusError()) is False

    def test_generic_exception_not_retryable(self):
        class ValueError(Exception):
            pass
        assert _is_retryable(ValueError()) is False
