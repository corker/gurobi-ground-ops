"""Seeded synthetic instances. Where the numbers come from is in docs/domain.md."""

import random

from ground_ops.domain import GAP_MINUTES, AssignmentInstance, CoverageInstance, Handler, ShiftPattern, Task

ARRIVALS_FROM = 6 * 60
ARRIVALS_UNTIL = 14 * 60
PUSH_BACK = 4
TASKS_PER_TURNAROUND = 2

UNLOAD = (7, 24, 10)
LOAD = (8, 20, 13)
GROUND_TIME = (26, 52, 28)

SHIFT_STARTS = range(5 * 60, 10 * 60 + 1, 30)
SHIFT_LENGTHS = (4 * 60, 6 * 60, 8 * 60)


def _minutes(rng: random.Random, low_high_mode: tuple[int, int, int]) -> int:
    low, high, mode = low_high_mode
    return round(rng.triangular(low, high, mode))


def _turnaround_tasks(rng: random.Random, first_id: int) -> tuple[Task, Task]:
    arrival = rng.randrange(ARRIVALS_FROM, ARRIVALS_UNTIL, 5)
    departure = arrival + _minutes(rng, GROUND_TIME)
    unload = Task(id=first_id, start=arrival, end=arrival + _minutes(rng, UNLOAD))
    load_end = departure - PUSH_BACK
    load = Task(id=first_id + 1, start=load_end - _minutes(rng, LOAD), end=load_end)
    return unload, load


def peak_concurrency(tasks: tuple[Task, ...]) -> int:
    """The most tasks that pairwise conflict at one moment: the fewest handlers that can cover them all."""
    return max((sum(1 for t in tasks if t.start <= p.start < t.end + GAP_MINUTES) for p in tasks), default=0)


def generate_assignment(n_tasks: int, seed: int, n_handlers: int | None = None) -> AssignmentInstance:
    """Model 1 instance with two baggage tasks per turnaround.

    By default there is one spare handler beyond the peak overlap. Fewer than the peak overlap makes it infeasible;
    the handlers are drawn in order, so a smaller count keeps the first handlers of the default instance.
    """
    if n_tasks < TASKS_PER_TURNAROUND or n_tasks % TASKS_PER_TURNAROUND:
        raise ValueError(f"the task count must be a positive multiple of {TASKS_PER_TURNAROUND}, got {n_tasks}")
    if n_handlers is not None and n_handlers < 0:
        raise ValueError(f"the handler count can't be negative, got {n_handlers}")
    rng = random.Random(seed)
    tasks = tuple(t for i in range(0, n_tasks, TASKS_PER_TURNAROUND) for t in _turnaround_tasks(rng, i))
    handlers = tuple(
        Handler(id=h, shift_start=start, shift_end=start + rng.choice(SHIFT_LENGTHS))
        for h in range(peak_concurrency(tasks) + 1 if n_handlers is None else n_handlers)
        for start in [rng.choice(SHIFT_STARTS)]
    )
    return AssignmentInstance(tasks=tasks, handlers=handlers)


def move_task(instance: AssignmentInstance, task_id: int, minutes: int) -> AssignmentInstance:
    """The same instance with one task shifted in time, as when a flight is delayed."""
    if all(t.id != task_id for t in instance.tasks):
        raise ValueError(f"there is no task {task_id}")
    tasks = tuple(
        Task(id=t.id, start=t.start + minutes, end=t.end + minutes) if t.id == task_id else t for t in instance.tasks
    )
    return AssignmentInstance(tasks=tasks, handlers=instance.handlers)


SLOTS_PER_DAY = 48
PATTERN_LENGTHS = (8, 12, 16)
MIN_LENGTH_WITH_BREAK = 12
# People needed per hour of the day, 00:00 to 23:00: quiet nights, a morning and an evening peak.
HOURLY_DEMAND = (1, 1, 1, 1, 1, 3, 8, 8, 8, 6, 6, 6, 5, 5, 5, 5, 7, 7, 7, 7, 4, 4, 2, 2)


def shift_patterns() -> tuple[ShiftPattern, ...]:
    """Every 4-, 6- and 8-hour shift that fits in the day; shifts of 6 hours or more break at the half-way slot."""
    starts_and_lengths = [(start, length) for length in PATTERN_LENGTHS for start in range(SLOTS_PER_DAY - length + 1)]
    return tuple(
        ShiftPattern(
            id=i,
            start=start,
            length=length,
            break_slot=start + length // 2 if length >= MIN_LENGTH_WITH_BREAK else None,
        )
        for i, (start, length) in enumerate(starts_and_lengths)
    )


def generate_coverage(seed: int) -> CoverageInstance:
    """Model 2 instance: the hourly demand profile, varied by up to one person per half-hour slot."""
    rng = random.Random(seed)
    demand = tuple(max(1, HOURLY_DEMAND[slot // 2] + rng.randint(-1, 1)) for slot in range(SLOTS_PER_DAY))
    return CoverageInstance(demand=demand, patterns=shift_patterns())
