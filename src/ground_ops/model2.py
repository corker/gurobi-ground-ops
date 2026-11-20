"""Model 2: choose how many people to roster on each shift pattern to cover demand at minimum cost.

The formulation is in the README's Models section.
"""

import math

import gurobipy as gp
from gurobipy import GRB

from ground_ops.domain import CoverageInstance, Result, Status, covers, paid_slots
from ground_ops.progress import ProgressRecorder, phase
from ground_ops.solver import DEFAULT_SETTINGS, SolverSettings, check_size, gurobi_env


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


def solve_coverage(
    instance: CoverageInstance,
    *,
    recorder: ProgressRecorder | None = None,
    settings: SolverSettings = DEFAULT_SETTINGS,
) -> Result:
    if not instance.demand:
        raise ValueError("an instance needs at least one demand slot")
    with gurobi_env(settings) as env:
        with phase(recorder, "build model"):
            model, y = build_model(instance, env)
        with model:
            check_size(model.NumVars, model.NumConstrs)
            with phase(recorder, "solve"):
                model.optimize(recorder)
            if recorder is not None:
                recorder.finish(model)
            if model.Status == GRB.INFEASIBLE:
                return Result(status=Status.INFEASIBLE, objective=None, bound=None, gap=None, solution={})
            return _result(model, y)


def _result(model: gp.Model, y: gp.tupledict[int, gp.Var]) -> Result:
    match model.Status:
        case GRB.OPTIMAL:
            status = Status.OPTIMAL
        case GRB.WORK_LIMIT:
            status = Status.LIMIT_REACHED
        case GRB.INTERRUPTED:
            status = Status.INTERRUPTED
        case code:
            raise RuntimeError(f"Gurobi stopped with status code {code}, which this version doesn't handle yet.")
    # Before the first bound or incumbent, Gurobi reports them as infinite.
    bound = model.ObjBound if math.isfinite(model.ObjBound) else None
    if not model.SolCount:
        return Result(status=status, objective=None, bound=bound, gap=None, solution={})
    gap = model.MIPGap if math.isfinite(model.MIPGap) else None
    staffing = {pattern_id: people for pattern_id, var in y.items() if (people := round(var.X)) > 0}
    return Result(status=status, objective=model.ObjVal, bound=bound, gap=gap, solution=staffing)
