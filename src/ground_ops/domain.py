"""Domain types and rules shared by the instance generator, the models and the checks."""

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

GAP_MINUTES = 10

# Strict: a wrong type is an error, never silently converted ("3" stays a string and is refused).
FROZEN = ConfigDict(frozen=True, strict=True)


class Task(BaseModel):
    model_config = FROZEN

    id: int
    start: int
    end: int


class Handler(BaseModel):
    model_config = FROZEN

    id: int
    shift_start: int
    shift_end: int


class AssignmentInstance(BaseModel):
    model_config = FROZEN

    tasks: tuple[Task, ...]
    handlers: tuple[Handler, ...]


class ShiftPattern(BaseModel):
    """A shift people can be rostered on, in half-hour slots. `break_slot` is unpaid and uncovered."""

    model_config = FROZEN

    id: int
    start: int
    length: int
    break_slot: int | None


class CoverageInstance(BaseModel):
    """Model 2: `demand[s]` is the number of people needed in half-hour slot `s`."""

    model_config = FROZEN

    demand: tuple[int, ...]
    patterns: tuple[ShiftPattern, ...]


class Status(StrEnum):
    OPTIMAL = "optimal"
    LIMIT_REACHED = "limit reached"
    INTERRUPTED = "interrupted"
    INFEASIBLE = "infeasible"


class Result(BaseModel):
    """A solve's outcome. `solution` maps task id to handler id (Model 1), or pattern id to people (Model 2).

    `iis` names the constraints of an irreducible inconsistent subsystem when Model 1 is infeasible: they can't all
    hold, but removing any one of them lets the rest of the list hold. The model may have other conflicts too.
    """

    model_config = FROZEN

    status: Status
    objective: float | None
    bound: float | None
    gap: float | None
    solution: Mapping[int, int]
    iis: tuple[str, ...] = ()


def conflict(a: Task, *, b: Task) -> bool:
    """True if one handler can't do both tasks, given the gap between them."""
    return a.start < b.end + GAP_MINUTES and b.start < a.end + GAP_MINUTES


def overtime(task: Task, *, handler: Handler) -> int:
    """Minutes of the task that fall outside the handler's shift window."""
    before = max(0, min(task.end, handler.shift_start) - task.start)
    after = max(0, task.end - max(task.start, handler.shift_end))
    return before + after


def covers(pattern: ShiftPattern, *, slot: int) -> bool:
    return pattern.start <= slot < pattern.start + pattern.length and slot != pattern.break_slot


def paid_slots(pattern: ShiftPattern) -> int:
    return pattern.length - (pattern.break_slot is not None)
