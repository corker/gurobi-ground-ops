"""What the progress callback costs: work units (deterministic) and wall-clock time, with and without it (D6)."""

import statistics
import time

from ground_ops.instances import generate_assignment
from ground_ops.model1 import build_model
from ground_ops.progress import ProgressRecorder
from ground_ops.solver import gurobi_env

REPEATS = 5


def solve(seed: int, with_callback: bool) -> tuple[float, int, float]:
    with gurobi_env(expose_search=True) as env:
        model, _ = build_model(generate_assignment(40, seed), env)
        with model:
            start = time.perf_counter()
            model.optimize(ProgressRecorder("experiment") if with_callback else None)
            return model.Work, int(model.NodeCount), time.perf_counter() - start


def main() -> None:
    for seed in (1, 3):
        runs = {flag: [solve(seed, with_callback=flag) for _ in range(REPEATS)] for flag in (False, True)}
        work = {flag: {round(w, 6) for w, _, _ in runs[flag]} for flag in runs}
        nodes = {flag: {n for _, n, _ in runs[flag]} for flag in runs}
        wall = {flag: sorted(t for _, _, t in runs[flag]) for flag in runs}
        print(
            f"seed {seed}, {REPEATS} runs each: work without {work[False]} / with {work[True]}; "
            f"nodes without {nodes[False]} / with {nodes[True]}; "
            f"wall median {statistics.median(wall[False]):.2f} s (range {wall[False][0]:.2f}-{wall[False][-1]:.2f}) "
            f"-> {statistics.median(wall[True]):.2f} s (range {wall[True][0]:.2f}-{wall[True][-1]:.2f})"
        )


if __name__ == "__main__":
    main()
