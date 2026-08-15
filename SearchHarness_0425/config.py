"""
Central configuration for SearchHarness.

Consolidates the previously scattered os.getenv calls and hardcoded
model-name defaults (9 occurrences across 8 files) into a single
dataclass-based config. No model name is hardcoded: MODEL_NAME must be
set via env (empty default). Existing code reads via `settings()` for
new refactors; legacy os.getenv calls remain for backward compatibility
but should migrate over time.

Usage:
    from config import settings
    s = settings()
    client = build_openai_client(s.api_base, s.api_key)
    model_id = s.model_id
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional


def _env(name: str, default: str = "") -> str:
    """Read an env var as a stripped string (empty string if unset/blank)."""
    return (os.getenv(name) or default).strip()


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class LLMConfig:
    """LLM API endpoint + model selection."""
    api_base: str
    api_key: str
    model_id: str
    executor_model_id: str
    executor_reasoning_effort: str
    timeout_s: int
    thinking_budget_tokens: int


@dataclass(frozen=True)
class GraderConfig:
    """Optional separate grader model (defaults to LLMConfig if unset)."""
    api_base: str
    api_key: str
    model_id: str


@dataclass(frozen=True)
class ToolsConfig:
    """External tool API keys + engine selection."""
    serper_api_key: str
    jina_api_key: str
    crawler_engine: str


@dataclass(frozen=True)
class PromptConfig:
    """Prompt-mode feature flags."""
    planner_simple_prompt: bool
    executor_simple_prompt: bool


@dataclass(frozen=True)
class LoggingConfig:
    """Logging level + format."""
    level: str


@dataclass(frozen=True)
class Settings:
    """Top-level settings aggregating all config groups."""
    llm: LLMConfig
    grader: GraderConfig
    tools: ToolsConfig
    prompt: PromptConfig
    logging: LoggingConfig

    # Convenience accessors (flat) for the most-used fields.
    @property
    def api_base(self) -> str:
        return self.llm.api_base

    @property
    def api_key(self) -> str:
        return self.llm.api_key

    @property
    def model_id(self) -> str:
        return self.llm.model_id

    @property
    def executor_model_id(self) -> str:
        return self.llm.executor_model_id or self.llm.model_id

    @property
    def executor_reasoning_effort(self) -> str:
        return self.llm.executor_reasoning_effort


_DEFAULT_MODEL = ""  # model-agnostic; set MODEL_NAME env to select the model


def settings() -> Settings:
    """Build a Settings instance from environment variables.

    Call this lazily (not at import time) so .env changes after import
    are respected, and so tests can monkeypatch os.environ.
    """
    llm = LLMConfig(
        api_base=_env("OPENAI_BASE_URL"),
        api_key=_env("OPENAI_API_KEY"),
        model_id=_env("MODEL_NAME", _DEFAULT_MODEL) or _DEFAULT_MODEL,
        executor_model_id=_env("EXECUTOR_MODEL_NAME", "") or _env("MODEL_NAME", _DEFAULT_MODEL),
        executor_reasoning_effort=_env("EXECUTOR_THINKING", ""),
        timeout_s=_env_int("LLM_TIMEOUT_S", 600),
        thinking_budget_tokens=_env_int("LLM_THINKING_BUDGET_TOKENS", 1000),
    )
    grader = GraderConfig(
        api_base=_env("GRADER_API_BASE") or _env("GRADER_OPENAI_BASE_URL") or llm.api_base,
        api_key=_env("GRADER_API_KEY") or _env("GRADER_OPENAI_API_KEY") or llm.api_key,
        model_id=_env("GRADER_MODEL") or _env("GRADER_MODEL_NAME") or llm.model_id,
    )
    tools = ToolsConfig(
        serper_api_key=_env("SERPER_API_KEY"),
        jina_api_key=_env("JINA_API_KEY"),
        crawler_engine=_env("CRAWLER_ENGINE", "jina"),
    )
    prompt = PromptConfig(
        planner_simple_prompt=_env_bool("PLANNER_SIMPLE_PROMPT"),
        executor_simple_prompt=_env_bool("EXECUTOR_SIMPLE_PROMPT"),
    )
    logging_cfg = LoggingConfig(
        level=_env("LOG_LEVEL", "INFO"),
    )
    return Settings(
        llm=llm,
        grader=grader,
        tools=tools,
        prompt=prompt,
        logging=logging_cfg,
    )
