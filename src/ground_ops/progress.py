"""A solve's progress, recorded by a Gurobi callback. No export here; telemetry.py exports it.

Callback codes: https://docs.gurobi.com/projects/optimizer/en/current/reference/numericcodes/callbacks.html
"""

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, replace

import gurobipy as gp
from gurobipy import GRB

type SpanStarter = Callable[[str], AbstractContextManager[object]]
type LineSink = Callable[[str], None]


@dataclass(frozen=True)
class Progress:
    elapsed: float
    work: float
    incumbent: float | None
    bound: float
    nodes: int
    iterations: int
    improvements: int

    @property
    def gap(self) -> float | None:
        """Gurobi's MIP gap, |incumbent - bound| / |incumbent|; None until there is an incumbent."""
        if self.incumbent is None:
            return None
        if self.incumbent == self.bound:
            return 0.0
        return abs(self.incumbent - self.bound) / abs(self.incumbent) if self.incumbent else None


class ProgressRecorder:
    """A Gurobi callback that keeps the latest progress of one solve.

    `start_span` opens a trace span for each phase of the run; `on_log_line` receives Gurobi's log lines.
    Both are optional, so a recorder works without any telemetry backend.
    """

    def __init__(
        self, run_id: str, *, start_span: SpanStarter | None = None, on_log_line: LineSink | None = None
    ) -> None:
        self.run_id = run_id
        self._start_span = start_span
        self._on_log_line = on_log_line
        self.latest: Progress | None = None
        self._best: float | None = None
        self._improvements = 0

    def finish(self, model: gp.Model) -> None:
        """Record the final state from the model: the last MIP callback can run before the final bound and incumbent."""
        self.latest = Progress(
            elapsed=model.Runtime,
            work=model.Work,
            incumbent=model.ObjVal if model.SolCount else None,
            bound=model.ObjBound,
            nodes=int(model.NodeCount),
            iterations=int(model.IterCount),
            improvements=self._improvements,
        )

    def phase(self, name: str) -> AbstractContextManager[object]:
        return self._start_span(name) if self._start_span is not None else nullcontext()

    def __call__(self, model: gp.Model, where: int) -> None:
        if where == GRB.Callback.MESSAGE:
            # Gurobi delivers its log to this callback even with OutputFlag=0, one line per call.
            line = model.cbGet(GRB.Callback.MSG_STRING).rstrip("\n")
            if line and self._on_log_line is not None:
                self._on_log_line(line)
        elif where == GRB.Callback.MIPSOL:
            # MIPSOL reports every new solution, not only better ones; both models minimise.
            objective = model.cbGet(GRB.Callback.MIPSOL_OBJ)
            if self._best is None or objective < self._best:
                self._best = objective
                self._improvements += 1
                if self.latest is not None:
                    self.latest = replace(self.latest, improvements=self._improvements)
        elif where == GRB.Callback.MIP:
            best = model.cbGet(GRB.Callback.MIP_OBJBST)
            self.latest = Progress(
                elapsed=model.cbGet(GRB.Callback.RUNTIME),
                work=model.cbGet(GRB.Callback.WORK),
                incumbent=None if best >= GRB.INFINITY else best,
                bound=model.cbGet(GRB.Callback.MIP_OBJBND),
                nodes=int(model.cbGet(GRB.Callback.MIP_NODCNT)),
                iterations=int(model.cbGet(GRB.Callback.MIP_ITRCNT)),
                improvements=self._improvements,
            )


def phase(recorder: ProgressRecorder | None, name: str) -> AbstractContextManager[object]:
    """A span for one phase of a solve, or nothing when the solve isn't being recorded."""
    return recorder.phase(name) if recorder is not None else nullcontext()
