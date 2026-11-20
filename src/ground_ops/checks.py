"""Checks a solution against the problem rules without trusting the solver."""

from collections.abc import Mapping
from itertools import combinations

from ground_ops.domain import AssignmentInstance, conflict, overtime


def assignment_violations(instance: AssignmentInstance, assignment: Mapping[int, int]) -> list[str]:
    """Every broken rule, as a readable sentence. An empty list means the assignment is feasible."""
    handler_ids = {h.id for h in instance.handlers}
    task_ids = {t.id for t in instance.tasks}
    problems = [f"task {t.id} has no handler" for t in instance.tasks if t.id not in assignment]
    problems += [f"task {t} doesn't exist" for t in assignment if t not in task_ids]
    problems += [f"handler {h} doesn't exist" for h in assignment.values() if h not in handler_ids]
    for a, b in combinations(instance.tasks, 2):
        handler = assignment.get(a.id)
        if handler is not None and handler == assignment.get(b.id) and conflict(a, b):
            problems.append(f"handler {handler} has conflicting tasks {a.id} and {b.id}")
    return problems


def total_overtime(instance: AssignmentInstance, assignment: Mapping[int, int]) -> int:
    """Total overtime of a complete assignment; check `assignment_violations` first."""
    handlers = {h.id: h for h in instance.handlers}
    return sum(overtime(t, handlers[assignment[t.id]]) for t in instance.tasks)
