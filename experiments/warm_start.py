"""Warm start against cold start after one task is delayed, in work units over 20 seeds (D8)."""

import statistics

from ground_ops.domain import Status
from ground_ops.instances import generate_assignment, move_task
from ground_ops.model1 import solve_assignment
from ground_ops.progress import ProgressRecorder
from ground_ops.solver import SolverSettings

SEEDS = range(1, 21)
N_TASKS = 40
MOVED_TASK = 4
DELAY_MINUTES = 25
EXPOSED = SolverSettings(expose_search=True)


def work(instance_seed: int, start: dict[int, int] | None) -> float:
    recorder = ProgressRecorder("experiment")
    delayed = move_task(generate_assignment(N_TASKS, instance_seed), MOVED_TASK, DELAY_MINUTES)
    result = solve_assignment(delayed, recorder=recorder, settings=EXPOSED, start=start)
    assert result.status is Status.OPTIMAL
    assert recorder.latest is not None
    return recorder.latest.work


def describe(values: list[float]) -> str:
    return f"median {statistics.median(values):.3f} (min {min(values):.3f}, max {max(values):.3f})"


def main() -> None:
    print(f"Model 1, {N_TASKS} tasks, task {MOVED_TASK} delayed {DELAY_MINUTES} min, Presolve=0, Cuts=0")
    print("seed  cold     full start  partial start  (work units)")
    cold, full, partial = [], [], []
    for seed in SEEDS:
        previous = dict(solve_assignment(generate_assignment(N_TASKS, seed), settings=EXPOSED).solution)
        cold.append(work(seed, None))
        full.append(work(seed, previous))
        partial.append(work(seed, {t: h for t, h in previous.items() if t != MOVED_TASK}))
        print(f"{seed:>4}  {cold[-1]:7.3f}  {full[-1]:10.3f}  {partial[-1]:13.3f}")
    for name, values in (("cold", cold), ("full start", full), ("partial start", partial)):
        print(f"{name}: {describe(values)}")
    for name, warm in (("full start", full), ("partial start", partial)):
        print(f"{name}: less work than cold on {sum(w < c for w, c in zip(warm, cold, strict=True))} of {len(cold)}")


if __name__ == "__main__":
    main()
