"""How many Model 1 instances of each size fit the free licence's 2,000 variables and 2,000 constraints.

Counts the model's size without building it, so it needs no Gurobi licence at all.
"""

from ground_ops.instances import generate_assignment
from ground_ops.model1 import model_size
from ground_ops.solver import FREE_LICENCE_LIMIT

SEEDS = range(1, 21)


def main() -> None:
    print(f"Model 1, default handlers, {len(SEEDS)} seeds per size, limit {FREE_LICENCE_LIMIT} of each")
    for n_tasks in range(40, 62, 2):
        sizes = [model_size(generate_assignment(n_tasks, seed=seed)) for seed in SEEDS]
        fits = sum(max(n_vars, n_constrs) <= FREE_LICENCE_LIMIT for n_vars, n_constrs in sizes)
        largest = max(max(size) for size in sizes)
        print(f"{n_tasks} tasks: {fits}/{len(SEEDS)} fit; largest variables or constraints {largest}")


if __name__ == "__main__":
    main()
