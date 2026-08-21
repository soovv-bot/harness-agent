"""Contract layer — pure data structures shared across layers (RD §6).

L0 of the dependency stack: this package must never import any other project
module (rule R1). Everything here is a stdlib dataclass or a lightweight
validator; no network, no config, no business logic.
"""

from contract.agent import Findings, Plan, PlanStep, Subtask, SubtaskResult
from contract.candidate import CandidateRecord, QueryRecord, QueryVerdict
from contract.run import GradeResult, PipelineOptions, RunResult, TaskResult
from contract.trajectory import (
    Message,
    ToolResult,
    TrajectoryDoc,
    TrajectoryEvent,
)

__all__ = [
    "Findings",
    "Plan",
    "PlanStep",
    "Subtask",
    "SubtaskResult",
    "CandidateRecord",
    "QueryRecord",
    "QueryVerdict",
    "GradeResult",
    "PipelineOptions",
    "RunResult",
    "TaskResult",
    "Message",
    "ToolResult",
    "TrajectoryDoc",
    "TrajectoryEvent",
]
