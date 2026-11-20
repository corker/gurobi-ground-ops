"""Gurobi setup shared by both models: one deterministic environment and the free-licence size check."""

from collections.abc import Iterator
from contextlib import contextmanager

import gurobipy as gp

FREE_LICENCE_LIMIT = 2000


@contextmanager
def gurobi_env() -> Iterator[gp.Env]:
    with gp.Env(empty=True) as env:
        env.setParam("OutputFlag", 0)
        # One thread and a fixed seed, so the search path doesn't depend on the machine's core count.
        env.setParam("Threads", 1)
        env.setParam("Seed", 0)
        env.start()
        yield env


def check_size(model: gp.Model) -> None:
    """Raise before solving if the model is too big for the licence bundled with gurobipy."""
    if model.NumVars > FREE_LICENCE_LIMIT or model.NumConstrs > FREE_LICENCE_LIMIT:
        raise ValueError(
            f"this instance needs {model.NumVars} variables and {model.NumConstrs} constraints; "
            f"the free Gurobi licence allows {FREE_LICENCE_LIMIT} of each; use a smaller instance, such as fewer tasks"
        )
