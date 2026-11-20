from itertools import product

import pytest

from ground_ops.checks import assignment_violations, total_overtime
from ground_ops.domain import AssignmentInstance, Handler, Status, Task
from ground_ops.instances import generate_assignment
from ground_ops.model1 import solve_assignment

# Worked by hand: handler 1 must take tasks 1 and 2, so task 3 goes to handler 0, 15 minutes past its shift.
HAND_MADE = AssignmentInstance(
    tasks=(Task(0, 360, 380), Task(1, 470, 490), Task(2, 500, 520), Task(3, 475, 495)),
    handlers=(Handler(0, 360, 480), Handler(1, 420, 540)),
)


def brute_force_optimum(instance: AssignmentInstance) -> int:
    handler_ids = [h.id for h in instance.handlers]
    feasible = (
        dict(zip((t.id for t in instance.tasks), choice, strict=True))
        for choice in product(handler_ids, repeat=len(instance.tasks))
    )
    return min(total_overtime(instance, a) for a in feasible if not assignment_violations(instance, a))


def test_hand_made_instance_has_the_hand_computed_optimum() -> None:
    result = solve_assignment(HAND_MADE)
    assert result.status is Status.OPTIMAL
    assert result.objective == 15
    assert assignment_violations(HAND_MADE, result.solution) == []


@pytest.mark.parametrize("seed", range(1, 6))
def test_optimum_matches_brute_force_on_small_instances(seed: int) -> None:
    instance = generate_assignment(6, seed)
    result = solve_assignment(instance)
    assert result.status is Status.OPTIMAL
    assert result.objective == brute_force_optimum(instance)


def test_solution_is_feasible_and_its_overtime_equals_the_objective() -> None:
    instance = generate_assignment(30, seed=1)
    result = solve_assignment(instance)
    assert result.status is Status.OPTIMAL
    assert result.objective == 8  # regression value, measured when this test was written
    assert assignment_violations(instance, result.solution) == []
    assert total_overtime(instance, result.solution) == result.objective
    assert result.gap == 0


def test_peak_concurrency_handlers_suffice_and_one_fewer_is_infeasible() -> None:
    instance = generate_assignment(30, seed=1)
    peak = len(instance.handlers) - 1
    enough = AssignmentInstance(instance.tasks, instance.handlers[:peak])
    too_few = AssignmentInstance(instance.tasks, instance.handlers[: peak - 1])
    assert solve_assignment(enough).status is Status.OPTIMAL
    assert solve_assignment(too_few).status is Status.INFEASIBLE


def test_infeasible_instance_reports_infeasible_without_a_solution() -> None:
    overlapping = AssignmentInstance(tasks=(Task(0, 360, 400), Task(1, 380, 420)), handlers=(Handler(0, 360, 600),))
    result = solve_assignment(overlapping)
    assert result.status is Status.INFEASIBLE
    assert result.objective is None
    assert result.solution == {}


def test_instance_over_the_free_licence_limit_is_rejected_before_solving() -> None:
    with pytest.raises(ValueError, match="free Gurobi licence allows 2000"):
        solve_assignment(generate_assignment(80, seed=1))


def test_instance_without_tasks_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one task"):
        solve_assignment(AssignmentInstance(tasks=(), handlers=(Handler(0, 360, 600),)))


def test_instance_without_handlers_is_infeasible() -> None:
    assert solve_assignment(AssignmentInstance(tasks=(Task(0, 360, 400),), handlers=())).status is Status.INFEASIBLE
