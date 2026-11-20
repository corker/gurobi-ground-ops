"""Gurobi setup shared by both models: one deterministic environment and the free-licence size check."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import gurobipy as gp

FREE_LICENCE_LIMIT = 2000


@contextmanager
def gurobi_env(*, log_file: Path | None = None, expose_search: bool = False) -> Iterator[gp.Env]:
    """`expose_search` sets Presolve=0 and Cuts=0, so small instances need a visible branch-and-bound search."""
    if log_file is not None and not log_file.parent.is_dir():
        raise ValueError(f"can't write the log: {log_file.parent} isn't a directory")
    with gp.Env(empty=True) as env:
        if log_file is None:
            env.setParam("OutputFlag", 0)
        else:
            env.setParam("LogToConsole", 0)
            env.setParam("LogFile", str(log_file))
            # A log is written to be read: one progress line a second instead of the default five.
            env.setParam("DisplayInterval", 1)
        if expose_search:
            env.setParam("Presolve", 0)
            env.setParam("Cuts", 0)
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
