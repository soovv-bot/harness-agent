"""Tests for llm_usage (M0 T8): thread-safe accumulation, tags, cost, snapshot."""
from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

import utils.llm_usage as llm_usage
from utils.llm_usage import UsageTracker, normalize_usage


@pytest.fixture(autouse=True)
def _fresh_pricing(monkeypatch):
    """No external pricing files — start from a clean cache."""
    monkeypatch.setenv("LLM_PRICING_JSON", "")
    monkeypatch.setenv("LLM_PRICING_YAML", "/nonexistent/model_pricing.yaml")
    llm_usage.reset_pricing_cache()
    yield
    llm_usage.reset_pricing_cache()


class TestNormalizeUsage:
    def test_none(self):
        assert normalize_usage(None) == {
            "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "reasoning_tokens": 0
        }

    def test_object(self):
        usage = SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            completion_tokens_details=SimpleNamespace(reasoning_tokens=3),
        )
        n = normalize_usage(usage)
        assert n["prompt_tokens"] == 10
        assert n["reasoning_tokens"] == 3

    def test_dict(self):
        n = normalize_usage({"prompt_tokens": "7", "completion_tokens": 2, "total_tokens": 0})
        assert n["total_tokens"] == 9  # recomputed when total missing/0

    def test_junk(self):
        assert normalize_usage({"prompt_tokens": "abc"})["prompt_tokens"] == 0


class TestTracker:
    def test_accumulates_by_model(self):
        t = UsageTracker()
        t.record("kimi-k3", {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
        t.record("kimi-k3", {"prompt_tokens": 6, "completion_tokens": 4, "total_tokens": 10})
        snap = t.snapshot()
        assert snap["total"]["calls"] == 2
        assert snap["total"]["prompt_tokens"] == 16
        assert snap["total"]["completion_tokens"] == 9
        assert snap["by_model"]["kimi-k3"]["calls"] == 2

    def test_cost_with_pricing(self, monkeypatch):
        monkeypatch.setenv("LLM_PRICING_JSON", '{"Kimi-K3": {"input": 1.0, "output": 2.0}}')
        llm_usage.reset_pricing_cache()
        t = UsageTracker()
        t.record("kimi-k3", {"prompt_tokens": 1_000_000, "completion_tokens": 500_000,
                             "total_tokens": 1_500_000})
        snap = t.snapshot()
        assert snap["pricing_known"] is True
        # 1.0 * 1 + 2.0 * 0.5 = 2.0 USD
        assert snap["by_model"]["kimi-k3"]["cost_usd"] == pytest.approx(2.0)
        assert snap["total"]["cost_usd"] == pytest.approx(2.0)

    def test_no_pricing_omits_cost(self):
        t = UsageTracker()
        t.record("unpriced-model", {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10})
        snap = t.snapshot()
        assert snap["pricing_known"] is False
        assert snap["by_model"]["unpriced-model"]["priced"] is False

    def test_tag_attribution(self):
        t = UsageTracker()
        with t.usage_tag("position_3"):
            t.record("m1", {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5})
        t.record("m1", {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})
        snap = t.snapshot()
        assert snap["by_tag"]["position_3"]["calls"] == 1
        assert snap["by_tag"]["position_3"]["total_tokens"] == 5
        assert snap["total"]["calls"] == 2  # untagged call still counted globally

    def test_tag_restores_after_nested(self):
        t = UsageTracker()
        with t.usage_tag("outer"):
            with t.usage_tag("inner"):
                pass
            assert t.current_tag() == "outer"
        assert t.current_tag() == ""

    def test_thread_safe(self):
        t = UsageTracker()

        def hammer(n: int) -> None:
            for _ in range(200):
                t.record("m", {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})

        threads = [threading.Thread(target=hammer, args=(i,)) for i in range(8)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        snap = t.snapshot()
        assert snap["total"]["calls"] == 1600
        assert snap["total"]["total_tokens"] == 3200

    def test_caller_buckets(self):
        t = UsageTracker()
        t.record("m", {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}, caller="primary")
        t.record("m", {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}, caller="structurer#1")
        snap = t.snapshot()
        assert snap["by_caller"]["primary"]["calls"] == 1
        assert snap["by_caller"]["structurer#1"]["calls"] == 1

    def test_reset(self):
        t = UsageTracker()
        t.record("m", {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10})
        t.reset()
        assert t.snapshot()["total"]["calls"] == 0

    def test_snapshot_json_serializable(self):
        import json

        t = UsageTracker()
        with t.usage_tag("p1"):
            t.record("m", {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}, caller="c")
        json.dumps(t.snapshot())  # must not raise


class TestLookupPrice:
    def test_longest_match_wins(self, monkeypatch):
        monkeypatch.setenv(
            "LLM_PRICING_JSON",
            '{"Kimi": {"input": 1, "output": 1}, "Kimi-K3": {"input": 2, "output": 4}}',
        )
        llm_usage.reset_pricing_cache()
        p = llm_usage.lookup_price("moonshot/kimi-k3-0905")
        assert p == {"input": 2.0, "output": 4.0}

    def test_default_fallback(self, monkeypatch):
        monkeypatch.setenv("LLM_PRICING_JSON", '{"default": {"input": 0.5, "output": 1.5}}')
        llm_usage.reset_pricing_cache()
        assert llm_usage.lookup_price("unknown-model") == {"input": 0.5, "output": 1.5}

    def test_none_when_empty(self):
        assert llm_usage.lookup_price("anything") is None
