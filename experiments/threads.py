"""The same solves with one thread and with four: does the search change, and is each repeatable? (D7)"""

from ground_ops.instances import generate_assignment
from ground_ops.model1 import build_model
from ground_ops.solver import SolverSettings, gurobi_env

SEEDS = range(1, 6)
N_TASKS = 40


def search(seed: int, threads: int) -> tuple[float, int, float]:
    with gurobi_env(SolverSettings(expose_search=True)) as env:
        model, _ = build_model(generate_assignment(N_TASKS, seed), env)
        with model:
            model.Params.Threads = threads
            model.optimize()
            return model.ObjVal, int(model.NodeCount), model.Work


def main() -> None:
    print(f"Model 1, {N_TASKS} tasks, Presolve=0, Cuts=0, Seed=0; each run twice")
    for seed in SEEDS:
        for threads in (1, 4):
            first, second = search(seed, threads), search(seed, threads)
            objective, nodes, work = first
            print(
                f"seed {seed}, {threads} thread(s): objective {objective:g}, nodes {nodes}, work {work:.4f}, "
                f"repeat identical: {first == second}"
            )


if __name__ == "__main__":
    main()
