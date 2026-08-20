"""Compatibility helpers for reasoning-capable models over OpenAI-compatible APIs.

Provides two opt-in controls via environment variables:

    LLM_THINKING_BUDGET_TOKENS=<int>
        For models that emit ``reasoning_content`` and expose a thinking-budget
        extension, cap the reasoning token budget so it doesn't consume the
        entire ``max_tokens`` allocation and leave ``content`` empty. Standard
        OpenAI models that produce no reasoning are unaffected when this is
        unset.

    LLM_STRUCTURER_MAX_TOKENS=<int>  (default 3000)
        When the auto-structuring fallback is triggered (see
        ``chat_completion_with_structuring``), the max_tokens for the second
        "structuring" call that converts reasoning_content into structured
        output. Must be large enough for the model's reasoning to finish
        naturally so content is emitted.

Thinking control follows the OpenAI standard ``reasoning_effort`` parameter,
passed as a top-level kwarg. No vendor-specific ``extra_body`` injection is
performed. Supported values span the OpenAI o-series set plus the GLM-5 native
``max`` level (see below).

Effort values
--------------
This module accepts the union of two vendor vocabularies and forwards the
resolved value verbatim to the endpoint:

    OpenAI o-series (o1/o3/o4, GPT-5):  minimal | low | medium | high
    GLM-5 (Zhipu/Bigmodel):             max | high
                                         (``max`` is the default; any value
                                          other than ``high`` runs at ``max``)

``none`` is accepted as a backward-compatibility alias for ``minimal``.

GLM-5.2 notes
-------------
- GLM-5.2 has **no way to disable thinking** — it is always-on. Setting
  ``reasoning_effort=minimal``/``low``/``medium`` does NOT turn thinking off;
  on the native Zhipu API those values fall through to ``max``, and on some
  LiteLLM gateways they are remapped to ``high``. Use ``max`` for deepest
  reasoning and ``high`` for faster/lighter reasoning.
- OpenAI-standard ``minimal``/``low``/``medium`` are **not** part of the GLM-5
  spec. They are accepted here so the same config works against true OpenAI
  o-series endpoints without code changes; GLM-5 endpoints will reinterpret
  them as described above.

Kimi K3 notes
-------------
- Kimi K3 is always-on thinking and returns ``reasoning_content``. It honors
  only **three** effort levels: ``low`` | ``high`` | ``max`` (default ``max``).
  ``minimal`` and ``medium`` are **not** supported — sending them makes the
  endpoint silently fall back to ``max`` (the *strongest* reasoning), the
  opposite of what a ``minimal`` request intended.
- Per-model remapping (``minimal→low``, ``medium→high``) is now data-driven
  via ``model_profiles.yaml`` (see ``model_profiles.py``). Add/adjust a model
  there — no code changes needed.
- **Preserved thinking history**: Kimi K3 was trained to see its prior
  ``reasoning_content`` across turns. ``assistant_message_to_dict`` keeps
  ``reasoning_content`` on assistant messages, satisfying this requirement.
- The structurer skip heuristic (``_requested_effort_is_minimal``) is
  model-aware via the profile's ``minimal_effort_is_honored`` flag: for Kimi
  K3 a large ``reasoning_content`` under a "low" request is normal (the level
  is honored), not evidence the endpoint ignored the request, so the skip
  does not fire there.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import os
import time
from loguru import logger


THINKING_BUDGET_ENV = "LLM_THINKING_BUDGET_TOKENS"

# Accepted reasoning_effort values: OpenAI o-series set ∪ GLM-5 native set.
# ``none`` is a backward-compat alias for ``minimal`` (resolved in _resolve_effort).
# Per-model remapping (e.g. Kimi K3 minimal→low) is handled by model_profiles.
_VALID_EFFORTS = {"minimal", "low", "medium", "high", "max"}


def _resolve_effort(reasoning_effort_override: Optional[str]) -> Optional[str]:
    """Resolve the reasoning_effort value to inject.

    Precedence: explicit override > LLM_THINKING_BUDGET_TOKENS env > None.

    - Override accepts OpenAI standard values (minimal/low/medium/high) plus
      the GLM-5 native ``max`` level. ``none`` is accepted as an alias for
      ``minimal`` (weakest reasoning) for backward compatibility with existing
      ``EXECUTOR_THINKING=none`` configs.
    - When no override and no budget env is set, returns None → don't inject
      reasoning_effort; let the endpoint apply its default.
    - Budget → effort mapping (only when env is set):
        budget <= 0    → "minimal" (weakest)
        budget <= 1024 → "low"
        budget <= 4096 → "medium"
        budget > 4096  → "high"
    """
    if reasoning_effort_override:
        if reasoning_effort_override == "none":
            return "minimal"
        return reasoning_effort_override
    budget_raw = (os.getenv(THINKING_BUDGET_ENV) or "").strip()
    if not budget_raw:
        return None
    try:
        budget = int(budget_raw)
    except ValueError:
        return None
    if budget <= 0:
        return "minimal"
    if budget <= 1024:
        return "low"
    if budget <= 4096:
        return "medium"
    return "high"


def build_chat_completion_kwargs(
    *,
    model_id: str,
    messages: list[Any],
    tools: Optional[list[Dict[str, Any]]] = None,
    temperature: Optional[float] = None,
    reasoning_effort_override: Optional[str] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Build sanitized chat completion kwargs for OpenAI-compatible endpoints.

    ``reasoning_effort_override`` (when set) takes precedence over the
    ``LLM_THINKING_BUDGET_TOKENS`` env-derived effort, allowing per-role control
    (e.g. executor disables thinking while planner keeps it). When neither is
    set, ``reasoning_effort`` is not injected and the endpoint default applies.
    """
    kwargs: Dict[str, Any] = {
        "model": model_id,
        "messages": messages,
    }
    if tools is not None:
        kwargs["tools"] = tools
    if temperature is not None:
        kwargs["temperature"] = temperature

    for key, value in extra.items():
        if value is None:
            continue
        kwargs[key] = value

    effort = _resolve_effort(reasoning_effort_override)
    if effort:
        # Per-model remap (e.g. Kimi K3 minimal→low) via model_profiles.yaml.
        try:
            from model_profiles import get_model_profile
            effort = get_model_profile(model_id).snap_effort(effort)
        except Exception:
            pass  # fall back to resolved effort if profiles unavailable
        if effort:
            kwargs["reasoning_effort"] = effort
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


