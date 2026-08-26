"""Wiring tests: cache inside chat_completion_with_structuring and HTTP tools.

Uses stub clients (no network, no real OpenAI objects) to prove:
- record mode: 1st call goes to stub client, 2nd identical call hits cache
- replay mode: miss raises DiskCacheMissError, hit returns cached message
- cache hits skip usage recording (replay shows no API spend)
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import utils.disk_cache as dc
from llm.compat import chat_completion_with_structuring
from utils.llm_usage import UsageTracker


@pytest.fixture(autouse=True)
def _cache_env(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_CACHE_MODE", "off")
    monkeypatch.setenv("LLM_CACHE_DIR", str(tmp_path / "cache"))
    tracker = UsageTracker()
    tracker.reset()
    yield tracker


def _stub_client(content: str = "hello"):
    calls = {"n": 0}

    class _Chat:
        @property
        def completions(self_):
            return self_

        def create(self_, **kwargs):
            calls["n"] += 1
            msg = SimpleNamespace(role="assistant", content=content,
                                  reasoning_content="r", tool_calls=[])
            usage = SimpleNamespace(prompt_tokens=10, completion_tokens=3, total_tokens=13)
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=usage)

    return SimpleNamespace(chat=_Chat()), calls


class TestLLMCacheWiring:
    def test_off_passthrough(self, monkeypatch):
        monkeypatch.setenv("LLM_STREAM_ENABLED", "0")
        client, calls = _stub_client()
        kwargs = dict(client=client, model_id="m", messages=[{"role": "user", "content": "q"}])
        chat_completion_with_structuring(**kwargs)
        chat_completion_with_structuring(**kwargs)
        assert calls["n"] == 2  # no caching

    def test_record_then_hit(self, monkeypatch):
        monkeypatch.setenv("LLM_CACHE_MODE", "record")
        monkeypatch.setenv("LLM_STREAM_ENABLED", "0")
        client, calls = _stub_client()
        kwargs = dict(client=client, model_id="m", messages=[{"role": "user", "content": "q"}])
        r1 = chat_completion_with_structuring(**kwargs)
        r2 = chat_completion_with_structuring(**kwargs)
        assert calls["n"] == 1  # second call served from cache
        assert r2.content == "hello"
        assert r2.reasoning_content == "r"

    def test_replay_miss_raises(self, monkeypatch):
        monkeypatch.setenv("LLM_CACHE_MODE", "replay")
        client, _ = _stub_client()
        with pytest.raises(dc.DiskCacheMissError):
            chat_completion_with_structuring(client=client, model_id="m",
                                             messages=[{"role": "user", "content": "q"}])

    def test_replay_hit_after_record(self, monkeypatch):
        monkeypatch.setenv("LLM_STREAM_ENABLED", "0")
        client, calls = _stub_client()
        kwargs = dict(client=client, model_id="m", messages=[{"role": "user", "content": "q"}])
        monkeypatch.setenv("LLM_CACHE_MODE", "record")
        chat_completion_with_structuring(**kwargs)
        monkeypatch.setenv("LLM_CACHE_MODE", "replay")
        r = chat_completion_with_structuring(**kwargs)
        assert r.content == "hello" and calls["n"] == 1

    def test_hit_skips_usage_recording(self, monkeypatch):
        monkeypatch.setenv("LLM_STREAM_ENABLED", "0")
        monkeypatch.setenv("LLM_CACHE_MODE", "record")
        client, calls = _stub_client()
        kwargs = dict(client=client, model_id="m", messages=[{"role": "user", "content": "q"}])
        tracker = UsageTracker()
        chat_completion_with_structuring(**kwargs)
        n1 = tracker.snapshot()["total"]["calls"]
        chat_completion_with_structuring(**kwargs)  # cache hit
        assert tracker.snapshot()["total"]["calls"] == n1  # no double-count

    def test_stream_flag_shares_cache(self, monkeypatch):
        monkeypatch.setenv("LLM_STREAM_ENABLED", "0")
        monkeypatch.setenv("LLM_CACHE_MODE", "record")
        client, calls = _stub_client()
        chat_completion_with_structuring(client=client, model_id="m",
                                         messages=[{"role": "user", "content": "q"}], stream=True)
        r = chat_completion_with_structuring(client=client, model_id="m",
                                             messages=[{"role": "user", "content": "q"}], stream=False)
        assert calls["n"] == 1  # stream flags excluded from key


class TestHTTPCacheWiring:
    def test_serper_cached(self, monkeypatch):
        from tools import search_tools as st
        monkeypatch.setenv("LLM_CACHE_MODE", "record")
        monkeypatch.setenv("SERPER_API_KEY", "k")
        net = {"n": 0}

        class FakeResp:
            ok = True
            text = "{\"organic\": []}"

        def fake_post(self, url, headers=None, data=None, timeout=None):
            net["n"] += 1
            return FakeResp()

        monkeypatch.setattr(st.requests.Session, "post", fake_post)
        assert st._call_serper_api("q1") == "{\"organic\": []}"
        assert st._call_serper_api("q1") == "{\"organic\": []}"
        assert net["n"] == 1

    def test_serper_replay_miss_raises(self, monkeypatch):
        from tools import search_tools as st
        monkeypatch.setenv("LLM_CACHE_MODE", "replay")
        with pytest.raises(dc.DiskCacheMissError):
            st._call_serper_api("never-cached-query")

    def test_crawl_keyed_by_engine(self, monkeypatch):
        from tools import search_tools as st
        monkeypatch.setenv("LLM_CACHE_MODE", "record")
        monkeypatch.setattr(st, "_crawl_url_uncached", lambda u: "TRAF")
        monkeypatch.setenv("CRAWLER_ENGINE", "trafilatura")
        assert st._crawl_url("http://x") == "TRAF"
        monkeypatch.setattr(st, "_crawl_url_uncached", lambda u: "JINA")
        monkeypatch.setenv("CRAWLER_ENGINE", "jina")
        assert st._crawl_url("http://x") == "JINA"  # different engine → miss
        # back to trafilatura → original hit
        monkeypatch.setenv("CRAWLER_ENGINE", "trafilatura")
        assert st._crawl_url("http://x") == "TRAF"

    def test_wiki_cached(self, monkeypatch):
        from tools import search_tools as st
        monkeypatch.setenv("LLM_CACHE_MODE", "record")
        monkeypatch.setattr(st, "_search_wiki_uncached", lambda e: f"WIKI:{e}")
        assert st._search_wiki("Ent") == "WIKI:Ent"
        monkeypatch.setattr(st, "_search_wiki_uncached", lambda e: 1 / 0)
        assert st._search_wiki("Ent") == "WIKI:Ent"  # hit, no recompute
