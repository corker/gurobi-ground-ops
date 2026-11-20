"""How many instances Gurobi solves at the root node, with default settings and with the search exposed (D4)."""

import statistics

from ground_ops.instances import generate_assignment, generate_coverage
from ground_ops.model1 import solve_assignment
from ground_ops.model2 import solve_coverage
from ground_ops.progress import ProgressRecorder
from ground_ops.solver import SolverSettings

SEEDS = range(1, 21)


def assignment_nodes(n_tasks: int, seed: int, exposed: bool) -> int:
    recorder = ProgressRecorder("experiment")
    solve_assignment(
        generate_assignment(n_tasks, seed), recorder=recorder, settings=SolverSettings(expose_search=exposed)
    )
    assert recorder.latest is not None
    return recorder.latest.nodes


def coverage_nodes(seed: int, exposed: bool) -> int:
    recorder = ProgressRecorder("experiment")
    solve_coverage(generate_coverage(seed), recorder=recorder, settings=SolverSettings(expose_search=exposed))
    assert recorder.latest is not None
    return recorder.latest.nodes


def report(label: str, exposed: bool, counts: list[int]) -> None:
    settings = "Presolve=0, Cuts=0" if exposed else "defaults"
    print(
        f"{label}, {settings}: {sum(n <= 1 for n in counts)}/{len(counts)} at the root; "
        f"nodes min {min(counts)}, median {statistics.median(counts):g}, max {max(counts)}"
    )


def main() -> None:
    for n_tasks in (20, 30, 40, 48):
        for exposed in (False, True):
            report(f"Model 1, {n_tasks} tasks", exposed, [assignment_nodes(n_tasks, s, exposed) for s in SEEDS])
    for exposed in (False, True):
        report("Model 2, 48 slots", exposed, [coverage_nodes(s, exposed) for s in SEEDS])


if __name__ == "__main__":
    main()