def _structurer_skip_threshold() -> int:
    """Reasoning_content char count above which we assume the endpoint ignored
    reasoning_effort=none and skip the structurer chain entirely.

    Empirically (2026-08-04 run): when none was honored, reasoning maxed at
    ~4005c; when ignored, reasoning min was ~5683c. 5000 cleanly separates.
    Override via LLM_STRUCTURER_SKIP_THRESHOLD_CHARS.
    """
    raw = (os.getenv("LLM_STRUCTURER_SKIP_THRESHOLD_CHARS") or "").strip()
    try:
        val = int(raw)
        if val > 0:
            return val
    except ValueError:
        pass
    return 5000


def _requested_effort_is_minimal(reasoning_effort_override: Optional[str], model_id: str = "") -> bool:
    """Mirror _resolve_effort to detect whether the requested effort for THIS
    call was the weakest setting (minimal / "none" alias / budget<=0).

    Used by the structurer skip logic: if the primary call requested minimal
    reasoning but came back with a large reasoning_content, the endpoint likely
    ignored reasoning_effort and the structurer chain would also fail.

    Model-aware via model_profiles.yaml: delegates to the profile's
    ``is_minimal_request`` (which accounts for whether the model honors
    minimal/low — e.g. Kimi K3 does, so big reasoning is normal, not a skip
    signal). Falls back to the legacy env/budget check if profiles unavailable.
    """
    try:
        from model_profiles import get_model_profile
        return get_model_profile(model_id).is_minimal_request(reasoning_effort_override)
    except Exception:
        pass
    if reasoning_effort_override:
        return reasoning_effort_override in ("none", "minimal")
    budget_raw = (os.getenv(THINKING_BUDGET_ENV) or "").strip()
    if not budget_raw:
        return False  # no budget → None (endpoint default), not minimal
    try:
        return int(budget_raw) <= 0
    except ValueError:
        return False


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


