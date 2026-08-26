"""Tests for M1 disk cache: deterministic keys, record/replay, LLM/HTTP wiring."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import utils.disk_cache as dc


@pytest.fixture(autouse=True)
def _cache_env(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_CACHE_MODE", "off")
    monkeypatch.setenv("LLM_CACHE_DIR", str(tmp_path / "cache"))


def _record(monkeypatch):
    monkeypatch.setenv("LLM_CACHE_MODE", "record")


def _replay(monkeypatch):
    monkeypatch.setenv("LLM_CACHE_MODE", "replay")


class TestKeys:
    def test_llm_key_ignores_stream_flags(self):
        a = dc.make_llm_key({"model": "m", "messages": [{"role": "u", "content": "x"}], "stream": True})
        b = dc.make_llm_key({"model": "m", "messages": [{"role": "u", "content": "x"}], "stream": False,
                             "stream_options": {"include_usage": True}})
        assert a == b

    def test_llm_key_order_independent(self):
        a = dc.make_llm_key({"model": "m", "messages": [], "temperature": 0.7})
        b = dc.make_llm_key({"temperature": 0.7, "messages": [], "model": "m"})
        assert a == b

    def test_llm_key_content_sensitive(self):
        a = dc.make_llm_key({"model": "m", "messages": [{"role": "u", "content": "x"}]})
        b = dc.make_llm_key({"model": "m", "messages": [{"role": "u", "content": "y"}]})
        assert a != b

    def test_http_key(self):
        assert dc.make_http_key("crawl", "a") == dc.make_http_key("crawl", "a")
        assert dc.make_http_key("crawl", "a") != dc.make_http_key("crawl", "b")
        assert dc.make_http_key("crawl", "a") != dc.make_http_key("serper", "a")


class TestStore:
    def test_off_by_default(self):
        assert not dc.cache_enabled()
        assert dc.get_entry("llm", "k") is None
        dc.put_entry("llm", "k", {"v": 1})  # no-op

    def test_record_roundtrip(self, monkeypatch):
        _record(monkeypatch)
        dc.put_entry("llm", "k1", {"v": {"answer": 42}})
        assert dc.get_entry("llm", "k1") == {"v": {"answer": 42}}

    def test_atomic_write_is_valid_json(self, monkeypatch):
        _record(monkeypatch)
        dc.put_entry("http", "k", {"text": "你好"})
        raw = (dc.get_cache_root() / "http" / "k.json").read_text(encoding="utf-8")
        assert json.loads(raw)["text"] == "你好"

    def test_replay_never_writes(self, monkeypatch):
        _replay(monkeypatch)
        dc.put_entry("llm", "k", {"v": 1})
        assert dc.get_entry("llm", "k") is None

    def test_miss_or_raise_only_in_replay(self, monkeypatch):
        _record(monkeypatch)
        dc.miss_or_raise("llm", "k", "x")  # no raise
        _replay(monkeypatch)
        with pytest.raises(dc.DiskCacheMissError):
            dc.miss_or_raise("llm", "k", "x")


class TestMessageRoundtrip:
    def test_basic(self):
        msg = SimpleNamespace(role="assistant", content="hi", reasoning_content="think",
                              tool_calls=[], usage_metadata={"prompt_tokens": 1})
        d = dc.message_to_cached_dict(msg)
        r = dc.message_from_cached_dict(d)
        assert r.content == "hi" and r.reasoning_content == "think"
        assert r.role == "assistant" and not r.tool_calls
        assert r.usage_metadata == {"prompt_tokens": 1}

    def test_tool_calls(self):
        tc = SimpleNamespace(id="c1", type="function",
                             function=SimpleNamespace(name="search", arguments='{"q": 1}'))
        msg = SimpleNamespace(role="assistant", content=None, reasoning_content=None, tool_calls=[tc])
        r = dc.message_from_cached_dict(dc.message_to_cached_dict(msg))
        assert len(r.tool_calls) == 1
        assert r.tool_calls[0].function.name == "search"
        assert r.tool_calls[0].function.arguments == '{"q": 1}'
        assert r.model_dump(exclude_none=True)["tool_calls"]

    def test_json_safe(self):
        msg = SimpleNamespace(role="assistant", content="中文", reasoning_content=None, tool_calls=None)
        json.loads(json.dumps(dc.message_to_cached_dict(msg), ensure_ascii=False))
