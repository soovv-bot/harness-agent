"""Run-level contracts: options in, results out (RD §6).

Pure data structures — no project imports (rule R1).

These types formalize the dicts currently returned by
``SearchHarnessPipeline.run()`` and the runners' ``run_single_task()`` /
grader. Producers migrate incrementally (RD migration discipline), so each
type carries a tolerant ``from_dict`` and preserves unknown keys via
``extra`` where the legacy surface is not yet fully mapped.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PipelineOptions:
    """Options accepted by the search harness pipeline (was loose kwargs)."""

    max_iterations: int = 6
    max_subtasks_per_batch: int = 3
    max_concurrency: int = 4
    time_budget_s: Optional[float] = None
    search_budget: Optional[int] = None
    crawl_budget: Optional[int] = None
    enable_query_critic: bool = True
    enable_subtask_critic: bool = True
    enable_verification: bool = True
    flags: Dict[str, Any] = field(default_factory=dict)  # forward-compat escape hatch

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_iterations": self.max_iterations,
            "max_subtasks_per_batch": self.max_subtasks_per_batch,
            "max_concurrency": self.max_concurrency,
            "time_budget_s": self.time_budget_s,
            "search_budget": self.search_budget,
            "crawl_budget": self.crawl_budget,
            "enable_query_critic": self.enable_query_critic,
            "enable_subtask_critic": self.enable_subtask_critic,
            "enable_verification": self.enable_verification,
            "flags": self.flags,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PipelineOptions":
        known = {f for f in cls.__dataclass_fields__ if f != "flags"}
        kwargs = {k: d[k] for k in known if k in d and d[k] is not None}
        extra = {k: v for k, v in d.items() if k not in known and k != "flags"}
        flags = dict(d.get("flags") or {})
        flags.update(extra)
        kwargs["flags"] = flags
        return cls(**kwargs)


@dataclass
class RunResult:
    """Result of one ``pipeline.run()`` invocation (was a plain dict)."""

    answer: str = ""
    status: str = "unknown"  # completed | max_iterations_reached | budget_exhausted | error | ...
    iterations: int = 0
    state: Dict[str, Any] = field(default_factory=dict)
    answer_payload: Dict[str, Any] = field(default_factory=dict)
    failure_category: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "status": self.status,
            "iterations": self.iterations,
            "state": self.state,
            "answer_payload": self.answer_payload,
            "failure_category": self.failure_category,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RunResult":
        return cls(
            answer=d.get("answer", "") or "",
            status=d.get("status", "unknown") or "unknown",
            iterations=d.get("iterations", 0) or 0,
            state=dict(d.get("state") or {}),
            answer_payload=dict(d.get("answer_payload") or {}),
            failure_category=d.get("failure_category", "") or "",
        )


@dataclass
class GradeResult:
    """Result of grading one answer against the reference."""

    correct: bool = False
    extracted_answer: str = ""
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "correct": self.correct,
            "extracted_answer": self.extracted_answer,
            "reasoning": self.reasoning,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GradeResult":
        return cls(
            correct=bool(d.get("correct", False)),
            extracted_answer=d.get("extracted_answer", "") or "",
            reasoning=d.get("reasoning", "") or d.get("reason", "") or "",
        )


@dataclass
class TaskResult:
    """One benchmark task's end-to-end result (runner-level record)."""

    task_index: int
    question: str = ""
    correct_answer: str = ""
    answer: str = ""
    extracted_answer: str = ""
    correct: bool = False
    status: str = "unknown"
    failure_category: str = ""
    iterations: int = 0
    latency_s: float = 0.0
    trajectory_path: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "task_index": self.task_index,
            "question": self.question,
            "correct_answer": self.correct_answer,
            "answer": self.answer,
            "extracted_answer": self.extracted_answer,
            "correct": self.correct,
            "status": self.status,
            "failure_category": self.failure_category,
            "iterations": self.iterations,
            "latency_s": self.latency_s,
        }
        if self.trajectory_path is not None:
            d["trajectory_path"] = self.trajectory_path
        d.update(self.extra)
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TaskResult":
        known = set(cls.__dataclass_fields__) - {"extra"}
        extra = {k: v for k, v in d.items() if k not in known}
        return cls(
            task_index=d.get("task_index", -1),
            question=d.get("question", "") or "",
            correct_answer=d.get("correct_answer", "") or "",
            answer=d.get("answer", "") or "",
            extracted_answer=d.get("extracted_answer", "") or "",
            correct=bool(d.get("correct", False)),
            status=d.get("status", "unknown") or "unknown",
            failure_category=d.get("failure_category", "") or "",
            iterations=d.get("iterations", 0) or 0,
            latency_s=d.get("latency_s", 0.0) or 0.0,
            trajectory_path=d.get("trajectory_path"),
            extra=extra,
        )
