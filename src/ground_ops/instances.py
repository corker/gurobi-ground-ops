"""Seeded synthetic instances. Duration ranges follow the dataset described in docs/domain.md."""

import random

from ground_ops.domain import GAP_MINUTES, AssignmentInstance, Handler, Task

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
    unload = Task(first_id, arrival, arrival + _minutes(rng, UNLOAD))
    load_end = departure - PUSH_BACK
    load = Task(first_id + 1, load_end - _minutes(rng, LOAD), load_end)
    return unload, load


def peak_concurrency(tasks: tuple[Task, ...]) -> int:
    """The most tasks that pairwise conflict at one moment: the fewest handlers that can cover them all."""
    return max(sum(1 for t in tasks if t.start <= p.start < t.end + GAP_MINUTES) for p in tasks)


def generate_assignment(n_tasks: int, seed: int) -> AssignmentInstance:
    """Model 1 instance with two baggage tasks per turnaround and one spare handler."""
    if n_tasks < TASKS_PER_TURNAROUND or n_tasks % TASKS_PER_TURNAROUND:
        raise ValueError(f"the task count must be a positive multiple of {TASKS_PER_TURNAROUND}, got {n_tasks}")
    rng = random.Random(seed)
    tasks = tuple(t for i in range(0, n_tasks, TASKS_PER_TURNAROUND) for t in _turnaround_tasks(rng, i))
    handlers = tuple(
        Handler(h, start, start + rng.choice(SHIFT_LENGTHS))
        for h in range(peak_concurrency(tasks) + 1)
        for start in [rng.choice(SHIFT_STARTS)]
    )
    return AssignmentInstance(tasks, handlers)
