"""The HTTP API: start a run, follow its progress over server-sent events, read its result, cancel it.

Runs live in memory and are lost on restart. FastAPI's SSE support:
https://fastapi.tiangolo.com/tutorial/server-sent-events/
"""

import threading
import time
from collections.abc import Iterator
from contextlib import AbstractContextManager, nullcontext
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, ConfigDict, Field

from ground_ops.domain import FROZEN, AssignmentInstance, CoverageInstance, Result, Status
from ground_ops.instances import generate_assignment, generate_coverage
from ground_ops.model1 import model_size, solve_assignment
from ground_ops.model2 import solve_coverage
from ground_ops.progress import Progress, ProgressRecorder
from ground_ops.solver import FREE_LICENCE_LIMIT, SolverSettings, check_size
from ground_ops.telemetry import Telemetry, new_run_id

WORKERS = 2
PROGRESS_INTERVAL_S = 0.2

type ModelName = Literal["assignment", "coverage"]
type RunState = Literal["running", "done", "failed"]


class RunRequest(BaseModel):
    model_config = FROZEN

    model: ModelName
    # Each task is one constraint and each handler at least two variables, so larger values never fit the licence.
    tasks: int = Field(
        default=30, le=FREE_LICENCE_LIMIT, description="Model 1 only: the number of tasks, a positive even number"
    )
    handlers: int | None = Field(
        default=None,
        ge=0,
        le=FREE_LICENCE_LIMIT // 2,
        description="Model 1 only: default one more than the most tasks that overlap",
    )
    seed: int = 1
    expose_search: bool = Field(default=False, description="Presolve=0 and Cuts=0, so the search is visible")
    work_limit: float | None = Field(default=None, ge=0, description="Stop after this many work units")


class RunView(BaseModel):
    model_config = FROZEN

    id: str
    model: ModelName
    state: RunState
    instance: AssignmentInstance | CoverageInstance
    progress: Progress | None
    result: Result | None
    error: str | None


class Finished(BaseModel):
    """The last event of a run's stream."""

    model_config = FROZEN

    status: Status | None
    error: str | None


class Run(BaseModel):
    """A run's mutable state, shared between the solver thread and the request handlers."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    model: ModelName
    instance: AssignmentInstance | CoverageInstance
    stop: threading.Event = Field(default_factory=threading.Event)
    # Guards everything below; the solver thread notifies it whenever an event is added.
    changed: threading.Condition = Field(default_factory=threading.Condition)
    events: list[ServerSentEvent] = Field(default_factory=list)
    progress: Progress | None = None
    sampled_at: float = float("-inf")
    result: Result | None = None
    error: str | None = None
    done: bool = False

    def add_event(self, event: str, data: BaseModel) -> None:
        self.events.append(ServerSentEvent(id=str(len(self.events)), event=event, data=data))
        self.changed.notify_all()

    def view(self) -> RunView:
        with self.changed:
            state: RunState = "failed" if self.error is not None else "done" if self.done else "running"
            return RunView(
                id=self.id,
                model=self.model,
                state=state,
                instance=self.instance,
                progress=self.progress,
                result=self.result,
                error=self.error,
            )


def _instance(request: RunRequest) -> AssignmentInstance | CoverageInstance:
    if request.model == "coverage":
        return generate_coverage(request.seed)
    instance = generate_assignment(request.tasks, request.seed, request.handlers)
    check_size(*model_size(instance))
    return instance


def _execute(run: Run, settings: SolverSettings, telemetry: Telemetry | None, workers: threading.Semaphore) -> None:
    def on_progress(progress: Progress) -> None:
        with run.changed:
            run.progress = progress
            if (now := time.monotonic()) - run.sampled_at >= PROGRESS_INTERVAL_S:
                run.sampled_at = now
                run.add_event("progress", progress)

    recording: AbstractContextManager[ProgressRecorder] = (
        nullcontext(ProgressRecorder(run.id, on_progress=on_progress, stop=run.stop))
        if telemetry is None
        else telemetry.run(run.model, run.id, on_progress=on_progress, stop=run.stop)
    )
    result, error = None, None
    try:
        with recording as recorder:
            match run.instance:
                case AssignmentInstance():
                    result = solve_assignment(run.instance, recorder=recorder, settings=settings)
                case CoverageInstance():
                    result = solve_coverage(run.instance, recorder=recorder, settings=settings)
    except Exception as failure:
        # Whatever stops the solve, the run must end, or its event streams would wait forever.
        error = str(failure) or type(failure).__name__
    finally:
        # Free the worker first, so a client that sees `done` can start another run at once.
        workers.release()
        with run.changed:
            if run.progress is not None:
                run.add_event("progress", run.progress)
            run.result, run.error, run.done = result, error, True
            run.add_event("done", Finished(status=None if result is None else result.status, error=error))


def _stream(run: Run, after: int) -> Iterator[ServerSentEvent]:
    sent = after + 1
    while True:
        with run.changed:
            while len(run.events) <= sent and not run.done:
                run.changed.wait()
            pending, finished = run.events[sent:], run.done
        yield from pending
        sent += len(pending)
        if finished:
            return


def _start(run: Run, settings: SolverSettings, telemetry: Telemetry | None, workers: threading.Semaphore) -> None:
    try:
        threading.Thread(target=_execute, args=(run, settings, telemetry, workers), daemon=True).start()
    except RuntimeError:
        # A thread that never started will never free its worker.
        workers.release()
        raise


def create_app(telemetry: Telemetry | None) -> FastAPI:
    app = FastAPI(title="ground-ops")
    runs: dict[str, Run] = {}
    runs_lock = threading.Lock()
    workers = threading.BoundedSemaphore(WORKERS)

    def existing_run(run_id: str) -> Run:
        # A dependency, so a missing run is a 404 before an event stream's response starts.
        with runs_lock:
            run = runs.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"there is no run {run_id}")
        return run

    type ExistingRun = Annotated[Run, Depends(existing_run)]

    @app.post("/api/runs", status_code=202)
    def start_run(request: RunRequest) -> RunView:
        try:
            instance = _instance(request)
        except ValueError as invalid:
            raise HTTPException(status_code=422, detail=str(invalid)) from invalid
        if not workers.acquire(blocking=False):
            raise HTTPException(status_code=429, detail=f"all {WORKERS} workers are busy; try again when a run ends")
        run = Run(id=new_run_id(), model=request.model, instance=instance)
        settings = SolverSettings(expose_search=request.expose_search, work_limit=request.work_limit)
        _start(run, settings, telemetry, workers)
        with runs_lock:
            runs[run.id] = run
        return run.view()

    @app.get("/api/runs/{run_id}")
    def get_run(run: ExistingRun) -> RunView:
        return run.view()

    @app.get("/api/runs/{run_id}/events", response_class=EventSourceResponse)
    def run_events(
        run: ExistingRun, last_event_id: Annotated[int | None, Header(ge=0)] = None
    ) -> Iterator[ServerSentEvent]:
        """`progress` events at most every 0.2 s, then a final `progress` and a `done`. Resumes after Last-Event-ID."""
        yield from _stream(run, -1 if last_event_id is None else last_event_id)

    @app.post("/api/runs/{run_id}/cancel", status_code=202)
    def cancel_run(run: ExistingRun) -> RunView:
        with run.changed:
            if run.done:
                raise HTTPException(status_code=409, detail=f"run {run.id} has already ended")
            run.stop.set()
        return run.view()

    return app
