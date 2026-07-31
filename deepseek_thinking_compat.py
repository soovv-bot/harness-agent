"""Compatibility helpers for reasoning-capable models over OpenAI-compatible APIs.

Provides two opt-in controls via environment variables:

    DEEPSEEK_THINKING_MODE=auto|enabled|disabled
        DeepSeek-only model selection (deepseek-chat vs deepseek-reasoner).

    LLM_THINKING_BUDGET_TOKENS=<int>
        For models that emit ``reasoning_content`` and expose a thinking-budget
        extension (passed through the OpenAI SDK ``extra_body``), cap the
        reasoning token budget so it doesn't consume the entire ``max_tokens``
        allocation and leave ``content`` empty. DeepSeek-reasoner manages its
        own reasoning internally and is skipped. Standard OpenAI models that
        produce no reasoning are unaffected when this is unset.

    LLM_STRUCTURER_MAX_TOKENS=<int>  (default 8000)
        When the auto-structuring fallback is triggered (see
        ``chat_completion_with_structuring``), the max_tokens for the second
        "structuring" call that converts reasoning_content into structured
        output. Must be large enough for the model's reasoning to finish
        naturally so content is emitted.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import os
import time
from loguru import logger


THINKING_MODE_ENV = "DEEPSEEK_THINKING_MODE"
THINKING_BUDGET_ENV = "LLM_THINKING_BUDGET_TOKENS"
SUPPORTED_DEEPSEEK_MODELS = {"deepseek-chat", "deepseek-reasoner"}


def get_thinking_mode() -> str:
    mode = (os.getenv(THINKING_MODE_ENV, "auto") or "auto").strip().lower()
    if mode not in {"auto", "enabled", "disabled"}:
        return "auto"
    return mode


def resolve_effective_model(model_id: str) -> str:
    mode = get_thinking_mode()
    if model_id not in SUPPORTED_DEEPSEEK_MODELS:
        return model_id
    if mode == "enabled":
        return "deepseek-reasoner"
    if mode == "disabled":
        return "deepseek-chat"
    return model_id


def build_chat_completion_kwargs(
    *,
    model_id: str,
    messages: list[Any],
    tools: Optional[list[Dict[str, Any]]] = None,
    temperature: Optional[float] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Build sanitized chat completion kwargs for DeepSeek thinking compatibility."""
    effective_model = resolve_effective_model(model_id)
    kwargs: Dict[str, Any] = {
        "model": effective_model,
        "messages": messages,
    }
    if tools is not None:
        kwargs["tools"] = tools

    # deepseek-reasoner ignores sampling controls and rejects some advanced params.
    if effective_model != "deepseek-reasoner" and temperature is not None:
        kwargs["temperature"] = temperature

    unsupported_on_reasoner = {
        "temperature",
        "top_p",
        "presence_penalty",
        "frequency_penalty",
        "logprobs",
        "top_logprobs",
    }
    for key, value in extra.items():
        if value is None:
            continue
        if effective_model == "deepseek-reasoner" and key in unsupported_on_reasoner:
            continue
        kwargs[key] = value

    # Reasoning-capable models that emit reasoning_content can spend the entire
    # max_tokens budget on reasoning, leaving content empty. When the caller
    # opts in via LLM_THINKING_BUDGET_TOKENS, inject a thinking budget through
    # the OpenAI SDK extra_body passthrough. DeepSeek-reasoner manages its own
    # reasoning internally, so it is skipped.
    if effective_model not in SUPPORTED_DEEPSEEK_MODELS:
        budget_raw = (os.getenv(THINKING_BUDGET_ENV) or "").strip()
        if budget_raw:
            try:
                budget = int(budget_raw)
            except ValueError:
                budget = 0
            if budget > 0:
                existing_extra = kwargs.get("extra_body") or {}
                if isinstance(existing_extra, dict):
                    existing_extra.setdefault("thinking", {})
                    if isinstance(existing_extra["thinking"], dict):
                        existing_extra["thinking"].setdefault("type", "enabled")
                        existing_extra["thinking"].setdefault("budget_tokens", budget)
                    kwargs["extra_body"] = existing_extra
                else:
                    kwargs["extra_body"] = {
                        "thinking": {"type": "enabled", "budget_tokens": budget}
                    }
    return kwargs


def assistant_message_to_dict(message: Any) -> Dict[str, Any]:
    """Serialize an assistant message while preserving reasoning_content when present."""
    if isinstance(message, dict):
        payload = dict(message)
    elif hasattr(message, "model_dump"):
        payload = message.model_dump(exclude_none=True)
    else:
        payload = {
            "role": getattr(message, "role", "assistant"),
            "content": getattr(message, "content", None),
        }

    reasoning_content = getattr(message, "reasoning_content", None)
    if reasoning_content and "reasoning_content" not in payload:
        payload["reasoning_content"] = reasoning_content
    return payload


def _get_structurer_max_tokens() -> int:
    raw = (os.getenv("LLM_STRUCTURER_MAX_TOKENS") or "").strip()
    try:
        val = int(raw)
        if val > 0:
            return val
    except ValueError:
        pass
    return 3000


