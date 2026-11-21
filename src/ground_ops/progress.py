"""A solve's progress, recorded by a Gurobi callback. No export here; telemetry.py exports it.

Callback codes: https://docs.gurobi.com/projects/optimizer/en/current/reference/numericcodes/callbacks.html
"""

import math
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext

import gurobipy as gp
from gurobipy import GRB
from pydantic import BaseModel, computed_field

from ground_ops.domain import FROZEN

type SpanStarter = Callable[[str], AbstractContextManager[object]]
type LineSink = Callable[[str], None]
type ProgressSink = Callable[["Progress"], None]


class Progress(BaseModel):
    model_config = FROZEN

    elapsed: float
    work: float
    incumbent: float | None
    bound: float | None
    nodes: int
    iterations: int
    improvements: int

    @computed_field  # type: ignore[prop-decorator]  # mypy doesn't support decorators on a property
    @property
    def gap(self) -> float | None:
        """Gurobi's MIP gap, |incumbent - bound| / |incumbent|; None until there are both."""
        if self.incumbent is None or self.bound is None:
            return None
        if self.incumbent == self.bound:
            return 0.0
        return abs(self.incumbent - self.bound) / abs(self.incumbent) if self.incumbent else None


class ProgressRecorder:
    """A Gurobi callback that keeps the latest progress of one solve.

    `start_span` opens a trace span for each phase of the run; `on_log_line` receives Gurobi's log lines;
    `on_progress` receives each new progress sample. Setting `stop` asks the solve to end at its next callback.
    All are optional, so a recorder works without any telemetry backend or API.
    """

    def __init__(
        self,
        run_id: str,
        *,
        start_span: SpanStarter | None = None,
        on_log_line: LineSink | None = None,
        on_progress: ProgressSink | None = None,
        stop: threading.Event | None = None,
    ) -> None:
        self.run_id = run_id
        self.start_span: SpanStarter = start_span or (lambda _: nullcontext())
        self._on_log_line = on_log_line
        self._on_progress = on_progress
        self._stop = stop
        self.latest: Progress | None = None
        self._best: float | None = None
        self._improvements = 0

    def _record(self, progress: Progress) -> None:
        self.latest = progress
        if self._on_progress is not None:
            self._on_progress(progress)

    def finish(self, model: gp.Model) -> None:
        """Record the final state from the model: the last MIP callback can run before the final bound and incumbent."""
        # An infeasible model has no bound, and with no variables at all Gurobi refuses to report ObjBound.
        bound = None if model.Status == GRB.INFEASIBLE else model.ObjBound
        self._record(
            Progress(
                elapsed=model.Runtime,
                work=model.Work,
                incumbent=model.ObjVal if model.SolCount else None,
                # Before the root relaxation, Gurobi reports the bound as infinite.
                bound=bound if bound is not None and math.isfinite(bound) else None,
                nodes=int(model.NodeCount),
                iterations=int(model.IterCount),
                improvements=self._improvements,
            )
        )

    def __call__(self, model: gp.Model, where: int) -> None:  # noqa: PLR0917 - Gurobi calls it positionally
        if self._stop is not None and self._stop.is_set():
            # terminate() may be called from a callback; the solve then ends with status INTERRUPTED.
            # https://docs.gurobi.com/projects/optimizer/en/current/reference/python/model.html
            model.terminate()
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
                    self._record(self.latest.model_copy(update={"improvements": self._improvements}))
        elif where == GRB.Callback.MIP:
            best = model.cbGet(GRB.Callback.MIP_OBJBST)
            self._record(
                Progress(
                    elapsed=model.cbGet(GRB.Callback.RUNTIME),
                    work=model.cbGet(GRB.Callback.WORK),
                    incumbent=None if best >= GRB.INFINITY else best,
                    bound=model.cbGet(GRB.Callback.MIP_OBJBND),
                    nodes=int(model.cbGet(GRB.Callback.MIP_NODCNT)),
                    iterations=int(model.cbGet(GRB.Callback.MIP_ITRCNT)),
                    improvements=self._improvements,
                )
            )


def phase(recorder: ProgressRecorder | None, *, name: str) -> AbstractContextManager[object]:
    """A span for one phase of a solve, or nothing when the solve isn't being recorded."""
    return recorder.start_span(name) if recorder is not None else nullcontext()