def _env_false(name: str) -> bool:
    """True when an env var is explicitly set to a falsy string."""
    return (os.getenv(name) or "").strip().lower() in {"0", "false", "no", "n", "off"}


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


def _record_usage_safely(model_id: str, usage: Any, *, caller: str = "") -> None:
    """Best-effort usage recording — metering must never break generation."""
    try:
        from llm_usage import record_usage

        record_usage(model_id, usage, caller=caller)
    except Exception:
        pass


def _stream_timeout_s() -> Optional[float]:
    """Wall-clock stream timeout. Defaults to LLM_TIMEOUT_S so the configured
    timeout is actually enforced on streaming responses (httpx per-read timeout
    never fires while chunks keep arriving, so a runaway reasoning stream would
    otherwise hang forever — root cause of grader hangs observed 2026-08-04)."""
    raw = (os.getenv("LLM_STREAM_TIMEOUT_S") or "").strip()
    if raw:
        try:
            v = float(raw)
            return v if v > 0 else None
        except ValueError:
            pass
    raw = (os.getenv("LLM_TIMEOUT_S") or "").strip()
    if raw:
        try:
            v = float(raw)
            return v if v > 0 else None
        except ValueError:
            pass
    return None


def _stream_completion(
    client: Any,
    kwargs: dict,
    *,
    progress_label: str = "LLM",
) -> Any:
    """Execute a streaming chat completion and accumulate the result.

    Logs progress every ~10s to eliminate silent periods during long LLM calls.
    Returns a _StreamedMessage that mimics the non-streamed response object.

    A wall-clock stream timeout (``LLM_STREAM_TIMEOUT_S``, default ``LLM_TIMEOUT_S``)
    closes the stream and raises ``TimeoutError`` when exceeded — guards against
    endpoints that ignore ``reasoning_effort`` and emit unbounded reasoning with
    no content, which would otherwise hang the caller indefinitely.
    """
    stream_kwargs = dict(kwargs)
    stream_kwargs["stream"] = True
    # Ask the gateway to attach token usage on the final chunk (OpenAI-standard
    # stream_options). Some gateways 400 on unknown params — one retry without
    # it, and if no usage arrives we fall back to zero-token record so the
    # call is still counted.
    want_usage = not _env_false("LLM_STREAM_INCLUDE_USAGE")
    if want_usage and "stream_options" not in stream_kwargs:
        stream_kwargs["stream_options"] = {"include_usage": True}

    msg = _StreamedMessage()
    _t0 = time.time()
    _last_log = _t0
    chunk_count = 0
    stream_timeout = _stream_timeout_s()
    stream_usage = None

    stream = None
    try:
        try:
            stream = client.chat.completions.create(**stream_kwargs)
        except Exception as exc:
            if want_usage and "stream_options" in stream_kwargs and "stream_options" in str(exc).lower():
                logger.warning(f"[Stream] {progress_label} gateway rejected stream_options; retrying without it")
                stream_kwargs.pop("stream_options", None)
                stream = client.chat.completions.create(**stream_kwargs)
            else:
                raise
        for chunk in stream:
            chunk_count += 1
            if getattr(chunk, "usage", None):
                stream_usage = chunk.usage
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            msg._merge_delta(delta)

            # Progress log every 10s
            now = time.time()
            elapsed = now - _t0
            # Wall-clock stream timeout: close + raise so callers can degrade.
            if stream_timeout and elapsed >= stream_timeout:
                c_len = len(msg.content)
                r_len = len(msg.reasoning_content)
                logger.warning(
                    f"[Stream] {progress_label} TIMEOUT after {elapsed:.0f}s "
                    f"(limit {stream_timeout:.0f}s) | chunks={chunk_count} "
                    f"content={c_len}c reasoning={r_len}c — closing stream"
                )
                try:
                    stream.close()
                except Exception:
                    pass
                raise TimeoutError(
                    f"stream timeout after {elapsed:.0f}s (limit {stream_timeout:.0f}s) "
                    f"[{progress_label}] chunks={chunk_count} content={c_len}c reasoning={r_len}c"
                )
            if now - _last_log >= 10.0:
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
        _record_usage_safely(kwargs.get("model", ""), stream_usage, caller=progress_label)
        if stream_usage:
            try:
                from llm_usage import normalize_usage
                n = normalize_usage(stream_usage)
                msg.usage_metadata = n  # surfaced for recorder attribution
            except Exception:
                pass
        return msg
    except Exception as exc:
        elapsed = time.time() - _t0
        logger.error(f"[Stream] {progress_label} failed after {elapsed:.1f}s: {exc}")
        raise
    finally:
        if stream is not None:
            try:
                stream.close()
            except Exception:
                pass


