"""Model 1: assign handlers to tasks, minimising overtime. The formulation is in the README's Models section.

Status codes: https://docs.gurobi.com/projects/optimizer/en/current/reference/numericcodes/statuscodes.html
IIS: https://docs.gurobi.com/projects/optimizer/en/current/reference/python/model.html (Model.computeIIS)
Start: https://docs.gurobi.com/projects/optimizer/en/current/reference/attributes/variable.html
"""

import math
from collections.abc import Mapping
from itertools import combinations

import gurobipy as gp
from gurobipy import GRB

from ground_ops.domain import AssignmentInstance, Result, Status, conflict, overtime
from ground_ops.progress import ProgressRecorder, phase
from ground_ops.solver import DEFAULT_SETTINGS, SolverSettings, check_size, gurobi_env


def model_size(instance: AssignmentInstance) -> tuple[int, int]:
    """The variables and constraints build_model creates, counted without Gurobi so a request can be refused early."""
    conflicts = sum(conflict(a, b=b) for a, b in combinations(instance.tasks, 2))
    n_handlers = len(instance.handlers)
    return n_handlers * len(instance.tasks), len(instance.tasks) + conflicts * n_handlers


def build_model(instance: AssignmentInstance, *, env: gp.Env) -> tuple[gp.Model, gp.tupledict[tuple[int, int], gp.Var]]:
    model = gp.Model(env=env)
    handler_ids = [h.id for h in instance.handlers]
    x = model.addVars(handler_ids, [t.id for t in instance.tasks], vtype=GRB.BINARY, name="x")
    for task in instance.tasks:
        model.addConstr(x.sum("*", task.id) == 1, name=f"cover[{task.id}]")
    for a, b in combinations(instance.tasks, 2):
        if conflict(a, b=b):
            for h in handler_ids:
                model.addConstr(x[h, a.id] + x[h, b.id] <= 1, name=f"no_overlap[h{h},t{a.id},t{b.id}]")
    model.setObjective(
        gp.quicksum(overtime(t, handler=h) * x[h.id, t.id] for h in instance.handlers for t in instance.tasks),
        GRB.MINIMIZE,
    )
    # gurobipy applies changes lazily; without this, NumVars and NumConstrs read 0.
    model.update()
    return model, x


def solve_assignment(
    instance: AssignmentInstance,
    *,
    recorder: ProgressRecorder | None = None,
    settings: SolverSettings = DEFAULT_SETTINGS,
    start: Mapping[int, int] | None = None,
) -> Result:
    """`start` is a previous solution (task id to handler id) to warm-start from; tasks it leaves out start unset."""
    if not instance.tasks:
        raise ValueError("an instance needs at least one task")
    with gurobi_env(settings) as env:
        with phase(recorder, name="build model"):
            model, x = build_model(instance, env=env)
        with model:
            check_size(model.NumVars, n_constrs=model.NumConstrs)
            if start is not None:
                for (handler_id, task_id), var in x.items():
                    if task_id in start:
                        var.Start = int(start[task_id] == handler_id)
            with phase(recorder, name="solve"):
                model.optimize(recorder)
            if recorder is not None:
                recorder.finish(model)
            if model.Status == GRB.INFEASIBLE:
                # computeIIS obeys WorkLimit too, and a cut-short IIS isn't irreducible (IISMinimal=0).
                model.Params.WorkLimit = GRB.INFINITY
                with phase(recorder, name="compute IIS"):
                    model.computeIIS()
                iis = tuple(c.ConstrName for c in model.getConstrs() if c.IISConstr)
                return Result(status=Status.INFEASIBLE, objective=None, bound=None, gap=None, solution={}, iis=iis)
            return _result(model, x=x)


def _result(model: gp.Model, *, x: gp.tupledict[tuple[int, int], gp.Var]) -> Result:
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
    solution = {task_id: handler_id for (handler_id, task_id), var in x.items() if round(var.X) == 1}
    return Result(status=status, objective=model.ObjVal, bound=bound, gap=gap, solution=solution)
