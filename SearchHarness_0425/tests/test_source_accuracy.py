"""Unit tests for the data-source accuracy core in search_tools.py.

Covers the three 数据源管控 (data-source governance) features added to
``_postprocess_serper_results``:
  1. 数据源分级可信权重 — tiered credibility rerank
  2. 时效性强制约束 — timeliness filter for time-sensitive queries
  3. 去重与同源合并 — cross-domain repost merging

These tests import the real post-processing helpers from the local
tools/search_tools.py (SearchHarness_0425/tools/, on sys.path via conftest).
They are pure/deterministic — no network, no LLM, no Serper calls.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pytest

from tools.search_tools import (  # type: ignore
    _domain_credibility,
    _freshness_flag,
    _is_time_sensitive_query,
    _jaccard,
    _normalize_text_tokens,
    _parse_serper_date,
    _postprocess_serper_results,
    _source_weight,
    authoritative_domains_in,
    high_weight_sources_in,
    is_authoritative_source,
)


# ── helpers ──────────────────────────────────────────────────────────────────
def _serp(*results):
    return json.dumps({"organic": list(results)}, ensure_ascii=False)


def _result(title, link, snippet="", date=None, position=None):
    r = {"title": title, "link": link, "snippet": snippet}
    if date is not None:
        r["date"] = date
    if position is not None:
        r["position"] = position
    return r


@pytest.fixture(autouse=True)
def _restore_env(monkeypatch):
    """Ensure each test starts from the default env (all features ON)."""
    for k in ("SRC_CREDIBILITY_ENABLED", "SRC_FRESHNESS_ENABLED",
              "SRC_CROSSDOMAIN_DEDUP_ENABLED", "SRC_FRESHNESS_MAX_AGE_DAYS"):
        monkeypatch.delenv(k, raising=False)
    yield


# ── 1. 数据源分级可信权重 ─────────────────────────────────────────────────────
@pytest.mark.parametrize("url,expected", [
    ("https://arxiv.org/abs/2401.00001", 5),          # academic
    ("https://docs.python.org/3/", 5),               # official docs
    ("https://en.wikipedia.org/wiki/X", 4),          # encyclopedia
    ("https://data.gov.uk/data", 4),                  # official (.gov in labels)
    ("https://stackoverflow.com/q/1", 3),             # vertical forum
    ("https://random-blog.example.com/post", 2),      # generic web (default)
    ("https://reddit.com/r/x", 1),                    # UGC / self-media
    ("https://medium.com/@user/post", 1),             # UGC
    ("https://prnewswire.com/news", 1),               # press-release aggregator
    ("https://example.invalid/", 2),                 # unknown → generic
])
def test_domain_credibility_tiers(url, expected):
    assert _domain_credibility(url) == expected


def test_rerank_surfaces_high_credibility_above_generic():
    serp = _serp(
        _result("Apple", "https://blogspot.com/apple", "about apple", position=0),   # tier 1
        _result("Apple", "https://en.wikipedia.org/wiki/Apple", "apple fruit", position=1),  # tier 4
    )
    out = json.loads(_postprocess_serper_results(serp, "apple"))
    assert out["organic"][0]["link"] == "https://en.wikipedia.org/wiki/Apple"
    assert out["organic"][0]["credibility_tier"] == 4
    assert out["organic"][1]["credibility_tier"] == 1


# ── 2. 时效性强制约束 ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("query,expected", [
    ("Apple stock price today", True),
    ("latest 2026 model release", True),
    ("who won the championship 2025", True),
    ("current GDP of Japan", True),
    ("最新版本 发布", True),
    ("history of the Roman Empire", False),
    ("what is photosynthesis", False),
    ("who invented the telephone", False),
    ("牛顿第二定律 原理", False),
    ("", False),
])
def test_time_sensitive_classification(query, expected):
    assert _is_time_sensitive_query(query) == expected


def test_parse_serper_date_relative_and_absolute():
    now = datetime(2026, 8, 7, tzinfo=timezone.utc)
    assert _parse_serper_date("3 days ago", now).date() == datetime(2026, 8, 4).date()
    assert _parse_serper_date("2 weeks ago", now).date() == datetime(2026, 7, 24).date()
    assert _parse_serper_date("Dec 31, 2023", now).year == 2023
    assert _parse_serper_date("2023-12-31", now).year == 2023
    assert _parse_serper_date("in the year 2024 maybe", now).year == 2024  # year fallback
    assert _parse_serper_date(None, now) is None
    assert _parse_serper_date("not a date at all", now) is None


def test_stale_result_dropped_on_time_sensitive_query(monkeypatch):
    monkeypatch.setenv("SRC_FRESHNESS_MAX_AGE_DAYS", "730")
    serp = _serp(
        _result("Apple stock price 2023", "https://old.example.com/a",
                "AAPL closed 180 in 2023", date="Dec 31, 2023", position=0),
        _result("Apple stock price today", "https://fresh.example.com/b",
                "AAPL 202 today", date="1 day ago", position=1),
        _result("Apple stock today", "https://fresh2.example.com/c",
                "AAPL updated", date="2 days ago", position=2),
        _result("Apple - Wikipedia", "https://en.wikipedia.org/wiki/Apple",
                "Apple Inc.", date="1 week ago", position=3),
    )
    out = json.loads(_postprocess_serper_results(serp, "Apple stock price today"))
    links = [r["link"] for r in out["organic"]]
    assert "https://old.example.com/a" not in links  # stale 2023 dropped
    assert out["freshness_dropped"][0]["link"] == "https://old.example.com/a"


def test_stale_result_kept_on_general_knowledge_query(monkeypatch):
    """General-knowledge queries must NOT drop dated sources (relaxed)."""
    monkeypatch.setenv("SRC_FRESHNESS_MAX_AGE_DAYS", "730")
    serp = _serp(
        _result("Roman Empire 2023 notes", "https://old.example.com/rome",
                "Empire notes 2023", date="Jan 1, 2023", position=0),
        _result("Roman Empire", "https://en.wikipedia.org/wiki/Roman_Empire",
                "post-Republican state", date="1 week ago", position=1),
    )
    out = json.loads(_postprocess_serper_results(serp, "history of the Roman Empire"))
    links = [r["link"] for r in out["organic"]]
    assert "https://old.example.com/rome" in links  # NOT dropped for general knowledge
    assert out.get("freshness_dropped") is None


def test_floor_prevents_over_filtering(monkeypatch):
    """If freshness filter would drop below 3 results, restore stale ones."""
    monkeypatch.setenv("SRC_FRESHNESS_MAX_AGE_DAYS", "30")
    serp = _serp(
        _result("Old A", "https://a.example.com", "x", date="Jan 1, 2020", position=0),
        _result("Old B", "https://b.example.com", "y", date="Feb 1, 2020", position=1),
        _result("Old C", "https://c.example.com", "z", date="Mar 1, 2020", position=2),
    )
    out = json.loads(_postprocess_serper_results(serp, "current price update 2026"))
    # All stale, but floor restores up to 3 so the agent isn't left empty-handed.
    assert len(out["organic"]) >= 3
    assert all(r.get("freshness_flag") == "stale_kept" for r in out["organic"])


def test_freshness_flag_buckets():
    assert _freshness_flag(5, 730) == "fresh"
    assert _freshness_flag(100, 730) == "recent"
    assert _freshness_flag(800, 730) == "stale"


# ── 3. 去重与同源合并 ─────────────────────────────────────────────────────────
def test_per_domain_dedup_keeps_first():
    serp = _serp(
        _result("A", "https://example.com/p1", "snippet one", position=0),
        _result("B", "https://example.com/p2", "snippet two", position=1),
    )
    out = json.loads(_postprocess_serper_results(serp, "query"))
    assert len(out["organic"]) == 1
    assert out["organic"][0]["link"] == "https://example.com/p1"


def test_encyclopedia_whitelisted_from_domain_dedup():
    serp = _serp(
        _result("Rome history", "https://en.wikipedia.org/wiki/Rome", "a", position=0),
        _result("Rome empire", "https://en.wikipedia.org/wiki/Roman_Empire", "b", position=1),
    )
    out = json.loads(_postprocess_serper_results(serp, "Rome"))
    assert len(out["organic"]) == 2  # both kept — wikipedia whitelisted


def test_cross_domain_repost_merged_keeps_higher_credibility():
    title = "Apple stock price today closes at 202"
    snippet = "Apple AAPL closed at 202 dollars per share today on the exchange"
    serp = _serp(
        _result(title, "https://reddit.com/r/stocks", snippet, position=0),   # tier 1
        _result(title, "https://reuters.com/article/apple", snippet, position=1),  # tier 4
    )
    out = json.loads(_postprocess_serper_results(serp, "Apple stock price today"))
    links = [r["link"] for r in out["organic"]]
    assert links == ["https://reuters.com/article/apple"]  # higher tier kept
    assert out["dedup_merges"][0]["dropped_link"] == "https://reddit.com/r/stocks"


def test_cross_domain_merge_disabled_via_env(monkeypatch):
    monkeypatch.setenv("SRC_CROSSDOMAIN_DEDUP_ENABLED", "0")
    title = "Same title reposted across sites"
    snippet = "Identical snippet body across the two domains for testing"
    serp = _serp(
        _result(title, "https://a.example.com/x", snippet, position=0),
        _result(title, "https://b.example.com/y", snippet, position=1),
    )
    out = json.loads(_postprocess_serper_results(serp, "query"))
    assert len(out["organic"]) == 2  # NOT merged
    assert "dedup_merges" not in out


def test_jaccard_and_normalize():
    a = _normalize_text_tokens("The Quick Brown Fox!")
    b = _normalize_text_tokens("the quick brown fox")
    assert a == {"quick", "brown", "fox"}
    assert _jaccard(a, b) == 1.0
    assert _jaccard(set(), {"x"}) == 0.0


# ── env-gating / failure-safety ───────────────────────────────────────────────
def test_all_features_off_restores_passthrough_order(monkeypatch):
    monkeypatch.setenv("SRC_CREDIBILITY_ENABLED", "0")
    monkeypatch.setenv("SRC_FRESHNESS_ENABLED", "0")
    monkeypatch.setenv("SRC_CROSSDOMAIN_DEDUP_ENABLED", "0")
    serp = _serp(
        _result("A", "https://x.example.com/0", "s0", position=0),
        _result("B", "https://y.example.com/1", "s1", position=1),
    )
    out = json.loads(_postprocess_serper_results(serp, "latest news today"))
    # No rerank (credibility off), no freshness drop, no merge → Serper order.
    assert [r["link"] for r in out["organic"]] == [
        "https://x.example.com/0", "https://y.example.com/1"
    ]


def test_malformed_json_returns_raw_unchanged():
    raw = "this is not json"
    assert _postprocess_serper_results(raw, "q") == raw


def test_empty_organic_returns_raw():
    assert _postprocess_serper_results(json.dumps({"organic": []}), "q") == \
        json.dumps({"organic": []})


def test_source_quality_metadata_emitted():
    serp = _serp(_result("A", "https://en.wikipedia.org/wiki/A", "x", position=0))
    out = json.loads(_postprocess_serper_results(serp, "what is A"))
    assert "source_quality" in out
    assert set(out["source_quality"]) == {
        "query_time_sensitive", "freshness_max_age_days",
        "credibility_enabled", "freshness_enabled", "crossdomain_dedup_enabled",
    }


# ── 权威来源判定 (is_authoritative_source / authoritative_domains_in) ────────

@pytest.mark.parametrize("url,expected", [
    ("https://en.wikipedia.org/wiki/Python", True),       # tier 4 encyclopedia
    ("https://www.wikipedia.org/wiki/X", True),          # www-stripped
    ("https://arxiv.org/abs/2401.00001", True),          # tier 5 academic
    ("https://docs.python.org/3/", True),                # tier 5 official docs
    ("https://www.reuters.com/article/abc", True),        # tier 4 wire
    ("https://gov.uk/news", True),                       # .gov TLD → tier 4
    ("https://example.gov.uk/news", True),               # second-level .gov
    ("https://mit.edu/research", True),                  # .edu → tier 4
    ("https://reddit.com/r/singularity", False),         # tier 1 UGC
    ("https://medium.com/@user/post", False),            # tier 1 self-media
    ("https://example.com/post", False),                 # tier 2 generic
    ("https://stackoverflow.com/q/1", False),            # tier 3 (not >=4)
    ("not a url", False),
    ("", False),
    (None, False),
])
def test_is_authoritative_source(url, expected):
    assert is_authoritative_source(url) == expected


def test_authoritative_domains_dedup_same_domain():
    urls = [
        "https://en.wikipedia.org/wiki/A",
        "https://en.wikipedia.org/wiki/B",        # same domain → 1
        "https://arxiv.org/abs/1",
        "https://reuters.com/a",
        "https://reuters.com/b",                  # same domain → 1
        "https://reddit.com/c",                   # not authoritative
        "not-a-url",
    ]
    doms = authoritative_domains_in(urls)
    assert doms == ["arxiv.org", "reuters.com", "wikipedia.org"]


def test_authoritative_domains_empty_and_non_http():
    assert authoritative_domains_in([]) == []
    assert authoritative_domains_in(["", "no-scheme", "ftp://x.com"]) == []


# ── Executor authority-consensus early-stop ──────────────────────────────────

def _make_executor_for_authority(monkeypatch):
    """Build a SearchAgentV3-ish stub exercising only the consensus check."""
    import search_agent_v3
    # Minimal stand-in: only the fields the consensus check touches.
    class _Stub:
        def __init__(self):
            self._authority_early_stop = True
            self._authority_consensus_done = False
            self._authority_min_sources = 2
            self._fact_confirm_min_sources = 2
            self._candidate_tool_updates = {"candidate_assessments": []}
        _candidate_name = search_agent_v3.SearchAgentV3._candidate_name  # bound below
        _consensus_candidate = search_agent_v3.SearchAgentV3._consensus_candidate
        _authority_consensus_candidate = search_agent_v3.SearchAgentV3._authority_consensus_candidate
    # Bind the real instance methods onto stub instances (they use self).
    return _Stub()


def test_executor_consensus_fires_on_two_authoritative_domains(monkeypatch):
    """Two tier-4 authoritative domains (reuters/bbc) → authoritative_consensus."""
    stub = _make_executor_for_authority(monkeypatch)
    stub._candidate_tool_updates["candidate_assessments"] = [
        {"name": "Achimota School", "status": "active", "evidence": [
            {"source_url": "https://www.reuters.com/world/a/achimota"},
            {"source_url": "https://www.bbc.com/news/achimota"},
        ]},
    ]
    result = stub._consensus_candidate()
    assert result is not None
    assert result["name"] == "Achimota School"
    assert result["kind"] == "authoritative_consensus"
    assert stub._authority_consensus_candidate() == "Achimota School"


def test_executor_fact_confirmed_fires_on_two_weight10_sources(monkeypatch):
    """Two weight-10 sources (official doc + academic) → fact_confirmed."""
    stub = _make_executor_for_authority(monkeypatch)
    stub._candidate_tool_updates["candidate_assessments"] = [
        {"name": "Python 3.12 release", "status": "active", "evidence": [
            {"source_url": "https://docs.python.org/3/whatsnew/3.12"},
            {"source_url": "https://arxiv.org/abs/2401.00001"},
        ]},
    ]
    result = stub._consensus_candidate()
    assert result is not None
    assert result["name"] == "Python 3.12 release"
    assert result["kind"] == "fact_confirmed"
    assert set(result["sources"]) == {"python.org", "arxiv.org"}


def test_executor_fact_confirmed_fires_on_official_financial_reports(monkeypatch):
    """ir.apple.com + sec.gov → fact_confirmed (official financial reports)."""
    stub = _make_executor_for_authority(monkeypatch)
    stub._candidate_tool_updates["candidate_assessments"] = [
        {"name": "Apple Q4 revenue", "status": "active", "evidence": [
            {"source_url": "https://ir.apple.com/investor-relations/q4"},
            {"source_url": "https://www.sec.gov/cgi-bin/browse-edgar?apple"},
        ]},
    ]
    result = stub._consensus_candidate()
    assert result is not None
    assert result["kind"] == "fact_confirmed"
    assert set(result["sources"]) == {"apple.com", "sec.gov"}


def test_executor_fact_confirmed_preferred_over_authoritative(monkeypatch):
    """If both tiers qualify, fact_confirmed (weight=10) wins."""
    stub = _make_executor_for_authority(monkeypatch)
    stub._candidate_tool_updates["candidate_assessments"] = [
        {"name": "X", "status": "active", "evidence": [
            {"source_url": "https://docs.python.org/3/x"},        # weight 10
            {"source_url": "https://arxiv.org/abs/1"},            # weight 10
            {"source_url": "https://www.reuters.com/article/x"},  # weight 8
            {"source_url": "https://www.bbc.com/news/x"},         # weight 8
        ]},
    ]
    result = stub._consensus_candidate()
    assert result["kind"] == "fact_confirmed"


def test_executor_consensus_does_not_fire_on_one_domain(monkeypatch):
    stub = _make_executor_for_authority(monkeypatch)
    stub._candidate_tool_updates["candidate_assessments"] = [
        {"name": "X", "evidence": [
            {"source_url": "https://www.reuters.com/article/x"},
            {"source_url": "https://www.reuters.com/article/x2"},   # same domain
        ]},
    ]
    assert stub._consensus_candidate() is None


def test_executor_consensus_skips_contradicted(monkeypatch):
    stub = _make_executor_for_authority(monkeypatch)
    stub._candidate_tool_updates["candidate_assessments"] = [
        {"name": "X", "verification_status": "contradicted", "evidence": [
            {"source_url": "https://www.reuters.com/article/x"},
            {"source_url": "https://www.bbc.com/news/x"},
        ]},
    ]
    assert stub._consensus_candidate() is None


def test_executor_consensus_disabled_by_env(monkeypatch):
    stub = _make_executor_for_authority(monkeypatch)
    stub._authority_early_stop = False
    stub._candidate_tool_updates["candidate_assessments"] = [
        {"name": "X", "evidence": [
            {"source_url": "https://www.reuters.com/article/x"},
            {"source_url": "https://www.bbc.com/news/x"},
        ]},
    ]
    assert stub._consensus_candidate() is None


def test_executor_consensus_respects_min_sources(monkeypatch):
    stub = _make_executor_for_authority(monkeypatch)
    stub._authority_min_sources = 3
    stub._candidate_tool_updates["candidate_assessments"] = [
        {"name": "X", "evidence": [
            {"source_url": "https://www.reuters.com/article/x"},
            {"source_url": "https://www.bbc.com/news/x"},
        ]},
    ]
    assert stub._consensus_candidate() is None


def test_executor_fact_confirmed_respects_min_sources(monkeypatch):
    """fact_confirmed requires _fact_confirm_min_sources distinct weight-10 domains."""
    stub = _make_executor_for_authority(monkeypatch)
    stub._fact_confirm_min_sources = 3
    stub._candidate_tool_updates["candidate_assessments"] = [
        {"name": "X", "evidence": [
            {"source_url": "https://docs.python.org/3/x"},  # weight 10 (tier 5)
            {"source_url": "https://example.com/post"},     # weight 3 (tier 2)
        ]},
    ]
    # Only 1 weight-10 source, fact needs 3 → no fact_confirmed.
    # Only 1 authoritative (tier>=4) domain → no authoritative_consensus.
    assert stub._consensus_candidate() is None


def test_executor_consensus_accepts_legacy_source_field(monkeypatch):
    stub = _make_executor_for_authority(monkeypatch)
    stub._candidate_tool_updates["candidate_assessments"] = [
        {"name": "X", "evidence": [
            {"source": "https://www.reuters.com/article/x"},        # legacy field
            {"source": "https://www.bbc.com/news/x"},
        ]},
    ]
    result = stub._consensus_candidate()
    assert result is not None
    assert result["name"] == "X"
    assert result["kind"] == "authoritative_consensus"


# ── Pipeline authoritative-consensus early-stop ──────────────────────────────

class _FakeStateStore:
    """Minimal stand-in for SearchStateStore.export_compact_state()."""
    def __init__(self, records):
        self._records = records
    def export_compact_state(self):
        return {"candidate_records": self._records}


def _make_pipeline_for_authority(records):
    import search_harness_pipeline_v4 as pipe
    class _Stub:
        state_store = _FakeStateStore(records)
        workflow_stage = "candidate_verification"
        CANDIDATE_VERIFICATION = "candidate_verification"
        def _viable_candidate_records(self, compact_state=None):
            return []
        def _tied_candidate_blocks_early_stop(self, *a, **k):
            return False
        _authoritative_consensus_early_stop = \
            pipe.SearchHarnessPipelineV4._authoritative_consensus_early_stop
    return _Stub()


def test_pipeline_consensus_fires(monkeypatch):
    """Two tier-4 domains → authoritative_consensus_early_stop."""
    monkeypatch.setenv("PIPELINE_AUTHORITY_EARLY_STOP", "1")
    monkeypatch.setenv("PIPELINE_AUTHORITY_MIN_SOURCES", "2")
    stub = _make_pipeline_for_authority([
        {"name": "X", "status": "active", "verification_status": "partial",
         "evidence": [
             {"source_url": "https://www.reuters.com/article/x"},
             {"source_url": "https://www.bbc.com/news/x"},
         ]},
    ])
    out = stub._authoritative_consensus_early_stop(iteration=3)
    assert out is not None
    assert out["trigger"] == "authoritative_consensus_early_stop"
    assert out["details"]["candidate"] == "X"
    assert set(out["details"]["authoritative_domains"]) == {"reuters.com", "bbc.com"}


def test_pipeline_fact_confirmed_fires_on_weight10(monkeypatch):
    """Two weight-10 sources → fact_confirmed_early_stop (strongest stop)."""
    monkeypatch.setenv("PIPELINE_AUTHORITY_EARLY_STOP", "1")
    monkeypatch.setenv("PIPELINE_FACT_CONFIRM_MIN_SOURCES", "2")
    stub = _make_pipeline_for_authority([
        {"name": "Apple Q4 revenue", "status": "active",
         "evidence": [
             {"source_url": "https://ir.apple.com/investor-relations/q4"},
             {"source_url": "https://www.sec.gov/cgi-bin/browse-edgar?apple"},
         ]},
    ])
    out = stub._authoritative_consensus_early_stop(iteration=2)
    assert out is not None
    assert out["trigger"] == "fact_confirmed_early_stop"
    assert out["details"]["candidate"] == "Apple Q4 revenue"
    assert set(out["details"]["high_weight_domains"]) == {"apple.com", "sec.gov"}


def test_pipeline_fact_confirmed_preferred_over_authoritative(monkeypatch):
    """If both tiers qualify, fact_confirmed wins."""
    monkeypatch.setenv("PIPELINE_AUTHORITY_EARLY_STOP", "1")
    stub = _make_pipeline_for_authority([
        {"name": "X", "status": "active", "evidence": [
            {"source_url": "https://docs.python.org/3/x"},        # weight 10
            {"source_url": "https://arxiv.org/abs/1"},            # weight 10
            {"source_url": "https://www.reuters.com/article/x"},  # weight 8
            {"source_url": "https://www.bbc.com/news/x"},         # weight 8
        ]},
    ])
    out = stub._authoritative_consensus_early_stop(iteration=1)
    assert out["trigger"] == "fact_confirmed_early_stop"


def test_pipeline_consensus_skips_contradicted(monkeypatch):
    monkeypatch.setenv("PIPELINE_AUTHORITY_EARLY_STOP", "1")
    stub = _make_pipeline_for_authority([
        {"name": "X", "verification_status": "contradicted",
         "evidence": [
             {"source_url": "https://www.reuters.com/article/x"},
             {"source_url": "https://www.bbc.com/news/x"},
         ]},
    ])
    assert stub._authoritative_consensus_early_stop(iteration=1) is None


def test_pipeline_consensus_disabled_by_env(monkeypatch):
    monkeypatch.setenv("PIPELINE_AUTHORITY_EARLY_STOP", "0")
    stub = _make_pipeline_for_authority([
        {"name": "X", "evidence": [
            {"source_url": "https://www.reuters.com/article/x"},
            {"source_url": "https://www.bbc.com/news/x"},
        ]},
    ])
    assert stub._authoritative_consensus_early_stop(iteration=1) is None


def test_pipeline_consensus_needs_two_distinct_domains(monkeypatch):
    monkeypatch.setenv("PIPELINE_AUTHORITY_EARLY_STOP", "1")
    stub = _make_pipeline_for_authority([
        {"name": "X", "evidence": [
            {"source_url": "https://www.reuters.com/article/x"},
            {"source_url": "https://www.reuters.com/article/x2"},   # same domain
        ]},
    ])
    assert stub._authoritative_consensus_early_stop(iteration=1) is None


# ── Source-weight scoring ────────────────────────────────────────────────────

@pytest.mark.parametrize("url, expected", [
    # tier 5 → weight 10 (official docs / academic / official financial reports)
    ("https://docs.python.org/3/whatsnew/3.12", 10),
    ("https://arxiv.org/abs/2401.00001", 10),
    ("https://ir.apple.com/investor-relations", 10),
    ("https://investor.microsoft.com/", 10),
    ("https://www.sec.gov/cgi-bin/browse-edgar", 10),
    ("https://www.nature.com/articles/1", 10),
    # tier 4 → weight 8 (encyclopedia / official institutions / authoritative media)
    ("https://en.wikipedia.org/wiki/X", 8),
    ("https://www.reuters.com/article/x", 8),
    ("https://www.bbc.com/news/x", 8),
    ("https://www.nasa.gov/mission/x", 8),
    ("https://www.harvard.edu/news/x", 8),
    # tier 3 → weight 5 (vertical professional)
    ("https://stackoverflow.com/q/1", 5),
    ("https://www.imdb.com/title/x", 5),
    # tier 2 → weight 3 (generic web, default)
    ("https://example.com/post", 3),
    ("https://www.random-blog.net/article", 3),
    # tier 1 → weight 2 (UGC / self-media / press-release)
    ("https://www.reddit.com/r/x", 2),
    ("https://medium.com/@u/p", 2),
    ("https://blogspot.com/2024/x", 2),
    ("https://www.prnewswire.com/news/x", 2),
])
def test_source_weight(url, expected):
    assert _source_weight(url) == expected


def test_high_weight_sources_in_dedup():
    """Only weight>=10 domains, same base-domain deduplicated."""
    urls = [
        "https://ir.apple.com/a",         # weight 10 (apple.com)
        "https://www.sec.gov/b",          # weight 10 (sec.gov)
        "https://en.wikipedia.org/c",     # weight 8  → excluded by min_weight=10
        "https://docs.python.org/3/d",    # weight 10 (python.org)
        "https://www.reuters.com/e",      # weight 8  → excluded
        "https://reddit.com/r/x",         # weight 2  → excluded
    ]
    assert set(high_weight_sources_in(urls, min_weight=10)) == {
        "apple.com", "sec.gov", "python.org"
    }


def test_high_weight_sources_in_same_domain_counts_once():
    """Two pages from ir.apple.com count as one independent source."""
    urls = [
        "https://ir.apple.com/a",
        "https://ir.apple.com/b",
        "https://arxiv.org/1",
    ]
    assert set(high_weight_sources_in(urls, min_weight=10)) == {"apple.com", "arxiv.org"}


def test_high_weight_sources_in_empty():
    assert high_weight_sources_in([], min_weight=10) == []
    assert high_weight_sources_in(None, min_weight=10) == []


def test_high_weight_sources_in_min_weight_threshold():
    """min_weight=8 includes tier-4 (wikipedia/reuters) too."""
    urls = [
        "https://en.wikipedia.org/x",      # weight 8
        "https://www.reuters.com/y",       # weight 8
        "https://arxiv.org/1",             # weight 10
        "https://reddit.com/r/x",          # weight 2
    ]
    assert set(high_weight_sources_in(urls, min_weight=8)) == {
        "wikipedia.org", "reuters.com", "arxiv.org"
    }
