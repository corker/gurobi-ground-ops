"""Model 1's no-overlap rule written pairwise (as in the package) and as one constraint per clique: constraint count,
LP bound and optimum (D3, D15).

Two tasks conflict when the intervals [start, end + GAP_MINUTES) overlap, so the conflicts form an interval graph. Its
maximal cliques are the tasks running at some task's start, so one constraint per handler and start time covers every
conflict, and is tighter than the pairwise constraints it replaces.

Model.relax: https://docs.gurobi.com/projects/optimizer/en/current/reference/python/model.html
"""

import gurobipy as gp
from gurobipy import GRB

from ground_ops.domain import GAP_MINUTES, AssignmentInstance, overtime
from ground_ops.instances import generate_assignment
from ground_ops.model1 import build_model
from ground_ops.solver import DEFAULT_SETTINGS, gurobi_env

SEEDS = range(1, 6)


def cliques(instance: AssignmentInstance) -> set[frozenset[int]]:
    return {
        group
        for point in {t.start for t in instance.tasks}
        if len(group := frozenset(t.id for t in instance.tasks if t.start <= point < t.end + GAP_MINUTES)) > 1
    }


def build_clique_model(instance: AssignmentInstance, *, env: gp.Env) -> gp.Model:
    model = gp.Model(env=env)
    handler_ids = [h.id for h in instance.handlers]
    x = model.addVars(handler_ids, [t.id for t in instance.tasks], vtype=GRB.BINARY, name="x")
    for task in instance.tasks:
        model.addConstr(x.sum("*", task.id) == 1)
    for group in sorted(cliques(instance), key=sorted):
        for h in handler_ids:
            model.addConstr(gp.quicksum(x[h, t] for t in sorted(group)) <= 1)
    model.setObjective(
        gp.quicksum(overtime(t, handler=h) * x[h.id, t.id] for h in instance.handlers for t in instance.tasks),
        GRB.MINIMIZE,
    )
    model.update()
    return model


def measure(model: gp.Model) -> str:
    with model.relax() as relaxed:
        relaxed.optimize()
        bound = relaxed.ObjVal
    model.optimize()
    return f"{model.NumConstrs} constraints, LP bound {bound:g}, optimum {model.ObjVal:g}"


def main() -> None:
    print("Model 1, default settings; constraints include the cover constraints")
    for n_tasks in (20, 30, 40):
        for seed in SEEDS:
            instance = generate_assignment(n_tasks, seed=seed)
            with gurobi_env(DEFAULT_SETTINGS) as env:
                model, _ = build_model(instance, env=env)
                with model:
                    pairwise = measure(model)
                with build_clique_model(instance, env=env) as model:
                    clique = measure(model)
            print(
                f"{n_tasks} tasks, seed {seed}, {len(instance.handlers)} handlers: pairwise {pairwise}; clique {clique}"
            )


if __name__ == "__main__":
    main()
