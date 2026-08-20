"""Shared test fixtures for SearchHarness pipeline tests.

Provides:
- ``FakeOpenAIClient`` / ``fake_openai_client``: an OpenAI-compatible client
  whose ``chat.completions.create`` returns scripted responses. Supports both
  the streaming and non-streaming code paths used by
  ``chat_completion_with_structuring`` so tests don't depend on
  ``LLM_STREAM_ENABLED``.
- ``patch_llm_clients``: a pytest fixture/autouse helper that monkeypatches
  ``build_openai_client`` in every consumer module so the pipeline and its
  agents use the fake client without real network calls.
- stub search tools (``stub_search_tools``): replaces ``ToolProcessor.tools``
  entries with deterministic in-memory implementations.

The fake client is intentionally minimal: it only implements the surface area
exercised by the pipeline (``client.chat.completions.create`` returning an
object with ``.choices[0].message`` carrying ``content`` / ``reasoning_content``
/ ``tool_calls``). No real ``openai`` package is required to run these tests.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional

import pytest

# Put the SearchHarness_0425 dir on sys.path so `import query_critic` works
# the same way the existing tests/test_core_rules.py does it.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# The `tools` package (tool_processor, search_tools) is now local at
# SearchHarness_0425/tools/, importable directly since PROJECT_ROOT is on sys.path.

# Consumer modules that do `from openai_client_factory import build_openai_client`
# and store the imported name in their own namespace. Each must be patched.
LLM_CLIENT_CONSUMERS = [
    "planning_agent_v3",
    "search_agent_v3",
    "subtask_critic",
    "query_critic",
    "search_crawl_controller",
    "search_finalizer",
    "planning_direction_critic",
    "llm_client",
]


class _FakeToolCall:
    """Mimics an OpenAI streaming tool_call delta."""

    def __init__(self, index: int, call_id: str, name: str, arguments: str) -> None:
        self.index = index
        self.id = call_id
        self.type = "function"
        self.function = SimpleNamespace(name=name, arguments=arguments)


class _FakeDelta:
    def __init__(self, content: str, reasoning_content: str, tool_calls: List[_FakeToolCall]) -> None:
        self.content = content
        self.reasoning_content = reasoning_content
        self.tool_calls = tool_calls


class _FakeChoice:
    def __init__(self, message: SimpleNamespace) -> None:
        # Non-streaming path reads .message; streaming path reads .delta.
        self.message = message
        self.delta = _FakeDelta(
            content=message.content or "",
            reasoning_content=message.reasoning_content or "",
            tool_calls=list(message.tool_calls or []),
        )


class _FakeCompletion:
    def __init__(self, message: SimpleNamespace) -> None:
        self.choices = [_FakeChoice(message)]


class _FakeChatCompletions:
    def __init__(self, responder: Callable[[Dict[str, Any]], SimpleNamespace]) -> None:
        self._responder = responder
        self.calls: List[Dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        message = self._responder(kwargs)
        completion = _FakeCompletion(message)
        if kwargs.get("stream"):
            # Streaming path iterates over chunks; one chunk carrying the full
            # message is sufficient for _StreamedMessage._merge_delta.
            return iter([completion])
        return completion


class FakeOpenAIClient:
    """Minimal OpenAI-compatible client for tests.

    ``responder`` receives the raw kwargs of each ``create`` call and returns a
    ``SimpleNamespace`` message with ``content`` / ``reasoning_content`` /
    ``tool_calls``. Use ``ScriptedResponder`` for ordered, content-keyed scripts.
    """

    def __init__(self, responder: Callable[[Dict[str, Any]], SimpleNamespace]) -> None:
        self.chat = SimpleNamespace(completions=_FakeChatCompletions(responder))

    @property
    def calls(self) -> List[Dict[str, Any]]:
        return self.chat.completions.calls


def make_message(
    content: str = "",
    reasoning_content: str = "",
    tool_calls: Optional[List[Dict[str, Any]]] = None,
) -> SimpleNamespace:
    """Build a fake assistant message with OpenAI-shaped tool_calls."""
    tcs: List[_FakeToolCall] = []
    for i, tc in enumerate(tool_calls or []):
        tcs.append(_FakeToolCall(
            index=i,
            call_id=tc.get("id", f"call_{i}"),
            name=tc["name"],
            arguments=tc.get("arguments", "") if isinstance(tc.get("arguments"), str) else __import__("json").dumps(tc.get("arguments", {}), ensure_ascii=False),
        ))
    return SimpleNamespace(
        role="assistant",
        content=content or None,
        reasoning_content=reasoning_content or None,
        tool_calls=tcs,
    )


class ScriptedResponder:
    """Returns scripted messages in call order, keyed by an optional matcher.

    If ``scripts`` is a list, each LLM call pops the next message. If a matcher
    is provided, it is called with (messages, kwargs) and should return the
    index into ``scripts``; otherwise scripts are consumed sequentially.
    """

    def __init__(self, scripts: List[SimpleNamespace]) -> None:
        self._scripts: List[SimpleNamespace] = list(scripts)
        self._cursor = 0

    def __call__(self, kwargs: Dict[str, Any]) -> SimpleNamespace:
        if self._cursor >= len(self._scripts):
            # Default: empty content (signals "nothing to say")
            return make_message(content="")
        msg = self._scripts[self._cursor]
        self._cursor += 1
        return msg


def install_fake_llm(monkeypatch: pytest.MonkeyPatch, responder: Callable[[Dict[str, Any]], SimpleNamespace]) -> FakeOpenAIClient:
    """Patch every consumer module's ``build_openai_client`` to return a fake.

    Returns the fake client so tests can inspect ``.calls``.
    """
    fake_client = FakeOpenAIClient(responder)

    def fake_factory(api_base: str = "", api_key: str = "", *, timeout_s: Optional[float] = None, **_: Any) -> FakeOpenAIClient:
        return fake_client

    import importlib
    for mod_name in LLM_CLIENT_CONSUMERS:
        mod = importlib.import_module(mod_name)
        monkeypatch.setattr(mod, "build_openai_client", fake_factory, raising=False)
    return fake_client


@pytest.fixture()
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> Callable[[Callable[[Dict[str, Any]], SimpleNamespace]], FakeOpenAIClient]:
    """Fixture returning a callable that installs a fake LLM responder."""
    return lambda responder: install_fake_llm(monkeypatch, responder)


def stub_tool_processor(monkeypatch: pytest.MonkeyPatch) -> Dict[str, Callable[[Dict[str, Any]], str]]:
    """Replace ToolProcessor's search/visit_urls/search_wiki with in-memory stubs.

    Returns the dict of stub callables so tests can spy on invocations.
    """
    import importlib
    tool_processor_mod = importlib.import_module("tools.tool_processor")  # local package
    # Patch the bound methods on the class so every ToolProcessor() instance
    # uses the stubs. Each stub returns a JSON string (the executor wraps it).
    calls: Dict[str, List[Dict[str, Any]]] = {"search": [], "visit_urls": [], "search_wiki": []}

    def _stub_search(arguments: Dict[str, Any]) -> str:
        queries = arguments.get("query", []) or []
        # Deterministic fake SERP: one organic result per query.
        results = []
        for i, q in enumerate(queries):
            results.append({
                "title": f"Result {i} for {q}",
                "link": f"https://example.com/{i}",
                "snippet": f"Snippet about {q}. Candidate: AlphaEntity.",
            })
        import json
        return json.dumps({"organic": results}, ensure_ascii=False)

    def _stub_visit_urls(arguments: Dict[str, Any]) -> str:
        urls = arguments.get("urls", []) or []
        import json
        return json.dumps(
            [{"url": u, "content": f"Page content for {u}. Mentions AlphaEntity confirmed."} for u in urls],
            ensure_ascii=False,
        )

    def _stub_search_wiki(arguments: Dict[str, Any]) -> str:
        entities = arguments.get("entities", []) or []
        import json
        return json.dumps(
            {e: {"summary": f"Wikipedia summary for {e}."} for e in entities},
            ensure_ascii=False,
        )

    stubs = {
        "search": _stub_search,
        "visit_urls": _stub_visit_urls,
        "search_wiki": _stub_search_wiki,
    }

    original_init = tool_processor_mod.ToolProcessor.__init__

    def _patched_init(self: Any) -> None:
        original_init(self)
        for name, fn in stubs.items():
            self.tools[name] = fn

    monkeypatch.setattr(tool_processor_mod.ToolProcessor, "__init__", _patched_init)
    return stubs
