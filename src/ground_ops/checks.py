"""Checks a solution against the problem rules without trusting the solver."""

from collections.abc import Mapping
from itertools import combinations

from ground_ops.domain import AssignmentInstance, CoverageInstance, conflict, covers, overtime, paid_slots


def assignment_violations(instance: AssignmentInstance, *, assignment: Mapping[int, int]) -> list[str]:
    """Every broken rule, as a readable sentence. An empty list means the assignment is feasible."""
    handler_ids = {h.id for h in instance.handlers}
    task_ids = {t.id for t in instance.tasks}
    problems = [f"task {t.id} has no handler" for t in instance.tasks if t.id not in assignment]
    problems += [f"task {t} doesn't exist" for t in assignment if t not in task_ids]
    problems += [f"handler {h} doesn't exist" for h in assignment.values() if h not in handler_ids]
    for a, b in combinations(instance.tasks, 2):
        handler = assignment.get(a.id)
        if handler is not None and handler == assignment.get(b.id) and conflict(a, b=b):
            problems.append(f"handler {handler} has conflicting tasks {a.id} and {b.id}")
    return problems


def total_overtime(instance: AssignmentInstance, *, assignment: Mapping[int, int]) -> int:
    """Total overtime of a complete assignment; check `assignment_violations` first."""
    handlers = {h.id: h for h in instance.handlers}
    return sum(overtime(t, handler=handlers[assignment[t.id]]) for t in instance.tasks)


def coverage_shortfalls(instance: CoverageInstance, *, staffing: Mapping[int, int]) -> list[str]:
    """Every broken rule, as a readable sentence. An empty list means every slot has enough people."""
    patterns = {p.id: p for p in instance.patterns}
    problems = [f"pattern {p} doesn't exist" for p in staffing if p not in patterns]
    problems += [f"pattern {p} has {n} people" for p, n in staffing.items() if n < 0]
    for slot, needed in enumerate(instance.demand):
        on_duty = sum(n for p, n in staffing.items() if n > 0 and p in patterns and covers(patterns[p], slot=slot))
        if on_duty < needed:
            problems.append(f"slot {slot} has {on_duty} on duty, needs {needed}")
    return problems


def total_paid_slots(instance: CoverageInstance, *, staffing: Mapping[int, int]) -> int:
    """Total paid half-hours of a valid staffing; check `coverage_shortfalls` first."""
    patterns = {p.id: p for p in instance.patterns}
    return sum(n * paid_slots(patterns[p]) for p, n in staffing.items())