def chat_completion_with_structuring(
    client: Any,
    *,
    model_id: str,
    messages: list[Any],
    tools: Optional[list[Dict[str, Any]]] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    structurer_format_hint: str = "",
    reasoning_effort_override: Optional[str] = None,
    structurer_reasoning_effort_override: Optional[str] = "minimal",
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

    ``reasoning_effort_override`` is forwarded to the primary call for per-role
    control (e.g. executor="none"). The structurer call uses a separate,
    lower effort (``structurer_reasoning_effort_override``, default ``"minimal"``)
    because structuring is a mechanical extraction/reformatting task — using
    the primary's high effort on a simple prompt causes reasoning starvation
    (0 content + large reasoning) on models like Kimi-K3.

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
        reasoning_effort_override=reasoning_effort_override,
        **extra,
    )

    # Primary call — streaming if enabled
    if _is_streaming_enabled():
        response = _stream_completion(client, kwargs, progress_label="primary")
    else:
        completion = client.chat.completions.create(**kwargs)
        response = completion.choices[0].message
        _record_usage_safely(model_id, getattr(completion, "usage", None), caller="primary")
        try:
            from llm_usage import normalize_usage
            response.usage_metadata = normalize_usage(getattr(completion, "usage", None))
        except Exception:
            pass

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
    #
    # For models that do NOT honor minimal effort (e.g. GLM-5.2 maps minimal→max),
    # the skip guard is harmful: it abandons structuring entirely and returns
    # 0-content, wasting the whole turn. Instead, always attempt structuring
    # with progressively smaller max_tokens to force concise content output.
    #
    # Guard: skip structurer chain only when the model HONORS minimal effort
    # AND both primary and structurer used minimal AND reasoning exceeded the
    # threshold (proving the endpoint ignored minimal). When the model does
    # not honor minimal (minimal_effort_is_honored=False), never skip — try
    # with smaller budgets instead.
    _model_honors_minimal = True
    try:
        from model_profiles import get_model_profile
        _model_honors_minimal = get_model_profile(model_id).minimal_effort_is_honored
    except Exception:
        pass

    if (_model_honors_minimal
            and _requested_effort_is_minimal(structurer_reasoning_effort_override, model_id)
            and _requested_effort_is_minimal(reasoning_effort_override, model_id)
            and len(reasoning_content) > _structurer_skip_threshold()):
        logger.warning(
            f"[Structurer] skipping chain: primary 0-content but reasoning={len(reasoning_content)}c "
            f"(>{_structurer_skip_threshold()}c) indicates endpoint ignored reasoning_effort=minimal; "
            f"structurer (also minimal) would fail too — returning 0-content for caller degradation"
        )
        return response

    structurer_max = _get_structurer_max_tokens()
    hint = structurer_format_hint or "Output the result in the format described in the original task."
    structurer_prompt = _build_structurer_prompt(reasoning_content, hint)
    # For models that ignore minimal effort, use smaller max_tokens to force
    # content over reasoning. Try: [structurer_max, 1500, 1000, 800].
    # The smaller budgets force the model to stop reasoning and emit content.
    if not _model_honors_minimal:
        attempt_budgets = (structurer_max, 1500, 1000, 800)
    else:
        attempt_budgets = (structurer_max, max(1500, structurer_max - 1000), max(1200, structurer_max - 1500))
    for attempt_idx, attempt_max in enumerate(attempt_budgets):
        structurer_kwargs = build_chat_completion_kwargs(
            model_id=model_id,
            messages=[{"role": "user", "content": structurer_prompt}],
            temperature=0.3,
            max_tokens=attempt_max,
            reasoning_effort_override=structurer_reasoning_effort_override,
        )
        try:
            if _is_streaming_enabled():
                structurer_response = _stream_completion(client, structurer_kwargs, progress_label=f"structurer#{attempt_idx+1}")
            else:
                structurer_completion = client.chat.completions.create(**structurer_kwargs)
                structurer_response = structurer_completion.choices[0].message
                _record_usage_safely(model_id, getattr(structurer_completion, "usage", None),
                                     caller=f"structurer#{attempt_idx+1}")
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
        # Early-break: for models that HONOR minimal effort, reaching here means
        # attempt #1 (largest budget) returned 0 content AND 0 extractable
        # reasoning. Attempts #2/#3 use the same structurer effort with a SMALLER
        # max_tokens — they cannot recover. Empirically (2026-08-04) #2/#3 never
        # succeeded when #1 failed (7/7).
        # For models that do NOT honor minimal (GLM-5.2): smaller budgets CAN
        # force content, so don't early-break — try all budgets.
        if attempt_idx == 0 and _model_honors_minimal:
            logger.warning(
                f"[Structurer] early-break after #1 (0-content, 0-extracted): "
                f"#2/#3 same effort + smaller budget won't recover"
            )
            break

    # Last-resort: if all structurer attempts failed, try broader extraction
    # from the original reasoning_content. Some models write JSON or plain
    # text answers in reasoning without XML tags. Returning non-empty content
    # here lets the caller's parser attempt to make sense of it.
    if not (getattr(response, "content", None) or "").strip():
        json_extracted = _extract_json_from_reasoning(reasoning_content)
        if json_extracted:
            logger.info(
                f"[Structurer] last-resort JSON extraction from reasoning "
                f"succeeded ({len(json_extracted)}c) after all structurer "
                f"attempts failed"
            )
            try:
                response.content = json_extracted
            except Exception:
                pass

    return response


