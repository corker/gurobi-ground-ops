"""Gurobi setup shared by both models: one deterministic environment and the free-licence size check.

Parameters: https://docs.gurobi.com/projects/optimizer/en/current/reference/parameters.html
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import gurobipy as gp

FREE_LICENCE_LIMIT = 2000


@dataclass(frozen=True)
class SolverSettings:
    """`log_file` appends Gurobi's log to a file. `expose_search` sets Presolve=0 and Cuts=0, so small instances
    need a visible branch-and-bound search. `work_limit` stops the solve after that many work units, Gurobi's
    deterministic effort measure."""

    log_file: Path | None = None
    expose_search: bool = False
    work_limit: float | None = None


DEFAULT_SETTINGS = SolverSettings()

# Gurobi: "environment creation and deletion are not thread-safe" (https://support.gurobi.com/hc/en-us/articles/40912136522129).
_ENV_LOCK = threading.Lock()


@contextmanager
def gurobi_env(settings: SolverSettings) -> Iterator[gp.Env]:
    if settings.log_file is not None and not settings.log_file.parent.is_dir():
        raise ValueError(f"can't write the log: {settings.log_file.parent} isn't a directory")
    if settings.work_limit is not None and not settings.work_limit >= 0:
        raise ValueError(f"the work limit must be zero or more work units, got {settings.work_limit}")
    with _ENV_LOCK:
        env = gp.Env(empty=True)
    try:
        if settings.log_file is None:
            env.setParam("OutputFlag", 0)
        else:
            env.setParam("LogToConsole", 0)
            env.setParam("LogFile", str(settings.log_file))
            # A log is written to be read: one progress line a second instead of the default five.
            env.setParam("DisplayInterval", 1)
        if settings.expose_search:
            env.setParam("Presolve", 0)
            env.setParam("Cuts", 0)
        if settings.work_limit is not None:
            env.setParam("WorkLimit", settings.work_limit)
        # One thread and a fixed seed, so the search path doesn't depend on the machine's core count.
        env.setParam("Threads", 1)
        env.setParam("Seed", 0)
        with _ENV_LOCK:
            env.start()
        yield env
    finally:
        with _ENV_LOCK:
            env.dispose()


def check_size(n_vars: int, n_constrs: int) -> None:
    """Raise if a model this big doesn't fit the licence bundled with gurobipy."""
    if n_vars > FREE_LICENCE_LIMIT or n_constrs > FREE_LICENCE_LIMIT:
        raise ValueError(
            f"this instance needs {n_vars} variables and {n_constrs} constraints; "
            f"the free Gurobi licence allows {FREE_LICENCE_LIMIT} of each; use a smaller instance, such as fewer tasks"
        )
