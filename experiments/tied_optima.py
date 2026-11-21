"""How many different schedules share the optimal objective in Model 1 (D10).

With PoolSearchMode=2, Gurobi searches for the PoolSolutions best solutions. If the worst stored solution is worse than
the optimum, every optimal schedule is in the pool, so the count is exact; otherwise it is a lower bound.
https://docs.gurobi.com/projects/optimizer/en/current/features/solutionpool.html
"""

from gurobipy import GRB

from ground_ops.instances import generate_assignment
from ground_ops.model1 import build_model
from ground_ops.solver import DEFAULT_SETTINGS, gurobi_env

SEEDS = range(1, 6)
POOL = 2000


def tied_optima(n_tasks: int, *, seed: int) -> tuple[float, int, bool]:
    """The optimum, how many stored solutions reach it, and whether that count is exact."""
    with gurobi_env(DEFAULT_SETTINGS) as env:
        model, _ = build_model(generate_assignment(n_tasks, seed=seed), env=env)
        with model:
            model.Params.PoolSearchMode = 2
            model.Params.PoolSolutions = POOL
            # The pool docs: set the optimality gap to 0 with PoolSearchMode=2, or better solutions can be missed.
            model.Params.MIPGap = 0
            model.optimize()
            assert model.Status == GRB.OPTIMAL
            objectives = []
            for n in range(model.SolCount):
                model.Params.SolutionNumber = n
                objectives.append(model.PoolNObjVal)
            ties = sum(objective == model.ObjVal for objective in objectives)
            return model.ObjVal, ties, ties < model.SolCount


def main() -> None:
    print(f"Model 1, default settings, PoolSearchMode=2, PoolSolutions={POOL}, MIPGap=0")
    for n_tasks in (10, 20, 30):
        for seed in SEEDS:
            objective, ties, exact = tied_optima(n_tasks, seed=seed)
            count = f"{ties}" if exact else f"at least {ties}"
            print(f"{n_tasks} tasks, seed {seed}: optimum {objective:g}, optimal schedules {count}")


if __name__ == "__main__":
    main()
