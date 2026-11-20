import pytest

from ground_ops.domain import paid_slots
from ground_ops.instances import (
    ARRIVALS_FROM,
    LOAD,
    SLOTS_PER_DAY,
    UNLOAD,
    generate_assignment,
    generate_coverage,
    peak_concurrency,
    shift_patterns,
)


def test_same_seed_gives_the_same_instance() -> None:
    assert generate_assignment(20, seed=7) == generate_assignment(20, seed=7)


def test_different_seeds_give_different_instances() -> None:
    assert generate_assignment(20, seed=7) != generate_assignment(20, seed=8)


def test_task_durations_stay_within_the_dataset_ranges() -> None:
    instance = generate_assignment(200, seed=3)
    unloads, loads = instance.tasks[0::2], instance.tasks[1::2]
    assert all(UNLOAD[0] <= t.end - t.start <= UNLOAD[1] for t in unloads)
    assert all(LOAD[0] <= t.end - t.start <= LOAD[1] for t in loads)
    assert all(t.start >= ARRIVALS_FROM for t in unloads)


def test_instance_has_one_spare_handler_beyond_peak_concurrency() -> None:
    instance = generate_assignment(30, seed=1)
    assert len(instance.handlers) == peak_concurrency(instance.tasks) + 1


@pytest.mark.parametrize("n_tasks", [0, 1, 7, -2])
def test_task_count_must_be_a_positive_multiple_of_two(n_tasks: int) -> None:
    with pytest.raises(ValueError, match="multiple of 2"):
        generate_assignment(n_tasks, seed=1)


def test_shift_patterns_are_every_4_6_and_8_hour_shift_that_fits_the_day() -> None:
    patterns = shift_patterns()
    assert len(patterns) == 41 + 37 + 33
    assert all(p.start + p.length <= SLOTS_PER_DAY for p in patterns)
    assert len({(p.start, p.length) for p in patterns}) == len(patterns)


def test_only_shifts_of_six_hours_or_more_have_one_unpaid_break_inside_the_shift() -> None:
    for p in shift_patterns():
        if p.length < 12:
            assert p.break_slot is None
        else:
            assert p.break_slot is not None
            assert p.start < p.break_slot < p.start + p.length - 1
            assert paid_slots(p) == p.length - 1


def test_coverage_demand_is_seeded_and_needs_someone_in_every_slot() -> None:
    instance = generate_coverage(seed=5)
    assert instance == generate_coverage(seed=5)
    assert len(instance.demand) == SLOTS_PER_DAY
    assert min(instance.demand) >= 1