def _extract_json_from_reasoning(reasoning: str) -> str:
    """Extract a JSON object or array from reasoning_content as a last resort.

    Reasoning models sometimes produce the final JSON output within their
    reasoning text (e.g. query_critic results). This catches cases where
    _extract_structured_from_reasoning found no XML tags but the model still
    wrote valid JSON in reasoning.
    """
    if not reasoning:
        return ""
    import re
    # Try to find a JSON array first (query_critic output)
    arr_match = re.search(r'\[[^\[]*?\{.*?\}[^\]]*?\]', reasoning, re.DOTALL)
    if arr_match:
        candidate = arr_match.group(0)
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            pass
    # Try a JSON object
    obj_match = re.search(r'\{.*\}', reasoning, re.DOTALL)
    if obj_match:
        candidate = obj_match.group(0)
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            pass
    return ""


def _extract_structured_from_reasoning(reasoning: str, format_hint: str) -> str:
    """Try to extract structured output tags directly from reasoning_content.

    Reasoning models often produce the final structured output (e.g. <planning>,
    <findings>, <answer>) within their reasoning text, even when the content
    field is empty. This avoids a second API call.
    """
    if not reasoning:
        return ""

    # JSON fallback: if the format hint mentions JSON, or if reasoning
    # contains a JSON object, extract it. GLM-5.2 reasoning models fill all
    # tokens with reasoning and leave content empty; the JSON answer is often
    # present in reasoning_content.
    import re as _re
    json_match = _re.search(r'\{[^{}]*"(?:extracted|correct|reason|answer)"[^{}]*\}', reasoning, _re.DOTALL)
    if json_match:
        return json_match.group()
    # Broader JSON search — any complete {...} block
    json_broad = _re.search(r'\{.*\}', reasoning, _re.DOTALL)
    if json_broad and ('"correct"' in json_broad.group() or '"extracted"' in json_broad.group()):
        return json_broad.group()

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
