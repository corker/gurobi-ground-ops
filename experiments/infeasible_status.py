"""Which status Gurobi returns for infeasible Model 1 instances (D9)."""

from collections import Counter

from gurobipy import GRB

from ground_ops.instances import generate_assignment, peak_concurrency
from ground_ops.model1 import build_model
from ground_ops.solver import SolverSettings, gurobi_env

SIZES = (2, 10, 20, 40, 48)
SEEDS = range(1, 21)
NAMES = {GRB.INFEASIBLE: "INFEASIBLE", GRB.INF_OR_UNBD: "INF_OR_UNBD"}


def main() -> None:
    statuses: Counter[int] = Counter()
    for n_tasks in SIZES:
        for seed in SEEDS:
            too_few = peak_concurrency(generate_assignment(n_tasks, seed).tasks) - 1
            for exposed in (False, True):
                with gurobi_env(SolverSettings(expose_search=exposed)) as env:
                    model, _ = build_model(generate_assignment(n_tasks, seed, n_handlers=too_few), env)
                    with model:
                        model.optimize()
                        statuses[model.Status] += 1
    counts = ", ".join(f"status {code} ({NAMES.get(code, '?')}) {n} times" for code, n in sorted(statuses.items()))
    print(f"{statuses.total()} infeasible solves: {counts}")


if __name__ == "__main__":
    main()
