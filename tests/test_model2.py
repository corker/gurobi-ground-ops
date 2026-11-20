import random
from itertools import product

import pytest

from ground_ops.checks import coverage_shortfalls, total_paid_slots
from ground_ops.domain import CoverageInstance, ShiftPattern, Status
from ground_ops.instances import generate_coverage
from ground_ops.model2 import solve_coverage
from ground_ops.solver import SolverSettings

# Worked by hand: all three 2-slot shifts, or the 4-slot shift plus the middle one, cost 6 paid slots.
HAND_MADE = CoverageInstance(
    demand=(1, 2, 2, 1),
    patterns=(
        ShiftPattern(0, start=0, length=2, break_slot=None),
        ShiftPattern(1, start=1, length=2, break_slot=None),
        ShiftPattern(2, start=2, length=2, break_slot=None),
        ShiftPattern(3, start=0, length=4, break_slot=None),
    ),
)


def small_instance(seed: int) -> CoverageInstance:
    rng = random.Random(seed)
    starts_and_lengths = [(s, n) for n in (2, 3) for s in range(6 - n + 1)]
    patterns = tuple(ShiftPattern(i, s, n, s + 1 if n == 3 else None) for i, (s, n) in enumerate(starts_and_lengths))
    return CoverageInstance(tuple(rng.randint(0, 2) for _ in range(6)), patterns)


def brute_force_optimum(instance: CoverageInstance) -> int:
    # No optimal roster puts more people on one pattern than the peak demand: cutting it back still covers every slot.
    ids = [p.id for p in instance.patterns]
    counts = product(range(max(instance.demand) + 1), repeat=len(ids))
    staffings = (dict(zip(ids, c, strict=True)) for c in counts)
    return min(total_paid_slots(instance, s) for s in staffings if not coverage_shortfalls(instance, s))


def test_hand_made_instance_has_the_hand_computed_optimum() -> None:
    result = solve_coverage(HAND_MADE)
    assert result.status is Status.OPTIMAL
    assert result.objective == 6
    assert coverage_shortfalls(HAND_MADE, result.solution) == []


@pytest.mark.parametrize("seed", range(1, 11))
def test_optimum_matches_brute_force_on_small_instances(seed: int) -> None:
    instance = small_instance(seed)
    result = solve_coverage(instance)
    assert result.status is Status.OPTIMAL
    assert result.objective == brute_force_optimum(instance)


def test_full_day_roster_covers_demand_and_its_cost_equals_the_objective() -> None:
    instance = generate_coverage(seed=1)
    result = solve_coverage(instance)
    assert result.status is Status.OPTIMAL
    assert result.objective == 239  # regression value, measured when this test was written
    assert coverage_shortfalls(instance, result.solution) == []
    assert total_paid_slots(instance, result.solution) == result.objective
    assert result.gap == 0


def test_a_slot_no_pattern_covers_makes_the_instance_infeasible() -> None:
    uncovered = CoverageInstance(demand=(1, 1), patterns=(ShiftPattern(0, start=0, length=1, break_slot=None),))
    result = solve_coverage(uncovered)
    assert result.status is Status.INFEASIBLE
    assert result.solution == {}


def test_instance_without_demand_slots_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one demand slot"):
        solve_coverage(CoverageInstance(demand=(), patterns=()))


def test_an_effort_limit_returns_a_feasible_roster_with_a_nonzero_gap() -> None:
    instance = generate_coverage(seed=1)
    result = solve_coverage(instance, settings=SolverSettings(expose_search=True, work_limit=0.001))
    assert result.status is Status.LIMIT_REACHED
    assert result.gap is not None
    assert result.gap > 0
    assert coverage_shortfalls(instance, result.solution) == []
    assert total_paid_slots(instance, result.solution) == result.objective
