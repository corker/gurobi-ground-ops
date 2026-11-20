import pytest

from ground_ops.instances import ARRIVALS_FROM, LOAD, UNLOAD, generate_assignment, peak_concurrency


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
