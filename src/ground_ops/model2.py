"""Model 2: choose how many people to roster on each shift pattern to cover demand at minimum cost.

The formulation is in the README's Models section.
"""

import gurobipy as gp
from gurobipy import GRB

from ground_ops.domain import CoverageInstance, Result, Status, covers, paid_slots
from ground_ops.solver import check_size, gurobi_env


def build_model(instance: CoverageInstance, env: gp.Env) -> tuple[gp.Model, gp.tupledict[int, gp.Var]]:
    model = gp.Model(env=env)
    y = model.addVars([p.id for p in instance.patterns], vtype=GRB.INTEGER, name="y")
    for slot, needed in enumerate(instance.demand):
        model.addConstr(
            gp.quicksum(y[p.id] for p in instance.patterns if covers(p, slot)) >= needed, name=f"demand[{slot}]"
        )
    model.setObjective(gp.quicksum(paid_slots(p) * y[p.id] for p in instance.patterns), GRB.MINIMIZE)
    # gurobipy applies changes lazily; without this, NumVars and NumConstrs read 0.
    model.update()
    return model, y


def solve_coverage(instance: CoverageInstance) -> Result:
    if not instance.demand:
        raise ValueError("an instance needs at least one demand slot")
    with gurobi_env() as env:
        model, y = build_model(instance, env)
        with model:
            check_size(model)
            model.optimize()
            return _result(model, y)


def _result(model: gp.Model, y: gp.tupledict[int, gp.Var]) -> Result:
    if model.Status == GRB.INFEASIBLE:
        return Result(Status.INFEASIBLE, objective=None, bound=None, gap=None, solution={})
    if model.Status == GRB.OPTIMAL:
        staffing = {pattern_id: people for pattern_id, var in y.items() if (people := round(var.X)) > 0}
        return Result(Status.OPTIMAL, model.ObjVal, model.ObjBound, model.MIPGap, staffing)
    raise RuntimeError(f"Gurobi stopped with status code {model.Status}, which this version doesn't handle yet.")