def _build_structurer_prompt(reasoning_content: str, hint: str) -> str:
    """Build a structuring prompt using the reasoning's conclusion (tail).

    Reasoning models put their conclusions at the END of reasoning_content.
    Using the first N chars gives the model an incomplete analysis, causing it
    to re-reason from scratch and fill the entire token budget with new
    reasoning. Using the tail (conclusion) lets the model format it directly.
    """
    rlen = len(reasoning_content)
    # Use last 1500 chars (conclusion) + first 500 chars (context)
    if rlen <= 2000:
        excerpt = reasoning_content
    else:
        head = reasoning_content[:500]
        tail = reasoning_content[-1500:]
        excerpt = head + "\n...[truncated]...\n" + tail
    return (
        "You have completed your analysis. Now OUTPUT THE RESULT ONLY.\n"
        + hint
        + "\n\nStart your response with the appropriate opening tag immediately. "
        "No preamble, no explanation, no reasoning. Just the structured output.\n\n"
        "Your analysis (conclusion at the end):\n"
        + excerpt
    )


def _is_streaming_enabled() -> bool:
    """Check if streaming mode is enabled via environment variable."""
    raw = (os.getenv("LLM_STREAM_ENABLED") or "1").strip().lower()  # default: enabled
    return raw in {"1", "true", "yes", "y", "on"}


class _StreamedMessage:
    """Accumulated message from streaming chunks, mimicking the non-streamed response."""

    def __init__(self) -> None:
        self.role = "assistant"
        self.content: str = ""
        self.reasoning_content: str = ""
        self.tool_calls: list = []
        self._tool_call_map: dict = {}  # index -> dict with id, name, arguments

    def _merge_delta(self, delta: Any) -> None:
        """Merge a streaming delta into accumulated state."""
        # content
        dc = getattr(delta, "content", None)
        if dc:
            self.content += dc
        # reasoning_content
        dr = getattr(delta, "reasoning_content", None)
        if dr:
            self.reasoning_content += dr
        # tool_calls
        dtc = getattr(delta, "tool_calls", None)
        if dtc:
            for tc in dtc:
                idx = getattr(tc, "index", None)
                if idx is None:
                    continue
                slot = self._tool_call_map.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                if getattr(tc, "id", None):
                    slot["id"] = tc.id
                fn = getattr(tc, "function", None)
                if fn is not None:
                    if getattr(fn, "name", None):
                        slot["name"] = fn.name
                    if getattr(fn, "arguments", None):
                        slot["arguments"] += fn.arguments

    def _finalize(self) -> None:
        """Build tool_calls list from accumulated map."""
        from types import SimpleNamespace
        for idx in sorted(self._tool_call_map.keys()):
            slot = self._tool_call_map[idx]
            self.tool_calls.append(SimpleNamespace(
                id=slot["id"],
                type="function",
                function=SimpleNamespace(name=slot["name"], arguments=slot["arguments"]),
            ))

    def model_dump(self, **kwargs: Any) -> dict:
        d = {"role": self.role, "content": self.content or None}
        if self.reasoning_content:
            d["reasoning_content"] = self.reasoning_content
        if self.tool_calls:
            d["tool_calls"] = [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in self.tool_calls
            ]
        return d


def _stream_completion(
    client: Any,
    kwargs: dict,
    *,
    progress_label: str = "LLM",
) -> Any:
    """Execute a streaming chat completion and accumulate the result.

    Logs progress every ~10s to eliminate silent periods during long LLM calls.
    Returns a _StreamedMessage that mimics the non-streamed response object.
    """
    stream_kwargs = dict(kwargs)
    stream_kwargs["stream"] = True

    msg = _StreamedMessage()
    _t0 = time.time()
    _last_log = _t0
    chunk_count = 0

    try:
        stream = client.chat.completions.create(**stream_kwargs)
        for chunk in stream:
            chunk_count += 1
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            msg._merge_delta(delta)

            # Progress log every 10s
            now = time.time()
            if now - _last_log >= 10.0:
                elapsed = now - _t0
                c_len = len(msg.content)
                r_len = len(msg.reasoning_content)
                tc_n = len(msg._tool_call_map)
                logger.info(
                    f"[Stream] {progress_label} streaming... {elapsed:.0f}s elapsed, "
                    f"{chunk_count} chunks, content={c_len}c reasoning={r_len}c tool_calls={tc_n}"
                )
                _last_log = now

        msg._finalize()
        elapsed = time.time() - _t0
        c_len = len(msg.content)
        r_len = len(msg.reasoning_content)
        tc_n = len(msg.tool_calls)
        logger.info(
            f"[Stream] {progress_label} done in {elapsed:.1f}s | "
            f"content={c_len}c reasoning={r_len}c tool_calls={tc_n}"
        )
        return msg
    except Exception as exc:
        elapsed = time.time() - _t0
        logger.error(f"[Stream] {progress_label} failed after {elapsed:.1f}s: {exc}")
        raise


