"""Domain types and rules shared by the instance generator, the models and the checks."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

GAP_MINUTES = 10


@dataclass(frozen=True)
class Task:
    id: int
    start: int
    end: int


@dataclass(frozen=True)
class Handler:
    id: int
    shift_start: int
    shift_end: int


@dataclass(frozen=True)
class AssignmentInstance:
    tasks: tuple[Task, ...]
    handlers: tuple[Handler, ...]


class Status(StrEnum):
    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"


@dataclass(frozen=True)
class Result:
    """A solve's outcome. For Model 1, `solution` maps each task id to its handler id."""

    status: Status
    objective: float | None
    bound: float | None
    gap: float | None
    solution: Mapping[int, int]


def conflict(a: Task, b: Task) -> bool:
    """True if one handler can't do both tasks, given the gap between them."""
    return a.start < b.end + GAP_MINUTES and b.start < a.end + GAP_MINUTES


def overtime(task: Task, handler: Handler) -> int:
    """Minutes of the task that fall outside the handler's shift window."""
    before = max(0, min(task.end, handler.shift_start) - task.start)
    after = max(0, task.end - max(task.start, handler.shift_end))
    return before + after
