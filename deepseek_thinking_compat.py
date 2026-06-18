"""Compatibility helpers for DeepSeek thinking / non-thinking modes.

Supports a single environment switch:

    DEEPSEEK_THINKING_MODE=auto|enabled|disabled

Behavior for DeepSeek models:
- auto: keep the configured model as-is
- enabled: force deepseek-reasoner
- disabled: force deepseek-chat

For non-DeepSeek models, the helper is effectively a no-op.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import os


THINKING_MODE_ENV = "DEEPSEEK_THINKING_MODE"
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
