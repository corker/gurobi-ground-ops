from itertools import product

import pytest

from ground_ops.checks import assignment_violations, total_overtime
from ground_ops.domain import AssignmentInstance, Handler, Status, Task
from ground_ops.instances import generate_assignment, move_task
from ground_ops.model1 import solve_assignment
from ground_ops.progress import ProgressRecorder
from ground_ops.solver import SolverSettings

EXPOSED = SolverSettings(expose_search=True)

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


# Brute force grows as handlers ** tasks, so 8-task cases use only seeds that need at most 4 handlers.
EIGHT_TASK_SEEDS = [s for s in range(1, 60) if len(generate_assignment(8, s).handlers) <= 4][:5]
BRUTE_FORCE_CASES = [(6, seed) for seed in range(1, 21)] + [(8, seed) for seed in EIGHT_TASK_SEEDS]


@pytest.mark.parametrize(("n_tasks", "seed"), BRUTE_FORCE_CASES)
def test_optimum_matches_brute_force_on_small_instances(n_tasks: int, seed: int) -> None:
    instance = generate_assignment(n_tasks, seed)
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


def test_effort_limit_returns_feasible_with_nonzero_gap() -> None:
    # Default settings solve every instance here at the root, so the search is exposed to have something to stop.
    instance = generate_assignment(40, seed=1)
    result = solve_assignment(instance, settings=SolverSettings(expose_search=True, work_limit=0.5))
    assert result.status is Status.LIMIT_REACHED
    assert result.objective is not None
    assert result.gap is not None
    assert result.gap > 0
    assert assignment_violations(instance, result.solution) == []
    assert total_overtime(instance, result.solution) == result.objective


def test_a_limit_before_the_root_relaxation_keeps_the_first_schedule_but_reports_no_bound() -> None:
    instance = generate_assignment(40, seed=1)
    result = solve_assignment(instance, settings=SolverSettings(expose_search=True, work_limit=0))
    assert result.status is Status.LIMIT_REACHED
    assert (result.bound, result.gap) == (None, None)
    assert assignment_violations(instance, result.solution) == []


@pytest.mark.parametrize("work_limit", [-1.0, float("nan")])
def test_a_negative_or_nan_work_limit_is_rejected(work_limit: float) -> None:
    with pytest.raises(ValueError, match="work limit must be zero or more"):
        solve_assignment(HAND_MADE, settings=SolverSettings(work_limit=work_limit))


@pytest.mark.parametrize(("seed", "partial"), [(1, False), (2, False), (3, False), (1, True)])
def test_a_warm_start_from_the_previous_schedule_is_used_and_reaches_the_cold_optimum(seed: int, partial: bool) -> None:
    before = generate_assignment(20, seed)
    previous = solve_assignment(before).solution
    delayed = move_task(before, task_id=4, minutes=25)
    start = {t: h for t, h in previous.items() if not (partial and t == 4)}
    lines: list[str] = []
    warm = solve_assignment(delayed, recorder=ProgressRecorder("warm", on_log_line=lines.append), start=start)
    # "Loaded user MIP start" when the old schedule still fits; "User MIP start violates" when Gurobi repairs it.
    assert any("user mip start" in line.lower() for line in lines)
    assert warm.objective == solve_assignment(delayed).objective
    assert assignment_violations(delayed, warm.solution) == []


def test_iis_names_the_two_overlapping_tasks_and_the_one_handler_who_cant_do_both() -> None:
    # Task 2 is hours later and doesn't conflict with either, so its cover constraint isn't part of the conflict.
    instance = AssignmentInstance(
        tasks=(Task(0, 360, 400), Task(1, 380, 420), Task(2, 540, 560)), handlers=(Handler(0, 360, 600),)
    )
    assert set(solve_assignment(instance).iis) == {"cover[0]", "cover[1]", "no_overlap[h0,t0,t1]"}


def test_a_work_limit_doesnt_cut_the_iis_short() -> None:
    instance = generate_assignment(30, seed=1, n_handlers=4)
    limited = solve_assignment(instance, settings=SolverSettings(work_limit=0.005))
    assert limited.status is Status.INFEASIBLE
    assert limited.iis == solve_assignment(instance).iis


def test_iis_of_a_generated_instance_with_too_few_handlers_names_cover_and_overlap_constraints() -> None:
    result = solve_assignment(generate_assignment(30, seed=1, n_handlers=2))
    assert result.status is Status.INFEASIBLE
    assert any(name.startswith("cover[") for name in result.iis)
    assert any(name.startswith("no_overlap[") for name in result.iis)


def test_same_seed_and_threads_give_the_same_search() -> None:
    def search() -> tuple[int, int, float]:
        recorder = ProgressRecorder("x")
        solve_assignment(generate_assignment(40, seed=3), recorder=recorder, settings=EXPOSED)
        assert recorder.latest is not None
        return recorder.latest.nodes, recorder.latest.iterations, recorder.latest.work

    first = search()
    assert first[0] > 1
    assert search() == first
