"""Model 1: assign handlers to tasks, minimising overtime. The formulation is in the README's Models section."""

from itertools import combinations
from pathlib import Path

import gurobipy as gp
from gurobipy import GRB

from ground_ops.domain import AssignmentInstance, Result, Status, conflict, overtime
from ground_ops.progress import ProgressRecorder, phase
from ground_ops.solver import check_size, gurobi_env


def build_model(instance: AssignmentInstance, env: gp.Env) -> tuple[gp.Model, gp.tupledict[tuple[int, int], gp.Var]]:
    model = gp.Model(env=env)
    handler_ids = [h.id for h in instance.handlers]
    x = model.addVars(handler_ids, [t.id for t in instance.tasks], vtype=GRB.BINARY, name="x")
    for task in instance.tasks:
        model.addConstr(x.sum("*", task.id) == 1, name=f"cover[{task.id}]")
    for a, b in combinations(instance.tasks, 2):
        if conflict(a, b):
            for h in handler_ids:
                model.addConstr(x[h, a.id] + x[h, b.id] <= 1, name=f"no_overlap[h{h},t{a.id},t{b.id}]")
    model.setObjective(
        gp.quicksum(overtime(t, h) * x[h.id, t.id] for h in instance.handlers for t in instance.tasks),
        GRB.MINIMIZE,
    )
    # gurobipy applies changes lazily; without this, NumVars and NumConstrs read 0.
    model.update()
    return model, x


def solve_assignment(
    instance: AssignmentInstance,
    *,
    recorder: ProgressRecorder | None = None,
    log_file: Path | None = None,
    expose_search: bool = False,
) -> Result:
    if not instance.tasks:
        raise ValueError("an instance needs at least one task")
    with gurobi_env(log_file=log_file, expose_search=expose_search) as env:
        with phase(recorder, "build model"):
            model, x = build_model(instance, env)
        with model:
            check_size(model)
            with phase(recorder, "solve"):
                model.optimize(recorder)
            if recorder is not None and model.Status == GRB.OPTIMAL:
                recorder.finish(model)
            return _result(model, x)


def _result(model: gp.Model, x: gp.tupledict[tuple[int, int], gp.Var]) -> Result:
    if model.Status == GRB.INFEASIBLE:
        return Result(Status.INFEASIBLE, objective=None, bound=None, gap=None, solution={})
    if model.Status == GRB.OPTIMAL:
        solution = {task_id: handler_id for (handler_id, task_id), var in x.items() if round(var.X) == 1}
        return Result(Status.OPTIMAL, model.ObjVal, model.ObjBound, model.MIPGap, solution)
    raise RuntimeError(f"Gurobi stopped with status code {model.Status}, which this version doesn't handle yet.")
