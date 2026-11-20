import gurobipy as gp
from gurobipy import GRB


def test_free_licence_solves_a_small_mip() -> None:
    with gp.Env(empty=True) as env:
        env.setParam("OutputFlag", 0)
        env.setParam("Threads", 1)
        env.setParam("Seed", 0)
        env.start()
        with gp.Model(env=env) as model:
            x = model.addVar(vtype=GRB.INTEGER, name="x")
            y = model.addVar(vtype=GRB.INTEGER, name="y")
            model.addConstr(x + 2 * y >= 3)
            model.setObjective(x + y, GRB.MINIMIZE)
            model.optimize()

            assert model.Status == GRB.OPTIMAL
            assert model.ObjVal == 2