def chat_completion_with_structuring(
    client: Any,
    *,
    model_id: str,
    messages: list[Any],
    tools: Optional[list[Dict[str, Any]]] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    structurer_format_hint: str = "",
    **extra: Any,
) -> Any:
    """Chat completion with automatic structuring for reasoning-only models.

    Some reasoning models (e.g. GLM-5.2 on certain endpoints) always put their
    output in ``reasoning_content`` and leave ``content`` empty, regardless of
    thinking-budget or response-format controls. When this happens, the
    downstream parsers that expect structured tags/JSON in ``content`` fail.

    This wrapper makes the primary call. If ``content`` is empty but
    ``reasoning_content`` is populated (and there are no tool_calls), it makes
    a second "structuring" call with a simple prompt that asks the model to
    convert its reasoning into structured output. The structuring call uses a
    large max_tokens so the model's (naturally shorter) reasoning finishes and
    content is emitted.

    Returns the response message object. If structuring succeeded, returns the
    structurer's response (with content populated). Otherwise returns the
    original response.
    """
    kwargs = build_chat_completion_kwargs(
        model_id=model_id,
        messages=messages,
        tools=tools,
        temperature=temperature,
        max_tokens=max_tokens,
        **extra,
    )

    # Primary call — streaming if enabled
    if _is_streaming_enabled():
        response = _stream_completion(client, kwargs, progress_label="primary")
    else:
        completion = client.chat.completions.create(**kwargs)
        response = completion.choices[0].message

    content = (getattr(response, "content", None) or "").strip()
    reasoning_content = (getattr(response, "reasoning_content", None) or "").strip()
    tool_calls = getattr(response, "tool_calls", None)

    # Content populated, or tool calls present, or no reasoning to structure
    if content or tool_calls or not reasoning_content:
        return response

    # Content is empty, no tool calls, but reasoning is populated.
    # Strategy 1: Try to extract structured tags directly from reasoning_content
    # (fast, no API call). Reasoning models often produce the structured output
    # within their reasoning text.
    extracted = _extract_structured_from_reasoning(reasoning_content, structurer_format_hint)
    if extracted:
        try:
            # Create a synthetic response with the extracted content
            response.content = extracted
            return response
        except Exception:
            pass

    # Strategy 2: Make structuring call(s) with decreasing max_tokens.
    # Reasoning models fill the token budget with reasoning. Smaller max_tokens
    # forces the model to be concise and produce content. Try a few sizes.
    structurer_max = _get_structurer_max_tokens()
    hint = structurer_format_hint or "Output the result in the format described in the original task."
    structurer_prompt = _build_structurer_prompt(reasoning_content, hint)
    # Retry with decreasing max_tokens: [3000, 2000, 1500]
    for attempt_idx, attempt_max in enumerate((structurer_max, max(1500, structurer_max - 1000), max(1200, structurer_max - 1500))):
        structurer_kwargs = build_chat_completion_kwargs(
            model_id=model_id,
            messages=[{"role": "user", "content": structurer_prompt}],
            temperature=0.3,
            max_tokens=attempt_max,
        )
        try:
            if _is_streaming_enabled():
                structurer_response = _stream_completion(client, structurer_kwargs, progress_label=f"structurer#{attempt_idx+1}")
            else:
                structurer_completion = client.chat.completions.create(**structurer_kwargs)
                structurer_response = structurer_completion.choices[0].message
            structurer_content = (getattr(structurer_response, "content", None) or "").strip()
            # Also check if structurer put it in reasoning_content
            structurer_reasoning = (getattr(structurer_response, "reasoning_content", None) or "").strip()
            if structurer_content:
                return structurer_response
            if structurer_reasoning:
                extracted2 = _extract_structured_from_reasoning(structurer_reasoning, hint)
                if extracted2:
                    structurer_response.content = extracted2
                    return structurer_response
        except Exception:
            pass

    return response


def _extract_structured_from_reasoning(reasoning: str, format_hint: str) -> str:
    """Try to extract structured output tags directly from reasoning_content.

    Reasoning models often produce the final structured output (e.g. <planning>,
    <findings>, <answer>) within their reasoning text, even when the content
    field is empty. This avoids a second API call.
    """
    if not reasoning:
        return ""

    # Look for complete tag blocks in reasoning_content
    # Use a simple approach: find <tag>...</tag> and extract the content
    for tag_name in ("planning", "findings", "answer"):
        open_tag = f"<{tag_name}>"
        close_tag = f"</{tag_name}>"
        # Find all occurrences — use the last one (model may echo examples first)
        last_idx = reasoning.rfind(close_tag)
        if last_idx == -1:
            continue
        # Find the matching open tag before this close tag
        search_start = reasoning.rfind(open_tag, 0, last_idx)
        if search_start == -1:
            continue
        inner = reasoning[search_start + len(open_tag):last_idx].strip()
        if inner:
            return f"{open_tag}\n{inner}\n{close_tag}"

    return ""
